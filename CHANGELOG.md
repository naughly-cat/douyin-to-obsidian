# Changelog

本项目遵循 [Semantic Versioning](https://semver.org/)；当前仍处于 `0.x` 早期阶段。

## [0.1.0] - 2026-09-22

### Added

- 抖音、小红书分享文本解析与本地 Whisper 转写；
- MediaCrawler JSON、JSONL、CSV 批量数据适配；
- Obsidian 单篇笔记、汇总库与 Dataview 索引导出；
- Whisper 模型双源下载和内置 SHA256 校验；
- Agent Skill 入口、离线测试与多版本 CI。

### Security

- HTTPS 默认严格校验，不安全重试必须显式启用；
- 未内置校验和的模型名称会被拒绝；
- Frontmatter 字段安全转义，远程文本不能插入额外 YAML 字段。

### Fixed

- 汇总库改用结构化 sidecar 保存状态并采用原子写入；
- 批量转写缓存改为原子写入，缓存损坏时停止覆盖并提示显式重建；
- 同一 URL 在内容 ID 变化后仍可正确去重；
- 单篇笔记文件名加入稳定短哈希，避免相同标题前缀互相覆盖；
- Markdown 代码围栏会根据正文内容自动加长，避免逐字稿截断文档结构。
