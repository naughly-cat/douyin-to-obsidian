---
name: douyin-to-obsidian
version: 0.2.0
description: >-
  抖音/小红书内容研究与 Obsidian 素材库技能。既支持分享链接、MediaCrawler 批量数据和本地音视频的
  Whisper 转写、前15秒钩子提取与 Obsidian 双链入库，也提供 Douyin Viral Topic Radar：
  从一批抖音作品与评论中计算作者基线异常、跨账号复现、近期密度、高意图互动、评论需求和可用时的低粉突破，
  找出被市场反复验证的“问题母题”，再由 Agent 做语义合并与选题迁移。
---

# douyin-to-obsidian 0.2

这个 Skill 现在有两条独立但可串联的工作流：

1. **Material Library**：把短视频/图文变成可搜索、可引用、可复用的 Obsidian 文本资产；
2. **Douyin Viral Topic Radar**：把“高赞视频列表”升级成“爆款问题母题雷达”。

核心变化：

> **不要问“最近有哪些高赞视频”，而要问“最近哪些普通人的具体问题，被多个独立账号反复验证为高需求？”**

---

## 1. Radar 的判断原则

### 1.1 单条爆款不是母题

一条 10 万赞视频只能证明“这条视频成功了”，不能单独证明题材成功。

优先寻找：

- 多个独立账号都做过相似问题；
- 这些作品相对作者自己的近期基线明显异常；
- 最近 7–30 天仍在反复出现；
- 收藏、分享、评论等高意图互动强；
- 评论区持续出现“怎么做 / 能不能用于 X / 求方法 / 求模板”；
- 如果抓到可靠粉丝数，再看小账号是否也能突破。

### 1.2 先算 Market Score，再算项目 Fit Score

Radar 输出的 **Market Score** 只回答：

> 这个问题母题有没有被抖音市场反复验证？

它不回答：

> 我们应该不应该拍？

最终立项还必须进入上层项目自己的 Fit Score，例如：

- 问题共鸣；
- 结果是否可见；
- 制作成本；
- AI 是否真的必要；
- 本人能否可信实测；
- 收藏/搜索价值。

### 1.3 缺失数据不能补脑

Radar 对缺失指标采用 `N/A + 可用权重归一`：

- 作者作品样本不足 → 不计算爆款倍率；
- 没抓评论 → 不计算评论需求密度；
- 没抓粉丝数 → 不计算低粉突破；
- 没发布时间 → 不计算近期密度。

禁止把缺数据当 0 分，也禁止猜粉丝数、发布时间或互动。

---

## 2. Market Score

默认权重：

| 维度 | 权重 |
|---|---:|
| 跨账号爆款复现 | 25 |
| 相对作者自身基线异常 | 20 |
| 近 7/30 天热度密度 | 15 |
| 收藏/分享等高意图互动 | 15 |
| 评论区需求密度 | 15 |
| 低粉账号突破（数据可用时） | 10 |

结构化真源会保留每个维度的 `score / weight / available`，便于复核，不只输出一个总分。

---

## 3. Radar 标准工作流

### Step A：设计采样，不要只搜一个关键词

搜索目标是“问题空间”，不是“工具名”。

AI 普通人赛道示例：

```text
上班：
AI PDF, AI会议, AI周报, AI PPT, AI邮件, AI工作效率

信息过载：
AI整理资料, AI收藏夹, AI知识库, AI截图整理, AI总结文章

写作表达：
AI写文案, 去AI味, AI改写, AI写口播, AI写标题

学习理解：
普通人怎么用AI, AI学习, AI读书, AI看教程, AI论文

生活：
AI旅行规划, AI日程, AI复盘, AI购物决策
```

另外补充：

- 2–5 个对标账号主页样本；
- 新 AI 能力对应的“真实问题”关键词；
- 评论区裂变出来的新需求词。

不要只抓“ChatGPT / Claude / 豆包”等工具名，否则样本会被工具热点污染。

### Step B：用 MediaCrawler 抓作品 + 评论

本项目不内置爬虫，仍由用户已有的 MediaCrawler 负责公开内容采集。

抖音关键词示例：

```bash
cd ~/MediaCrawler
uv run main.py --platform dy --lt qrcode --type search \
  --keywords "AI PDF,AI会议,AI整理资料,去AI味,普通人怎么用AI" \
  --save_data_option jsonl
```

评论抓取是否开启、每篇抓多少条等配置，按**当前安装的 MediaCrawler 版本**设置；不要凭旧文档伪造命令行参数。

原则：

- 只抓公开可访问内容；
- 不绕过登录或访问控制；
- 合理控制频率；
- 遵守 MediaCrawler 许可与目标平台规则。

### Step C：跑定量雷达

```bash
douyin-to-obsidian radar \
  --data-dir ~/MediaCrawler/data \
  --platform dy \
  --window-days 30 \
  --recent-days 7 \
  --min-authors 2 \
  --top 20
```

重要：

- `radar` 默认 `--min-likes 0`，因为需要普通作品参与作者基线计算；
- 不要先把所有低赞作品过滤掉，否则“相对作者基线异常”会失真；
- `radar` 本身**不会为了几百条样本批量跑 Whisper**；
- 如果此前 `batch` 已转写过，会自动复用 `.transcripts_cache.json` 增强母题聚类；
- 想提高语义质量，可以先对重点高赞样本执行 `batch`，再重跑 radar。

### Step D：Agent 做语义复核

CLI 是定量第一遍，不假装纯规则能理解所有中文语义。

Agent 必须读取：

```text
.douyin-to-obsidian/viral-topic-radar.json
数据-抖音爆款选题雷达.md
```

然后做第二遍：

1. **合并同义母题**  
   例如“AI 看 PDF / AI 读行业报告 / AI 总结论文”可能都属于：
   > 长资料看不完：让 AI 先读。

2. **拆开错误聚类**  
   例如“AI 写周报”和“AI 去 AI 味”都有“写作”，但用户需求可能完全不同。

3. **去工具化命名**  
   不用：
   > ChatGPT PDF。

   改成：
   > 领导发来几十页资料，我能不能不从第一页开始看？

4. **从评论区长出需求树**  
   例如：
   > PDF → 论文 → 合同 → 财报 → 扫描件 → 公司隐私资料。

5. **只把市场已验证母题交给上层 Fit Score**  
   不直接复制原视频标题，不直接把 Market Score 当立项结论。

---

## 4. Radar CLI

### 默认运行

```bash
douyin-to-obsidian radar --data-dir ~/MediaCrawler/data
```

### 常用参数

```bash
douyin-to-obsidian radar \
  --data-dir ~/MediaCrawler/data \
  --platform dy \
  --min-likes 0 \
  --window-days 30 \
  --recent-days 7 \
  --min-authors 2 \
  --top 20
```

参数含义：

- `--min-likes`：进入基线分析的最低点赞，默认 0；
- `--window-days`：母题观察窗口，默认 30；
- `--recent-days`：短周期窗口，默认 7；
- `--min-authors`：进入母题榜至少需要多少独立作者，默认 2；
- `--top`：输出多少个母题；
- `--no-comments`：不加载评论，评论需求维度会标 N/A；
- `--date`：仅扫描文件名含指定日期的采集批次。

---

## 5. Radar 输出

默认生成：

```text
<OBSIDIAN_DIR>/
├── 数据-抖音爆款选题雷达.md
└── .douyin-to-obsidian/
    └── viral-topic-radar.json
```

Markdown 看板包含：

- 母题 Market Score 排名；
- 独立作者数；
- 样本数；
- 作者基线异常倍率；
- 7 日 / 30 日时间密度；
- 高意图互动；
- 评论需求密度；
- 低粉突破（数据存在时）；
- 爆款证据视频；
- 评论区未满足需求；
- Agent 二次复核清单。

JSON 是结构化真源，Markdown 是阅读看板。

---

## 6. Radar 数据口径

### 作者基线

优先用：

> 当前视频之外，该作者其他已采样作品点赞中位数。

要求至少有足够其他作品。

```text
viral_multiplier = 当前作品点赞 / 作者其他作品点赞中位数
```

作者样本不足时不算，不退化成“全站平均”。

### 高意图互动

当前启发式：

```text
(2 × 分享 + 1.5 × 收藏 + 0.5 × 评论) / 点赞
```

再与当前样本整体分布比较，不把绝对点赞当唯一热度。

### 评论需求

识别：

- 怎么 / 如何；
- 求教程 / 求方法 / 求提示词 / 求模板；
- 能不能用于 X；
- 有没有 / 哪里 / 哪个；
- 收费 / 免费；
- 隐私 / 安全；
- 论文 / 合同 / 财报 / 扫描件等迁移场景。

这是“需求信号”，不是事实判断。

---

## 7. 原有 Material Library 功能继续保留

### 单分享链接

```bash
douyin-to-obsidian url "https://v.douyin.com/xxx/" --aggregate
```

### MediaCrawler 批量转写

```bash
douyin-to-obsidian batch \
  --data-dir ~/MediaCrawler/data \
  --platform dy \
  --min-likes 500 \
  --limit 20
```

### 本地音视频

```bash
douyin-to-obsidian file ~/Downloads/demo.mp4 \
  --title "素材标题" \
  --aggregate
```

### 刷新索引

```bash
douyin-to-obsidian index
```

原有能力包括：

- Whisper 本地 ASR；
- 前 15 秒钩子；
- 完整逐字稿；
- YAML Frontmatter；
- Obsidian 双链；
- 汇总大库；
- 单篇笔记；
- 转写缓存；
- 创作者 dossier。

---

## 8. 推荐的 Agent 调用语义

以下请求应优先走 Radar，而不是简单 `batch`：

- “帮我找最近抖音 AI 赛道的爆款选题”
- “看看最近哪些 AI 题材多个账号都爆了”
- “帮我做一份抖音选题雷达”
- “别只看点赞，帮我找低粉也能爆的选题”
- “从评论区找下一批 AI 选题”
- “分析周好好、王较劲这类账号做过的母题，再找跨账号验证”

以下请求仍走 Material Library：

- “把这个视频转成文字”
- “把这批视频写进 Obsidian”
- “帮我提取前 15 秒”
- “把本地视频转写”

如果用户同时要“采素材 + 找题”：

> 先 MediaCrawler 采样 → radar 找母题 → 对重点证据 batch 转写 → 写入 Obsidian。

---

## 9. 和 ai个人成长项目的接口

在 `ai-growth-diary/projects/ai个人成长` 中：

```text
Douyin Viral Topic Radar
        ↓
Market Score
        ↓
Agent 语义复核 / 去工具化
        ↓
TOPIC_SCOUT_SOP 的 Fit Score
        ↓
真实实验设计
        ↓
ai-learning-diary-writer
```

注意：

> **Radar 负责“市场有没有验证”，TOPIC_SCOUT 负责“我们值不值得做”。**

两者不要合成一个总分，否则很容易把“市场很热但我们做不出差异”的题误判为高优先级。

---

## 10. 安全与真实性

- 不绕过登录态、付费墙、风控或访问限制；
- 不高频抓取；
- 不把原作者完整文案直接改写后发布；
- 评论只用于需求研究，不公开整理个人敏感信息；
- 不把绝对点赞等同于选题强度；
- 不把轻量规则聚类声称成“AI 已经完全理解语义”；
- `agent_semantic_review_required=true` 的母题必须人工/Agent 复核；
- 任何市场结论都要说明采样窗口和样本范围。
