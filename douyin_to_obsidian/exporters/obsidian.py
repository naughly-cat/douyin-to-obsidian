# -*- coding: utf-8 -*-
"""
Obsidian 知识库 Markdown 导出器 (Obsidian Exporter)
===================================================
- 生成原生 Obsidian Markdown 规范文档
- 标准 YAML Frontmatter，天然适配 Dataview 插件检索
- 原生 Callout 语法（前15秒反差钩子、逐字稿台词）
- 支持单篇笔记沉淀、汇总逐字稿母库、创作者对标看板与双链知识索引
"""

import base64
import hashlib
import json
import os
import re
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..core.analyzer import ContentAnalyzer


class ObsidianExporter:
    """Obsidian 笔记生成与双链知识库总装"""

    def __init__(self, output_dir: Path):
        self.output_dir = Path(output_dir).expanduser().resolve()
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _single_line(value: Any) -> str:
        """将不可信的展示字段压成单行，避免破坏 Markdown 结构。"""
        return " ".join(str(value or "").split())

    @staticmethod
    def _yaml_scalar(value: Any) -> str:
        """JSON 字符串是合法 YAML 标量，可可靠转义换行、引号与反斜杠。"""
        return json.dumps(str(value or ""), ensure_ascii=False)

    @staticmethod
    def _fenced_text(text: str, language: str = "text") -> List[str]:
        """生成不会被正文中反引号提前闭合的 Markdown 代码块。"""
        runs = [len(m.group(0)) for m in re.finditer(r"`+", text)]
        fence = "`" * max(3, (max(runs) + 1) if runs else 3)
        return [f"{fence}{language}", text, fence]

    @staticmethod
    def _atomic_write_text(target_file: Path, content: str) -> None:
        """在同一目录写临时文件后原子替换，避免中断时留下半截文件。"""
        target_file.parent.mkdir(parents=True, exist_ok=True)
        tmp_name = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=target_file.parent,
                prefix=f".{target_file.name}.",
                suffix=".tmp",
                delete=False,
            ) as tmp:
                tmp.write(content)
                tmp.flush()
                os.fsync(tmp.fileno())
                tmp_name = tmp.name
            os.replace(tmp_name, target_file)
        finally:
            if tmp_name and os.path.exists(tmp_name):
                os.unlink(tmp_name)

    @staticmethod
    def _sanitize_filename(name: str) -> str:
        """过滤文件名非法字符（\\ / : * ? \" < > |）"""
        sanitized = re.sub(r'[\\/*?:"<>|]', "", name).strip()
        sanitized = sanitized.replace("\n", " ").replace("\r", " ")
        return sanitized[:80] if sanitized else "未命名笔记"

    def export_single_note(self, item: Dict[str, Any], subfolder: str = "单篇口播笔记") -> Path:
        """
        为单个短视频/图文笔记生成独立的 Obsidian Markdown 文件。
        非常适合 Obsidian 关系图谱与双链引用。
        """
        today = time.strftime("%Y-%m-%d")
        title = str(item.get("title") or "无标题作品")
        author = str(item.get("author") or "未知创作者")
        display_title = self._single_line(title)
        display_author = self._single_line(author)
        platform_code = item.get("platform", "")
        platform_name = "抖音" if platform_code == "douyin" else ("小红书" if platform_code == "xiaohongshu" else platform_code)
        
        likes = ContentAnalyzer.parse_count(item.get("liked_count", 0))
        shares = ContentAnalyzer.parse_count(item.get("share_count", 0))
        comments = ContentAnalyzer.parse_count(item.get("comment_count", 0))
        url = str(item.get("url") or "")
        hook = self._single_line(item.get("hook_15s") or "（未提取到独立钩子）")
        transcript = str(item.get("transcript") or item.get("desc") or "（暂无台词内容）").strip()
        topic = str(item.get("topic") or ContentAnalyzer.categorize(title, transcript))
        topic_tag = f"话题/{topic.split()[-1] if ' ' in topic else topic}"

        note_dir = self.output_dir / subfolder
        note_dir.mkdir(parents=True, exist_ok=True)

        identity_hash = hashlib.sha256(self._entry_key(item).encode("utf-8")).hexdigest()[:10]
        filename = self._sanitize_filename(
            f"{platform_name}-{display_author}-{display_title[:25]}-{identity_hash}"
        ) + ".md"
        target_file = note_dir / filename

        md_lines = [
            "---",
            f"title: {self._yaml_scalar(title)}",
            f"author: {self._yaml_scalar(author)}",
            f"platform: {self._yaml_scalar(platform_name)}",
            f"topic: {self._yaml_scalar(topic)}",
            f"likes: {likes}",
            f"shares: {shares}",
            f"comments: {comments}",
            f"url: {self._yaml_scalar(url)}",
            f"created_at: '{today}'",
            "tags:",
            f"  - {self._yaml_scalar('语料/口播文案')}",
            f"  - {self._yaml_scalar(f'平台/{platform_name}')}",
            f"  - {self._yaml_scalar('爆款拆解/钩子')}",
            f"  - {self._yaml_scalar(topic_tag)}",
            "---",
            "",
            "> [!NOTE] 知识库双链导航",
            "> - 上级索引：[[00_素材库索引]]",
            "> - 爆款总库：[[数据-爆款口播逐字稿与黄金钩子库]]",
            "",
            f"# {display_title}",
            "",
            f"- **创作者**：`{display_author}`",
            f"- **平台**：{platform_name}",
            f"- **数据表现**：👍 **{ContentAnalyzer.format_count(likes)}** 赞 · 🔁 **{ContentAnalyzer.format_count(shares)}** 分享 · 💬 **{ContentAnalyzer.format_count(comments)}** 评论",
            f"- **原视频链接**：[点击直达播放]({url})" if url else "- **原视频链接**：无",
            f"- **分类主题**：`{topic}`",
            "",
            "---",
            "",
            "## 🎯 前15秒黄金反差钩子",
            "",
            "> [!TIP] 开头反差与受众注意力抓手",
            f"> *\"{hook}\"*",
            "",
            "---",
            "",
            "## 🎙️ 完整口播逐字稿 / 正文",
            "",
        ]
        md_lines.extend(self._fenced_text(transcript))
        md_lines.append("")

        # 如果包含时间戳片段
        segments = item.get("segments")
        if segments and isinstance(segments, list):
            md_lines.extend([
                "---",
                "",
                "## ⏱️ 时间戳分段台词",
                "",
                "| 时间段 | 口播台词 |",
                "|---|---|",
            ])
            for seg in segments:
                t_from = seg.get("from", "")
                t_to = seg.get("to", "")
                t_text = self._single_line(seg.get("text", "")).replace("|", "-")
                md_lines.append(f"| `{t_from} ~ {t_to}` | {t_text} |")
            md_lines.append("")

        self._atomic_write_text(target_file, "\n".join(md_lines))

        return target_file

    @staticmethod
    def _entry_key(item: Dict[str, Any]) -> str:
        """条目去重键：优先平台+内容 id，其次原文链接，最后标题+作者。"""
        cid = str(item.get("id") or "").strip()
        if cid and not cid.lower().startswith("http"):
            platform = str(item.get("platform") or "unknown").strip().lower()
            return f"id:{platform}:{cid}"
        url = str(item.get("url") or "").strip()
        if url:
            return f"url:{url}"
        platform = str(item.get("platform") or "unknown").strip().lower()
        return f"title:{platform}:{item.get('title', '')}|author:{item.get('author', '')}"

    def _load_aggregate_entries(self, target_file: Path) -> Dict[str, Dict[str, Any]]:
        """
        读取已有汇总大库的条目块，返回 {key: {"block": 原始渲染块, "likes": int}}。
        兼容旧版无标记文件：无键标记时从链接行提取，再退化为内容哈希。
        """
        entries: Dict[str, Dict[str, Any]] = {}
        if not target_file.exists():
            return entries
        try:
            content = target_file.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise RuntimeError(f"无法读取旧汇总库，已停止写入以保护历史数据: {target_file}") from exc

        # 每个条目以 "## 序号. 【..赞" 行开始，前瞻切分以保留标题行
        blocks = re.split(r"(?m)(?=^## \d+\. 【)", content)
        for block in blocks[1:]:
            block = block.rstrip()
            block = re.sub(r"\n---\s*$", "", block).rstrip()

            mb = re.search(r"<!-- d2o-key-b64: ([A-Za-z0-9_=-]+) -->", block)
            m = re.search(r"<!-- d2o-key: (.*?) -->", block)
            if mb:
                try:
                    key = base64.urlsafe_b64decode(mb.group(1).encode("ascii")).decode("utf-8")
                except Exception:
                    key = "legacy:" + hashlib.md5(block[:160].encode("utf-8")).hexdigest()
            elif m:
                key = m.group(1).strip()
            else:
                mu = re.search(r"\]\((https?://[^)\s]+)\)", block)
                if mu:
                    key = f"url:{mu.group(1)}"
                else:
                    key = "legacy:" + hashlib.md5(block[:160].encode("utf-8")).hexdigest()

            ml = re.search(r"<!-- d2o-likes: (\d+) -->", block)
            if ml:
                likes = int(ml.group(1))
            else:
                mh = re.search(r"【([\d.,]+\s*[万亿]?)赞", block)
                likes = ContentAnalyzer.parse_count(mh.group(1)) if mh else 0

            mu = re.search(r"\]\((https?://[^)\s]+)\)", block)
            entries[key] = {
                "block": block,
                "likes": likes,
                "url": mu.group(1) if mu else "",
            }
        declared_size = re.search(r"sample_size:\s*(\d+)", content)
        if declared_size and int(declared_size.group(1)) > 0 and not entries:
            raise RuntimeError(
                f"旧汇总库声明含有条目但无法解析，已停止写入: {target_file}"
            )
        return entries

    def _aggregate_state_path(self) -> Path:
        return self.output_dir / ".douyin-to-obsidian" / "aggregate-state.json"

    def _load_aggregate_state(self, target_file: Path) -> Dict[str, Dict[str, Any]]:
        """读取结构化真源；首次升级时只从旧 Markdown 迁移一次。"""
        state_file = self._aggregate_state_path()
        if not state_file.exists():
            return self._load_aggregate_entries(target_file)
        try:
            state = json.loads(state_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"汇总状态文件损坏，已停止写入以保护历史数据: {state_file}") from exc
        if state.get("schema_version") != 1 or not isinstance(state.get("entries"), dict):
            raise RuntimeError(f"不支持的汇总状态文件格式: {state_file}")
        return state["entries"]

    def _save_aggregate_state(self, entries: Dict[str, Dict[str, Any]]) -> None:
        state = {
            "schema_version": 1,
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "entries": entries,
        }
        payload = json.dumps(state, ensure_ascii=False, indent=2, default=str) + "\n"
        self._atomic_write_text(self._aggregate_state_path(), payload)

    def _render_aggregate_entry(self, rank: int, item: Dict[str, Any]) -> List[str]:
        """渲染单条汇总条目（含去重与排序用的隐藏标记）"""
        title = self._single_line(item.get("title") or "无标题")
        author = self._single_line(item.get("author") or "未知")
        platform_code = item.get("platform", "")
        p_name = "抖音" if platform_code == "douyin" else ("小红书" if platform_code == "xiaohongshu" else platform_code)
        likes_n = ContentAnalyzer.parse_count(item.get("liked_count", 0))
        likes = ContentAnalyzer.format_count(likes_n)
        shares = ContentAnalyzer.format_count(ContentAnalyzer.parse_count(item.get("share_count", 0)))
        url = item.get("url") or ""
        hook = self._single_line(item.get("hook_15s") or "（无明显钩子台词）")
        transcript = str(item.get("transcript") or item.get("desc") or "（无文本内容）")
        topic = self._single_line(item.get("topic") or ContentAnalyzer.categorize(title, transcript))

        encoded_key = base64.urlsafe_b64encode(
            self._entry_key(item).encode("utf-8")
        ).decode("ascii")

        lines = [
            f"## {rank}. 【{likes}赞 · {p_name}】{title[:40]}",
            f"<!-- d2o-key-b64: {encoded_key} -->",
            f"<!-- d2o-likes: {likes_n} -->",
            "",
            f"- **创作者**：`{author}`  ",
            f"- **互动数据**：👍 **{likes}** 赞 · 🔁 **{shares}** 转发  ",
            f"- **核心分类**：`{topic}`  ",
        ]
        if url:
            lines.append(f"- **链接**：[原视频/笔记直达]({url})  ")
        lines.extend([
            "- **🎯 前15秒黄金反差钩子**：",
            f"  > *\"{hook}\"*",
            "",
            "- **🎙️ 完整口播逐字稿**：",
            "<details>",
            f"<summary>展开查看 {len(transcript)} 字口播全文</summary>",
            "",
        ])
        lines.extend(self._fenced_text(transcript))
        lines.extend(["</details>", "", "---", ""])
        return lines

    def export_aggregate_library(
        self,
        items: List[Dict[str, Any]],
        filename: str = "数据-爆款口播逐字稿与黄金钩子库.md",
    ) -> Path:
        """
        生成全量汇总大库（合并式追加）：
        - 读取已有大库并与本次条目按键去重合并（本次数据覆盖旧数据）
        - 兼容旧版无标记条目，保留并重排名
        - 全量条目按点赞降序重新排序
        """
        today = time.strftime("%Y-%m-%d")
        target_file = self.output_dir / filename

        # 合并已有条目与本次条目；同链接的旧版条目视为重复，避免迁移期出现双份
        merged: Dict[str, Dict[str, Any]] = self._load_aggregate_state(target_file)
        for item in items:
            url = str(item.get("url") or "").strip()
            new_key = self._entry_key(item)
            cid = str(item.get("id") or "").strip()
            platform = str(item.get("platform") or "unknown").strip().lower()
            for existing_key, existing in list(merged.items()):
                existing_item = existing.get("item") or {}
                existing_url = str(existing.get("url") or existing_item.get("url") or "").strip()
                existing_cid = str(existing_item.get("id") or "").strip()
                existing_platform = str(existing_item.get("platform") or "unknown").strip().lower()
                if (
                    existing_key == new_key
                    or (url and existing_url == url)
                    or (cid and existing_cid == cid and existing_platform == platform)
                ):
                    merged.pop(existing_key, None)
            merged[new_key] = {
                "item": item,
                "likes": ContentAnalyzer.parse_count(item.get("liked_count", 0)),
                "url": url,
            }

        sorted_entries = sorted(
            merged.values(),
            key=lambda e: e["likes"],
            reverse=True,
        )
        self._save_aggregate_state(merged)

        # 保留首次创建日期
        created_at = today
        if target_file.exists():
            m = re.search(r"created_at: '(\d{4}-\d{2}-\d{2})'", target_file.read_text(encoding="utf-8"))
            if m:
                created_at = m.group(1)

        md_lines = [
            "---",
            "type: voiceover-scripts-library",
            "source: 抖音 / 小红书视频 Whisper 本地 ASR 高精转写",
            f"sample_size: {len(sorted_entries)} 篇精选作品",
            f"created_at: '{created_at}'",
            f"updated_at: '{today}'",
            "tags:",
            "  - 语料/口播文案",
            "  - 脚本/黄金钩子",
            "  - 爆款拆解/对标分析",
            "---",
            "",
            "> [!NOTE] 知识库导航",
            "> - 返回全局索引：[[00_素材库索引]]",
            "",
            "# 爆款社媒口播逐字稿与前15秒黄金钩子全量母库",
            "",
            f"> **统计周期**：截至 {today}  ",
            f"> **样本规模**：精选并已完成 ASR 转录的 **{len(sorted_entries)}** 篇高赞内容。  ",
            "> **说明**：所有口播均为 Whisper 原音逐字转写，真实还原开篇节奏、黄金钩子与语言风格。",
            "",
            "---",
            "",
        ]

        for rank, entry in enumerate(sorted_entries, 1):
            if entry.get("item") is not None:
                md_lines.extend(self._render_aggregate_entry(rank, entry["item"]))
            else:
                block = re.sub(r"(?m)^## \d+\. ", f"## {rank}. ", entry["block"], count=1)
                md_lines.extend([block, "", "---", ""])

        self._atomic_write_text(target_file, "\n".join(md_lines))

        return target_file

    def export_creator_dossier(
        self,
        items: List[Dict[str, Any]],
        creator_name: str,
        filename: Optional[str] = None,
    ) -> Path:
        """
        生成针对特定博主的对标深度画像与逐字稿库
        """
        today = time.strftime("%Y-%m-%d")
        display_creator = self._single_line(creator_name)
        fname = filename or f"对标账号-{self._sanitize_filename(display_creator)}-话题与口播看板.md"
        target_file = self.output_dir / fname

        total_likes = sum(ContentAnalyzer.parse_count(x.get("liked_count", 0)) for x in items)
        avg_likes = total_likes // max(1, len(items))

        sorted_items = sorted(
            items,
            key=lambda x: ContentAnalyzer.parse_count(x.get("liked_count", 0)),
            reverse=True,
        )

        md_lines = [
            "---",
            "type: creator-dossier",
            f"creator: {self._yaml_scalar(creator_name)}",
            f"sample_size: {len(items)} 篇作品",
            f"created_at: '{today}'",
            "tags:",
            f"  - {self._yaml_scalar(f'对标账号/{display_creator}')}",
            "  - 创作者调研",
            "  - 语料/逐字稿",
            "---",
            "",
            "> [!NOTE] 知识库导航",
            "> - 返回索引：[[00_素材库索引]]",
            "> - 爆款总库：[[数据-爆款口播逐字稿与黄金钩子库]]",
            "",
            f"# 对标博主调研画像：{display_creator}",
            "",
            f"> **样本规模**：共采集并分析 **{len(items)}** 期作品  ",
            f"> **平均点赞**：**{ContentAnalyzer.format_count(avg_likes)}** 赞  ",
            f"> **总曝光互动**：**{ContentAnalyzer.format_count(total_likes)}** 赞",
            "",
            "---",
            "",
            "## 📊 视频与口播逐字稿列表",
            "",
        ]

        for idx, item in enumerate(sorted_items, 1):
            title = self._single_line(item.get("title") or "无标题")
            likes = ContentAnalyzer.format_count(ContentAnalyzer.parse_count(item.get("liked_count", 0)))
            hook = self._single_line(item.get("hook_15s") or "—")
            transcript = str(item.get("transcript") or item.get("desc") or "—")
            url = item.get("url") or ""

            md_lines.extend([
                f"### {idx}. 【{likes}赞】{title[:35]}",
                f"- **前15s钩子**：> *\"{hook}\"*",
            ])
            if url:
                md_lines.append(f"- **链接**：[原视频直达]({url})")
            md_lines.extend([
                "- **完整口播**：",
            ])
            md_lines.extend(self._fenced_text(transcript))
            md_lines.append("")

        self._atomic_write_text(target_file, "\n".join(md_lines))

        return target_file

    def update_index_hub(self, filename: str = "00_素材库索引.md") -> Path:
        """
        生成或更新 Obsidian 素材库总览与双链索引
        """
        today = time.strftime("%Y-%m-%d")
        target_file = self.output_dir / filename

        md_lines = [
            "---",
            "type: material-hub-index",
            "channel: 短视频口播文案库",
            f"updated_at: '{today}'",
            "tags:",
            "  - 知识库/索引",
            "  - 口播文案",
            "  - 选题库",
            "---",
            "",
            "# 🧭 短视频口播文案与爆款素材库全局索引",
            "",
            f"> 最后更新时间：{today}  ",
            "> 本索引由 `douyin-to-obsidian` 自动维护，整合爆款问题母题雷达、抖音/小红书口播、黄金钩子及对标博主资产。",
            "",
            "---",
            "",
            "## 📚 核心知识资产",
            "",
            "- 📡 **Douyin Viral Topic Radar**：[[数据-抖音爆款选题雷达]]",
            "- 🎙️ **爆款全量口播总库**：[[数据-爆款口播逐字稿与黄金钩子库]]",
            "- 📁 **单篇精细化口播笔记**：查看 `单篇口播笔记/` 目录",
            "",
            "## 🔍 常用检索方式 (Obsidian Dataview 示例)",
            "",
            "```dataview",
            "TABLE author AS 创作者, topic AS 核心主题, likes AS 点赞数",
            'FROM #语料/口播文案',
            "SORT likes DESC",
            "LIMIT 15",
            "```",
            "",
            "---",
            "> 💡 *提示：本知识库由开源工具 [douyin-to-obsidian](https://github.com/naughly-cat/douyin-to-obsidian) 驱动生成。*",
        ]

        self._atomic_write_text(target_file, "\n".join(md_lines))

        return target_file
