# -*- coding: utf-8 -*-
"""
MediaCrawler 抓取数据适配器 (Crawler Adapter)
===========================================
- 扫描 MediaCrawler 导出的数据目录（支持 douyin/xiaohongshu 目录别名）
- 批量加载并规范化 JSON / JSONL / CSV 作品数据
- 排除评论数据，自动去重与过滤低互动作品
- 提供断点转写缓存管理，避免重复下载与重复转写消耗算力
"""

import csv
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from .analyzer import ContentAnalyzer


class CrawlerAdapter:
    """批量抓取数据适配与缓存管理"""

    PLATFORM_DIRS = {
        "douyin": ["douyin", "dy"],
        "xiaohongshu": ["xiaohongshu", "xhs"],
        "bilibili": ["bilibili", "bili"],
    }

    @classmethod
    def load_crawled_data(
        cls,
        data_dir: Path,
        platform: str = "all",
        min_likes: int = 0,
        date_filter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        从 MediaCrawler 数据目录加载作品记录。
        """
        data_dir = Path(data_dir).expanduser().resolve()
        if not data_dir.exists():
            print(f"[-] 数据目录不存在: {data_dir}")
            return []

        target_platforms = []
        if platform == "all":
            target_platforms = list(cls.PLATFORM_DIRS.keys())
        elif platform in ("dy", "douyin"):
            target_platforms = ["douyin"]
        elif platform in ("xhs", "xiaohongshu"):
            target_platforms = ["xiaohongshu"]
        else:
            target_platforms = [platform]

        items_map: Dict[str, Dict[str, Any]] = {}

        for pf in target_platforms:
            subdirs = cls.PLATFORM_DIRS.get(pf, [pf])
            for sdir in subdirs:
                pf_path = data_dir / sdir
                if not pf_path.exists():
                    continue

                # 扫描 json/jsonl/csv
                for file_path in pf_path.rglob("*.*"):
                    if file_path.suffix.lower() not in (".json", ".jsonl", ".csv"):
                        continue
                    if "comment" in file_path.name.lower():
                        continue
                    if date_filter and date_filter not in file_path.name:
                        continue

                    cls._parse_file(file_path, pf, items_map, min_likes)

        return list(items_map.values())

    @classmethod
    def _parse_file(
        cls,
        file_path: Path,
        platform: str,
        items_map: Dict[str, Dict[str, Any]],
        min_likes: int,
    ):
        """解析单个数据文件并入库去重"""
        ext = file_path.suffix.lower()
        records: List[Dict[str, Any]] = []

        try:
            if ext == ".jsonl":
                with open(file_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            try:
                                records.append(json.loads(line))
                            except Exception:
                                continue
            elif ext == ".json":
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        records = data
                    elif isinstance(data, dict):
                        records = data.get("data", [data])
            elif ext == ".csv":
                with open(file_path, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    records = list(reader)
        except Exception as e:
            print(f"[-] 读取文件失败 {file_path}: {e}")
            return

        for raw in records:
            # 过滤评论记录
            if "comment_id" in raw or "sub_comment_count" in raw:
                continue

            cid = str(
                raw.get("aweme_id")
                or raw.get("note_id")
                or raw.get("id")
                or raw.get("url")
                or ""
            ).strip()
            if not cid:
                continue

            likes = ContentAnalyzer.parse_count(
                raw.get("liked_count")
                or raw.get("digg_count")
                or raw.get("like_count")
                or raw.get("likes")
            )
            if likes < min_likes:
                continue

            title = raw.get("title") or raw.get("desc") or "无标题作品"
            # user 字段在不同导出格式里可能是 dict，也可能是字符串昵称
            user_raw = raw.get("user")
            if isinstance(user_raw, dict):
                user_nick = user_raw.get("nickname")
            elif isinstance(user_raw, str) and user_raw.strip():
                user_nick = user_raw.strip()
            else:
                user_nick = None
            author = (
                raw.get("nickname")
                or raw.get("user_nickname")
                or raw.get("author")
                or user_nick
                or "未知创作者"
            )
            url = (
                raw.get("url")
                or raw.get("note_url")
                or raw.get("aweme_url")
                or ""
            )

            # 音视频直链
            audio_url = (
                raw.get("video_download_url")
                or raw.get("audio_download_url")
                or raw.get("music_download_url")
                or raw.get("video_url")
                or ""
            )

            item = {
                "id": cid,
                "platform": platform,
                "title": ContentAnalyzer.clean_title(title),
                "author": str(author),
                "url": url,
                "audio_url": audio_url,
                "video_url": raw.get("video_download_url") or raw.get("video_url") or "",
                "desc": raw.get("desc") or raw.get("content") or "",
                "transcript": raw.get("transcript") or "",
                "hook_15s": raw.get("hook_15s") or "",
                "liked_count": likes,
                "collected_count": ContentAnalyzer.parse_count(
                    raw.get("collected_count") or raw.get("collect_count")
                ),
                "share_count": ContentAnalyzer.parse_count(
                    raw.get("share_count") or raw.get("shared_count")
                ),
                "comment_count": ContentAnalyzer.parse_count(
                    raw.get("comment_count") or raw.get("comments_count")
                ),
                "_source_file": str(file_path),
            }

            if cid not in items_map:
                items_map[cid] = item
            else:
                # 补充字段（例如已转录的 transcript）
                if not items_map[cid].get("transcript") and item.get("transcript"):
                    items_map[cid]["transcript"] = item["transcript"]

    @classmethod
    def load_cache(cls, cache_path: Path) -> Dict[str, Dict[str, Any]]:
        """加载已转写的内容缓存"""
        if cache_path.exists():
            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except (OSError, json.JSONDecodeError) as exc:
                raise RuntimeError(
                    f"转写缓存损坏，已停止写入；确认后可使用 --reset-cache 重建: {cache_path}"
                ) from exc
            if not isinstance(data, dict):
                raise RuntimeError(f"转写缓存格式无效: {cache_path}")
            return data
        return {}

    @classmethod
    def save_cache(cls, cache: Dict[str, Dict[str, Any]], cache_path: Path):
        """保存已转写的内容缓存"""
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_name = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=cache_path.parent,
                prefix=f".{cache_path.name}.",
                suffix=".tmp",
                delete=False,
            ) as tmp:
                json.dump(cache, tmp, ensure_ascii=False, indent=2)
                tmp.write("\n")
                tmp.flush()
                os.fsync(tmp.fileno())
                tmp_name = tmp.name
            os.replace(tmp_name, cache_path)
        finally:
            if tmp_name and os.path.exists(tmp_name):
                os.unlink(tmp_name)
