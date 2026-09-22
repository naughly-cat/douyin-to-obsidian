# -*- coding: utf-8 -*-
import pytest
from douyin_to_obsidian.core.analyzer import ContentAnalyzer


def test_parse_count():
    assert ContentAnalyzer.parse_count("1.2万") == 12000
    assert ContentAnalyzer.parse_count("500") == 500
    assert ContentAnalyzer.parse_count(888) == 888
    assert ContentAnalyzer.parse_count(None) == 0
    assert ContentAnalyzer.parse_count("无效数字") == 0


def test_format_count():
    assert ContentAnalyzer.format_count(15000) == "1.5万"
    assert ContentAnalyzer.format_count(500) == "500"
    assert ContentAnalyzer.format_count(0) == "0"


def test_extract_hook_from_segments():
    segments = [
        {"from": "00:00:01,000", "to": "00:00:04,500", "text": "为什么说普通人学AI90%都在走弯路？"},
        {"from": "00:00:05,000", "to": "00:00:10,000", "text": "你看了那么多教程，实际上根本没跑通一个真实需求。"},
        {"from": "00:00:16,000", "to": "00:00:20,000", "text": "今天这期视频我来告诉你正确的闭坑指南。"},
    ]
    hook = ContentAnalyzer.extract_hook("full text", segments=segments)
    assert "普通人学AI" in hook
    assert "真实需求" in hook
    assert "闭坑指南" not in hook  # 超过 15 秒的不应被计入


def test_extract_hook_from_plain_text():
    text = "AI时代很多人都焦虑失业。其实根本不用慌，关键是先用起来！我们来看看三款核心神器。"
    hook = ContentAnalyzer.extract_hook(text)
    assert "AI时代很多人都焦虑失业" in hook


def test_categorize():
    cat1 = ContentAnalyzer.categorize("Cursor深度编程实战", "手把手教你如何用大模型写代码")
    assert "AI工具实测" in cat1

    cat2 = ContentAnalyzer.categorize("AI副业月入过万的真相", "告诉你普通人赚钱去魅")
    assert "职场生存与商业变现" in cat2 or "认知重塑" in cat2


def test_clean_title():
    raw = "震惊！原来普通人学AI这么简单 #AI工具 #自律成长\n\n"
    clean = ContentAnalyzer.clean_title(raw)
    assert "#AI工具" not in clean
    assert clean == "震惊！原来普通人学AI这么简单"
