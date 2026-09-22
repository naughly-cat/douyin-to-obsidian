# -*- coding: utf-8 -*-
"""
内容分析器 (Content Analyzer)
==============================
- 黄金15秒开头钩子智能切分与反差提取
- 图文笔记核心钩子提炼
- 播放/点赞/互动指标解析与格式化
- 话题与心智模型智能分类打标
"""

import re
from typing import Any, Dict, List, Optional


class ContentAnalyzer:
    """文案与受众心理特征分析器"""

    # 预设主题分类规则（可扩展）
    CATEGORY_RULES = {
        "🛠️ AI工具实测与工作流": [
            "deepseek", "chatgpt", "gpt", "claude", "cursor", "gemini",
            "agent", "工作流", "提示词", "prompt", "开发", "编程",
            "实测", "工具", "模型", "代码", "workflow"
        ],
        "🧠 认知重塑与去魅思考": [
            "去魅", "骗局", "神话", "炒作", "被替代", "淘汰", "真相",
            "本质", "幻觉", "降温", "吹牛", "底层逻辑", "反差", "闭坑"
        ],
        "💼 职场生存与商业变现": [
            "赚钱", "商业", "副业", "变现", "裁员", "失业", "老板",
            "公司", "薪资", "产业", "风口", "创业", "经济", "月入"
        ],
        "🚀 个人成长与心智模型": [
            "学习", "思考", "普通人", "习惯", "成长", "读书", "认知",
            "注意力", "时间", "信息差", "思维", "自律", "自学", "日记"
        ],
        "🌐 科技趋势与行业洞察": [
            "硅谷", "奥特曼", "马斯克", "英伟达", "算力", "开源",
            "闭源", "趋势", "未来", "投资", "发布会"
        ],
    }

    @staticmethod
    def parse_count(val: Any) -> int:
        """解析点赞、收藏等互动数字，兼容 '1.2万'、'500'、数字类型"""
        if val is None:
            return 0
        try:
            return int(val)
        except (ValueError, TypeError):
            if isinstance(val, str) and "万" in val:
                try:
                    return int(float(val.replace("万", "").strip()) * 10000)
                except Exception:
                    return 0
            return 0

    @staticmethod
    def format_count(n: int) -> str:
        """格式化数字为阅读友好的计数表达"""
        if n >= 10000:
            return f"{n / 10000:.1f}万"
        return str(n)

    @classmethod
    def extract_hook(
        cls,
        transcript: str,
        segments: Optional[List[Dict[str, Any]]] = None,
        max_chars: int = 120,
    ) -> str:
        """
        提取前15秒黄金钩子：
        1. 优先根据 ASR 时间戳提取 <= 15.0 秒的台词
        2. 若无时间戳，则截取前两句或前 max_chars 字
        """
        if segments:
            hook_texts = []
            for seg in segments:
                t_from = seg.get("from", "00:00:00,000")
                txt = seg.get("text", "").strip()
                try:
                    # 兼容 "00:00:03,120" 或 "3.12s" 格式
                    if "s" in str(t_from):
                        sec = float(str(t_from).replace("s", ""))
                    else:
                        parts = str(t_from).replace(",", ".").split(":")
                        sec = (
                            float(parts[0]) * 3600
                            + float(parts[1]) * 60
                            + float(parts[2])
                        )
                except Exception:
                    sec = 0.0

                if sec <= 15.0 and txt:
                    hook_texts.append(txt)

            if hook_texts:
                return " ".join(hook_texts).strip()

        # 基于标点断句提取核心开头
        if not transcript:
            return "（暂无台词内容）"

        clean_text = transcript.strip().replace("\n", " ")
        sentences = re.split(r"[。！？!?…]+", clean_text)
        hook = ""
        for s in sentences:
            s = s.strip()
            if not s:
                continue
            if len(hook) + len(s) <= max_chars:
                hook += s + "。 "
            else:
                if not hook:
                    hook = s[:max_chars]
                break

        return hook.strip() or clean_text[:max_chars]

    @classmethod
    def categorize(cls, title: str, text: str) -> str:
        """基于关键词特征进行短视频/文案主题归类"""
        combined = f"{title} {text}".lower()
        for cat, keywords in cls.CATEGORY_RULES.items():
            if any(k in combined for k in keywords):
                return cat
        return "📌 综合探索与随笔"

    @staticmethod
    def clean_title(title: str) -> str:
        """去除多余话题标签（#xxx）与特殊换行字符"""
        if not title:
            return "无标题作品"
        t = re.sub(r"#\S+", "", title).strip()
        t = t.replace("\n", " ").replace("\r", " ").replace("|", "-")
        return t.strip() if t.strip() else title[:30]
