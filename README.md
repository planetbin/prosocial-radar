# Prosocial Research Radar

每日自动爬取 PubMed + OpenAlex 的亲社会行为（prosocial behavior）相关论文，
AI 生成摘要，推送到邮箱。支持本地运行和 GitHub Actions 永久部署。

---

## 功能

- 每日从 PubMed / OpenAlex 爬取亲社会行为、利他、共情、合作等主题论文
- 三通道检索（最近 90 天 + 按日期 + 按相关性），保证每天有新论文
- 双层关键词过滤（主题严格，期刊放宽）
- 自动去重，历史记录防止重复推送
- AI 摘要（DeepSeek 主用，Anthropic 备用）
- HTML 邮件美化推送

---

## 项目结构

```
.
├── prosocial_radar/           # 核心模块
│   ├── config.py              # 检索关键词、期刊清单、参数
│   ├── pubmed.py              # PubMed 三通道爬取
│   ├── openalex.py            # 引用数补全
│   ├── filter.py              # 去重 + 双层关键词过滤
│   ├── scorer.py              # 综合评分（相关度/时效/引用/期刊）
│   ├── history.py             # 历史记录与去重
│   ├── summarizer.py          # DeepSeek / Anthropic 摘要
│   ├── push.py                # 邮件推送（capymail + SMTP）
│   └── output.py              # CSV / JSON 输出
├── run_radar.py               # 主入口
├── scheduler.py               # 本地定时守护进程
├── .github/workflows/
│   └── daily_radar.yml        # GitHub Actions 每日调度
├── requirements.txt
├── GITHUB_SETUP.md            # GitHub Actions 部署指南
└── README.md
```

---

## 本地运行

### 安装
```bash
pip install -r requirements.txt
```

### 设置环境变量
```bash
export DEEPSEEK_API_KEY="sk-xxxx"           # 必填：AI 摘要
export GMAIL_ADDRESS="you@gmail.com"        # 必填：SMTP 发件人
export GMAIL_APP_PASSWORD="xxxxxxxxxxxxxxxx" # 必填：Gmail 应用密码
```

### 单次运行
```bash
python run_radar.py --top 8         # 推送 top 8 篇
python run_radar.py --no-ai         # 跳过 AI 摘要（调试用）
python run_radar.py --max 100       # 只取前 100 篇
```

### 本地定时守护
```bash
python scheduler.py              # 每天 08:00 自动运行
```

---

## GitHub Actions 部署（推荐，永久自动运行）

详见 [`GITHUB_SETUP.md`](GITHUB_SETUP.md)。

四步上线：
1. 推送代码到 GitHub 仓库
2. 在 **Settings → Secrets** 添加：`DEEPSEEK_API_KEY` / `GMAIL_ADDRESS` / `GMAIL_APP_PASSWORD`
3. 启用 GitHub Actions
4. 每天 UTC 00:00 (北京 08:00) 自动运行

---

## 收件人配置

编辑 `prosocial_radar/push.py`：
```python
RECIPIENTS = [
    "xxx@gmail.com",
    "xxx@xx.com",
    # 添加更多邮箱...
]
```

---

## 检索主题配置

编辑 `prosocial_radar/config.py`：
- `PUBMED_QUERY`：PubMed 检索式
- `TARGET_JOURNALS`：tier-1 期刊名单（用作质量标签，不作硬过滤）
- `RECENT_DAYS`：最近 N 天论文专用通道（默认 90）

编辑 `prosocial_radar/filter.py`：
- `TIER_A`：核心概念关键词（必须命中 ≥1）
- `TIER_B`：方法/语境关键词（必须命中 ≥1）

---

## 输出文件

每次运行都会在 `outputs/` 生成：
- `prosocial_papers_YYYYMMDD.csv`
- `prosocial_papers_YYYYMMDD.json`

历史记录在 `data/sent_history.json`（防止重复推送）。

---

## 费用

| 服务 | 费用 |
|---|---|
| PubMed / OpenAlex | 完全免费 |
| DeepSeek API | 每次运行约 $0.0002 |
| Gmail SMTP | 免费 |
| GitHub Actions | 私有仓库每月 2000 分钟免费（每次运行约 2 分钟） |
