# -*- coding: utf-8 -*-
import time

from douyin_to_obsidian.core.radar import ViralTopicRadar


def _item(
    cid,
    author,
    title,
    likes,
    *,
    author_id=None,
    shares=0,
    collects=0,
    comments=0,
    days_ago=1,
    follower_count=0,
):
    return {
        "id": cid,
        "platform": "douyin",
        "title": title,
        "author": author,
        "author_id": author_id or author,
        "liked_count": likes,
        "share_count": shares,
        "collected_count": collects,
        "comment_count": comments,
        "create_time": int(time.time() - days_ago * 86400),
        "follower_count": follower_count,
        "url": f"https://example.com/{cid}",
        "desc": "",
        "transcript": "",
        "hook_15s": "",
    }


def test_radar_finds_cross_account_long_document_mother_topic():
    now = time.time()
    items = [
        _item("a1", "作者A", "ChatGPT帮我看50页PDF", 1000, author_id="A", shares=80, collects=150, comments=60, days_ago=1, follower_count=5000),
        _item("a2", "作者A", "我的桌面收纳", 100, author_id="A", days_ago=10, follower_count=5000),
        _item("a3", "作者A", "周末随手记录", 120, author_id="A", days_ago=12, follower_count=5000),
        _item("b1", "作者B", "豆包直接读行业报告靠谱吗", 800, author_id="B", shares=70, collects=120, comments=50, days_ago=2, follower_count=8000),
        _item("b2", "作者B", "午饭吃什么", 80, author_id="B", days_ago=9, follower_count=8000),
        _item("b3", "作者B", "手机桌面整理", 90, author_id="B", days_ago=11, follower_count=8000),
    ]
    comments = [
        {"comment_id": "c1", "item_id": "a1", "content": "论文也可以吗？", "like_count": 30, "reply_count": 3},
        {"comment_id": "c2", "item_id": "a1", "content": "求提示词", "like_count": 20, "reply_count": 1},
        {"comment_id": "c3", "item_id": "b1", "content": "合同能不能这样看", "like_count": 10, "reply_count": 0},
        {"comment_id": "c4", "item_id": "b1", "content": "学到了", "like_count": 1, "reply_count": 0},
    ]

    radar = ViralTopicRadar(window_days=30, recent_days=7, min_authors=2, now_ts=now)
    report = radar.build(items, comments=comments, top_n=10)

    assert report["topic_count"] >= 1
    topic = report["topics"][0]
    assert "长资料" in topic["mother_topic"]
    assert topic["unique_authors"] == 2
    assert topic["median_viral_multiplier"] > 5
    assert topic["demand_comment_count"] == 3
    assert topic["market_score"] > 50
    assert topic["low_follower_breakouts"] >= 1


def test_radar_missing_dimensions_are_marked_unavailable_not_invented():
    now = time.time()
    items = [
        _item("x1", "甲", "50页PDF怎么快速看", 500, author_id="X", days_ago=1),
        _item("y1", "乙", "行业报告太长让AI先读", 600, author_id="Y", days_ago=1),
    ]
    # 删除时间与粉丝，模拟采集字段不完整
    for item in items:
        item["create_time"] = 0
        item["follower_count"] = 0

    radar = ViralTopicRadar(window_days=30, recent_days=7, min_authors=2, now_ts=now)
    report = radar.build(items, comments=[])

    topic = report["topics"][0]
    breakdown = topic["score_breakdown"]
    assert breakdown["relative_author_anomaly"]["available"] is False
    assert breakdown["recency_density"]["available"] is False
    assert breakdown["comment_demand_density"]["available"] is False
    assert breakdown["low_follower_breakthrough"]["available"] is False
    assert 0 <= topic["market_score"] <= 100


def test_different_ai_tool_names_do_not_split_same_problem():
    now = time.time()
    items = [
        _item("p1", "甲", "ChatGPT读PDF到底行不行", 500, author_id="P1", days_ago=1),
        _item("p2", "乙", "Gemini帮我看50页报告", 700, author_id="P2", days_ago=1),
        _item("p3", "丙", "用豆包总结一份论文", 900, author_id="P3", days_ago=2),
    ]
    radar = ViralTopicRadar(window_days=30, recent_days=7, min_authors=2, now_ts=now)
    report = radar.build(items)

    assert report["topic_count"] == 1
    assert report["topics"][0]["unique_authors"] == 3
    assert "长资料" in report["topics"][0]["mother_topic"]
