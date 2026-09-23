---
name: douyin-to-obsidian
description: >-
  一键采集抖音与小红书爆款口播文案，利用本地 Apple Silicon Metal GPU 加速的 Whisper ASR
  提取前15秒黄金反差钩子与完整口播逐字稿，自动结构化导出至 Obsidian 双链知识库（包含标准 YAML Frontmatter、
  Callout 块、Dataview 检索标签与双向链接母库）。支持单分享链接解析、MediaCrawler 批量数据富化及本地音视频直接转录；
  适用于用户要求把这些素材转写、结构化并写入 Obsidian 时。
---

# 抖音/小红书口播文案采集与 Obsidian 知识库导出技能 (douyin-to-obsidian)

`douyin-to-obsidian` 专注于将社媒短视频（抖音、小红书等）与图文笔记中的**高赞口播文案、黄金反差钩子与互动指标**，通过本地端侧高精度的 Whisper ASR 语音模型极速转录并沉淀为符合 Obsidian 双链规范的知识资产。

---

## 1. 核心能力与特性

- 🎯 **前15秒黄金反差钩子提炼**：根据 ASR 时间戳（$\le 15.0$ 秒）或图文首段反差句，精准切分最具受众吸引力的开头。
- 🎙️ **原生 Whisper ASR 本地极速转写**：
  - 默认采用 Apple Silicon (Metal GPU) 硬件加速的 `whisper-cli`；
  - 自动从国内高速源 (ModelScope) 镜像免梯下载 ggml 模型；
  - 支持 `tiny`、`base`、`small`、`medium`、`large-v3-turbo` 规格。
- 📓 **Obsidian 双链与 Dataview 适配**：
  - 标准 YAML Frontmatter 元数据（标题、创作者、平台、分类、点赞、分享、评论、链接）；
  - Obsidian Callout 原生语法（`> [!TIP] 前15秒黄金钩子`）；
  - 自动维护 `00_素材库索引.md` 与 `数据-爆款口播逐字稿与黄金钩子库.md`；
  - 使用 `.douyin-to-obsidian/aggregate-state.json` 保存结构化汇总状态，Markdown 由状态渲染。
- 🔄 **三大输入模式**：
  - **单链接/分享口令**：直接粘贴用户从抖音/小红书复制的分享文本；
  - **MediaCrawler 批量模式**：自动扫描并去重 MediaCrawler 抓取目录，过滤高赞内容后逐条转录；
  - **本地音视频文件模式**：直接转录本地 `.mp4/.mp3/.wav/.m4a` 文件。

---

## 2. 何时调用本技能 (Trigger Scenarios)

当用户或上层工作流发出以下指令时调用本技能：
1. **单篇视频解析**：“帮我把这个抖音视频转写成 Obsidian 笔记”、“分析这个小红书笔记的口播并存入知识库”；
2. **关键词收集 → 入库**：“按‘AI 自媒体’这个关键词收集公开内容，把口播整理进 Obsidian”；
3. **创作者主页 → 入库**：“把这个抖音/小红书博主主页的公开作品整理成文字素材库”；
4. **批量素材处理**：“扫描刚抓取的抖音数据并把口播转录出来”、“把点赞超过 500 的学AI视频全部转写并更新到 Obsidian”；
5. **本地音视频沉淀**：“把这段本地录音/视频提取文案写入知识库”。

---

## 3. 标准 CLI 命令参考

优先调用已安装的全局命令 `douyin-to-obsidian`。若命令不存在，先查看项目 README 的安装步骤；从源码直接运行时，工作目录必须是本技能根目录，或先执行 `python3 -m pip install -e .`。

网络请求默认严格校验证书。不得自行添加 `--insecure`；只有用户明确要求、理解风险且确认目标地址可信时才可临时使用。

### 3.1 模式一：单个分享链接 / 文本快速转录
```bash
# 直接传入抖音/小红书分享口令或直链，自动转录并生成单篇 Obsidian 笔记
douyin-to-obsidian url "7.12 复制打开抖音，看看【xxx的作品】... https://v.douyin.com/xxx/"

# 同时自动追加更新到【汇总大库】
douyin-to-obsidian url "https://v.douyin.com/xxx/" --aggregate

# 自定义 Obsidian 目录与模型规格
douyin-to-obsidian url "https://v.douyin.com/xxx/" \
  --obsidian-dir ~/Documents/ObsidianVault/素材库 \
  --model small
```

### 3.2 模式二：MediaCrawler 批量数据扫描与富化

#### Agent 编排：关键词 / 创作者主页 → MediaCrawler → Obsidian

当用户给的是**关键词**或**创作者主页链接**时，本 Skill 可以在 Agent 层把两步串起来，但必须明确：`douyin-to-obsidian` 本身不内置爬虫，采集步骤由用户已安装的 MediaCrawler 完成，本 Skill 再读取其落盘数据并转写、结构化入库。

关键词示例（抖音）：

```bash
cd ~/MediaCrawler
uv run main.py --platform dy --lt qrcode --type search \
  --keywords "AI自媒体" --save_data_option jsonl

douyin-to-obsidian batch \
  --data-dir ~/MediaCrawler/data \
  --platform dy --aggregate
```

创作者主页示例（抖音）：

```bash
cd ~/MediaCrawler
uv run main.py --platform dy --lt qrcode --type creator \
  --creator_id "https://www.douyin.com/user/..." \
  --save_data_option jsonl

douyin-to-obsidian batch \
  --data-dir ~/MediaCrawler/data \
  --platform dy --aggregate
```

小红书同理使用 `--platform xhs`；创作者模式应传 MediaCrawler 可解析的完整主页 URL，若平台当前要求 `xsec_token/xsec_source` 等参数，则保留浏览器复制出的完整 URL，不自行伪造参数。

Agent 执行时必须先确认：MediaCrawler 已安装、目标内容为公开可访问、用户有权进行相应处理，并遵守 MediaCrawler 的非商业学习许可及目标平台规则。不得绕过登录/访问控制，不做大规模或高频抓取。

本项目不内置爬虫，批量数据来自开源项目 [MediaCrawler](https://github.com/NanmiCoder/MediaCrawler) 的抓取导出（安装与抓取步骤见项目 README「模式二」）。支持读取其导出的 JSON / JSONL / CSV 数据文件。

```bash
# 扫描 MediaCrawler 默认目录 (~/MediaCrawler/data)，筛选 >= 500 赞，单次最多转写 20 条
douyin-to-obsidian batch --min-likes 500 --limit 20

# 仅扫描小红书或抖音平台
douyin-to-obsidian batch --platform xhs --min-likes 200
douyin-to-obsidian batch --platform dy --min-likes 1000

# 指定抓取日期批次并重置缓存
douyin-to-obsidian batch --date 2026-09-20 --reset-cache
```

### 3.3 模式三：本地音视频文件转录
```bash
douyin-to-obsidian file ~/Downloads/interview.mp4 \
  --title "AI工具深度访谈" \
  --author "张三" \
  --aggregate
```

### 3.4 模式四：刷新全局双链索引
```bash
douyin-to-obsidian index
```

---

## 4. 输出产物规范

导出到 Obsidian 知识库后的目录结构：
```text
<OBSIDIAN_DIR>/
├── 00_素材库索引.md                         # 知识库母索引与 Dataview 看板
├── 数据-爆款口播逐字稿与黄金钩子库.md        # 全量爆款口播按赞数排序大库（含折叠逐字稿）
├── .douyin-to-obsidian/
│   └── aggregate-state.json                  # 汇总库结构化状态真源
└── 单篇口播笔记/                            # 每篇视频独立的 Markdown 资产
    ├── 抖音-{创作者}-{标题前缀}-{短哈希}.md
    └── 小红书-{创作者}-{标题前缀}-{短哈希}.md
```

### 单篇笔记 YAML Frontmatter 结构范例：
```markdown
---
title: "普通人学AI必须避开的三个大坑"
author: "AI实战家"
platform: "抖音"
topic: "🛠️ AI工具实测与工作流"
likes: 25000
shares: 3200
comments: 890
url: "https://www.douyin.com/video/..."
created_at: '2026-09-22'
tags:
  - 语料/口播文案
  - 平台/抖音
  - 爆款拆解/钩子
  - 话题/AI工具实测与工作流
---
```

---

## 5. 环境变量与配置优先级

1. **命令行参数**：`--obsidian-dir`
2. **环境变量**：`OBSIDIAN_VAULT_DIR` 或 `OBSIDIAN_DIR`
3. **默认回退**：`~/Documents/Obsidian/素材库/短视频口播`
4. **模型缓存**：`~/.cache/whisper`
5. **转写超时**：环境变量 `D2O_WHISPER_TIMEOUT`（秒，默认 120；长视频建议调大）

模型只接受内置 SHA256 的 `tiny`、`base`、`small`、`medium`、`large-v3-turbo`。不要绕过校验下载未知模型。
