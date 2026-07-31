# GitHub + Gitee 双向同步指南

## 1. 仓库状态

- **GitHub**: `https://github.com/wagziqag/phone-automation-system` (已创建, 1 commit)
- **Gitee**:  `https://gitee.com/wagziqag/phone-automation-system` (待同步)

## 2. 首次推送（纯 Python，无需 git 二进制）

```bash
# 设置凭据
export GITHUB_TOKEN=<your_github_token>
export GITHUB_USER=wagziqag

# 进入项目目录
cd phone-automation-system

# 推送全部文件到 GitHub
python3 scripts/github_push.py --branch main
```

脚本会:
1. 用 `GITHUB_TOKEN` 认证到 GitHub API
2. 递归收集所有文件（跳过 `.git/`, `__pycache__/`, `.d_b64` 等）
3. 对每个文件调用 Contents API 创建/更新
4. 超过 80KB 的文件自动走 Git Data API（blob → tree → commit → ref）

## 3. 自动镜像到 Gitee

### 方式 A: GitHub Actions（推荐）

仓库已内置 `.github/workflows/mirror-to-gitee.yml`。

在 GitHub 仓库 Settings → Secrets and variables → Actions 中添加:

| Secret 名 | 值 |
|-----------|-----|
| `GITEE_TOKEN` | `<your_gitee_token>` |
| `GITEE_USER`  | `wagziqag` |

之后每次 `git push` 到 GitHub，Actions 会自动推送到 Gitee。

### 方式 B: 手动镜像

```bash
export GITEE_TOKEN=<your_gitee_token>
export GITEE_USER=wagziqag
python3 scripts/gitee_mirror.py
```

## 4. 手机端 ZeroTermux 同步

手机上只需一行命令即可拉取最新代码:

```bash
# 从 GitHub 拉取（推荐，速度快）
cd ~/phone-automation-system
git pull origin main

# 或从 Gitee 拉取（国内网络更稳）
git pull https://gitee.com/wagziqag/phone-automation-system.git master
```

配合 `auto_update.sh` 可实现定时自动更新:

```bash
# 每 30 分钟检查一次更新
echo "*/30 * * * * cd ~/phone-automation-system && git pull -q" | crontab -
```

## 5. 工作流程（端到端）

```
┌────────────┐     push      ┌────────────┐    webhook    ┌────────────┐    git pull    ┌──────────────┐
│  Server    │ ──────────→  │  GitHub    │ ──────────→  │  Gitee     │ ──────────→  │  ZeroTermux  │
│  (开发/AI) │              │  (中转)    │              │  (镜像)    │              │  (手机执行)  │
└────────────┘              └────────────┘              └────────────┘              └──────────────┘
                                    │
                                    │ Actions CI
                                    ▼
                            ┌────────────┐
                            │ run tests  │ → 全绿才允许合并
                            └────────────┘
```

## 6. 安全提醒

⚠️ **立即轮换 Gitee Token**: 旧 token 已不再使用，到
https://gitee.com/profile/personal_access_tokens 确认当前 token 有效并妥善保存。

⚠️ **GitHub Token 权限**: 只应勾选 `repo` 权限（最低权限原则），
不要勾选 `admin:org` / `workflow` 等不必要权限。

## 7. 快速验证

推送成功后，浏览器打开:
- https://github.com/wagziqag/phone-automation-system
- https://gitee.com/wagziqag/phone-automation-system

应能看到完整项目文件结构。
