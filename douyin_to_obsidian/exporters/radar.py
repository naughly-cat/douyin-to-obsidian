# -*- coding: utf-8 -*-
"""Douyin Viral Topic Radar 的 Obsidian / JSON 导出。"""

import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List


class RadarExporter:
    """将结构化雷达结果导出为 JSON 真源 + Obsidian Markdown 看板。"""

    def __init__(self, output_dir: Path):
        self.output_dir = Path(output_dir).expanduser().resolve()
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _atomic_write(path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_name = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=path.parent,
                prefix=f".{path.name}.",
                suffix=".tmp",
                delete=False,
            ) as tmp:
                tmp.write(text)
                tmp.flush()
                os.fsync(tmp.fileno())
                tmp_name = tmp.name
            os.replace(tmp_name, path)
        finally:
            if tmp_name and os.path.exists(tmp_name):
                os.unlink(tmp_name)

    @staticmethod
    def _fmt(value: Any, digits: int = 1) -> str:
        if value is None:
            return "N/A"
        if isinstance(value, float):
            return f"{value:.{digits}f}"
        return str(value)

    @staticmethod
    def _safe(text: Any) -> str:
        return str(text or "").replace("|", "｜").replace("
", " ").strip()

    def export(
        self,
        report: Dict[str, Any],
        markdown_filename: str = "数据-抖音爆款选题雷达.md",
        state_filename: str = ".douyin-to-obsidian/viral-topic-radar.json",
    ) -> Dict[str, Path]:
        state_path = self.output_dir / state_filename
        md_path = self.output_dir / markdown_filename

        self._atomic_write(
            state_path,
            json.dumps(report, ensure_ascii=False, indent=2, default=str) + "
",
        )
        self._atomic_write(md_path, self._render_markdown(report))
        return {"json": state_path, "markdown": md_path}

    def _render_markdown(self, report: Dict[str, Any]) -> str:
        today = time.strftime("%Y-%m-%d")
        topics = list(report.get("topics") or [])
        lines: List[str] = [
            "---",
            "type: douyin-viral-topic-radar",
            f"generated_at: '{self._safe(report.get('generated_at'))}'",
            f"window_days: {report.get('window_days', 30)}",
            f"sample_size: {report.get('sample_size', 0)}",
            f"comment_sample_size: {report.get('comment_sample_size', 0)}",
            f"topic_count: {len(topics)}",
            "tags:",
            "  - 选题/抖音爆款雷达",
            "  - 爆款拆解/母题",
            "  - 数据/选题验证",
            "---",
            "",
            "# 📡 Douyin Viral Topic Radar",
            "",
            f"> 更新时间：{today}  ",
            f"> 观察窗口：最近 **{report.get('window_days', 30)} 天**；短周期：**{report.get('recent_days', 7)} 天**  ",
            f"> 视频样本：**{report.get('sample_size', 0)}**；评论样本：**{report.get('comment_sample_size', 0)}**  ",
            "> 核心原则：**不是找单条高赞视频，而是找被多个独立账号反复验证、且相对作者自身基线异常的“问题母题”。**",
            "",
            "> [!IMPORTANT] Market Score 只衡量“市场验证强度”，不是最终立项分。最终还要进入项目自身的 Fit Score（问题共鸣、结果可见、制作成本、AI 必要性、本人可信度、收藏价值）。",
            "",
            "## 🔥 母题榜",
            "",
            "| 排名 | Market Score | 问题母题 | 独立作者 | 样本 | 中位爆款倍率 | 7日/窗口 | 评论需求率 | 状态 |",
            "|---:|---:|---|---:|---:|---:|---:|---:|---|",
        ]

        for rank, topic in enumerate(topics, 1):
            ratio = topic.get("demand_ratio")
            ratio_text = "N/A" if ratio is None else f"{ratio * 100:.0f}%"
            recent = f"{topic.get('recent_count', 0)}/{topic.get('window_count', 0)}"
            mult = topic.get("median_viral_multiplier")
            mult_text = "N/A" if mult is None else f"{mult:.1f}×"
            review = "⚠️ 待语义复核" if topic.get("agent_semantic_review_required") else topic.get("confidence", "")
            lines.append(
                f"| {rank} | **{topic.get('market_score', 0):.1f}** | "
                f"{self._safe(topic.get('mother_topic'))} | {topic.get('unique_authors', 0)} | "
                f"{topic.get('sample_count', 0)} | {mult_text} | {recent} | {ratio_text} | {review} |"
            )

        if not topics:
            lines.extend([
                "",
                "> [!WARNING] 当前样本中没有满足跨账号门槛的母题。优先扩大关键词、创作者和评论采样，不要降低成“看到一条爆款就立项”。",
            ])

        lines.extend([
            "",
            "---",
            "",
            "## 🧭 如何读这个榜",
            "",
            "- **跨账号复现**：同一问题被多个独立作者做出来，比单条绝对高赞更可靠。",
            "- **爆款倍率**：视频点赞 ÷ 该作者其他已采样作品点赞中位数；至少需要足够作者样本才计算。",
            "- **近期密度**：同一母题是否在最近 7 天继续出现，而不是几个月前偶发。",
            "- **高意图互动**：收藏、分享、评论相对点赞的强度。",
            "- **评论需求率**：已抓评论里“怎么做 / 求方法 / 能不能用于 X”之类高意图问题占比。",
            "- **低粉突破**：只有抓到可靠粉丝数时才参与评分；没有数据不会猜。",
            "",
            "---",
            "",
        ])

        for rank, topic in enumerate(topics, 1):
            lines.extend([
                f"## {rank}. {self._safe(topic.get('mother_topic'))}",
                "",
                f"- **Market Score**：**{topic.get('market_score', 0):.1f}/100**",
                f"- **独立作者**：{topic.get('unique_authors', 0)}",
                f"- **样本数**：{topic.get('sample_count', 0)}",
                f"- **中位爆款倍率**：{self._fmt(topic.get('median_viral_multiplier'))}×" if topic.get("median_viral_multiplier") is not None else "- **中位爆款倍率**：N/A（作者基线样本不足）",
                f"- **最高爆款倍率**：{self._fmt(topic.get('max_viral_multiplier'))}×" if topic.get("max_viral_multiplier") is not None else "- **最高爆款倍率**：N/A",
                f"- **评论需求**：{topic.get('demand_comment_count', 0)}/{topic.get('loaded_comment_count', 0)}",
                f"- **低粉突破样本**：{topic.get('low_follower_breakouts', 0)}",
                f"- **置信状态**：{self._safe(topic.get('confidence'))}",
            ])

            if topic.get("agent_semantic_review_required"):
                lines.extend([
                    "",
                    "> [!WARNING] 该簇没有命中稳定的问题标签。请由 Agent 阅读证据视频的标题、钩子与评论后，判断是否应该与别的母题合并，并重写成“普通人的具体问题”，不要直接拿最高赞标题当母题。",
                ])

            lines.extend([
                "",
                "### 评分拆解",
                "",
                "| 维度 | 得分 | 权重 | 数据可用 |",
                "|---|---:|---:|---|",
            ])
            for key, label in [
                ("cross_account_reproduction", "跨账号爆款复现"),
                ("relative_author_anomaly", "相对作者基线异常"),
                ("recency_density", "近 7/30 天热度"),
                ("high_intent_engagement", "高意图互动"),
                ("comment_demand_density", "评论需求密度"),
                ("low_follower_breakthrough", "低粉账号突破"),
            ]:
                part = (topic.get("score_breakdown") or {}).get(key) or {}
                score = "N/A" if part.get("score") is None else f"{part.get('score'):.1f}"
                lines.append(
                    f"| {label} | {score} | {part.get('weight', 0)} | {'是' if part.get('available') else '否'} |"
                )

            lines.extend(["", "### 爆款证据", ""])
            for ev in topic.get("evidence") or []:
                mult = ev.get("viral_multiplier")
                mult_text = "基线不足" if mult is None else f"{mult:.1f}×基线"
                url = ev.get("url") or ""
                title = self._safe(ev.get("title"))
                link = f"[{title}]({url})" if url else title
                lines.append(
                    f"- **{self._safe(ev.get('author'))}** · {ev.get('likes', 0)}赞 · {mult_text} · {link}"
                )

            demands = topic.get("demand_questions") or []
            lines.extend(["", "### 评论区未满足需求", ""])
            if demands:
                for row in demands:
                    likes = row.get("like_count", 0)
                    replies = row.get("reply_count", 0)
                    lines.append(
                        f"- “{self._safe(row.get('content'))}” （{likes}赞 / {replies}回复）"
                    )
            else:
                lines.append("- 当前没有加载到可识别的高意图评论；优先补抓评论再判断需求树。")

            lines.extend([
                "",
                "### Agent 二次复核",
                "",
                "1. 去掉工具名后，这些视频是不是在解决同一个普通人问题？",
                "2. 有没有应该合并的近义母题，或被错误合并的不同需求？",
                "3. 评论区还能裂变出哪些更具体的问题？",
                "4. 只保留“市场已验证”的母题，再进入项目 Fit Score，不直接照搬原视频标题。",
                "",
                "---",
                "",
            ])

        return "
".join(lines)
