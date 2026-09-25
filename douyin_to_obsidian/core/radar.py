# -*- coding: utf-8 -*-
"""
Douyin Viral Topic Radar
========================
把“高赞视频列表”升级成“爆款问题母题雷达”。

本模块只做可复核的定量层：
- 作者近期样本基线与异常倍率
- 跨账号复现
- 近 7/30 天时间密度
- 收藏/分享/评论等高意图互动
- 评论区问题/求方法需求
- 可用时识别低粉突破

母题聚类采用轻量规则 + 字符 n-gram，相近但措辞不同的中文主题仍建议由 Agent
读取结构化结果后做二次语义合并。没有数据的指标会标记 unavailable，不会伪造。
"""

from __future__ import annotations

import math
import re
import statistics
import time
from collections import Counter, defaultdict
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

from .analyzer import ContentAnalyzer


class ViralTopicRadar:
    """从 MediaCrawler 规范化记录构建抖音爆款选题雷达。"""

    DEMAND_PATTERNS = [
        r"怎么", r"如何", r"求(教程|方法|提示词|链接|模板|分享|地址)?",
        r"能不能", r"可以.*吗", r"有没有", r"哪里", r"哪个", r"多少",
        r"收费", r"免费", r"教程", r"提示词", r"模板", r"方法",
        r"适合", r"支持", r"安全吗", r"隐私", r"公司文件", r"扫描件",
        r"论文", r"合同", r"财报", r"能用在", r"怎么弄", r"怎么做",
    ]

    TOOL_PATTERN = re.compile(
        r"\b(chatgpt|gpt[-\s]?\d*|claude|gemini|deepseek|kimi|豆包|通义|千问|"
        r"cursor|copilot|manus|扣子|coze|notebooklm|obsidian)\b",
        re.I,
    )

    CANONICAL_RULES: Sequence[Tuple[str, str, Sequence[str]]] = [
        (
            "long_document",
            "长资料看不完：让 AI 先读",
            ["pdf", "报告", "论文", "合同", "文档", "资料", "长文", "财报", "文件"],
        ),
        (
            "meeting",
            "开会记不住：让 AI 整理会议",
            ["会议", "开会", "会议纪要", "会议记录", "录音", "待办"],
        ),
        (
            "collection",
            "收藏太多找不到：让 AI 整理素材",
            ["收藏夹", "收藏", "素材库", "知识库", "截图", "笔记", "找不到", "整理素材"],
        ),
        (
            "writing",
            "写东西慢或 AI 味重：让 AI 辅助表达",
            ["文案", "写作", "文章", "口播", "邮件", "周报", "改写", "ai味", "ai 味"],
        ),
        (
            "ppt",
            "PPT 太费时间：让 AI 先做第一版",
            ["ppt", "幻灯片", "演示文稿"],
        ),
        (
            "learning",
            "陌生内容学不动：让 AI 先解释",
            ["学习", "自学", "教程", "看不懂", "听不懂", "课程", "读书", "知识点", "入门"],
        ),
        (
            "coding",
            "不会写代码：让 AI 先做可运行版本",
            ["代码", "编程", "写代码", "程序", "开发", "vibe coding", "终端", "报错"],
        ),
        (
            "planning",
            "计划太乱：让 AI 帮安排",
            ["计划", "日程", "安排", "时间管理", "复盘", "待办", "todo"],
        ),
        (
            "emotion",
            "情绪和困惑：让 AI 陪聊或分析",
            ["情绪", "心理", "焦虑", "咨询", "内耗", "倾诉", "关系"],
        ),
        (
            "travel",
            "旅行规划麻烦：让 AI 排路线",
            ["旅行", "旅游", "行程", "攻略", "路线", "酒店", "景点"],
        ),
        (
            "image_video",
            "不会做视觉内容：让 AI 生成图片或视频",
            ["ai绘画", "ai 绘画", "图片生成", "视频生成", "生图", "文生图", "文生视频", "动画"],
        ),
    ]

    GENERIC_STOP_PHRASES = [
        "今天给大家", "今天分享", "大家好", "你一定要", "一定要知道",
        "真的太强了", "太牛了", "建议收藏", "记得点赞", "关注我",
        "普通人", "这个东西", "这个工具", "人工智能",
    ]

    def __init__(
        self,
        window_days: int = 30,
        recent_days: int = 7,
        min_authors: int = 2,
        now_ts: Optional[float] = None,
    ):
        if window_days <= 0 or recent_days <= 0:
            raise ValueError("window_days/recent_days 必须为正整数")
        self.window_days = int(window_days)
        self.recent_days = int(recent_days)
        self.min_authors = max(1, int(min_authors))
        self.now_ts = float(now_ts or time.time())

    @staticmethod
    def _to_timestamp(value: Any) -> Optional[float]:
        if value in (None, "", 0, "0"):
            return None
        try:
            ts = float(value)
        except (TypeError, ValueError):
            return None
        # 毫秒时间戳
        if ts > 10_000_000_000:
            ts /= 1000.0
        # 过小值大概率不是 Unix 时间戳
        if ts < 946684800:  # 2000-01-01
            return None
        return ts

    def _age_days(self, value: Any) -> Optional[float]:
        ts = self._to_timestamp(value)
        if ts is None:
            return None
        return max(0.0, (self.now_ts - ts) / 86400.0)

    @staticmethod
    def _median(values: Iterable[float]) -> float:
        vals = [float(x) for x in values]
        return float(statistics.median(vals)) if vals else 0.0

    @staticmethod
    def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
        return max(lo, min(hi, v))

    @classmethod
    def _canonical_tags(cls, text: str) -> List[str]:
        low = text.lower()
        tags: List[str] = []
        for key, _label, words in cls.CANONICAL_RULES:
            if any(word.lower() in low for word in words):
                tags.append(key)
        return tags

    @classmethod
    def _label_for_tags(cls, tags: Sequence[str], fallback: str) -> str:
        if tags:
            labels = {key: label for key, label, _ in cls.CANONICAL_RULES}
            # 单母题时用完整人类可读标签；多标签时保留两个核心维度
            if len(tags) == 1:
                return labels.get(tags[0], fallback)
            short = []
            short_map = {
                "long_document": "长资料",
                "meeting": "会议",
                "collection": "收藏整理",
                "writing": "写作表达",
                "ppt": "PPT",
                "learning": "学习理解",
                "coding": "AI编程",
                "planning": "计划复盘",
                "emotion": "情绪",
                "travel": "旅行规划",
                "image_video": "视觉生成",
            }
            for tag in tags[:2]:
                if tag in short_map:
                    short.append(short_map[tag])
            if short:
                return " + ".join(short) + "：普通人的具体问题如何交给 AI"
        return fallback

    @classmethod
    def _normalized_topic_text(cls, item: Dict[str, Any]) -> str:
        parts = [
            str(item.get("title") or ""),
            str(item.get("hook_15s") or ""),
            str(item.get("desc") or "")[:160],
            str(item.get("transcript") or "")[:180],
        ]
        text = " ".join(parts).lower()
        text = cls.TOOL_PATTERN.sub(" ai ", text)
        text = re.sub(r"#\S+", " ", text)
        for phrase in cls.GENERIC_STOP_PHRASES:
            text = text.replace(phrase, " ")
        # 统一一部分常见近义词，提升跨表达聚类
        replacements = [
            (r"(pdf|报告|论文|合同|财报|文档|长文|文件)", " 长资料 "),
            (r"(收藏夹|收藏|素材库|知识库|截图)", " 收藏整理 "),
            (r"(会议纪要|会议记录|开会|会议)", " 会议 "),
            (r"(文章|口播|文案|写作|邮件|周报)", " 写作 "),
            (r"(幻灯片|ppt)", " ppt "),
            (r"(写代码|代码|编程|开发)", " 编程 "),
            (r"(旅游|旅行|行程|攻略)", " 旅行 "),
        ]
        for pattern, repl in replacements:
            text = re.sub(pattern, repl, text, flags=re.I)
        text = re.sub(r"[^0-9a-z\u4e00-\u9fff]+", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def _ngrams(text: str, n: int = 2) -> Set[str]:
        compact = re.sub(r"\s+", "", text)
        if len(compact) < n:
            return {compact} if compact else set()
        return {compact[i:i + n] for i in range(len(compact) - n + 1)}

    @classmethod
    def _topic_signature(cls, item: Dict[str, Any]) -> Dict[str, Any]:
        text = cls._normalized_topic_text(item)
        tags = cls._canonical_tags(text)
        # 标题更能代表“题”而不是全文细节
        title = ContentAnalyzer.clean_title(str(item.get("title") or ""))
        fallback = title[:28] or "未命名母题"
        return {
            "text": text,
            "tags": tags,
            "ngrams": cls._ngrams(text[:140]),
            "label": cls._label_for_tags(tags, fallback),
        }

    @staticmethod
    def _similarity(a: Dict[str, Any], b: Dict[str, Any]) -> float:
        tags_a, tags_b = set(a["tags"]), set(b["tags"])
        grams_a, grams_b = a["ngrams"], b["ngrams"]
        tag_overlap = len(tags_a & tags_b)
        union = grams_a | grams_b
        jaccard = (len(grams_a & grams_b) / len(union)) if union else 0.0

        # 同一问题标签是强信号；没有标签时要求更高文本相似度
        if tag_overlap >= 1:
            return min(1.0, 0.62 + 0.38 * jaccard)
        return jaccard

    @classmethod
    def _is_demand_comment(cls, text: str) -> bool:
        value = str(text or "").strip()
        if not value:
            return False
        if "?" in value or "？" in value:
            return True
        return any(re.search(p, value, re.I) for p in cls.DEMAND_PATTERNS)

    @staticmethod
    def _author_key(item: Dict[str, Any]) -> str:
        author_id = str(item.get("author_id") or "").strip()
        if author_id:
            return f"id:{author_id}"
        return f"name:{str(item.get('author') or '未知创作者').strip()}"

    @staticmethod
    def _engagement_rate(item: Dict[str, Any]) -> float:
        likes = max(1, ContentAnalyzer.parse_count(item.get("liked_count", 0)))
        shares = ContentAnalyzer.parse_count(item.get("share_count", 0))
        collects = ContentAnalyzer.parse_count(item.get("collected_count", 0))
        comments = ContentAnalyzer.parse_count(item.get("comment_count", 0))
        # 分享权重略高于收藏，评论只算半权重，避免评论量大但意图弱的内容虚高
        return (2.0 * shares + 1.5 * collects + 0.5 * comments) / likes

    @classmethod
    def _attach_creator_profiles(
        cls,
        items: List[Dict[str, Any]],
        creator_profiles: Optional[Dict[str, Dict[str, Any]]],
    ) -> None:
        profiles = creator_profiles or {}
        for item in items:
            if ContentAnalyzer.parse_count(item.get("follower_count", 0)) > 0:
                continue
            author_id = str(item.get("author_id") or "").strip()
            author = str(item.get("author") or "").strip()
            profile = None
            if author_id:
                profile = profiles.get(f"id:{author_id}")
            if profile is None and author:
                profile = profiles.get(f"name:{author}")
            if profile:
                item["follower_count"] = ContentAnalyzer.parse_count(
                    profile.get("follower_count", 0)
                )

    def _enrich_video_metrics(
        self,
        items: List[Dict[str, Any]],
        comments: Sequence[Dict[str, Any]],
        creator_profiles: Optional[Dict[str, Dict[str, Any]]],
    ) -> List[Dict[str, Any]]:
        self._attach_creator_profiles(items, creator_profiles)

        author_likes: Dict[str, List[int]] = defaultdict(list)
        for item in items:
            author_likes[self._author_key(item)].append(
                ContentAnalyzer.parse_count(item.get("liked_count", 0))
            )

        comments_by_item: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for comment in comments:
            item_id = str(comment.get("item_id") or "").strip()
            if item_id:
                comments_by_item[item_id].append(comment)

        enriched: List[Dict[str, Any]] = []
        for item in items:
            row = dict(item)
            likes = ContentAnalyzer.parse_count(row.get("liked_count", 0))
            author_key = self._author_key(row)
            samples = author_likes.get(author_key, [])
            # 用“其他作品”的中位数做基线，避免爆款本身把基线抬高
            others = list(samples)
            try:
                others.remove(likes)
            except ValueError:
                pass
            if len(others) >= 2:
                baseline = self._median(others)
                baseline_source = "author_other_posts"
            elif len(samples) >= 3:
                baseline = self._median(samples)
                baseline_source = "author_posts"
            else:
                baseline = 0.0
                baseline_source = "unavailable"

            multiplier = (likes / baseline) if baseline > 0 else None
            item_comments = comments_by_item.get(str(row.get("id") or ""), [])
            demand = [x for x in item_comments if self._is_demand_comment(x.get("content", ""))]
            demand_sorted = sorted(
                demand,
                key=lambda x: (
                    ContentAnalyzer.parse_count(x.get("like_count", 0))
                    + 2 * ContentAnalyzer.parse_count(x.get("reply_count", 0))
                ),
                reverse=True,
            )

            follower_count = ContentAnalyzer.parse_count(row.get("follower_count", 0))
            low_follower_breakthrough = False
            if follower_count > 0 and follower_count <= 30000:
                low_follower_breakthrough = likes >= max(1000, int(follower_count * 0.5))

            sig = self._topic_signature(row)
            row["_radar"] = {
                "author_key": author_key,
                "author_sample_count": len(samples),
                "author_baseline_likes": round(baseline, 2) if baseline else None,
                "baseline_source": baseline_source,
                "viral_multiplier": round(multiplier, 3) if multiplier is not None else None,
                "engagement_rate": round(self._engagement_rate(row), 6),
                "age_days": (
                    round(self._age_days(row.get("create_time")), 2)
                    if self._age_days(row.get("create_time")) is not None
                    else None
                ),
                "follower_count": follower_count or None,
                "low_follower_breakthrough": low_follower_breakthrough,
                "loaded_comment_count": len(item_comments),
                "demand_comment_count": len(demand),
                "demand_ratio": round(len(demand) / len(item_comments), 4) if item_comments else None,
                "top_demand_comments": [
                    {
                        "content": str(x.get("content") or "")[:180],
                        "like_count": ContentAnalyzer.parse_count(x.get("like_count", 0)),
                        "reply_count": ContentAnalyzer.parse_count(x.get("reply_count", 0)),
                    }
                    for x in demand_sorted[:5]
                ],
                "topic_signature": {
                    "label": sig["label"],
                    "tags": sig["tags"],
                    "text": sig["text"][:240],
                },
            }
            row["_signature"] = sig
            enriched.append(row)
        return enriched

    def _cluster(self, items: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
        clusters: List[List[Dict[str, Any]]] = []
        for item in items:
            sig = item["_signature"]
            best_idx = None
            best_sim = 0.0
            for idx, cluster in enumerate(clusters):
                # 与簇内最多前三个代表样本比较，避免超大簇成本过高
                sims = [
                    self._similarity(sig, other["_signature"])
                    for other in cluster[:3]
                ]
                sim = max(sims) if sims else 0.0
                if sim > best_sim:
                    best_sim = sim
                    best_idx = idx
            threshold = 0.58 if sig["tags"] else 0.28
            if best_idx is not None and best_sim >= threshold:
                clusters[best_idx].append(item)
            else:
                clusters.append([item])

        # 第二遍：相同主标签的弱小簇合并，减少同义母题碎片
        merged: List[List[Dict[str, Any]]] = []
        for cluster in clusters:
            tags = Counter(
                tag
                for item in cluster
                for tag in item["_signature"]["tags"]
            )
            primary = tags.most_common(1)[0][0] if tags else None
            target = None
            if primary:
                for idx, existing in enumerate(merged):
                    existing_tags = Counter(
                        tag
                        for item in existing
                        for tag in item["_signature"]["tags"]
                    )
                    existing_primary = existing_tags.most_common(1)[0][0] if existing_tags else None
                    if existing_primary == primary:
                        target = idx
                        break
            if target is None:
                merged.append(cluster)
            else:
                merged[target].extend(cluster)
        return merged

    @staticmethod
    def _percentile_rank(value: float, population: Sequence[float]) -> float:
        vals = [float(x) for x in population if x is not None]
        if not vals:
            return 0.5
        below = sum(1 for x in vals if x <= value)
        return below / len(vals)

    @staticmethod
    def _component(value: Optional[float], weight: float) -> Dict[str, Any]:
        if value is None:
            return {"score": None, "weight": weight, "available": False}
        return {
            "score": round(max(0.0, min(weight, value)), 2),
            "weight": weight,
            "available": True,
        }

    def _score_cluster(
        self,
        cluster: List[Dict[str, Any]],
        all_engagement_rates: Sequence[float],
    ) -> Dict[str, Any]:
        unique_authors = len({self._author_key(x) for x in cluster})

        author_score_map = {1: 0.0, 2: 10.0, 3: 18.0, 4: 22.0}
        cross_account = author_score_map.get(unique_authors, 25.0 if unique_authors >= 5 else 0.0)

        multipliers = [
            x["_radar"]["viral_multiplier"]
            for x in cluster
            if x["_radar"]["viral_multiplier"] is not None
        ]
        median_mult = self._median(multipliers) if multipliers else None
        anomaly = None
        if median_mult is not None:
            anomaly = 20.0 * self._clamp((median_mult - 1.0) / 2.0)

        ages = [x["_radar"]["age_days"] for x in cluster if x["_radar"]["age_days"] is not None]
        recency = None
        recent_count = 0
        window_count = 0
        if ages:
            recent_count = sum(1 for d in ages if d <= self.recent_days)
            window_count = sum(1 for d in ages if d <= self.window_days)
            if window_count > 0:
                density = recent_count / window_count
                freshest = min(ages)
                freshness = 1.0 - self._clamp(freshest / self.window_days)
                recency = 15.0 * self._clamp(0.65 * min(1.0, density * 2.0) + 0.35 * freshness)

        cluster_engagement = self._median(
            x["_radar"]["engagement_rate"] for x in cluster
        )
        engagement_pct = self._percentile_rank(cluster_engagement, all_engagement_rates)
        engagement_score = 15.0 * engagement_pct

        loaded_comments = sum(x["_radar"]["loaded_comment_count"] for x in cluster)
        demand_comments = sum(x["_radar"]["demand_comment_count"] for x in cluster)
        demand_ratio = (demand_comments / loaded_comments) if loaded_comments else None
        demand_score = (
            15.0 * self._clamp(demand_ratio / 0.25)
            if demand_ratio is not None
            else None
        )

        follower_available = any(x["_radar"]["follower_count"] for x in cluster)
        breakthroughs = sum(
            1 for x in cluster if x["_radar"]["low_follower_breakthrough"]
        )
        low_follower_score = None
        if follower_available:
            low_follower_score = 10.0 if breakthroughs >= 1 else 0.0

        breakdown = {
            "cross_account_reproduction": self._component(cross_account, 25),
            "relative_author_anomaly": self._component(anomaly, 20),
            "recency_density": self._component(recency, 15),
            "high_intent_engagement": self._component(engagement_score, 15),
            "comment_demand_density": self._component(demand_score, 15),
            "low_follower_breakthrough": self._component(low_follower_score, 10),
        }

        available_weight = sum(
            part["weight"] for part in breakdown.values() if part["available"]
        )
        raw_score = sum(
            part["score"] for part in breakdown.values()
            if part["available"] and part["score"] is not None
        )
        market_score = round((raw_score / available_weight * 100.0), 1) if available_weight else 0.0

        return {
            "market_score": market_score,
            "score_breakdown": breakdown,
            "available_weight": available_weight,
            "unique_authors": unique_authors,
            "median_viral_multiplier": round(median_mult, 2) if median_mult is not None else None,
            "max_viral_multiplier": (
                round(max(multipliers), 2) if multipliers else None
            ),
            "recent_count": recent_count,
            "window_count": window_count,
            "median_engagement_rate": round(cluster_engagement, 4),
            "engagement_percentile": round(engagement_pct, 3),
            "loaded_comment_count": loaded_comments,
            "demand_comment_count": demand_comments,
            "demand_ratio": round(demand_ratio, 4) if demand_ratio is not None else None,
            "low_follower_breakouts": breakthroughs,
        }

    @staticmethod
    def _best_label(cluster: List[Dict[str, Any]]) -> Tuple[str, List[str], bool]:
        tags = Counter(tag for item in cluster for tag in item["_signature"]["tags"])
        if tags:
            ordered = [x[0] for x in tags.most_common(2)]
            fallback = str(cluster[0].get("title") or "未命名母题")[:28]
            return ViralTopicRadar._label_for_tags(ordered, fallback), ordered, False

        # 无规则标签时用最高赞标题作为候选名，并强制 Agent 复核
        top = max(
            cluster,
            key=lambda x: ContentAnalyzer.parse_count(x.get("liked_count", 0)),
        )
        return (
            f"待语义复核：{ContentAnalyzer.clean_title(str(top.get('title') or '未命名'))[:32]}",
            [],
            True,
        )

    @staticmethod
    def _collect_demand_questions(cluster: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        candidates: List[Dict[str, Any]] = []
        seen: Set[str] = set()
        for item in cluster:
            for comment in item["_radar"]["top_demand_comments"]:
                content = str(comment.get("content") or "").strip()
                key = re.sub(r"\s+", "", content)
                if not key or key in seen:
                    continue
                seen.add(key)
                row = dict(comment)
                row["source_item_id"] = item.get("id")
                row["source_title"] = item.get("title")
                candidates.append(row)
        return sorted(
            candidates,
            key=lambda x: x.get("like_count", 0) + 2 * x.get("reply_count", 0),
            reverse=True,
        )[:8]

    @staticmethod
    def _evidence(cluster: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        def rank_key(item: Dict[str, Any]) -> Tuple[float, int]:
            mult = item["_radar"]["viral_multiplier"]
            return (float(mult or 0.0), ContentAnalyzer.parse_count(item.get("liked_count", 0)))

        rows = sorted(cluster, key=rank_key, reverse=True)[:6]
        out = []
        for item in rows:
            out.append({
                "id": item.get("id"),
                "title": item.get("title"),
                "author": item.get("author"),
                "likes": ContentAnalyzer.parse_count(item.get("liked_count", 0)),
                "shares": ContentAnalyzer.parse_count(item.get("share_count", 0)),
                "collects": ContentAnalyzer.parse_count(item.get("collected_count", 0)),
                "comments": ContentAnalyzer.parse_count(item.get("comment_count", 0)),
                "viral_multiplier": item["_radar"]["viral_multiplier"],
                "author_baseline_likes": item["_radar"]["author_baseline_likes"],
                "age_days": item["_radar"]["age_days"],
                "follower_count": item["_radar"]["follower_count"],
                "url": item.get("url") or "",
            })
        return out

    def build(
        self,
        items: Sequence[Dict[str, Any]],
        comments: Optional[Sequence[Dict[str, Any]]] = None,
        creator_profiles: Optional[Dict[str, Dict[str, Any]]] = None,
        top_n: int = 20,
    ) -> Dict[str, Any]:
        """
        构建结构化雷达报告。

        items 应包含尽量完整的一批同赛道作品，而不是只喂“已经爆了”的视频；
        否则作者基线和异常倍率没有意义。
        """
        source_items = [dict(x) for x in items if str(x.get("id") or "").strip()]
        all_comments = list(comments or [])

        enriched = self._enrich_video_metrics(
            source_items,
            all_comments,
            creator_profiles,
        )

        # 只把时间窗内作品用于母题候选；没有时间字段的样本仍保留，避免旧数据完全不可用
        candidates = [
            x for x in enriched
            if x["_radar"]["age_days"] is None
            or x["_radar"]["age_days"] <= self.window_days
        ]
        clusters = self._cluster(candidates)
        all_engagement = [x["_radar"]["engagement_rate"] for x in candidates]

        topic_rows: List[Dict[str, Any]] = []
        for idx, cluster in enumerate(clusters, 1):
            score = self._score_cluster(cluster, all_engagement)
            label, tags, needs_review = self._best_label(cluster)
            if score["unique_authors"] < self.min_authors:
                # 单账号内容仍保留在视频明细中，但不进入默认“跨账号母题榜”
                continue

            confidence = "high"
            if needs_review or score["available_weight"] < 55:
                confidence = "medium"
            if score["unique_authors"] < 3:
                confidence = "emerging"

            topic_rows.append({
                "topic_id": f"T{idx:03d}",
                "mother_topic": label,
                "canonical_tags": tags,
                "sample_count": len(cluster),
                **score,
                "confidence": confidence,
                "agent_semantic_review_required": needs_review,
                "demand_questions": self._collect_demand_questions(cluster),
                "evidence": self._evidence(cluster),
            })

        topic_rows.sort(
            key=lambda x: (x["market_score"], x["unique_authors"], x["sample_count"]),
            reverse=True,
        )
        topic_rows = topic_rows[: max(1, int(top_n))]

        # 清掉只供内部聚类的 _signature，保留可审计 _radar
        for item in enriched:
            item.pop("_signature", None)

        return {
            "schema_version": 1,
            "type": "douyin-viral-topic-radar",
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "window_days": self.window_days,
            "recent_days": self.recent_days,
            "min_authors": self.min_authors,
            "sample_size": len(source_items),
            "candidate_size": len(candidates),
            "comment_sample_size": len(all_comments),
            "topic_count": len(topic_rows),
            "methodology": {
                "principle": "先看跨账号与相对作者基线，再看绝对点赞；缺失指标不伪造，按可用权重归一。",
                "market_score_weights": {
                    "cross_account_reproduction": 25,
                    "relative_author_anomaly": 20,
                    "recency_density": 15,
                    "high_intent_engagement": 15,
                    "comment_demand_density": 15,
                    "low_follower_breakthrough": 10,
                },
                "semantic_note": "母题聚类为轻量规则+n-gram第一遍；agent_semantic_review_required=true 的簇必须由 Agent 二次语义合并/改名。",
            },
            "topics": topic_rows,
            "videos": enriched,
        }
