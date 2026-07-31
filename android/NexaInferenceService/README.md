# Nexa Inference Service (APK)

Android 原生 APK：在手机本地运行一个 **localhost HTTP 推理服务**，
通过 **Nexa Android SDK** 调用端侧模型（LLM / VLM），
优先使用 **Qualcomm Hexagon NPU**，不可用时回退 **CPU**。

`marvis-zerotermux`（ZeroTermux 内的 Python 控制框架）通过
`http://127.0.0.1:8080` 调用本服务，实现**全部本地、CPU/NPU 模式下运行**的
跨 APP 真实手机自动化。

## 架构

```
┌─────────────────────────┐         localhost HTTP          ┌──────────────────────────┐
│  ZeroTermux (marvis)    │  POST /v1/chat/completions      │   NexaInferenceService   │
│  modules/nexa_client.py │ ───────────────────────────────▶│   (本 APK, 前台服务)      │
│  modules/inference.py   │ ◀───────────────────────────────│   LocalHttpServer        │
│  observer.describe_..   │       JSON (OpenAI 风格)         │   NexaEngine             │
└─────────────────────────┘                                  │   └─ NexaSdk(plugin=npu) │
                                                               │      Hexagon NPU / CPU  │
                                                               └──────────────────────────┘
```

## HTTP 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET  | `/health` | 健康 + 当前 plugin + 是否支持 Hexagon |
| GET  | `/v1/models` | 已加载模型清单 |
| POST | `/v1/load` | 加载模型 `{key,type,model_name,model_path,plugin}` |
| POST | `/v1/chat/completions` | LLM 对话（OpenAI 风格 messages） |
| POST | `/v1/vision` | VLM 图文（messages 内含 `image_url` data URI） |

### 示例

```bash
# 健康检查
curl http://127.0.0.1:8080/health

# 加载模型（由 ZeroTermux 自动完成，亦可手动）
curl -X POST http://127.0.0.1:8080/v1/load -H 'Content-Type: application/json' \
  -d '{"key":"default","type":"vlm","model_name":"omni-neural","plugin":"npu"}'

# LLM
curl -X POST http://127.0.0.1:8080/v1/chat/completions -H 'Content-Type: application/json' \
  -d '{"model":"default","messages":[{"role":"user","content":"当前屏幕在做什么？"}],"max_tokens":256}'

# VLM（截图 base64）
curl -X POST http://127.0.0.1:8080/v1/vision -H 'Content-Type: application/json' \
  -d '{"model":"default","messages":[{"role":"user","content":[
        {"type":"text","text":"描述这个界面并给出可点击元素"},
        {"type":"image_url","image_url":{"url":"data:image/jpeg;base64,<BASE64>"}}
      ]}],"max_tokens":256}'
```

## 构建与安装

```bash
cd android/NexaInferenceService
./gradlew assembleDebug
adb install -r app/build/outputs/apk/debug/app-debug.apk
# 打开 App → “启动推理服务”；或重启由 BootReceiver 自启
```

> 沙箱无 Android SDK/NDK/Nexa 库，无法在此编译；源码与接口契约已就绪。
> 构建前请阅读 [NEXA_SDK_NOTES.md](./NEXA_SDK_NOTES.md) 校正 Nexa Kotlin API 签名。

## 与六大支柱的对接

- **真实 ADB 交互**：推理仍在手机本地，与 ZeroTermux 的 `adb shell` 执行完全解耦、互不阻塞。
- **全部 CPU 模式**：`plugin="cpu"` 即纯 CPU；默认 `npu` 在非高通自动降级 cpu。
- **视觉辅助 / 语义规划**：`/v1/vision` 替代远端 VLM，截图本地分析，零外网。
- **自主进化**：本服务只负责推理；训练/评估由 `modules/auto_evolution.py` 等在控制端完成。
