# -*- coding: utf-8 -*-
"""
配置模块：统一管理 Obsidian 路径、ASR 引擎设置、MediaCrawler 路径与分析规则。
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional


class Config:
    """全局配置管理器"""

    DEFAULT_WHISPER_MODEL = "base"
    DEFAULT_WHISPER_CACHE = Path.home() / ".cache" / "whisper"
    DEFAULT_WHISPER_CLI_PATH = "/opt/homebrew/bin/whisper-cli"
    MODELSCOPE_WHISPER_URL = (
        "https://www.modelscope.cn/models/iceCream2025/whisper.cpp/resolve/master"
    )
    # 回退官方源（whisper.cpp 官方 HuggingFace 仓库，文件与镜像源一致）
    OFFICIAL_WHISPER_URL = (
        "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/{filename}"
    )
    # 内置 SHA256 校验和（与 whisper.cpp 官方发布一致，防止下载被篡改或损坏）
    MODEL_SHA256 = {
        "ggml-tiny.bin": "be07e048e1e599ad46341c8d2a135645097a538221678b7acdd1b1919c6e1b21",
        "ggml-base.bin": "60ed5bc3dd14eea856493d334349b405782ddcaf0028d4b5df4088345fba2efe",
        "ggml-small.bin": "1be3a9b2063867b937e64e2ec7483364a79917e157fa98c5d94b5c1fffea987b",
        "ggml-medium.bin": "6c14d5adee5f86394037b4e4e8b59f1673b6cee10e3cf0b11bbdbee79c156208",
        "ggml-large-v3-turbo.bin": "1fc70f774d38eb169993ac391eea357ef47c88757ef72ee5943879b7e8e2bc69",
    }

    # 默认 MediaCrawler 存放路径
    DEFAULT_MC_DATA_DIR = Path.home() / "MediaCrawler" / "data"

    def __init__(
        self,
        obsidian_dir: Optional[str] = None,
        whisper_model: str = DEFAULT_WHISPER_MODEL,
        whisper_cli_path: Optional[str] = None,
        mc_data_dir: Optional[str] = None,
    ):
        # 优先级：传入参数 > 环境变量 OBSIDIAN_VAULT_DIR > 环境变量 OBSIDIAN_DIR > 默认文档路径
        env_obsidian = os.getenv("OBSIDIAN_VAULT_DIR") or os.getenv("OBSIDIAN_DIR")
        if obsidian_dir:
            self.obsidian_dir = Path(obsidian_dir).expanduser().resolve()
        elif env_obsidian:
            self.obsidian_dir = Path(env_obsidian).expanduser().resolve()
        else:
            self.obsidian_dir = (
                Path.home() / "Documents" / "Obsidian" / "素材库" / "短视频口播"
            )

        self.whisper_model = whisper_model
        self.whisper_cli_path = (
            Path(whisper_cli_path).expanduser().resolve()
            if whisper_cli_path
            else Path(self.DEFAULT_WHISPER_CLI_PATH)
        )
        self.whisper_cache_dir = self.DEFAULT_WHISPER_CACHE

        if mc_data_dir:
            self.mc_data_dir = Path(mc_data_dir).expanduser().resolve()
        else:
            self.mc_data_dir = self.DEFAULT_MC_DATA_DIR

    def ensure_obsidian_dirs(self) -> Path:
        """确保目标 Obsidian 目录存在"""
        self.obsidian_dir.mkdir(parents=True, exist_ok=True)
        return self.obsidian_dir

    def to_dict(self) -> Dict[str, Any]:
        return {
            "obsidian_dir": str(self.obsidian_dir),
            "whisper_model": self.whisper_model,
            "whisper_cli_path": str(self.whisper_cli_path),
            "whisper_cache_dir": str(self.whisper_cache_dir),
            "mc_data_dir": str(self.mc_data_dir),
        }
