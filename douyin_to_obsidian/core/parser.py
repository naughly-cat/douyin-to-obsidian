# -*- coding: utf-8 -*-
"""
链接提取与轻量媒体解析器 (Media Parser)
=====================================
- 从用户粘贴的包含文本、表情符号的分享文本中智能提取实际链接
- 支持抖音 (v.douyin.com / douyin.com/video/...)
- 支持小红书 (xhslink.com / xiaohongshu.com/explore/...)
- 支持解析 302 重定向与获取无水印音视频直链
"""

import json
import re
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional, Tuple

from .net import urlopen_verified


class MediaParser:
    """抖音/小红书分享文本与直链解析器"""

    URL_PATTERN = re.compile(r"https?://[^\s\u4e00-\u9fa5]+")

    USER_AGENT = (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1"
    )

    @classmethod
    def extract_url(cls, text: str) -> Optional[str]:
        """从杂乱的分享口令或文本中提取纯净的 HTTP/HTTPS 链接"""
        if not text:
            return None
        match = cls.URL_PATTERN.search(text)
        if match:
            return match.group(0).strip()
        return None

    @classmethod
    def identify_platform(cls, url: str) -> str:
        """根据 URL 判断目标社媒平台"""
        url_lower = url.lower()
        if "douyin" in url_lower or "iesdouyin" in url_lower:
            return "douyin"
        elif "xhslink" in url_lower or "xiaohongshu" in url_lower:
            return "xiaohongshu"
        elif "bilibili" in url_lower or "b23.tv" in url_lower:
            return "bilibili"
        return "unknown"

    @classmethod
    def resolve_redirect(cls, url: str) -> str:
        """追踪 301/302 重定向获得真实落地地址"""
        req = urllib.request.Request(url, headers={"User-Agent": cls.USER_AGENT})
        try:
            with urlopen_verified(req, timeout=10) as resp:
                return resp.geturl()
        except Exception:
            return url

    @classmethod
    def parse_share_content(cls, raw_input: str) -> Dict[str, Any]:
        """
        解析用户输入（分享文本或单链接），尝试解析基础元信息与媒体直链。
        """
        raw_url = cls.extract_url(raw_input)
        if not raw_url:
            raise ValueError(f"无法在输入文本中找到有效 URL: {raw_input}")

        platform = cls.identify_platform(raw_url)
        real_url = cls.resolve_redirect(raw_url)

        if platform == "douyin":
            return cls._parse_douyin(real_url, raw_input)
        elif platform == "xiaohongshu":
            return cls._parse_xiaohongshu(real_url, raw_input)
        else:
            return {
                "id": raw_url,
                "platform": platform,
                "title": raw_input.replace(raw_url, "").strip() or "未命名分享内容",
                "author": "未知创作者",
                "url": real_url,
                "audio_url": "",
                "video_url": "",
                "desc": raw_input,
                "liked_count": 0,
            }

    @classmethod
    def _parse_douyin(cls, real_url: str, raw_input: str) -> Dict[str, Any]:
        """解析抖音真实落地地址"""
        # 尝试从 URL 提取 video_id
        # 例如: https://www.douyin.com/video/7412345678901234567
        video_id_match = re.search(r"/(?:video|note)/(\d+)", real_url)
        video_id = video_id_match.group(1) if video_id_match else ""

        # 尝试拉取落地页 HTML 提取预渲染的 _ROUTER_DATA 或视频直链
        title = ""
        author = ""
        audio_url = ""
        video_url = ""
        likes = 0

        # 从原始文本中清洗标题
        clean_text = raw_input.replace(cls.extract_url(raw_input) or "", "")
        # 清除常见的 "7.12 复制打开抖音，看看【xxx的作品】" 格式
        title_match = re.search(r"【(.*?)的作品】(.*)", clean_text)
        if title_match:
            author = title_match.group(1).strip()
            title = title_match.group(2).strip()
        else:
            title = clean_text.strip()[:60]

        req = urllib.request.Request(
            real_url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
                ),
                "Referer": "https://www.douyin.com/",
            },
        )
        try:
            with urlopen_verified(req, timeout=10) as resp:
                html = resp.read().decode("utf-8", errors="ignore")

                # 匹配标题
                t_match = re.search(r"<title>(.*?)</title>", html)
                if t_match and not title:
                    title = t_match.group(1).replace(" - 抖音", "").strip()

                # 匹配音视频直链
                # 抖音网页中包含 play_addr 或 src="https://...aweme/v1/playwm/..."
                play_urls = re.findall(
                    r'https://[a-zA-Z0-9.-]+\.douyinvod\.com/[a-zA-Z0-9/._-]+', html
                )
                if play_urls:
                    video_url = play_urls[0]
                    audio_url = play_urls[0]
        except Exception:
            pass

        return {
            "id": video_id or real_url,
            "platform": "douyin",
            "title": title or "抖音短视频",
            "author": author or "抖音创作者",
            "url": real_url,
            "audio_url": audio_url,
            "video_url": video_url,
            "desc": title,
            "liked_count": likes,
        }

    @classmethod
    def _parse_xiaohongshu(cls, real_url: str, raw_input: str) -> Dict[str, Any]:
        """解析小红书真实落地地址"""
        # 例如: https://www.xiaohongshu.com/explore/66e...
        note_id_match = re.search(r"/(?:explore|discovery/item)/([a-zA-Z0-9]+)", real_url)
        note_id = note_id_match.group(1) if note_id_match else ""

        clean_text = raw_input.replace(cls.extract_url(raw_input) or "", "").strip()
        title = clean_text[:50]
        author = "小红书创作者"

        # 尝试匹配 【标题】 作者 发布了一篇小红书笔记
        m = re.search(r"【(.*?)】\s*(.*?)\s*发布了一篇小红书笔记", clean_text)
        if m:
            title = m.group(1).strip()
            author = m.group(2).strip()

        desc = clean_text

        # 尝试拉取落地页 HTML 提取 initial-state
        req = urllib.request.Request(
            real_url,
            headers={
                "User-Agent": cls.USER_AGENT,
                "Referer": "https://www.xiaohongshu.com/",
            },
        )
        video_url = ""
        try:
            with urlopen_verified(req, timeout=10) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
                state_match = re.search(r"window\.__INITIAL_STATE__\s*=\s*({.*?});</script>", html)
                if state_match:
                    try:
                        state = json.loads(state_match.group(1).replace("undefined", "null"))
                        note_data = state.get("note", {}).get("noteDetailMap", {}).get(note_id, {}).get("note", {})
                        if note_data:
                            title = note_data.get("title") or title
                            desc = note_data.get("desc") or desc
                            author = note_data.get("user", {}).get("nickname") or author
                            # 如果是视频笔记
                            video_info = note_data.get("video", {})
                            if video_info:
                                media = video_info.get("media", {})
                                stream = media.get("stream", {}).get("h264", [])
                                if stream:
                                    video_url = stream[0].get("masterUrl", "")
                    except Exception:
                        pass
        except Exception:
            pass

        return {
            "id": note_id or real_url,
            "platform": "xiaohongshu",
            "title": title or "小红书笔记",
            "author": author,
            "url": real_url,
            "audio_url": video_url,
            "video_url": video_url,
            "desc": desc,
            "liked_count": 0,
        }
