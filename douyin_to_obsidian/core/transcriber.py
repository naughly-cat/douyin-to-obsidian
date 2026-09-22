# -*- coding: utf-8 -*-
"""
语音识别转写引擎 (Whisper ASR Engine)
=====================================
- 默认支持 Apple Silicon (Metal GPU) 加速的 whisper-cli
- 自动从国内高速镜像源 (ModelScope) 自动下载并缓存 ggml 语音模型
- 自动处理音视频提取、防盗链 Referer 请求头注入与 16kHz PCM 转码
- 支持 fallback 模式（若未安装 whisper-cli 则支持 faster-whisper 或友好提示）
"""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..config import Config
from .net import urlopen_verified


def _sha256_of(path: Path) -> str:
    """流式计算文件 SHA256"""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _download_to(url: str, temp_path: Path, timeout: int = 60) -> None:
    """从指定 URL 下载文件到临时路径（含进度显示），失败抛异常"""
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"},
    )
    with urlopen_verified(req, timeout=timeout) as resp, open(temp_path, "wb") as f:
        total_size = int(resp.headers.get("Content-Length", 0))
        downloaded = 0
        chunk_size = 1024 * 1024
        while True:
            chunk = resp.read(chunk_size)
            if not chunk:
                break
            f.write(chunk)
            downloaded += len(chunk)
            if total_size > 0:
                pct = (downloaded / total_size) * 100
                mb_cur = downloaded // (1024 * 1024)
                mb_tot = total_size // (1024 * 1024)
                sys.stdout.write(f"\r[*] 模型下载进度: {pct:.1f}% ({mb_cur}MB / {mb_tot}MB)")
                sys.stdout.flush()
    sys.stdout.write("\n")


def ensure_model(model_name: str = "base", cache_dir: Optional[Path] = None) -> Path:
    """
    确保本地存在指定的 ggml 模型文件：
    - 已缓存模型先做 SHA256 完整性校验，不符则重新下载
    - 优先国内 ModelScope 镜像源，失败自动回退 whisper.cpp 官方源
    - 下载完成后强制校验内置校验和，不符即丢弃并尝试下一来源
    """
    cache_path = cache_dir or Config.DEFAULT_WHISPER_CACHE
    model_filename = f"ggml-{model_name}.bin"
    if model_filename not in Config.MODEL_SHA256:
        supported = ", ".join(
            name.removeprefix("ggml-").removesuffix(".bin")
            for name in Config.MODEL_SHA256
        )
        raise ValueError(f"不支持或未校验的 Whisper 模型: {model_name}；可选: {supported}")
    cache_path.mkdir(parents=True, exist_ok=True)
    model_file = cache_path / model_filename
    expected_sha = Config.MODEL_SHA256.get(model_filename)

    if model_file.exists() and model_file.stat().st_size > 10 * 1024 * 1024:
        print("[*] 校验已缓存模型完整性...")
        if _sha256_of(model_file) == expected_sha:
            return model_file
        print("[!] 缓存模型校验和不符，将删除并重新下载。")
        model_file.unlink()

    sources = [
        f"{Config.MODELSCOPE_WHISPER_URL}/{model_filename}",
        Config.OFFICIAL_WHISPER_URL.format(filename=model_filename),
    ]
    last_err: Optional[Exception] = None
    for url in sources:
        temp_path = model_file.with_suffix(".tmp")
        print(f"[*] 正在下载 Whisper 模型 {model_filename} ...\n    来源: {url}")
        try:
            _download_to(url, temp_path)
            actual_sha = _sha256_of(temp_path)
            if actual_sha != expected_sha:
                raise RuntimeError(
                    f"下载文件 SHA256 校验不符（实际 {actual_sha[:16]}...），已丢弃。"
                )
            print("[+] SHA256 校验通过")
            temp_path.rename(model_file)
            print(f"[+] Whisper 模型 {model_filename} 已就绪: {model_file}")
            return model_file
        except Exception as e:
            last_err = e
            print(f"[-] 该来源下载失败: {e}")
            if temp_path.exists():
                temp_path.unlink()
    raise RuntimeError(f"Whisper 模型下载失败（已尝试全部来源）: {last_err}")


def download_media_stream(url: str, dest_path: Path, timeout: int = 20) -> bool:
    """
    下载媒体流，根据目标域名自动注入平台防盗链 Referer 请求头。
    """
    if not url:
        return False

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        ),
    }

    url_lower = url.lower()
    if "douyin" in url_lower or "aweme" in url_lower:
        headers["Referer"] = "https://www.douyin.com/"
    elif "xiaohongshu" in url_lower or "xhs" in url_lower:
        headers["Referer"] = "https://www.xiaohongshu.com/"
    elif "bilibili" in url_lower:
        headers["Referer"] = "https://www.bilibili.com/"

    req = urllib.request.Request(url, headers=headers)
    try:
        with urlopen_verified(req, timeout=timeout) as resp, open(
            dest_path, "wb"
        ) as f:
            shutil.copyfileobj(resp, f)
        return dest_path.exists() and dest_path.stat().st_size > 1024
    except Exception as e:
        print(f"[-] 下载音频流失败: {e} (URL: {url[:60]}...)")
        return False


def convert_to_wav(input_path: Path, output_path: Path) -> bool:
    """
    调用 ffmpeg 提取音频并重采样为标准 16kHz 16-bit 单声道 PCM WAV。
    """
    ffmpeg_bin = shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg"
    if not Path(ffmpeg_bin).exists():
        return False

    cmd = [
        str(ffmpeg_bin),
        "-y",
        "-i",
        str(input_path),
        "-ar",
        "16000",
        "-ac",
        "1",
        "-c:a",
        "pcm_s16le",
        str(output_path),
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, timeout=60)
        return (
            res.returncode == 0
            and output_path.exists()
            and output_path.stat().st_size > 1024
        )
    except Exception as e:
        print(f"[-] ffmpeg 转码异常: {e}")
        return False


class Transcriber:
    """语音识别与台词转写器"""

    def __init__(
        self,
        model_name: str = "base",
        cli_path: Optional[str] = None,
        cache_dir: Optional[Path] = None,
        timeout: Optional[int] = None,
    ):
        self.model_name = model_name
        self.cli_path = (
            Path(cli_path).resolve()
            if cli_path
            else Path(shutil.which("whisper-cli") or Config.DEFAULT_WHISPER_CLI_PATH)
        )
        self.cache_dir = cache_dir or Config.DEFAULT_WHISPER_CACHE
        # whisper 子进程超时（秒）：可传参或环境变量 D2O_WHISPER_TIMEOUT，长视频建议调大
        if timeout is not None:
            self.timeout = int(timeout)
        else:
            try:
                self.timeout = int(os.getenv("D2O_WHISPER_TIMEOUT", "120"))
            except ValueError:
                self.timeout = 120
        if self.timeout <= 0:
            self.timeout = 120

    def is_cli_available(self) -> bool:
        """检查本机是否存在 whisper-cli 可执行文件"""
        return self.cli_path.exists() and os.access(self.cli_path, os.X_OK)

    def transcribe_wav_file(
        self, wav_path: Path, language: str = "zh"
    ) -> Dict[str, Any]:
        """
        核心转写方法：输入 16kHz WAV 音频文件，调用 Whisper 转录并解析时间戳与台词。
        """
        if not self.is_cli_available():
            # 尝试使用 faster-whisper Python 库降级执行
            return self._transcribe_fallback(wav_path, language=language)

        model_path = ensure_model(self.model_name, self.cache_dir)

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_prefix = Path(tmp_dir) / "transcription"
            cmd = [
                str(self.cli_path),
                "-m",
                str(model_path),
                "-l",
                language,
                "-f",
                str(wav_path),
                "-otxt",
                "-oj",
                "-of",
                str(output_prefix),
                "-np",
            ]

            try:
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=self.timeout)
                if res.returncode != 0:
                    print(f"[-] whisper-cli 执行返回非零状态: {res.stderr}")
                    return {"transcript": "", "hook_15s": "", "segments": []}

                txt_file = output_prefix.with_suffix(".txt")
                json_file = output_prefix.with_suffix(".json")

                full_text = ""
                if txt_file.exists():
                    full_text = txt_file.read_text(encoding="utf-8").strip()

                segments: List[Dict[str, Any]] = []
                hook_15s_texts: List[str] = []

                if json_file.exists():
                    try:
                        data = json.loads(json_file.read_text(encoding="utf-8"))
                        for seg in data.get("transcription", []):
                            ts = seg.get("timestamps", {})
                            t_from = ts.get("from", "00:00:00,000")
                            t_to = ts.get("to", "00:00:00,000")
                            txt = seg.get("text", "").strip()

                            # 计算前15秒钩子文案
                            try:
                                parts = t_from.replace(",", ".").split(":")
                                sec_from = (
                                    float(parts[0]) * 3600
                                    + float(parts[1]) * 60
                                    + float(parts[2])
                                )
                            except Exception:
                                sec_from = 0.0

                            segments.append(
                                {
                                    "from": t_from,
                                    "to": t_to,
                                    "text": txt,
                                }
                            )

                            if sec_from <= 15.0 and txt:
                                hook_15s_texts.append(txt)
                    except Exception as e:
                        print(f"[-] 解析 Whisper JSON 字幕失败: {e}")

                hook_15s = (
                    " ".join(hook_15s_texts)
                    if hook_15s_texts
                    else (full_text[:60] if full_text else "")
                )

                return {
                    "transcript": full_text,
                    "hook_15s": hook_15s,
                    "segments": segments,
                }
            except Exception as e:
                print(f"[-] whisper-cli 转录异常: {e}")
                return {"transcript": "", "hook_15s": "", "segments": []}

    def _transcribe_fallback(
        self, wav_path: Path, language: str = "zh"
    ) -> Dict[str, Any]:
        """
        若未安装 whisper-cli 时尝试通过 Python 第三方库降级
        """
        try:
            from faster_whisper import WhisperModel

            print("[*] 检测到未安装 whisper-cli，使用 faster-whisper 进行降级转录...")
            model = WhisperModel(self.model_name, device="auto", compute_type="default")
            segs, _ = model.transcribe(str(wav_path), language=language)

            segments = []
            hook_15s_texts = []
            full_texts = []

            for s in segs:
                txt = s.text.strip()
                if txt:
                    full_texts.append(txt)
                    segments.append(
                        {
                            "from": f"{s.start:.2f}s",
                            "to": f"{s.end:.2f}s",
                            "text": txt,
                        }
                    )
                    if s.start <= 15.0:
                        hook_15s_texts.append(txt)

            full_text = " ".join(full_texts)
            hook_15s = (
                " ".join(hook_15s_texts)
                if hook_15s_texts
                else (full_text[:60] if full_text else "")
            )
            return {
                "transcript": full_text,
                "hook_15s": hook_15s,
                "segments": segments,
            }
        except ImportError:
            raise FileNotFoundError(
                f"未检测到 whisper-cli ({self.cli_path})，且未安装 faster-whisper。\n"
                "推荐安装 whisper-cpp (macOS 可直接执行: brew install whisper-cpp)，\n"
                "或执行: pip install faster-whisper 以使用 Python 降级引擎。"
            )

    def transcribe_file(self, media_path: Path) -> Dict[str, Any]:
        """
        输入任意音视频文件（.mp4 / .mp3 / .wav / .m4a），先转为 16kHz WAV 再转录。
        """
        media_path = Path(media_path).resolve()
        if not media_path.exists():
            raise FileNotFoundError(f"媒体文件不存在: {media_path}")

        with tempfile.TemporaryDirectory() as tmp_dir:
            wav_path = Path(tmp_dir) / "converted.wav"
            if not convert_to_wav(media_path, wav_path):
                # 如果转码失败且自身就是 wav，尝试直接转录
                if media_path.suffix.lower() == ".wav":
                    wav_path = media_path
                else:
                    raise RuntimeError(f"ffmpeg 无法转码音频: {media_path}")

            return self.transcribe_wav_file(wav_path)

    def transcribe_url(self, media_url: str) -> Dict[str, Any]:
        """
        从音视频直链下载媒体流并完成转录。
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            raw_media = Path(tmp_dir) / "downloaded.media"
            ok = download_media_stream(media_url, raw_media)
            if not ok:
                return {"transcript": "", "hook_15s": "", "segments": []}

            return self.transcribe_file(raw_media)
