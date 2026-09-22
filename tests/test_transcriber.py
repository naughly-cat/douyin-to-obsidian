# -*- coding: utf-8 -*-
from pathlib import Path

import pytest

from douyin_to_obsidian.core.transcriber import Transcriber, ensure_model


def test_timeout_default():
    t = Transcriber()
    assert t.timeout == 120


def test_timeout_explicit_override():
    t = Transcriber(timeout=30)
    assert t.timeout == 30


def test_timeout_env_override(monkeypatch):
    monkeypatch.setenv("D2O_WHISPER_TIMEOUT", "600")
    t = Transcriber()
    assert t.timeout == 600

    # 环境变量非法时应回退默认值而不是崩溃
    monkeypatch.setenv("D2O_WHISPER_TIMEOUT", "abc")
    t2 = Transcriber()
    assert t2.timeout == 120

    monkeypatch.setenv("D2O_WHISPER_TIMEOUT", "-1")
    t3 = Transcriber()
    assert t3.timeout == 120


def test_unverified_model_name_is_rejected_before_filesystem_access(tmp_path):
    with pytest.raises(ValueError, match="未校验"):
        ensure_model("../../unexpected", cache_dir=Path(tmp_path))
