# -*- coding: utf-8 -*-
import json
import tempfile
from pathlib import Path
import pytest
from douyin_to_obsidian.core.crawler_adapter import CrawlerAdapter


def test_load_crawled_data_and_filter():
    with tempfile.TemporaryDirectory() as tmp_dir:
        data_dir = Path(tmp_dir)
        dy_dir = data_dir / "douyin" / "jsonl"
        dy_dir.mkdir(parents=True, exist_ok=True)

        # 构造一条符合条件、一条低于赞数阈值、一条评论记录
        sample_records = [
            {
                "aweme_id": "7111111111",
                "title": "高赞视频：AI工具合集",
                "nickname": "科技博主",
                "liked_count": 2500,
                "video_download_url": "https://example.com/video1.mp4",
                "desc": "详细教程见置顶",
            },
            {
                "aweme_id": "7222222222",
                "title": "低赞视频：随手拍",
                "nickname": "路人甲",
                "liked_count": 10,
                "video_download_url": "https://example.com/video2.mp4",
            },
            {
                "comment_id": "9999999999",
                "content": "这是一条评论",
                "liked_count": 5000,
            }
        ]

        test_file = dy_dir / "sample.jsonl"
        with open(test_file, "w", encoding="utf-8") as f:
            for r in sample_records:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

        # 读取最低 500 赞
        items = CrawlerAdapter.load_crawled_data(data_dir, platform="douyin", min_likes=500)
        assert len(items) == 1
        assert items[0]["id"] == "7111111111"
        assert items[0]["title"] == "高赞视频：AI工具合集"
        assert items[0]["author"] == "科技博主"
        assert items[0]["liked_count"] == 2500


def test_cache_save_and_load():
    with tempfile.TemporaryDirectory() as tmp_dir:
        cache_file = Path(tmp_dir) / ".cache.json"
        cache_data = {
            "vid123": {
                "title": "缓存测试",
                "transcript": "这是已转写的口播",
                "hook_15s": "这是前15s钩子",
            }
        }
        CrawlerAdapter.save_cache(cache_data, cache_file)
        loaded = CrawlerAdapter.load_cache(cache_file)
        assert "vid123" in loaded
        assert loaded["vid123"]["transcript"] == "这是已转写的口播"


def test_corrupt_cache_fails_closed_instead_of_being_overwritten():
    with tempfile.TemporaryDirectory() as tmp_dir:
        cache_file = Path(tmp_dir) / ".cache.json"
        cache_file.write_text("{broken", encoding="utf-8")

        with pytest.raises(RuntimeError, match="转写缓存损坏"):
            CrawlerAdapter.load_cache(cache_file)

        assert cache_file.read_text(encoding="utf-8") == "{broken"


def test_user_field_variants_do_not_crash():
    # user 字段为字符串 / dict / 缺失时都应正常解析，不得中断整批
    with tempfile.TemporaryDirectory() as tmp_dir:
        data_dir = Path(tmp_dir)
        dy_dir = data_dir / "douyin" / "jsonl"
        dy_dir.mkdir(parents=True, exist_ok=True)

        sample_records = [
            {"aweme_id": "a1", "title": "字符串user", "user": "字符串昵称", "liked_count": 600},
            {"aweme_id": "a2", "title": "字典user", "user": {"nickname": "字典昵称"}, "liked_count": 600},
            {"aweme_id": "a3", "title": "无user", "liked_count": 600},
        ]
        test_file = dy_dir / "users.jsonl"
        with open(test_file, "w", encoding="utf-8") as f:
            for r in sample_records:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

        items = {x["id"]: x for x in CrawlerAdapter.load_crawled_data(data_dir, platform="douyin", min_likes=500)}
        assert len(items) == 3
        assert items["a1"]["author"] == "字符串昵称"
        assert items["a2"]["author"] == "字典昵称"
        assert items["a3"]["author"] == "未知创作者"
