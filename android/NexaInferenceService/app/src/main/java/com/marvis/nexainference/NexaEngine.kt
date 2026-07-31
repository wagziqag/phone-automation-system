package com.marvis.nexainference

import ai.nexa.core.*
import kotlinx.coroutines.flow.fold
import kotlinx.coroutines.runBlocking
import java.util.concurrent.ConcurrentHashMap

/**
 * Nexa 推理引擎封装。
 *
 * 负责加载 LLM / VLM 并通过 Nexa SDK 生成本地推理结果。
 * 硬件后端由 pluginId 控制："npu"(Hexagon) 或 "cpu"。
 *
 * ── SDK 适配注意（不可编译时请见 NEXA_SDK_NOTES.md）──
 * 以下 LlmWrapper / LlmCreateInput / VlmWrapper / VlmCreateInput /
 * ModelConfig / GenerationConfig / generateStreamFlow 的命名与签名，
 * 依据官方文档中 VlmWrapper.builder()...build().onSuccess{}.onFailure{} 范式推断。
 * 若官方 Kotlin API 有差异，仅需修改本文件即可，不影响其余模块。
 */
class NexaEngine(preferredPlugin: String = "npu") {

    @Volatile
    private var pluginId: String = HardwareProbe.resolvePlugin(preferredPlugin)

    private val llmCache = ConcurrentHashMap<String, Any>()
    private val vlmCache = ConcurrentHashMap<String, Any>()

    fun currentPlugin(): String = pluginId

    fun fallbackToCpu() {
        pluginId = "cpu"
    }

    // ───────── LLM ─────────
    fun loadLlm(key: String, modelName: String, modelPath: String?) {
        val input = LlmCreateInput(
            model_name = modelName,
            model_path = modelPath ?: "",
            plugin_id = pluginId,
            config = ModelConfig()
        )
        LlmWrapper.builder()
            .llmCreateInput(input)
            .build()
            .onSuccess { llm -> llmCache[key] = llm }
            .onFailure { e -> throw RuntimeException("LLM 加载失败 ($modelName): ${e.message}", e) }
    }

    fun generateLlm(key: String, prompt: String, maxTokens: Int): String {
        val llm = llmCache[key] ?: throw IllegalStateException("LLM '$key' 尚未加载")
        return runBlocking {
            // VERIFY: generateStreamFlow(prompt, GenerationConfig) 返回 Flow<String>
            (llm as LlmWrapper).generateStreamFlow(prompt, GenerationConfig(max_tokens = maxTokens))
                .fold("") { acc, tok -> acc + tok }
        }
    }

    // ───────── VLM ─────────
    fun loadVlm(key: String, modelName: String, modelPath: String?) {
        val input = VlmCreateInput(
            model_name = modelName,
            model_path = modelPath ?: "",
            plugin_id = pluginId,
            config = ModelConfig()
        )
        VlmWrapper.builder()
            .vlmCreateInput(input)
            .build()
            .onSuccess { vlm -> vlmCache[key] = vlm }
            .onFailure { e -> throw RuntimeException("VLM 加载失败 ($modelName): ${e.message}", e) }
    }

    /**
     * VLM 图文推理。
     * @param imagePath 设备上的图片文件路径（由 HTTP 服务把 base64 解码后写入）。
     * @param prompt 文本指令。
     *
     * VERIFY: 官方 VLM 示例仅展示 generateStreamFlow("Hello!", GenerationConfig())。
     * 多模态图片输入最可能签名是 generateStreamFlow(imagePath, prompt, GenerationConfig)。
     * 若实际为其它（如 VlmCreateInput 内带 image，或 generateStreamFlow(imageBytes, prompt, cfg)），
     * 仅改此一处即可。
     */
    fun generateVlm(key: String, imagePath: String, prompt: String, maxTokens: Int): String {
        val vlm = vlmCache[key] ?: throw IllegalStateException("VLM '$key' 尚未加载")
        return runBlocking {
            (vlm as VlmWrapper).generateStreamFlow(imagePath, prompt, GenerationConfig(max_tokens = maxTokens))
                .fold("") { acc, tok -> acc + tok }
        }
    }
}
