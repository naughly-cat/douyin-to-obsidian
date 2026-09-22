# douyin-to-obsidian

<p align="center">
  <strong>一键采集抖音与小红书爆款口播文案，通过本地 Whisper 提取黄金钩子与完整逐字稿，无缝同步至 Obsidian 双链知识库。</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License">
  <img src="https://img.shields.io/badge/python-3.9%2B-green.svg" alt="Python">
  <img src="https://img.shields.io/badge/tested-macOS-success.svg" alt="Tested on macOS">
  <img src="https://img.shields.io/badge/Linux%20%7C%20Windows-experimental-lightgrey.svg" alt="Linux and Windows experimental">
  <img src="https://img.shields.io/badge/Obsidian-Compatible-705dcf.svg" alt="Obsidian">
  <img src="https://img.shields.io/badge/Whisper-Metal%20GPU-red.svg" alt="Whisper">
</p>

---

## 💡 为什么做这个项目？

很多内容创作者、个人成长记录者以及知识工作者，在刷抖音和小红书时看到优质的爆款短视频或干货笔记，常常面临三大痛点：
1. **收藏即吃灰**：点赞收藏后几乎再也不会点开，视频无法被检索、摘录和复用。
2. **缺乏结构化**：短视频的核心价值在**口播台词**与**开头前15秒反差钩子**，传统截图或收藏夹无法沉淀文本语料。
3. **商业云转写昂贵/繁琐**：市面上的转写工具要么按分钟收费，要么操作繁复且无法一键打通个人笔记系统。

`douyin-to-obsidian` 应运而生：
- 🎯 **本地极速转录**：借助 Apple Silicon (Metal GPU) 与 `whisper.cpp`，转写过程在本地完成；
- 🇨🇳 **国内镜像优先**：优先从 ModelScope 下载 Whisper 模型，失败后回退官方 HuggingFace 源；
- 🧠 **开头片段提取**：按 ASR 时间戳切分前 15 秒台词，保留原始开篇节奏；
- 📓 **原生融入 Obsidian**：自动生成带 YAML 属性、Callout 块、Dataview 查询与双链导航的精美 Markdown 文档；
- 🤖 **Agent 原生技能**：自带 `SKILL.md`，可作为 Claude Code / Antigravity / Codex 的原生 Agent Skill 调用。

---

## ✨ 核心特性

- **多模式输入支持**：
  - 🔗 **单链接/分享文本**：直接粘贴抖音/小红书手机端分享文本，自动提取并转录；
  - 📦 **MediaCrawler 批量数据对接**：无缝读取 MediaCrawler 抓取目录（JSON/JSONL/CSV），按点赞阈值批量富化；
  - 📁 **本地音视频文件**：支持本地 `.mp4/.mp3/.wav/.m4a` 直接解析沉淀。
- **高精音频处理流水线**：
  - 自动注入平台防盗链 Referer 请求头拉取媒体流；
  - 自动调用 `ffmpeg` 进行 16kHz 16-bit 单声道 PCM 统一重采样；
  - Whisper 分段时间戳与字幕生成。
- **下载安全与可靠性**：
  - Whisper 模型内置 whisper.cpp 官方 SHA256 校验和，下载后自动完整性校验，被篡改或损坏的文件直接丢弃；
  - ModelScope 主源失败自动回退 whisper.cpp 官方源（HuggingFace）；
  - 网络请求默认严格 HTTPS 证书校验；只有用户显式传入 `--insecure` 时才允许一次不安全重试。
- **Obsidian 深度整合**：
  - **单篇口播笔记**：包含互动指标（点赞/分享/评论）、前15秒反差钩子、完整逐字稿代码块、分段时间戳；
  - **汇总爆款大库**：合并式追加、重复条目自动去重，按热度降序展示所有已转写爆款及折叠全文；
  - **全局双链索引**：内置 Dataview 查询块，支持按创作者、分类、点赞随时检索。
  - **结构化状态与原子写入**：汇总状态保存在 `.douyin-to-obsidian/aggregate-state.json`，Markdown 仅作为渲染产物，降低中断或手工编辑导致历史数据丢失的风险。

---

## 🛠️ 前置准备

### 1. 系统依赖
- **Python 3.9+**（CI 覆盖 3.9–3.12）
- **ffmpeg**（音视频流提取与重采样）：
  - macOS: `brew install ffmpeg`
  - Ubuntu/Debian: `sudo apt install ffmpeg`
  - Windows: `winget install Gyan.FFmpeg`
- **whisper-cli**（推荐，享 Metal GPU 极致加速）：
  - macOS: `brew install whisper-cpp`
  - 或安装 Python 降级库：`pip install faster-whisper`

---

## 🚀 快速上手

### 1. 安装项目

```bash
git clone https://github.com/naughly-cat/douyin-to-obsidian.git
cd douyin-to-obsidian
pip install -e .
```

### 2. 配置 Obsidian 目录（可选）
可以通过环境变量指定知识库位置（建议写入 `~/.zshrc` 或 `~/.bashrc`）：
```bash
export OBSIDIAN_VAULT_DIR="/Users/your_name/Documents/ObsidianVault/素材库"
```
若未配置环境变量，亦可通过 `--obsidian-dir` 命令行参数随时传入。

另外，环境变量 `D2O_WHISPER_TIMEOUT` 可调整单次语音转写的子进程超时秒数（默认 120，长视频建议调大）。

默认情况下，HTTPS 证书校验失败会立即终止。请优先修复本机证书环境；只有在你理解中间人攻击风险且确认目标地址可信时，才临时添加 `--insecure`。

---

## 💻 命令行用法 (CLI)

### 模式一：转录单个分享链接或口令
直接将手机复制的分享文案粘贴即可：
```bash
# 抖音分享口令
douyin-to-obsidian url "7.12 复制打开抖音，看看【演示博主的作品】普通人学AI总是在放弃？ https://v.douyin.com/iABC123/"

# 小红书分享链接
douyin-to-obsidian url "http://xhslink.com/a/xyz123"

# 同时追加到汇总大库，并指定使用 small 模型
douyin-to-obsidian url "https://v.douyin.com/iABC123/" --aggregate --model small
```

### 模式二：MediaCrawler 批量抓取数据富化

批量模式基于开源爬虫项目 [MediaCrawler](https://github.com/NanmiCoder/MediaCrawler)（支持小红书、抖音等多平台公开数据抓取）。**本项目不内置爬虫**，只读取 MediaCrawler 导出的数据文件（JSON / JSONL / CSV 均支持）。

#### 第一步：安装 MediaCrawler

```bash
# 克隆到 ~/MediaCrawler 可与默认扫描目录对齐（克隆到别处也可以，用 --data-dir 指定即可）
git clone https://github.com/NanmiCoder/MediaCrawler.git ~/MediaCrawler
cd ~/MediaCrawler

# 依赖 uv（https://docs.astral.sh/uv/getting-started/installation）与 Node.js（>=16）
uv sync
```

浏览器配置（二选一）：
- **CDP 模式（默认）**：复用本机 Chrome（≥144）的登录态，在 Chrome 地址栏打开 `chrome://inspect/#remote-debugging` 并勾选 "Allow remote debugging for this browser instance"；
- **Playwright 模式**：在 `config/base_config.py` 中设 `ENABLE_CDP_MODE = False`，然后执行 `uv run playwright install`。

#### 第二步：抓取数据

```bash
# 关键词搜索并抓取帖子信息（首次运行会弹出浏览器，扫码登录）
uv run main.py --platform xhs --lt qrcode --type search
uv run main.py --platform dy --lt qrcode --type search

# 查看全部参数
uv run main.py --help
```

数据默认落盘在 MediaCrawler 项目的 `data/<平台>/` 目录下（JSON / JSONL / CSV 可在 `config/base_config.py` 中配置）。

#### 第三步：批量转录到 Obsidian

```bash
# 扫描 MediaCrawler 数据目录，筛选点赞 >= 500 的作品，转录前 20 条
douyin-to-obsidian batch --data-dir ~/MediaCrawler/data --min-likes 500 --limit 20

# 仅处理抖音平台，并指定采集日期批次
douyin-to-obsidian batch --platform dy --date 2026-09-20
```

> ⚠️ MediaCrawler 仅供学习研究使用（其自身许可禁止商业用途）；抓取内容的版权归原作者所有，请遵守目标平台的服务条款，合理控制抓取频率。

### 模式三：本地音视频文件转录
```bash
douyin-to-obsidian file ~/Downloads/interview.mp4 --title "AI工具深度访谈" --author "李四"
```

### 模式四：刷新知识库索引
```bash
douyin-to-obsidian index
```

---

## 🤖 作为 AI Agent Skill 使用

本项目根目录包含标准的 `SKILL.md`，兼容 **Antigravity**、**Claude Code** 以及 **Codex** 等智能体框架。

将本仓库克隆或软链接至 Agent 技能目录（如 `.agents/skills/douyin-to-obsidian`），并安装 CLI：

```bash
cd .agents/skills/douyin-to-obsidian
python3 -m pip install -e .
```

安装完成后即可向 AI 发出自然语言指令：
- *“帮我把这个抖音视频转写成 Obsidian 笔记，提取前15秒反差钩子”*
- *“把刚刚爬取的学AI爆款视频里点赞超过 1000 的全部转录出来并更新知识库索引”*

---

## 📁 产物在 Obsidian 中的呈现

导出的笔记支持 Obsidian 原生 Markdown；安装 Dataview 插件后可使用内置查询：

### 单篇口播笔记效果
````markdown
---
title: "为什么普通人学AI总是在放弃？"
author: "演示博主"
platform: "抖音"
topic: "🧠 认知重塑与去魅思考"
likes: 28000
shares: 4500
comments: 1200
url: "https://example.com/demo/video"
created_at: '2026-09-22'
tags:
  - 语料/口播文案
  - 平台/抖音
  - 爆款拆解/钩子
---

> [!NOTE] 知识库双链导航
> - 上级索引：[[00_素材库索引]]
> - 爆款总库：[[数据-爆款口播逐字稿与黄金钩子库]]

# 为什么普通人学AI总是在放弃？

- **创作者**：`演示博主`
- **数据表现**：👍 **2.8万** 赞 · 🔁 **4500** 分享 · 💬 **1200** 评论

## 🎯 前15秒黄金反差钩子
> [!TIP] 开头反差与受众注意力抓手
> *"很多人以为学AI要先背提示词学Python，其实全搞反了。今天告诉你真正能让你拿到结果的唯一心法。"*

## 🎙️ 完整口播逐字稿
```text
大家好，我是演示博主。最近收到很多读者留言……
```
````

---

## 🗺️ 项目结构

```text
douyin-to-obsidian/
├── SKILL.md                          # Agent Skill 规范定义
├── README.md                         # 本文档
├── CHANGELOG.md                      # 版本变更记录
├── CONTRIBUTING.md                   # 贡献指南
├── SECURITY.md                       # 漏洞报告与安全边界
├── pyproject.toml                    # PEP 621 现代打包构建配置
├── requirements.txt                  # 依赖清单
├── LICENSE                           # MIT 许可证
├── .github/workflows/ci.yml          # GitHub Actions CI 自动化测试
├── examples/                         # 导出笔记效果示例
├── douyin_to_obsidian/               # 核心源码包
│   ├── __init__.py
│   ├── cli.py                        # CLI 命令行交互入口
│   ├── config.py                     # 配置解析与模型 SHA256 校验和
│   ├── core/
│   │   ├── transcriber.py            # Whisper ASR、模型下载校验与镜像回退
│   │   ├── parser.py                 # 分享链接与媒体直链解析
│   │   ├── analyzer.py               # 黄金15秒钩子提炼与主题打标
│   │   ├── net.py                    # HTTP 工具（默认严格 TLS 证书校验）
│   │   └── crawler_adapter.py        # MediaCrawler 批量数据读取与缓存
│   └── exporters/
│       └── obsidian.py               # 原生 Obsidian Markdown 与双链生成
└── tests/                            # pytest 自动化测试套件
    ├── test_analyzer.py
    ├── test_cli.py
    ├── test_parser.py
    ├── test_crawler_adapter.py
    ├── test_net.py
    ├── test_obsidian_exporter.py
    └── test_transcriber.py
```

---

## 🤝 参与贡献 (Contributing)

欢迎提交 Issue 和 Pull Request，开发环境、测试与提交要求见 [CONTRIBUTING.md](CONTRIBUTING.md)。安全问题请不要提交公开 Issue，改按 [SECURITY.md](SECURITY.md) 说明私下报告。

示例目录中的人物、互动数字、链接与逐字稿均为虚构演示数据，不对应真实创作者或真实作品。

---

## ⚠️ 免责声明

- 本项目的软件代码按 MIT License 授权；这不代表你自动获得第三方视频、音频、文字、商标或个人信息的使用权。
- 单链接模式面向用户主动提供的公开可访问链接；请勿用本工具绕过访问控制、批量滥用接口或干扰平台运行。
- 批量数据可由第三方项目 [MediaCrawler](https://github.com/NanmiCoder/MediaCrawler) 提供；MediaCrawler 有独立的非商业学习许可证，使用者必须另行遵守。
- 转写和导出的内容可能受版权、隐私权、个人信息保护规则及平台服务条款约束。公开、再分发或商业使用前，请确认你拥有必要授权。
- 本节仅用于说明项目边界，不构成法律意见。

---

## 📄 开源许可证

本项目采用 [MIT License](LICENSE) 授权许可。
