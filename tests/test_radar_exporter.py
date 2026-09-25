# -*- coding: utf-8 -*-
import json
from pathlib import Path
import tempfile

from douyin_to_obsidian.exporters.radar import RadarExporter


def test_radar_exporter_writes_json_and_markdown():
    report = {
        "generated_at": "2026-09-25T12:00:00+0800",
        "window_days": 30,
        "recent_days": 7,
        "sample_size": 6,
        "comment_sample_size": 4,
        "topics": [
            {
                "market_score": 82.5,
                "mother_topic": "长资料看不完：让 AI 先读",
                "unique_authors": 3,
                "sample_count": 4,
                "median_viral_multiplier": 3.2,
                "max_viral_multiplier": 8.1,
                "recent_count": 3,
                "window_count": 4,
                "demand_ratio": 0.4,
                "demand_comment_count": 4,
                "loaded_comment_count": 10,
                "low_follower_breakouts": 1,
                "confidence": "high",
                "agent_semantic_review_required": False,
                "score_breakdown": {
                    "cross_account_reproduction": {"score": 18, "weight": 25, "available": True},
                    "relative_author_anomaly": {"score": 20, "weight": 20, "available": True},
                    "recency_density": {"score": 12, "weight": 15, "available": True},
                    "high_intent_engagement": {"score": 12, "weight": 15, "available": True},
                    "comment_demand_density": {"score": 15, "weight": 15, "available": True},
                    "low_follower_breakthrough": {"score": 10, "weight": 10, "available": True},
                },
                "evidence": [
                    {
                        "title": "50页PDF不想看",
                        "author": "作者A",
                        "likes": 10000,
                        "viral_multiplier": 4.0,
                        "url": "https://example.com/v1",
                    }
                ],
                "demand_questions": [
                    {"content": "论文也可以吗？", "like_count": 20, "reply_count": 2}
                ],
            }
        ],
    }

    with tempfile.TemporaryDirectory() as tmp_dir:
        exporter = RadarExporter(Path(tmp_dir))
        paths = exporter.export(report)

        assert paths["json"].exists()
        assert paths["markdown"].exists()

        payload = json.loads(paths["json"].read_text(encoding="utf-8"))
        assert payload["topics"][0]["market_score"] == 82.5

        md = paths["markdown"].read_text(encoding="utf-8")
        assert "Douyin Viral Topic Radar" in md
        assert "长资料看不完" in md
        assert "论文也可以吗" in md
