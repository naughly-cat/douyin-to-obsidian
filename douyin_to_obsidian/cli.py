# -*- coding: utf-8 -*-
"""
命令行交互入口 (CLI Interface)
==============================
提供便捷的终端命令操作：
1. douyin-to-obsidian url "分享文本或链接"   # 单链接/分享口令转录导出
2. douyin-to-obsidian batch                 # MediaCrawler 批量数据扫描与转写
3. douyin-to-obsidian file "本地音视频路径"   # 本地音视频文件直接转录
4. douyin-to-obsidian radar                 # 抖音爆款问题母题雷达
5. douyin-to-obsidian index                 # 仅刷新知识库全局双链索引
"""

import argparse
import sys
import time
from pathlib import Path

from .config import Config
from .core.analyzer import ContentAnalyzer
from .core.crawler_adapter import CrawlerAdapter
from .core.net import configure_tls
from .core.radar import ViralTopicRadar
from .core.parser import MediaParser
from .core.transcriber import Transcriber
from .exporters.obsidian import ObsidianExporter
from .exporters.radar import RadarExporter


def cmd_url(args, cfg: Config):
    """处理单个短视频/图文笔记链接"""
    raw_input = args.input
    print(f"[*] 解析输入内容: {raw_input[:60]}...")

    parser = MediaParser()
    try:
        item = parser.parse_share_content(raw_input)
    except Exception as e:
        print(f"[-] 链接解析失败: {e}")
        sys.exit(1)

    print(f"[+] 识别平台: {item.get('platform')}, 标题: {item.get('title')}, 作者: {item.get('author')}")

    audio_url = item.get("audio_url")
    transcript = ""
    hook_15s = ""
    segments = []

    if audio_url:
        print("[*] 正在拉取音频流并启动 Whisper 本地高精转写...")
        transcriber = Transcriber(model_name=cfg.whisper_model, cli_path=str(cfg.whisper_cli_path))
        res = transcriber.transcribe_url(audio_url)
        transcript = res.get("transcript", "")
        hook_15s = res.get("hook_15s", "")
        segments = res.get("segments", [])

    # 若无音频直链或转写为空（如小红书纯图文），提取正文
    if not transcript:
        desc = item.get("desc") or ""
        if desc:
            transcript = desc
            hook_15s = ContentAnalyzer.extract_hook(desc)
            print(f"[+] 纯图文笔记，直接提取正文 ({len(desc)} 字)")

    if not transcript:
        print("[-] 未能获取有效音频流或文本正文，停止导出。")
        sys.exit(1)

    item["transcript"] = transcript
    item["hook_15s"] = hook_15s
    item["segments"] = segments

    # 导出到 Obsidian
    exporter = ObsidianExporter(cfg.obsidian_dir)
    single_note = exporter.export_single_note(item)
    print(f"\n[+] 成功生成 Obsidian 单篇口播笔记: {single_note}")

    if args.aggregate:
        lib_file = exporter.export_aggregate_library([item])
        print(f"[+] 已同步写入汇总大库: {lib_file}")

    exporter.update_index_hub()

    print("\n" + "=" * 50)
    print(f"🎯 前15秒黄金钩子: {hook_15s}")
    print(f"🎙️ 口播全文 (前100字): {transcript[:100]}...")
    print("=" * 50)


def cmd_file(args, cfg: Config):
    """处理本地音视频文件"""
    file_path = Path(args.file).expanduser().resolve()
    if not file_path.exists():
        print(f"[-] 本地文件不存在: {file_path}")
        sys.exit(1)

    print(f"[*] 处理本地文件: {file_path}")
    transcriber = Transcriber(model_name=cfg.whisper_model, cli_path=str(cfg.whisper_cli_path))
    res = transcriber.transcribe_file(file_path)

    transcript = res.get("transcript", "")
    hook_15s = res.get("hook_15s", "")
    segments = res.get("segments", [])

    title = args.title or file_path.stem
    author = args.author or "本地录音"

    item = {
        "id": str(file_path),
        "platform": "local",
        "title": title,
        "author": author,
        "url": "",
        "transcript": transcript,
        "hook_15s": hook_15s,
        "segments": segments,
        "liked_count": 0,
        "share_count": 0,
        "comment_count": 0,
    }

    exporter = ObsidianExporter(cfg.obsidian_dir)
    target_note = exporter.export_single_note(item)
    print(f"[+] 已导出至 Obsidian 笔记: {target_note}")

    if args.aggregate:
        exporter.export_aggregate_library([item])

    exporter.update_index_hub()


def cmd_batch(args, cfg: Config):
    """批量从 MediaCrawler 数据目录加载并富化"""
    data_dir = Path(args.data_dir or cfg.mc_data_dir).expanduser().resolve()
    cache_file = cfg.obsidian_dir / ".transcripts_cache.json"

    print(f"[*] 扫描 MediaCrawler 数据目录: {data_dir} (最低赞数: {args.min_likes})")
    items = CrawlerAdapter.load_crawled_data(
        data_dir,
        platform=args.platform,
        min_likes=args.min_likes,
        date_filter=args.date,
    )
    print(f"[+] 找到符合条件作品共 {len(items)} 条")

    try:
        cache = {} if args.reset_cache else CrawlerAdapter.load_cache(cache_file)
    except RuntimeError as exc:
        print(f"[-] {exc}")
        sys.exit(1)
    print(f"[+] 已有转写缓存: {len(cache)} 条")

    transcriber = Transcriber(model_name=cfg.whisper_model, cli_path=str(cfg.whisper_cli_path))
    enriched_list = []
    processed = 0
    cache_changed = False

    for item in items:
        cid = item.get("id")
        if not cid:
            continue

        # 检查缓存
        if cid in cache:
            c_entry = cache[cid]
            item["transcript"] = c_entry.get("transcript", "")
            item["hook_15s"] = c_entry.get("hook_15s", "")
            enriched_list.append(item)
            continue
        elif item.get("transcript", "").strip():
            # 自带文本
            hook = item.get("hook_15s") or ContentAnalyzer.extract_hook(item["transcript"])
            item["hook_15s"] = hook
            cache[cid] = {
                "title": item["title"],
                "transcript": item["transcript"],
                "hook_15s": hook,
            }
            cache_changed = True
            enriched_list.append(item)
            continue

        if processed >= args.limit:
            print(f"[!] 达到单次处理上限 ({args.limit}条)，停止转写。")
            break

        print(f"\n[{processed + 1}/{args.limit}] 处理: {item['title'][:30]}...")
        audio_url = item.get("audio_url")
        transcript = ""
        hook_15s = ""

        if audio_url:
            try:
                res = transcriber.transcribe_url(audio_url)
                transcript = res.get("transcript", "")
                hook_15s = res.get("hook_15s", "")
            except Exception as e:
                print(f"    [-] 转写失败: {e}")

        if not transcript and item.get("desc"):
            transcript = item["desc"]
            hook_15s = ContentAnalyzer.extract_hook(item["desc"])
            print(f"    [+] 纯图文，提取正文 ({len(transcript)} 字)")

        if transcript:
            item["transcript"] = transcript
            item["hook_15s"] = hook_15s
            cache[cid] = {
                "title": item["title"],
                "author": item["author"],
                "transcript": transcript,
                "hook_15s": hook_15s,
                "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
            cache_changed = True
            enriched_list.append(item)
            processed += 1
            CrawlerAdapter.save_cache(cache, cache_file)
            cache_changed = False

    if cache_changed:
        CrawlerAdapter.save_cache(cache, cache_file)

    print(f"\n[+] 本轮完成，有效富化作品共 {len(enriched_list)} 条。")

    # 导出到 Obsidian
    exporter = ObsidianExporter(cfg.obsidian_dir)
    # 批量生成单篇笔记
    for itm in enriched_list:
        exporter.export_single_note(itm)

    lib_path = exporter.export_aggregate_library(enriched_list)
    print(f"[+] 汇总大库已更新: {lib_path}")

    hub_path = exporter.update_index_hub()
    print(f"[+] 全局索引已更新: {hub_path}")


def cmd_radar(args, cfg: Config):
    """从 MediaCrawler 数据构建 Douyin Viral Topic Radar。"""
    data_dir = Path(args.data_dir or cfg.mc_data_dir).expanduser().resolve()
    print(
        f"[*] 构建 Douyin Viral Topic Radar: {data_dir} "
        f"(窗口={args.window_days}天, 最低作者数={args.min_authors})"
    )

    # 雷达需要“普通作品 + 爆款作品”一起参与作者基线计算，
    # 所以默认 min_likes=0，不建议只喂高赞样本。
    items = CrawlerAdapter.load_crawled_data(
        data_dir,
        platform=args.platform,
        min_likes=args.min_likes,
        date_filter=args.date,
    )
    if not items:
        print("[-] 没有找到可用于雷达分析的作品数据。")
        sys.exit(1)

    # 如果此前 batch 已经转写过，复用缓存增强语义聚类；radar 本身不批量跑 ASR。
    cache_file = cfg.obsidian_dir / ".transcripts_cache.json"
    try:
        cache = CrawlerAdapter.load_cache(cache_file)
    except RuntimeError as exc:
        print(f"[-] {exc}")
        sys.exit(1)

    cache_hits = 0
    for item in items:
        cid = str(item.get("id") or "")
        cached = cache.get(cid)
        if not cached:
            continue
        if not item.get("transcript") and cached.get("transcript"):
            item["transcript"] = cached.get("transcript", "")
        if not item.get("hook_15s") and cached.get("hook_15s"):
            item["hook_15s"] = cached.get("hook_15s", "")
        cache_hits += 1

    comments = []
    if not args.no_comments:
        comments = CrawlerAdapter.load_comments(
            data_dir,
            platform=args.platform,
            date_filter=args.date,
        )

    creator_profiles = CrawlerAdapter.load_creator_profiles(
        data_dir,
        platform=args.platform,
    )

    radar = ViralTopicRadar(
        window_days=args.window_days,
        recent_days=args.recent_days,
        min_authors=args.min_authors,
    )
    report = radar.build(
        items,
        comments=comments,
        creator_profiles=creator_profiles,
        top_n=args.top,
    )

    exporter = RadarExporter(cfg.obsidian_dir)
    paths = exporter.export(report)
    ObsidianExporter(cfg.obsidian_dir).update_index_hub()

    print(f"[+] 视频样本: {report['sample_size']} 条；评论样本: {report['comment_sample_size']} 条")
    print(f"[+] 命中转写缓存: {cache_hits} 条")
    print(f"[+] 跨账号母题: {report['topic_count']} 个")
    print(f"[+] 雷达看板: {paths['markdown']}")
    print(f"[+] 结构化真源: {paths['json']}")

    topics = report.get("topics") or []
    if topics:
        print("\n=== Top Viral Mother Topics ===")
        for idx, topic in enumerate(topics[: min(10, len(topics))], 1):
            mult = topic.get("median_viral_multiplier")
            mult_text = "N/A" if mult is None else f"{mult:.1f}x"
            print(
                f"{idx:>2}. {topic['market_score']:>5.1f} | "
                f"{topic['mother_topic']} | "
                f"{topic['unique_authors']} authors | {mult_text}"
            )
    else:
        print("[!] 当前没有满足跨账号门槛的母题；优先扩大关键词/创作者/评论采样。")


def cmd_index(args, cfg: Config):
    """刷新知识库索引"""
    exporter = ObsidianExporter(cfg.obsidian_dir)
    hub_path = exporter.update_index_hub()
    print(f"[+] 全局索引已刷新: {hub_path}")


def main():
    # Windows CI/终端可能默认 cp1252，中文 help 会触发 UnicodeEncodeError。
    # 能 reconfigure 时统一为 UTF-8；不支持的流保持原状。
    for stream in (sys.stdout, sys.stderr):
        try:
            if hasattr(stream, "reconfigure"):
                stream.reconfigure(encoding="utf-8")
        except (AttributeError, OSError):
            pass

    # default=SUPPRESS：顶层与子命令共用参数时不互相覆盖，
    # 子命令未提供时保留顶层传入值（或最终缺失，由 getattr 兜底）
    common_parser = argparse.ArgumentParser(add_help=False)
    common_parser.add_argument(
        "--obsidian-dir",
        type=str,
        default=argparse.SUPPRESS,
        help="目标 Obsidian 知识库目录（默认读取环境变量 OBSIDIAN_VAULT_DIR 或 ~/Documents/Obsidian/...）",
    )
    common_parser.add_argument(
        "--model",
        type=str,
        choices=["tiny", "base", "small", "medium", "large-v3-turbo"],
        default=argparse.SUPPRESS,
        help="Whisper 模型规格 (tiny, base, small, medium, large-v3-turbo)",
    )
    common_parser.add_argument(
        "--insecure",
        action="store_true",
        default=argparse.SUPPRESS,
        help="证书校验失败时允许一次不安全重试（有中间人攻击风险，不建议常用）",
    )

    parser = argparse.ArgumentParser(
        prog="douyin-to-obsidian",
        description="抖音/小红书口播文案采集与 Obsidian 知识库双链导出工具",
        parents=[common_parser],
    )

    subparsers = parser.add_subparsers(dest="subcommand", help="子命令")

    # url 子命令
    p_url = subparsers.add_parser(
        "url", help="采集单个分享链接/文本并转录到 Obsidian", parents=[common_parser]
    )
    p_url.add_argument("input", type=str, help="抖音/小红书分享口令或直达 URL")
    p_url.add_argument("--aggregate", action="store_true", help="同时写入汇总大库")

    # batch 子命令
    p_batch = subparsers.add_parser(
        "batch", help="从 MediaCrawler 抓取目录批量扫描与转写", parents=[common_parser]
    )
    p_batch.add_argument("--data-dir", type=str, default=None, help="MediaCrawler 数据目录")
    p_batch.add_argument(
        "--platform", type=str, default="all", choices=["all", "dy", "xhs", "douyin", "xiaohongshu"]
    )
    p_batch.add_argument("--min-likes", type=int, default=500, help="最低点赞门槛")
    p_batch.add_argument("--limit", type=int, default=30, help="单次最多转写条数")
    p_batch.add_argument("--date", type=str, default=None, help="指定日期批次 (如 2026-09-20)")
    p_batch.add_argument("--reset-cache", action="store_true", help="重置已有转写缓存")

    # radar 子命令
    p_radar = subparsers.add_parser(
        "radar",
        help="从 MediaCrawler 数据识别跨账号爆款问题母题",
        parents=[common_parser],
    )
    p_radar.add_argument("--data-dir", type=str, default=None, help="MediaCrawler 数据目录")
    p_radar.add_argument(
        "--platform",
        type=str,
        default="dy",
        choices=["dy", "douyin", "xhs", "xiaohongshu", "all"],
        help="默认分析抖音；也可用于小红书或混合样本",
    )
    p_radar.add_argument(
        "--min-likes",
        type=int,
        default=0,
        help="进入作者基线计算的最低点赞；默认0，避免只分析已爆作品造成基线失真",
    )
    p_radar.add_argument("--window-days", type=int, default=30, help="母题观察窗口，默认30天")
    p_radar.add_argument("--recent-days", type=int, default=7, help="短周期热度窗口，默认7天")
    p_radar.add_argument("--min-authors", type=int, default=2, help="进入母题榜的最少独立作者数")
    p_radar.add_argument("--top", type=int, default=20, help="最多输出母题数量")
    p_radar.add_argument("--date", type=str, default=None, help="可选：只扫描文件名包含该日期的批次")
    p_radar.add_argument("--no-comments", action="store_true", help="不读取评论数据（评论需求维度将不可用）")

    # file 子命令
    p_file = subparsers.add_parser(
        "file", help="转录本地音视频文件并导出到 Obsidian", parents=[common_parser]
    )
    p_file.add_argument("file", type=str, help="本地音视频文件路径 (.mp4, .mp3, .wav 等)")
    p_file.add_argument("--title", type=str, default=None, help="指定笔记标题")
    p_file.add_argument("--author", type=str, default=None, help="指定创作者名称")
    p_file.add_argument("--aggregate", action="store_true", help="同时写入汇总大库")

    # index 子命令
    subparsers.add_parser("index", help="刷新 Obsidian 知识库索引", parents=[common_parser])

    args = parser.parse_args()

    configure_tls(allow_insecure=getattr(args, "insecure", False))

    cfg = Config(
        obsidian_dir=getattr(args, "obsidian_dir", None),
        whisper_model=getattr(args, "model", Config.DEFAULT_WHISPER_MODEL),
    )

    if args.subcommand == "url":
        cmd_url(args, cfg)
    elif args.subcommand == "batch":
        cmd_batch(args, cfg)
    elif args.subcommand == "file":
        cmd_file(args, cfg)
    elif args.subcommand == "radar":
        cmd_radar(args, cfg)
    elif args.subcommand == "index":
        cmd_index(args, cfg)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
