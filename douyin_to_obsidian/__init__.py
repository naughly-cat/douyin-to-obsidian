# -*- coding: utf-8 -*-
"""
douyin-to-obsidian: 抖音/小红书口播文案采集、Whisper 语音转写与 Obsidian 知识库双链导出工具。
"""

__version__ = "0.1.0"
__author__ = "codergl"
__license__ = "MIT"

from .core.transcriber import Transcriber, ensure_model
from .core.parser import MediaParser
from .core.analyzer import ContentAnalyzer
from .core.crawler_adapter import CrawlerAdapter
from .exporters.obsidian import ObsidianExporter
from .config import Config

__all__ = [
    "Transcriber",
    "ensure_model",
    "MediaParser",
    "ContentAnalyzer",
    "CrawlerAdapter",
    "ObsidianExporter",
    "Config",
]
