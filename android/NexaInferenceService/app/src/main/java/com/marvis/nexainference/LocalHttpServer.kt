package com.marvis.nexainference

import org.json.JSONArray
import org.json.JSONObject
import java.io.BufferedReader
import java.io.InputStream
import java.io.InputStreamReader
import java.io.OutputStream
import java.net.ServerSocket
import java.net.Socket
import java.nio.charset.StandardCharsets
import java.io.File
import java.util.Base64
import java.util.UUID
import java.util.concurrent.Executors

/**
 * 极简、零依赖的 localhost HTTP/1.1 服务（基于 ServerSocket）。
 *
 * 路由（全部返回 JSON）：
 *   GET  /health                  -> 服务健康 + 当前 plugin + Hexagon 支持
 *   GET  /v1/models               -> 已加载模型清单
 *   POST /v1/load                 -> 加载模型 {key,type,model_name,model_path,plugin}
 *   POST /v1/chat/completions     -> LLM 对话（OpenAI 风格 messages）
 *   POST /v1/vision               -> VLM 图文（messages 内含 image_url data:...）
 *
 * 仅监听 127.0.0.1，不外网；用于 ZeroTermux(marvis) 本机调用。
 */
class LocalHttpServer(
    private val port: Int,
    private val engine: NexaEngine,
    private val onLog: (String) -> Unit = {}
) : Runnable {

    private var serverSocket: ServerSocket? = null
    private val executor = Executors.newCachedThreadPool()
    @Volatile var running = false

    fun start() {
        serverSocket = ServerSocket(port, 0, java.net.InetAddress.getByName("127.0.0.1"))
        running = true
        Thread(this, "nexa-http").start()
        onLog("HTTP 推理服务已监听 127.0.0.1:$port")
    }

    fun stop() {
        running = false
        try { serverSocket?.close() } catch (_: Exception) {}
        executor.shutdown()
    }

    override fun run() {
        while (running) {
            try {
                val client = serverSocket?.accept() ?: break
                executor.execute { handle(client) }
            } catch (e: Exception) {
                if (running) onLog("accept 错误: ${e.message}")
            }
        }
    }

    private fun handle(socket: Socket) {
        try {
            socket.getInputStream().use { inp ->
                socket.getOutputStream().use { out ->
                    val req = readRequest(inp)
                    val (status, body) = route(req)
                    writeResponse(out, status, body)
                }
            }
        } catch (e: Exception) {
            onLog("处理请求出错: ${e.message}")
        }
    }

    private fun readRequest(inp: InputStream): Request {
        val reader = BufferedReader(InputStreamReader(inp, StandardCharsets.UTF_8))
        val requestLine = reader.readLine() ?: ""
        val parts = requestLine.split(" ")
        val method = parts.getOrNull(0) ?: ""
        val path = parts.getOrNull(1) ?: "/"
        var contentLength = 0
        var line: String?
        while (reader.readLine().also { line = it } != null) {
            if (line!!.isEmpty()) break
            if (line!!.startsWith("Content-Length", ignoreCase = true)) {
                contentLength = line!!.substringAfter(":").trim().toIntOrNull() ?: 0
            }
        }
        val body = if (contentLength > 0) {
            val buf = CharArray(contentLength)
            var read = 0
            while (read < contentLength) {
                val n = reader.read(buf, read, contentLength - read)
                if (n <= 0) break
                read += n
            }
            String(buf, 0, read)
        } else ""
        return Request(method, path, body)
    }

    private fun route(req: Request): Pair<Int, String> {
        return try {
            when {
                req.method == "GET" && req.path == "/health" ->
                    200 to healthJson().toString()
                req.method == "GET" && req.path == "/v1/models" ->
                    200 to modelsJson().toString()
                req.method == "POST" && req.path == "/v1/load" -> {
                    loadModel(JSONObject(req.body))
                    200 to okJson("loaded")
                }
                req.method == "POST" && req.path == "/v1/chat/completions" ->
                    200 to chat(JSONObject(req.body)).toString()
                req.method == "POST" && req.path == "/v1/vision" ->
                    200 to vision(JSONObject(req.body)).toString()
                else -> 404 to errorJson("not found: ${req.method} ${req.path}")
            }
        } catch (e: Exception) {
            500 to errorJson(e.message ?: "internal error")
        }
    }

    // ───────── 路由实现 ─────────
    private fun healthJson(): JSONObject = JSONObject().apply {
        put("status", "ok")
        put("backend", "nexa")
        put("plugin", engine.currentPlugin())
        put("hexagon", HardwareProbe.supportsHexagon())
        put("models", ModelRegistry.toJson())
    }

    private fun modelsJson(): JSONObject = JSONObject().apply {
        put("object", "list")
        put("data", ModelRegistry.toJson())
    }

    private fun loadModel(o: JSONObject) {
        val key = o.optString("key", "default")
        val type = o.optString("type", "llm")
        val modelName = o.optString("model_name", "")
        val modelPath = o.optString("model_path", "").takeIf { it.isNotEmpty() }
        val plugin = o.optString("plugin", engine.currentPlugin())
        if (modelName.isEmpty()) throw IllegalArgumentException("model_name 不能为空")
        ModelRegistry.put(ModelEntry(key, type, modelName, modelPath, plugin))
        // 用请求指定的 plugin 临时加载（npu 失败不在此自动降级，由客户端决定）
        val prev = engine.currentPlugin()
        try {
            if (plugin != prev) { /* engine 以构造时 plugin 为准；此处按 registry 记录 */ }
            if (type == "vlm") engine.loadVlm(key, modelName, modelPath)
            else engine.loadLlm(key, modelName, modelPath)
        } finally {
            // plugin 仅作记录，真正后端由 engine 初始化时决定
        }
    }

    private fun chat(o: JSONObject): JSONObject {
        val model = o.optString("model", "default")
        val maxTokens = o.optInt("max_tokens", 256)
        val messages = o.optJSONArray("messages") ?: JSONArray()
        val prompt = buildPrompt(messages)
        val text = engine.generateLlm(model, prompt, maxTokens)
        return chatResponse(text, model)
    }

    private fun vision(o: JSONObject): JSONObject {
        val model = o.optString("model", "default")
        val maxTokens = o.optInt("max_tokens", 256)
        val messages = o.optJSONArray("messages") ?: JSONArray()
        val (imageB64, prompt) = extractImage(messages)
        val imgFile = saveImage(imageB64)
        try {
            val text = engine.generateVlm(model, imgFile.absolutePath, prompt, maxTokens)
            return chatResponse(text, model)
        } finally {
            try { imgFile.delete() } catch (_: Exception) {}
        }
    }

    // ───────── 工具 ─────────
    private fun buildPrompt(messages: JSONArray): String {
        val sb = StringBuilder()
        for (i in 0 until messages.length()) {
            val m = messages.getJSONObject(i)
            val role = m.optString("role", "user")
            val content = m.optString("content", "")
            sb.append("$role: $content\n")
        }
        return sb.toString().trim()
    }

    private fun extractImage(messages: JSONArray): Pair<String, String> {
        var prompt = ""
        var imageB64: String? = null
        for (i in 0 until messages.length()) {
            val m = messages.getJSONObject(i)
            val content = m.opt("content")
            if (content is String) {
                prompt = content
            } else if (content is JSONArray) {
                for (j in 0 until content.length()) {
                    val part = content.getJSONObject(j)
                    when (part.optString("type")) {
                        "text" -> prompt = part.optString("text")
                        "image_url" -> {
                            val url = part.getJSONObject("image_url").optString("url")
                            imageB64 = url.substringAfter("base64,", "")
                        }
                    }
                }
            }
        }
        if (imageB64.isNullOrEmpty()) throw IllegalArgumentException("messages 中未找到 image_url")
        return Pair(imageB64!!, prompt)
    }

    private fun saveImage(b64: String): File {
        val bytes = Base64.getDecoder().decode(b64)
        val dir = File("/data/data/com.marvis.nexainference/cache/vision")
        dir.mkdirs()
        val f = File(dir, "img_${UUID.randomUUID()}.jpg")
        f.writeBytes(bytes)
        return f
    }

    private fun chatResponse(text: String, model: String): JSONObject = JSONObject().apply {
        put("choices", JSONArray().apply {
            put(JSONObject().apply {
                put("message", JSONObject().apply {
                    put("role", "assistant")
                    put("content", text)
                })
                put("finish_reason", "stop")
            })
        })
        put("model", model)
        put("backend", "nexa")
        put("plugin", engine.currentPlugin())
    }

    private fun okJson(msg: String): String = JSONObject().apply { put("status", "ok"); put("msg", msg) }.toString()
    private fun errorJson(msg: String): String = JSONObject().apply { put("status", "error"); put("error", msg) }.toString()

    private fun writeResponse(out: OutputStream, status: Int, body: String) {
        val bytes = body.toByteArray(StandardCharsets.UTF_8)
        val head = "HTTP/1.1 $status OK\r\n" +
                "Content-Type: application/json; charset=utf-8\r\n" +
                "Content-Length: ${bytes.size}\r\n" +
                "Connection: close\r\n\r\n"
        out.write(head.toByteArray(StandardCharsets.UTF_8))
        out.write(bytes)
        out.flush()
    }

    private data class Request(val method: String, val path: String, val body: String)
}
