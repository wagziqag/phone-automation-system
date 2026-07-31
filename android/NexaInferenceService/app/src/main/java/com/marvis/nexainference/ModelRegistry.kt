package com.marvis.nexainference

import org.json.JSONArray

/**
 * 已加载模型登记表。
 * key -> (type, modelName, modelPath, plugin)
 */
data class ModelEntry(
    val key: String,
    val type: String,          // "llm" | "vlm"
    val modelName: String,     // Nexa Hub 名称，如 "omni-neural" / "NexaAI/Qwen3-1.7B-GGUF"
    val modelPath: String?,    // 本地 .nexa 路径（可选）
    val plugin: String         // "npu" | "cpu"
)

object ModelRegistry {
    private val entries = LinkedHashMap<String, ModelEntry>()

    fun put(entry: ModelEntry) {
        entries[entry.key] = entry
    }

    fun get(key: String): ModelEntry? = entries[key]

    fun list(): List<ModelEntry> = entries.values.toList()

    fun toJson(): JSONArray {
        val arr = JSONArray()
        for (e in entries.values) {
            arr.put(org.json.JSONObject().apply {
                put("key", e.key)
                put("type", e.type)
                put("model_name", e.modelName)
                put("model_path", e.modelPath ?: "")
                put("plugin", e.plugin)
            })
        }
        return arr
    }
}
