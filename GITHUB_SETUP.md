# GitHub Actions 部署指南

本指南将帮助你把 Prosocial Research Radar 部署到 GitHub，
实现真正的永久每日自动运行，无需本地机器保持在线。

---

## 准备工作（只需做一次）

### 第一步：创建 GitHub 仓库

1. 登录 [github.com](https://github.com)
2. 点击右上角 **+** → **New repository**
3. 仓库名称：`prosocial-radar`（或任意名称）
4. 设为 **Private**（推荐，保护你的历史数据）
5. 点击 **Create repository**

---

### 第二步：把代码推送到 GitHub

在你的本地终端（或在 HappyCapy 沙盒里）：

```bash
cd /path/to/workspace          # 进入项目目录

git init
git add .
git commit -m "init: prosocial research radar"

git remote add origin https://github.com/你的用户名/prosocial-radar.git
git branch -M main
git push -u origin main
```

---

### 第三步：配置 GitHub Secrets

这是最关键的一步。在你的 GitHub 仓库页面：

**Settings → Secrets and variables → Actions → New repository secret**

需要添加以下三个 Secret：

#### Secret 1：`DEEPSEEK_API_KEY`（主要，推荐）

用于 AI 摘要生成。DeepSeek 价格极低（约 $0.00014/千 token），每日 8 篇摘要费用不足 $0.001。

获取方式：
1. 前往 [platform.deepseek.com](https://platform.deepseek.com)
2. API Keys → Create new key
3. 复制密钥（格式：`sk-xxxx...`）

| 名称 | 值 |
|---|---|
| `DEEPSEEK_API_KEY` | `sk-xxxx...` |

#### Secret 1b：`ANTHROPIC_API_KEY`（可选备用）

DeepSeek 不可用时自动切换。如不需要备用可不填。

| 名称 | 值 |
|---|---|
| `ANTHROPIC_API_KEY` | `sk-ant-api03-xxxx...`（可选）|

---

#### Secret 2 & 3：Gmail 发信配置

用于发送每日邮件摘要到 xxx@gmail.com。

**需要一个 Gmail 账号作为发件人（可以是你自己的 Gmail）。**

**获取 Gmail App Password：**
1. 登录你的 Gmail → [myaccount.google.com/security](https://myaccount.google.com/security)
2. 开启**两步验证**（必须先开启）
3. 搜索 **App passwords** → 创建新密码
4. 应用名称：`prosocial-radar`
5. 复制生成的 16 位密码（格式：`xxxx xxxx xxxx xxxx`，去掉空格后是 `xxxxxxxxxxxxxxxx`）

| 名称 | 值 |
|---|---|
| `GMAIL_ADDRESS` | `你的邮箱@gmail.com` |
| `GMAIL_APP_PASSWORD` | `xxxxxxxxxxxxxxxx`（16位，无空格） |

---

### 第四步：确认 workflow 文件已上传

检查仓库里是否有这个文件：

```
.github/workflows/daily_radar.yml
```

如果有，GitHub Actions 会自动识别并启用。

---

### 第五步：测试手动触发

不用等到 08:00，可以立即测试：

1. 进入你的 GitHub 仓库
2. 点击顶部 **Actions** 标签
3. 左侧选择 **Prosocial Research Radar — Daily Run**
4. 点击 **Run workflow** → **Run workflow**（绿色按钮）
5. 等待约 2-3 分钟，查看运行日志

---

## 日常运行说明

### 自动执行时间

```yaml
schedule:
  - cron: "0 0 * * *"   # UTC 00:00 = 北京时间 08:00
```

如需修改时间，编辑 `.github/workflows/daily_radar.yml` 中的 cron 表达式：

| 期望时间 | cron 表达式 |
|---|---|
| 北京 08:00（UTC 00:00）| `"0 0 * * *"` |
| 北京 07:00（UTC 23:00）| `"0 23 * * *"` |
| 北京 09:00（UTC 01:00）| `"0 1 * * *"` |

---

### 历史去重机制

每次运行后，`data/sent_history.json` 会被自动 commit 回仓库，
下次运行时不会重复推送已发过的论文。

---

### 查看运行记录

GitHub → Actions → 点击任意一次运行记录 → 展开 **Run Prosocial Research Radar** 步骤

---

## 费用说明

| 服务 | 费用 |
|---|---|
| GitHub Actions | 免费（公开仓库无限；私有仓库每月 2000 分钟免费额度，本项目每次约 2 分钟） |
| Anthropic API | 按使用量计费；每次 8 篇摘要约 $0.001（极低） |
| PubMed / OpenAlex | 完全免费 |
| Gmail SMTP | 完全免费 |

---

## 常见问题

**Q：Actions 运行失败，报 `Authentication failed`**
A：检查 `GMAIL_APP_PASSWORD` 是否正确（16位，无空格），并确认已开启 Gmail 两步验证。

**Q：没有收到邮件**
A：检查 `GMAIL_ADDRESS` 是否填写正确。第一次运行邮件可能进垃圾箱，请检查。

**Q：AI 摘要全部为空**
A：检查 `ANTHROPIC_API_KEY` 是否有效，或账户是否有余额。

**Q：想暂停自动运行**
A：GitHub → Actions → 左侧选择 workflow → 右上角 **...** → **Disable workflow**
