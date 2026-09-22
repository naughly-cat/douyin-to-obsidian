# -*- coding: utf-8 -*-
import pytest
from douyin_to_obsidian.core.parser import MediaParser


def test_extract_url():
    text1 = "7.12 复制打开抖音，看看【演示博主的作品】https://v.douyin.com/iABC123/ 精彩内容不容错过"
    url1 = MediaParser.extract_url(text1)
    assert url1 == "https://v.douyin.com/iABC123/"

    text2 = "15 【超详细Cursor教学】 http://xhslink.com/a/xyz789 快来看看"
    url2 = MediaParser.extract_url(text2)
    assert url2 == "http://xhslink.com/a/xyz789"

    text_none = "这里没有任何链接"
    assert MediaParser.extract_url(text_none) is None


def test_identify_platform():
    assert MediaParser.identify_platform("https://v.douyin.com/iABC123/") == "douyin"
    assert MediaParser.identify_platform("https://www.douyin.com/video/7412345678") == "douyin"
    assert MediaParser.identify_platform("http://xhslink.com/a/xyz789") == "xiaohongshu"
    assert MediaParser.identify_platform("https://www.xiaohongshu.com/explore/123456") == "xiaohongshu"
    assert MediaParser.identify_platform("https://www.bilibili.com/video/BV1xx411c7mD") == "bilibili"
    assert MediaParser.identify_platform("https://example.com/other") == "unknown"
