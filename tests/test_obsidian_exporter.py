# -*- coding: utf-8 -*-
import tempfile
import json
from pathlib import Path
import pytest
from douyin_to_obsidian.exporters.obsidian import ObsidianExporter


def test_export_single_note():
    with tempfile.TemporaryDirectory() as tmp_dir:
        exporter = ObsidianExporter(Path(tmp_dir))
        item = {
            "title": "测试视频：普通人如何玩转大模型",
            "author": "测试博主",
            "platform": "douyin",
            "liked_count": 15000,
            "share_count": 1200,
            "comment_count": 300,
            "url": "https://www.douyin.com/video/123456",
            "hook_15s": "你以为学AI很难？其实只要掌握这三步！",
            "transcript": "大家好，今天给大家聊聊普通人学AI的核心逻辑。第一是不要死磕原理，第二是用场景驱动。",
            "segments": [
                {"from": "00:00:00,000", "to": "00:00:05,000", "text": "你以为学AI很难？其实只要掌握这三步！"},
                {"from": "00:00:05,000", "to": "00:00:10,000", "text": "大家好，今天给大家聊聊普通人学AI的核心逻辑。"},
            ]
        }

        note_path = exporter.export_single_note(item)
        assert note_path.exists()

        content = note_path.read_text(encoding="utf-8")
        # 检查 YAML Frontmatter
        assert "---" in content
        assert 'title: "测试视频：普通人如何玩转大模型"' in content
        assert 'author: "测试博主"' in content
        assert "likes: 15000" in content
        assert "语料/口播文案" in content
        # 检查 Callout 与内容
        assert "> [!TIP] 开头反差与受众注意力抓手" in content
        assert "你以为学AI很难？其实只要掌握这三步！" in content
        assert "完整口播逐字稿" in content
        assert "时间戳分段台词" in content


def test_export_aggregate_library():
    with tempfile.TemporaryDirectory() as tmp_dir:
        exporter = ObsidianExporter(Path(tmp_dir))
        items = [
            {
                "title": "爆款1",
                "author": "博主A",
                "platform": "douyin",
                "liked_count": 20000,
                "hook_15s": "钩子1",
                "transcript": "口播全文1",
            },
            {
                "title": "爆款2",
                "author": "博主B",
                "platform": "xiaohongshu",
                "liked_count": 50000,
                "hook_15s": "钩子2",
                "transcript": "口播全文2",
            }
        ]

        lib_file = exporter.export_aggregate_library(items)
        assert lib_file.exists()

        content = lib_file.read_text(encoding="utf-8")
        assert "爆款社媒口播逐字稿与前15秒黄金钩子全量母库" in content
        # 验证按点赞排序（5万赞的排在第一位）
        first_rank_pos = content.find("1. 【5.0万赞 · 小红书】爆款2")
        second_rank_pos = content.find("2. 【2.0万赞 · 抖音】爆款1")
        assert first_rank_pos != -1
        assert second_rank_pos != -1
        assert first_rank_pos < second_rank_pos


def test_export_aggregate_library_merges_across_runs():
    # 回归：多次导出应合并历史条目，而不是用本次条目覆盖整个大库
    with tempfile.TemporaryDirectory() as tmp_dir:
        exporter = ObsidianExporter(Path(tmp_dir))
        first = {
            "id": "v1",
            "title": "旧视频",
            "author": "博主A",
            "platform": "douyin",
            "liked_count": 100,
            "hook_15s": "钩子A",
            "transcript": "全文A",
            "url": "https://www.douyin.com/video/1",
        }
        exporter.export_aggregate_library([first])

        second = {
            "id": "v2",
            "title": "新视频",
            "author": "博主B",
            "platform": "xiaohongshu",
            "liked_count": 5000,
            "hook_15s": "钩子B",
            "transcript": "全文B",
            "url": "https://www.xiaohongshu.com/explore/2",
        }
        lib = exporter.export_aggregate_library([second])
        content = lib.read_text(encoding="utf-8")

        assert "旧视频" in content
        assert "新视频" in content
        assert "sample_size: 2 篇精选作品" in content
        # 高赞新条目应排在前面
        assert content.find("1. 【5000赞 · 小红书】新视频") < content.find("2. 【100赞 · 抖音】旧视频")


def test_export_aggregate_library_dedupes_same_item():
    # 同一条目（相同 id）重复导入不应产生重复段落，数据以最新一次为准
    with tempfile.TemporaryDirectory() as tmp_dir:
        exporter = ObsidianExporter(Path(tmp_dir))
        item = {
            "id": "v1",
            "title": "重复视频",
            "author": "博主A",
            "platform": "douyin",
            "liked_count": 100,
            "hook_15s": "钩子",
            "transcript": "全文",
            "url": "https://www.douyin.com/video/1",
        }
        exporter.export_aggregate_library([item])

        updated = dict(item, liked_count=200)
        lib = exporter.export_aggregate_library([updated, dict(updated)])
        content = lib.read_text(encoding="utf-8")

        assert content.count("重复视频") == 1
        assert "200赞" in content
        assert "sample_size: 1 篇精选作品" in content


def test_export_aggregate_library_dedupes_changed_id_by_url():
    """同一 URL 即使平台内容 ID 改变，也只能保留最新条目。"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        exporter = ObsidianExporter(Path(tmp_dir))
        first = {
            "id": "old-id",
            "title": "旧记录",
            "author": "博主A",
            "platform": "douyin",
            "liked_count": 100,
            "url": "https://www.douyin.com/video/1",
            "transcript": "旧全文",
        }
        second = dict(first, id="new-id", title="新记录", liked_count=200, transcript="新全文")

        exporter.export_aggregate_library([first])
        lib = exporter.export_aggregate_library([second])
        content = lib.read_text(encoding="utf-8")

        assert "旧记录" not in content
        assert "新记录" in content
        assert "sample_size: 1 篇精选作品" in content


def test_export_aggregate_library_persists_structured_sidecar():
    with tempfile.TemporaryDirectory() as tmp_dir:
        exporter = ObsidianExporter(Path(tmp_dir))
        item = {
            "id": "v1",
            "title": "测试",
            "author": "作者",
            "platform": "douyin",
            "liked_count": 123,
            "url": "https://www.douyin.com/video/1",
            "transcript": "正文",
        }

        exporter.export_aggregate_library([item])
        state_file = Path(tmp_dir) / ".douyin-to-obsidian" / "aggregate-state.json"

        assert state_file.exists()
        state = json.loads(state_file.read_text(encoding="utf-8"))
        assert state["schema_version"] == 1
        assert len(state["entries"]) == 1


def test_missing_sidecar_is_rebuilt_from_rendered_markdown():
    with tempfile.TemporaryDirectory() as tmp_dir:
        exporter = ObsidianExporter(Path(tmp_dir))
        first = {
            "id": "old-id",
            "title": "旧记录",
            "author": "作者",
            "platform": "douyin",
            "liked_count": 10,
            "url": "https://example.com/demo/1",
            "transcript": "旧正文",
        }
        exporter.export_aggregate_library([first])
        exporter._aggregate_state_path().unlink()

        second = dict(first, id="new-id", title="新记录", transcript="新正文")
        aggregate = exporter.export_aggregate_library([second])

        assert exporter._aggregate_state_path().exists()
        content = aggregate.read_text(encoding="utf-8")
        assert "旧记录" not in content
        assert "新记录" in content


def test_export_aggregate_library_refuses_corrupt_sidecar():
    with tempfile.TemporaryDirectory() as tmp_dir:
        exporter = ObsidianExporter(Path(tmp_dir))
        state_file = Path(tmp_dir) / ".douyin-to-obsidian" / "aggregate-state.json"
        state_file.parent.mkdir(parents=True)
        state_file.write_text("{broken", encoding="utf-8")

        with pytest.raises(RuntimeError, match="状态文件损坏"):
            exporter.export_aggregate_library([])


def test_legacy_aggregate_parse_failure_stops_instead_of_overwriting():
    with tempfile.TemporaryDirectory() as tmp_dir:
        exporter = ObsidianExporter(Path(tmp_dir))
        aggregate = Path(tmp_dir) / "数据-爆款口播逐字稿与黄金钩子库.md"
        original = "---\nsample_size: 2 篇精选作品\n---\n\n用户改坏了标题结构\n"
        aggregate.write_text(original, encoding="utf-8")

        with pytest.raises(RuntimeError, match="无法解析"):
            exporter.export_aggregate_library([])

        assert aggregate.read_text(encoding="utf-8") == original


def test_single_note_filename_contains_stable_identity():
    """相同作者和标题前缀的不同作品不得互相覆盖。"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        exporter = ObsidianExporter(Path(tmp_dir))
        common = {
            "title": "这是一个相同的超长标题前二十五个字绝对完全相同后缀甲",
            "author": "博主A",
            "platform": "douyin",
            "transcript": "第一篇",
        }
        first = dict(common, id="v1")
        second = dict(common, id="v2", title=common["title"][:-1] + "乙", transcript="第二篇")

        first_path = exporter.export_single_note(first)
        second_path = exporter.export_single_note(second)

        assert first_path != second_path
        assert "第一篇" in first_path.read_text(encoding="utf-8")
        assert "第二篇" in second_path.read_text(encoding="utf-8")


def test_single_note_frontmatter_escapes_untrusted_newlines():
    with tempfile.TemporaryDirectory() as tmp_dir:
        exporter = ObsidianExporter(Path(tmp_dir))
        note = exporter.export_single_note({
            "id": "v1",
            "title": "正常标题\nmalicious: true",
            "author": "作者\nadmin: true",
            "platform": "douyin",
            "url": "https://example.com/\"quoted\"",
            "transcript": "正文",
        })
        content = note.read_text(encoding="utf-8")
        frontmatter = content.split("---", 2)[1]

        assert "\nmalicious: true\n" not in frontmatter
        assert "\nadmin: true\n" not in frontmatter
        assert "\\nmalicious: true" in frontmatter
        assert "\\nadmin: true" in frontmatter


def test_transcript_backticks_do_not_close_markdown_fence():
    with tempfile.TemporaryDirectory() as tmp_dir:
        exporter = ObsidianExporter(Path(tmp_dir))
        note = exporter.export_single_note({
            "id": "v1",
            "title": "围栏测试",
            "author": "作者",
            "platform": "douyin",
            "transcript": "正文内含 ``` 三个反引号",
        })
        content = note.read_text(encoding="utf-8")

        assert "````text\n正文内含 ``` 三个反引号\n````" in content


def test_update_index_hub():
    with tempfile.TemporaryDirectory() as tmp_dir:
        exporter = ObsidianExporter(Path(tmp_dir))
        hub_file = exporter.update_index_hub()
        assert hub_file.exists()

        content = hub_file.read_text(encoding="utf-8")
        assert "短视频口播文案与爆款素材库全局索引" in content
        assert "[[数据-爆款口播逐字稿与黄金钩子库]]" in content
        assert "dataview" in content
