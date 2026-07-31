# Nexa Android SDK 适配说明（构建前必读）

本目录的 Kotlin 代码以 `ai.nexa:core`（Nexa/Qualcomm 端侧推理 SDK）为依赖。
由于 SDK 的 Kotlin API 随版本演进，**以下签名需在你本地用真实 SDK 校正**，
校正点集中在 `app/src/main/java/com/marvis/nexainference/NexaEngine.kt` 一个文件内，
不影响其余模块。

## 已知 API（依据官方文档 VLM 示例）

```kotlin
// build.gradle
implementation("ai.nexa:core:0.0.19")   // 若 0.0.19 不存在改用 0.0.15

// 初始化（Application.onCreate）
NexaSdk.getInstance().init(this)

// VLM（官方示例）
VlmWrapper.builder()
    .vlmCreateInput(
        VlmCreateInput(
            model_name = "omni-neural",
            model_path = "/data/data/.../models/OmniNeural-4B/files-1-1.nexa",
            plugin_id = "npu",          // "npu"=Hexagon, "cpu"=纯CPU
            config = ModelConfig()
        )
    )
    .build()
    .onSuccess { vlm ->
        vlm.generateStreamFlow("Hello!", GenerationConfig()).collect { print(it) }
    }
```

## 本工程推断/待校正点（VERIFY）

| 位置 | 推断写法 | 若编译失败请改为 |
|------|----------|------------------|
| import 包名 | `ai.nexa.core.*` | 以 SDK 实际包名为准 |
| LLM 封装类 | `LlmWrapper` / `LlmCreateInput` | 可能命名不同（如 `TextWrapper`），按 SDK 文档对齐 |
| `generateStreamFlow` | `generateStreamFlow(prompt, GenerationConfig)` 返回 `Flow<String>` | 以 SDK 实际返回类型为准（可能为 `Flow<String>` 或 `Sequence<String>`） |
| VLM 图片输入 | `generateStreamFlow(imagePath, prompt, GenerationConfig)` | 可能为 `generateStreamFlow(imageBytes, prompt, cfg)` 或图片在 `VlmCreateInput` 内传入 |
| `GenerationConfig(max_tokens=...)` | 命名参数构造 | 按 SDK 实际字段名（`max_new_tokens` 等）调整 |

## 硬件后端 plugin_id

- `"npu"`：Qualcomm Hexagon NPU（仅骁龙设备；`HardwareProbe` 会自动判断是否降级）
- `"cpu"`：纯 CPU（满足“全部 CPU 模式下运行”）
- `"gpu"`：Adreno GPU（可选）

`NexaEngine(preferredPlugin="npu")` 在非高通设备上自动降级为 `"cpu"`。

## 模型来源

- Hub 名称：`"omni-neural"`（VLM）、`"NexaAI/Qwen3-1.7B-GGUF"`（LLM）等
- 本地 `.nexa` 文件：把 `model_path` 指向设备上的 `.nexa` 权重路径
- 零样本 Day-0：Nexa 支持直接加载社区 GGUF/NEXA 权重，无需转换

## 构建

```bash
cd android/NexaInferenceService
./gradlew assembleDebug        # 需要 Android SDK + NDK（本地或 CI）
adb install -r app/build/outputs/apk/debug/app-debug.apk
# 打开 App 点“启动推理服务”，或重启手机由 BootReceiver 自启
```

沙箱环境（无 Android SDK/NDK/Nexa 库）**无法编译本 APK**，
源码与接口契约已就绪，请在 Android Studio / 本地 gradle 完成构建。
