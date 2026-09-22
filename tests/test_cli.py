# -*- coding: utf-8 -*-
from types import SimpleNamespace

from douyin_to_obsidian import cli
from douyin_to_obsidian.config import Config


def test_file_command_uses_config_default_model(monkeypatch, tmp_path):
    media_file = tmp_path / "sample.wav"
    media_file.write_bytes(b"RIFF-demo")
    observed = {}

    class FakeTranscriber:
        def __init__(self, model_name, cli_path):
            observed["model_name"] = model_name

        def transcribe_file(self, path):
            return {"transcript": "测试正文", "hook_15s": "测试钩子", "segments": []}

    class FakeExporter:
        def __init__(self, output_dir):
            pass

        def export_single_note(self, item):
            return tmp_path / "note.md"

        def export_aggregate_library(self, items):
            return tmp_path / "aggregate.md"

        def update_index_hub(self):
            return tmp_path / "index.md"

    monkeypatch.setattr(cli, "Transcriber", FakeTranscriber)
    monkeypatch.setattr(cli, "ObsidianExporter", FakeExporter)
    args = SimpleNamespace(
        file=str(media_file),
        title=None,
        author=None,
        aggregate=False,
    )
    cfg = Config(obsidian_dir=str(tmp_path / "vault"), whisper_model="base")

    cli.cmd_file(args, cfg)

    assert observed["model_name"] == "base"


def test_batch_persists_cache_for_records_with_existing_transcript(monkeypatch, tmp_path):
    saved = {}

    class FakeAdapter:
        @staticmethod
        def load_crawled_data(*args, **kwargs):
            return [{
                "id": "v1",
                "title": "已有正文",
                "author": "作者",
                "platform": "douyin",
                "transcript": "无需 ASR 的正文",
                "hook_15s": "",
                "liked_count": 1000,
            }]

        @staticmethod
        def load_cache(path):
            return {}

        @staticmethod
        def save_cache(cache, path):
            saved.update(cache)

    class FakeTranscriber:
        def __init__(self, model_name, cli_path):
            pass

    class FakeExporter:
        def __init__(self, output_dir):
            pass

        def export_single_note(self, item):
            return tmp_path / "note.md"

        def export_aggregate_library(self, items):
            return tmp_path / "aggregate.md"

        def update_index_hub(self):
            return tmp_path / "index.md"

    monkeypatch.setattr(cli, "CrawlerAdapter", FakeAdapter)
    monkeypatch.setattr(cli, "Transcriber", FakeTranscriber)
    monkeypatch.setattr(cli, "ObsidianExporter", FakeExporter)
    args = SimpleNamespace(
        data_dir=str(tmp_path / "data"),
        platform="all",
        min_likes=0,
        date=None,
        reset_cache=False,
        limit=10,
    )
    cfg = Config(obsidian_dir=str(tmp_path / "vault"), whisper_model="base")

    cli.cmd_batch(args, cfg)

    assert saved["v1"]["transcript"] == "无需 ASR 的正文"
