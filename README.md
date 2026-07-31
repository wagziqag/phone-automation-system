---
AIGC:
    Label: "1"
    ContentProducer: 001191440300708461136T1XGW3
    ProduceID: 5a874a85223d9a366f03e7a352328c76_fce87ab18a8611f19d23525400e6dd8f
    ReservedCode1: 2oncFr8GxXM+QI4SEzGnKoJLyauBBBGTHqbO26R7H3PVZNGuoSiM3Vdb1csVpNbhqh/pHX2rRrVYLRsLRPUDdW3Yl0ZMEtopNuhFNttp76sFdEtMvBMF/yn/1wxsPVjCfCe9lVwzaQsoQOpEVb1NsqFc1tWsqBBdbvFh5mxOg9bdd5x6nbyxi04ZFWc=
    ContentPropagator: 001191440300708461136T1XGW3
    PropagateID: 5a874a85223d9a366f03e7a352328c76_fce87ab18a8611f19d23525400e6dd8f
    ReservedCode2: 2oncFr8GxXM+QI4SEzGnKoJLyauBBBGTHqbO26R7H3PVZNGuoSiM3Vdb1csVpNbhqh/pHX2rRrVYLRsLRPUDdW3Yl0ZMEtopNuhFNttp76sFdEtMvBMF/yn/1wxsPVjCfCe9lVwzaQsoQOpEVb1NsqFc1tWsqBBdbvFh5mxOg9bdd5x6nbyxi04ZFWc=
---

# phone-automation-system — 模块总览

自成长的 AI 手机自动化智能体。全 CPU 模式，ADB 物理执行，Ollama 本地推理。

## 模块清单

| 模块 | 文件 | 行数 | 核心能力 |
|------|------|------|----------|
| **双向对话引擎** | `phone_interact.py` | 512 | Marvis↔元宝 ADB 对话、OCR 识别、Recipe 存储 |
| **Ollama 集成** | `phone_ollama.py` | 448 | 模型管理、任务规划、微调流水线、基准测试 |
| **自主探索+演示学习** | `phone_autonomy.py` | 634 | App 自动探索、人类演示录制回放、自动进化 |
| **定时任务+并行执行** | `phone_scheduler.py` | 593 | Cron 调度、并行执行、管道模式、守护进程 |
| **元宝剪切板交互** | `phone_yuanbao.py` | 299 | 剪切板桥接、知识提取、进化引擎 |
| **Nexa APK 桥接** | `nexa_bridge/` | 7 文件 | Android APK + HTTP Server + NPU 推理 |
| **ZeroTermux 客户端** | `nexa_client.py` | 120 | HTTP 调用 NexaBridge APK |
| **一键部署** | `deploy.sh` | 180 | 环境检测→安装→验证→守护 |

## 借鉴与整合

| 项目 | 借鉴点 | 落地模块 |
|------|--------|----------|
| **RedFox** | 统一 API 封装各平台差异 | nexa_bridge NexaEngine 适配层 |
| **Goose (Block)** | 本地 MCP + Recipes 可复用工作流 | phone_interact Recipe, phone_ollama RecipeManager |
| **Open-LLM-VTuber** | 视觉感知闭环 | phone_autonomy OCR + 屏幕分析 |
| **OpenSquilla** | 本地模型路由降成本 | phone_ollama CPU-only Ollama |
| **自主进化** | 收集→训练→评估→改进循环 | phone_autonomy AutoEvolution |

## 核心工作流

### 1. Marvis ↔ 元宝 双向对话

```bash
# ADB 全自动对话循环（非剪切板手动模式）
python3 phone_interact.py /debate "AI如何实现跨App手机自动化？"

# 无限学习循环
python3 phone_interact.py /loop "手机自动化"
```

**执行流程:**
1. Marvis 通过 Ollama 生成问题
2. ADB 启动元宝 → 点击输入框 → ADBKeyboard 输入
3. 等待元宝生成回复 → ADB 截图 → Tesseract OCR 读取
4. 提取知识点存入 phone_memory L1
5. 生成下一个追问 → 循环

### 2. 自主探索 App

```bash
python3 phone_autonomy.py /explore com.tencent.mm
```

1. 截图 → OCR 识别所有可点击元素
2. 按优先级点击（主按钮 > 导航 > 列表项）
3. 记录操作与屏幕状态变化
4. 构建 App UI 操作图谱

### 3. 演示学习

```bash
python3 phone_autonomy.py /record "打开微信发消息"
# 在手机上手动操作...
# 按 Enter 记录每步
# 输入 'done' 结束

python3 phone_autonomy.py /replay "打开微信发消息"
```

### 4. 定时任务 + 并行

```bash
# 添加定时任务
python3 phone_scheduler.py /add "@every 1h" adb_screencap

# 并行执行
python3 phone_scheduler.py /parallel "截图,OCR分析,发送通知"

# 管道模式
python3 phone_scheduler.py /pipe-create "监控流"
python3 phone_scheduler.py /pipe "监控流"

# 守护进程
python3 phone_scheduler.py /serve
```

### 5. 微调流水线

```bash
# 自动从记忆收集数据创建微调模型
python3 phone_ollama.py /finetune marvis-v1

# 基准测试
python3 phone_ollama.py /bench qwen2:0.5b
```

## 部署

```bash
cd /data/data/com.termux/files/home/phone-automation-system
bash deploy.sh
```

依赖: Python 3.8+, ADB localhost:5555, Tesseract OCR, Ollama (可选)
*（内容由AI生成，仅供参考）*
