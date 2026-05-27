from __future__ import annotations

import html
import json
import math
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from urllib.parse import quote


ROOT = Path.cwd()
OUTPUT = ROOT / "index.html"
BLESSINGS_FILE = ROOT / "blessings.json"
SOURCE_PATTERN = re.compile(r"^@?(?P<author>[^_]+)_(?P<date>\d{8})_(?P<title>.+?)\.(?P<ext>mp4|mp3|webp)$")
TRAILING_INDEX_PATTERN = re.compile(r"_(\d+)$")

THEME_KEYWORDS = {
    "猫咪": ["猫", "喵", "狸花", "流浪猫", "奶喵", "小黑猫", "三花"],
    "旅行": ["旅行", "青岛", "三亚", "迪士尼", "丽江", "云南", "桂林", "阳朔", "西双版纳", "玉龙雪山", "上海", "川西", "泰山", "西昌", "乐山"],
    "日常": ["日常", "生活", "碎片", "回忆", "幸福", "平淡", "生日", "过冬"],
    "美食": ["吃", "干饭", "美食", "香的勒", "鱼", "饭"],
    "节日": ["元宵", "烟花", "龙行", "年度", "金牛座", "大年初一", "春风有信"],
    "音乐": ["音乐", "solo", "街头", "蓝莲花"],
    "工作": ["求职", "招聘", "打工", "就业"],
    "玩具": ["泡泡玛特", "拉布布", "娃娃"],
}

THEME_ORDER = ["猫咪", "旅行", "日常", "美食", "节日", "音乐", "工作", "玩具"]
MONTH_NAMES = {
    1: "Jan",
    2: "Feb",
    3: "Mar",
    4: "Apr",
    5: "May",
    6: "Jun",
    7: "Jul",
    8: "Aug",
    9: "Sep",
    10: "Oct",
    11: "Nov",
    12: "Dec",
}


def normalize_story_key(stem: str) -> str:
    return TRAILING_INDEX_PATTERN.sub("", stem)


def clean_title(raw_title: str) -> str:
    title = TRAILING_INDEX_PATTERN.sub("", raw_title)
    title = title.replace("...", " ")
    parts = [part.strip() for part in title.split("_")]
    parts = [part for part in parts if part]
    if not parts:
        return title.strip() or "未命名记录"
    return " · ".join(parts)


def excerpt_from_title(title: str) -> str:
    pieces = [part.strip() for part in title.replace("...", " ").split("_") if part.strip()]
    if not pieces:
        return "一则被保存下来的生活片段。"
    if len(pieces) == 1:
        return f"{pieces[0]}。"
    return "，".join(pieces[: min(4, len(pieces))]) + "。"


def infer_themes(text: str) -> list[str]:
    matches: list[str] = []
    for theme, keywords in THEME_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            matches.append(theme)
    if not matches:
        matches.append("日常")
    return matches


def format_size(num_bytes: int) -> str:
    if num_bytes <= 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB"]
    power = min(int(math.log(num_bytes, 1024)), len(units) - 1)
    value = num_bytes / (1024**power)
    return f"{value:.1f} {units[power]}"


def to_asset_url(filename: str) -> str:
    return quote(filename, safe="@-_.()~/")


def read_posts() -> list[dict]:
    grouped: dict[str, dict] = {}

    for path in ROOT.iterdir():
        if not path.is_file():
            continue
        match = SOURCE_PATTERN.match(path.name)
        if not match:
            continue

        info = match.groupdict()
        story_key = normalize_story_key(path.stem)
        record = grouped.setdefault(
            story_key,
            {
                "author": info["author"],
                "date": info["date"],
                "raw_title": info["title"],
                "files": [],
            },
        )
        record["files"].append(
            {
                "name": path.name,
                "ext": info["ext"],
                "size": path.stat().st_size,
            }
        )

    posts: list[dict] = []
    for record in grouped.values():
        dt = datetime.strptime(record["date"], "%Y%m%d")
        files = sorted(record["files"], key=lambda item: (item["ext"], item["name"]))
        video_files = [item["name"] for item in files if item["ext"] == "mp4"]
        audio_files = [item["name"] for item in files if item["ext"] == "mp3"]
        image_files = [item["name"] for item in files if item["ext"] == "webp"]
        title = clean_title(record["raw_title"])
        themes = infer_themes(title)
        cover = image_files[0] if image_files else (video_files[0] if video_files else "")
        cover_type = "image" if image_files else ("video" if video_files else "none")
        media_count = len(video_files) + len(audio_files) + len(image_files)

        posts.append(
            {
                "title": title,
                "rawTitle": record["raw_title"],
                "date": record["date"],
                "displayDate": dt.strftime("%Y.%m.%d"),
                "year": str(dt.year),
                "month": MONTH_NAMES[dt.month],
                "day": dt.day,
                "timestamp": int(dt.timestamp()),
                "excerpt": excerpt_from_title(record["raw_title"]),
                "themes": themes,
                "cover": cover,
                "coverType": cover_type,
                "coverUrl": to_asset_url(cover) if cover else "",
                "videos": video_files,
                "audios": audio_files,
                "images": image_files,
                "videoUrls": [to_asset_url(name) for name in video_files],
                "audioUrls": [to_asset_url(name) for name in audio_files],
                "imageUrls": [to_asset_url(name) for name in image_files],
                "counts": {
                    "video": len(video_files),
                    "audio": len(audio_files),
                    "image": len(image_files),
                    "media": media_count,
                },
                "size": format_size(sum(item["size"] for item in files)),
            }
        )

    posts.sort(key=lambda item: item["date"], reverse=True)
    return posts


def build_summary(posts: list[dict]) -> dict:
    years = Counter(post["year"] for post in posts)
    themes = Counter(theme for post in posts for theme in post["themes"])
    total_videos = sum(post["counts"]["video"] for post in posts)
    total_audios = sum(post["counts"]["audio"] for post in posts)
    total_images = sum(post["counts"]["image"] for post in posts)

    featured = posts[:3]
    busiest_year = max(years.items(), key=lambda item: item[1])[0] if years else ""
    top_theme = max(themes.items(), key=lambda item: item[1])[0] if themes else "日常"

    return {
        "stats": {
            "stories": len(posts),
            "videos": total_videos,
            "audios": total_audios,
            "images": total_images,
        },
        "years": [{"year": year, "count": years[year]} for year in sorted(years.keys(), reverse=True)],
        "themes": [{"name": name, "count": themes[name]} for name in THEME_ORDER if themes[name] > 0],
        "featured": featured,
        "busiestYear": busiest_year,
        "topTheme": top_theme,
    }


def load_blessings() -> dict:
    default_items = [
        {
            "type": "letter",
            "lang": "zh",
            "title": "写给翻到这一页的人",
            "body": "这不是一份冷冰冰的文件清单，而是一册会呼吸的生活手账。\n愿你每次点开它，都能重新看见那些风、光、猫咪、城市和认真生活过的瞬间。",
            "quote": "把日子过得具体一点，回忆就会有温度。",
            "author": "本地书信",
            "source": "local",
        },
        {
            "type": "letter",
            "lang": "zh",
            "title": "把路上的风留给你",
            "body": "旅行的意义不一定是抵达远方，也可能是把一个普通下午过得更开阔。\n那些车窗外掠过的树影、突然亮起来的街灯、路边随手拍下的云，都会在多年以后替你作证。",
            "quote": "走过的路不会消失，它会悄悄变成你的语气。",
            "author": "本地书信",
            "source": "local",
        },
        {
            "type": "letter",
            "lang": "zh",
            "title": "关于小猫和陪伴",
            "body": "镜头里的小猫总是把时间变慢：一顿饭、一场午睡、一次笨拙的奔跑，都像生活伸出的柔软小手。\n你记录它们，其实也是在记录自己怎样被日常温柔地接住。",
            "quote": "陪伴不是宏大的词，它常常只是准时出现。",
            "author": "本地书信",
            "source": "local",
        },
        {
            "type": "letter",
            "lang": "zh",
            "title": "城市会替你保存心情",
            "body": "每座城市都有自己的光线。上海的热闹、青岛的雾、丽江的风、成都的慢，都被你放进了这些影像里。\n等以后再看，地点会先回来，然后是当时的天气、心跳和身边的人。",
            "quote": "城市不是背景，它是回忆的共同作者。",
            "author": "本地书信",
            "source": "local",
        },
        {
            "type": "letter",
            "lang": "zh",
            "title": "给未来的你",
            "body": "如果未来某天你觉得生活有些模糊，就回来翻一翻这些片段。\n你会发现自己曾经那么鲜明地笑过、走过、期待过，也曾经把普通一天认真保存成礼物。",
            "quote": "不要急着成为答案，先好好成为自己。",
            "author": "本地书信",
            "source": "local",
        },
        {
            "type": "letter",
            "lang": "zh",
            "title": "留给周末的一封信",
            "body": "愿你拥有一些不被催促的时间：慢慢吃饭，慢慢散步，慢慢把相册从头翻到尾。\n人需要这样的小空白，才能把心里的褶皱舒展开。",
            "quote": "松弛不是浪费，它是在给热爱续航。",
            "author": "本地书信",
            "source": "local",
        },
        {
            "type": "letter",
            "lang": "zh",
            "title": "雨天也值得被收藏",
            "body": "不是每段记录都要晴空万里。大雾、雨声、临时改变的计划，也会让故事变得更真实。\n那些不完美的天气，往往最能显出一个人继续出发的兴致。",
            "quote": "生活不总是发光，但它一直在发生。",
            "author": "本地书信",
            "source": "local",
        },
        {
            "type": "letter",
            "lang": "zh",
            "title": "生日与烟花",
            "body": "生日、节日和烟花都很短，可它们会把某一晚照得特别清楚。\n愿你年年都有新的愿望，也年年保留一点孩子气，继续相信热闹和浪漫。",
            "quote": "愿每一次庆祝，都不是为了证明什么，只是因为值得。",
            "author": "本地书信",
            "source": "local",
        },
        {
            "type": "letter",
            "lang": "en",
            "title": "A Small Note",
            "body": "Keep the tiny scenes. The soft light, the unfinished laugh, the road after rain.\nOne day, these fragments will become a map back to yourself.",
            "quote": "Memory grows clearer when it is held with care.",
            "author": "Local note",
            "source": "local",
        },
        {
            "type": "letter",
            "lang": "ja",
            "title": "小さな手紙",
            "body": "今日の光を、少しだけ残しておきましょう。\n等很久以后再回头，这些安静的小片段也会轻轻说：你来过，你爱过，你好好生活过。",
            "quote": "たいせつな日々は、静かに心に残る。",
            "author": "Local note",
            "source": "local",
        },
    ]
    if not BLESSINGS_FILE.exists():
        return {"updated_at": "", "items": default_items}
    try:
        data = json.loads(BLESSINGS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"updated_at": "", "items": default_items}
    items = data.get("items") or default_items
    return {
        "updated_at": data.get("updated_at", ""),
        "items": items,
    }


def render_html(posts: list[dict], summary: dict) -> str:
    payload = json.dumps({"posts": posts, "summary": summary, "blessings": load_blessings()}, ensure_ascii=False)
    featured = summary["featured"]

    def esc(value: str) -> str:
        return html.escape(value, quote=True)

    hero_cards = []
    for item in featured:
        thumb = esc(item["coverUrl"])
        title = esc(item["title"])
        desc = esc(item["excerpt"])
        fallback_payload = esc(
            json.dumps(
                {
                    "images": item["imageUrls"],
                    "videos": item["videoUrls"],
                    "title": item["title"],
                },
                ensure_ascii=False,
            )
        )
        thumb_markup = (
            f'<img src="{thumb}" alt="{title}" loading="lazy" data-fallback-media="{fallback_payload}" data-placeholder-text="封面加载失败">'
            if item["coverType"] == "image"
            else f'<video muted playsinline preload="metadata" src="{thumb}"></video>'
        )
        hero_cards.append(
            f"""
            <article class="hero-card" data-open-title="{title}">
              <div class="hero-thumb">
                {thumb_markup}
              </div>
              <div class="hero-copy">
                <p class="eyebrow">{esc(item["displayDate"])}</p>
                <h3>{title}</h3>
                <p>{desc}</p>
              </div>
            </article>
            """
        )

    hero_spot = featured[0] if featured else None
    hero_spot_markup = ""
    if hero_spot:
        hero_spot_title = esc(hero_spot["title"])
        hero_spot_cover = esc(hero_spot["coverUrl"])
        hero_spot_fallback = esc(
            json.dumps(
                {
                    "images": hero_spot["imageUrls"],
                    "videos": hero_spot["videoUrls"],
                    "title": hero_spot["title"],
                },
                ensure_ascii=False,
            )
        )
        hero_spot_media = (
            f'<img src="{hero_spot_cover}" alt="{hero_spot_title}" loading="lazy" data-fallback-media="{hero_spot_fallback}" data-placeholder-text="首屏封面加载失败">'
            if hero_spot["coverType"] == "image"
            else f'<video muted playsinline autoplay loop preload="metadata" src="{hero_spot_cover}"></video>'
        )
        hero_spot_markup = f"""
          <div class="hero-stage-card" data-open-title="{hero_spot_title}">
            <div class="hero-stage-media">
              {hero_spot_media}
            </div>
            <div class="hero-stage-copy">
              <p class="eyebrow">{esc(hero_spot["displayDate"])} · {esc(" · ".join(hero_spot["themes"]))}</p>
              <h3>{hero_spot_title}</h3>
              <p>{esc(hero_spot["excerpt"])}</p>
            </div>
          </div>
        """

    year_links = []
    for year in summary["years"]:
        year_links.append(
            f'<button class="year-pill" type="button" data-year-filter="{esc(year["year"])}">{esc(year["year"])} <span>{year["count"]}</span></button>'
        )

    theme_links = []
    for theme in summary["themes"]:
        theme_links.append(
            f'<button class="theme-pill" type="button" data-theme-filter="{esc(theme["name"])}">{esc(theme["name"])} <span>{theme["count"]}</span></button>'
        )

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>半块脆脆鲨 · 影像手账</title>
  <style>
    :root {{
      --bg: #f6f1e8;
      --paper: rgba(255, 250, 242, 0.82);
      --card: rgba(255, 252, 247, 0.92);
      --line: rgba(94, 70, 50, 0.16);
      --glass-fill: rgba(255, 255, 255, 0.42);
      --glass-fill-strong: rgba(255, 255, 255, 0.64);
      --glass-border: rgba(255, 255, 255, 0.54);
      --glass-edge: rgba(255, 255, 255, 0.78);
      --ink: #2f241b;
      --muted: #7a6554;
      --accent: #bc6c4a;
      --accent-soft: #f2d2bf;
      --accent-deep: #8f4930;
      --shadow: 0 24px 60px rgba(71, 44, 24, 0.12);
      --glass-shadow: 0 28px 70px rgba(60, 40, 24, 0.16), inset 0 1px 0 var(--glass-edge), inset 0 -22px 42px rgba(255, 255, 255, 0.22);
      --radius-xl: 28px;
      --radius-lg: 20px;
      --radius-md: 14px;
      --container: 1240px;
    }}

    * {{
      box-sizing: border-box;
    }}

    html {{
      scroll-behavior: smooth;
    }}

    body {{
      margin: 0;
      color: var(--ink);
      font-family: "Georgia", "Times New Roman", "Noto Serif SC", serif;
      background:
        radial-gradient(circle at top left, rgba(222, 174, 129, 0.3), transparent 30%),
        radial-gradient(circle at 85% 15%, rgba(174, 200, 190, 0.28), transparent 26%),
        linear-gradient(180deg, #f8f3eb 0%, #f3ede4 100%);
      background-attachment: fixed;
      min-height: 100vh;
      overflow-x: hidden;
    }}

    body::before {{
      content: "";
      position: fixed;
      inset: 0;
      pointer-events: none;
      background-image:
        linear-gradient(rgba(90, 62, 38, 0.03) 1px, transparent 1px),
        linear-gradient(90deg, rgba(90, 62, 38, 0.03) 1px, transparent 1px);
      background-size: 28px 28px;
      mask-image: linear-gradient(180deg, rgba(0, 0, 0, 0.26), transparent 80%);
    }}

    body::after {{
      content: "";
      position: fixed;
      inset: -22%;
      z-index: 0;
      pointer-events: none;
      background:
        linear-gradient(112deg, transparent 8%, rgba(255, 255, 255, 0.2) 33%, transparent 48%),
        linear-gradient(68deg, transparent 36%, rgba(255, 255, 255, 0.14) 50%, transparent 63%);
      filter: blur(24px);
      opacity: 0.36;
      mix-blend-mode: screen;
    }}

    img, video {{
      display: block;
      width: 100%;
    }}

    button, input {{
      font: inherit;
    }}

    .site-shell {{
      width: min(calc(100% - 32px), var(--container));
      margin: 0 auto;
      padding: 28px 0 60px;
      position: relative;
      z-index: 1;
    }}

    .topbar {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 18px;
      padding: 12px 0 28px;
    }}

    .brand {{
      display: flex;
      align-items: center;
      gap: 14px;
    }}

    .brand-mark {{
      width: 48px;
      height: 48px;
      border-radius: 16px;
      background: linear-gradient(135deg, #d48b62, #f1c98f);
      box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.55), var(--shadow);
      position: relative;
      overflow: hidden;
    }}

    .brand-mark::before,
    .brand-mark::after {{
      content: "";
      position: absolute;
      border-radius: 999px;
      background: rgba(255, 248, 239, 0.82);
    }}

    .brand-mark::before {{
      width: 28px;
      height: 12px;
      left: 10px;
      top: 11px;
      transform: rotate(-22deg);
    }}

    .brand-mark::after {{
      width: 16px;
      height: 16px;
      right: 9px;
      bottom: 10px;
    }}

    .brand h1 {{
      margin: 0;
      font-size: clamp(1.4rem, 2vw, 1.9rem);
      letter-spacing: 0.04em;
      font-weight: 600;
    }}

    .brand p,
    .toolbar-note {{
      margin: 0;
      color: var(--muted);
      font-size: 0.95rem;
    }}

    .hero {{
      display: grid;
      grid-template-columns: 1.15fr 0.85fr;
      gap: 22px;
      margin-bottom: 24px;
      perspective: 1200px;
    }}

    .hero-main,
    .hero-side,
    .panel {{
      -webkit-backdrop-filter: blur(24px) saturate(1.28);
      backdrop-filter: blur(24px) saturate(1.28);
      background:
        linear-gradient(135deg, rgba(255, 255, 255, 0.68), rgba(255, 255, 255, 0.24)),
        var(--paper);
      border: 1px solid var(--glass-border);
      border-radius: var(--radius-xl);
      box-shadow: var(--glass-shadow);
      position: relative;
    }}

    .hero-main::selection,
    .hero-side::selection,
    .panel::selection {{
      background: rgba(188, 108, 74, 0.22);
    }}

    .hero-main::marker,
    .hero-side::marker,
    .panel::marker {{
      color: var(--accent);
    }}

    .hero-main {{
      --cloud-x: 0px;
      --cloud-y: 0px;
      --glow-x: 0px;
      --glow-y: 0px;
      --leaf-a-x: 0px;
      --leaf-a-y: 0px;
      --leaf-b-x: 0px;
      --leaf-b-y: 0px;
      --hero-tilt-x: 0deg;
      --hero-tilt-y: 0deg;
      padding: clamp(26px, 4vw, 42px);
      overflow: hidden;
      min-height: 620px;
      background:
        linear-gradient(115deg, rgba(58, 37, 23, 0.24), rgba(76, 48, 27, 0.08)),
        radial-gradient(circle at 18% 22%, rgba(255, 221, 179, 0.38), transparent 24%),
      linear-gradient(180deg, rgba(255, 252, 247, 0.58), rgba(248, 240, 230, 0.62));
      isolation: isolate;
      transform-style: preserve-3d;
      transform: rotateX(var(--hero-tilt-x)) rotateY(var(--hero-tilt-y));
      transition: transform 240ms ease, box-shadow 240ms ease;
    }}

    .hero-main::after {{
      content: "";
      position: absolute;
      width: 520px;
      height: 520px;
      right: -120px;
      top: -140px;
      border-radius: 50%;
      background: radial-gradient(circle, rgba(255, 255, 255, 0.26), rgba(214, 131, 82, 0.2) 42%, transparent 68%);
      animation: drift 18s ease-in-out infinite alternate;
    }}

    .hero-main::before {{
      content: "";
      position: absolute;
      inset: auto auto 36px 40%;
      width: 220px;
      height: 120px;
      background:
        radial-gradient(circle at 15% 45%, rgba(238, 245, 255, 0.86) 0 18%, transparent 19%),
        radial-gradient(circle at 36% 35%, rgba(238, 245, 255, 0.9) 0 22%, transparent 23%),
        radial-gradient(circle at 58% 48%, rgba(238, 245, 255, 0.86) 0 24%, transparent 25%),
        radial-gradient(circle at 78% 40%, rgba(238, 245, 255, 0.82) 0 18%, transparent 19%);
      filter: blur(2px);
      opacity: 0.72;
      animation: cloudFloat 14s ease-in-out infinite alternate;
    }}

    .hero-breath {{
      position: absolute;
      inset: 0;
      z-index: 0;
      pointer-events: none;
      background:
        linear-gradient(180deg, rgba(255, 197, 142, 0.18), rgba(163, 206, 247, 0.14) 42%, rgba(248, 235, 215, 0.16));
      mix-blend-mode: soft-light;
      animation: dayGlow 12s ease-in-out infinite;
      transform: translate3d(var(--glow-x), var(--glow-y), 0) scale(1.04);
    }}

    .hero-copy-wrap {{
      position: relative;
      z-index: 1;
      display: grid;
      gap: 22px;
      align-content: space-between;
      min-height: 100%;
    }}

    .hero-decor {{
      position: absolute;
      inset: 0;
      pointer-events: none;
      overflow: hidden;
      z-index: 0;
    }}

    .leaf-shadow {{
      position: absolute;
      width: 180px;
      height: 180px;
      background:
        radial-gradient(ellipse at 30% 40%, rgba(109, 142, 100, 0.2) 0 18%, transparent 20%),
        radial-gradient(ellipse at 58% 25%, rgba(127, 164, 118, 0.18) 0 16%, transparent 18%),
        radial-gradient(ellipse at 70% 58%, rgba(149, 184, 137, 0.16) 0 18%, transparent 20%);
      filter: blur(10px);
      opacity: 0.72;
      transform-origin: center;
      animation: sway 7s ease-in-out infinite;
    }}

    .leaf-shadow.leaf-a {{
      top: 40px;
      right: 120px;
      --leaf-rotate: 14deg;
      --leaf-x: var(--leaf-a-x);
      --leaf-y: var(--leaf-a-y);
    }}

    .leaf-shadow.leaf-b {{
      bottom: 70px;
      left: 44%;
      width: 220px;
      height: 220px;
      --leaf-rotate: -18deg;
      --leaf-x: var(--leaf-b-x);
      --leaf-y: var(--leaf-b-y);
      animation-delay: -2.4s;
    }}

    .hero-stage {{
      display: grid;
      grid-template-columns: 1.1fr 0.9fr;
      gap: 18px;
      align-items: end;
    }}

    .hero-stage-card {{
      --stage-x: 0px;
      --stage-y: 0px;
      --stage-tilt-x: 0deg;
      --stage-tilt-y: 0deg;
      --stage-hover-y: 0px;
      position: relative;
      display: grid;
      overflow: hidden;
      border-radius: 28px;
      border: 1px solid rgba(255, 255, 255, 0.48);
      box-shadow: 0 30px 70px rgba(43, 24, 12, 0.18), inset 0 1px 0 rgba(255, 255, 255, 0.56);
      cursor: pointer;
      min-height: 280px;
      transform-style: preserve-3d;
      transform: translate3d(var(--stage-x), calc(var(--stage-y) + var(--stage-hover-y)), 34px) rotateX(var(--stage-tilt-x)) rotateY(var(--stage-tilt-y));
      transition: transform 180ms ease, box-shadow 260ms ease;
    }}

    .hero-stage-card::after {{
      content: "";
      position: absolute;
      inset: 0;
      background:
        linear-gradient(112deg, rgba(255, 255, 255, 0.34), transparent 28%, transparent 68%, rgba(255, 255, 255, 0.16)),
        linear-gradient(180deg, rgba(29, 18, 11, 0.02), rgba(29, 18, 11, 0.58));
      pointer-events: none;
    }}

    .hero-stage-media {{
      position: absolute;
      inset: 0;
      background: #e8dccd;
    }}

    .hero-stage-media img,
    .hero-stage-media video {{
      width: 100%;
      height: 100%;
      object-fit: cover;
      transform: scale(1.04);
    }}

    .hero-stage-card:hover {{
      --stage-hover-y: -4px;
      box-shadow: 0 34px 78px rgba(43, 24, 12, 0.22);
    }}

    .hero-stage-copy {{
      position: relative;
      z-index: 1;
      margin-top: auto;
      padding: 22px;
      color: #fffaf5;
      display: grid;
      gap: 8px;
      align-content: end;
    }}

    .hero-stage-copy h3 {{
      margin: 0;
      font-size: clamp(1.3rem, 2vw, 1.85rem);
      line-height: 1.28;
    }}

    .hero-stage-copy p {{
      color: rgba(255, 248, 241, 0.88);
      max-width: none;
      font-size: 0.98rem;
      line-height: 1.7;
    }}

    .hero-note {{
      padding: 18px;
      border-radius: 24px;
      background:
        linear-gradient(135deg, rgba(255, 255, 255, 0.72), rgba(255, 255, 255, 0.24)),
        rgba(255, 251, 245, 0.52);
      border: 1px solid rgba(255, 255, 255, 0.56);
      box-shadow: 0 16px 40px rgba(63, 41, 24, 0.08), inset 0 1px 0 rgba(255, 255, 255, 0.72);
      -webkit-backdrop-filter: blur(18px) saturate(1.18);
      backdrop-filter: blur(18px) saturate(1.18);
    }}

    .hero-note p {{
      margin: 0;
      font-size: 0.98rem;
      line-height: 1.8;
    }}

    .label {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      width: fit-content;
      padding: 8px 14px;
      border-radius: 999px;
      color: var(--accent-deep);
      background: rgba(255, 241, 231, 0.94);
      border: 1px solid rgba(188, 108, 74, 0.22);
      font-size: 0.88rem;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }}

    .hero-main h2 {{
      margin: 0;
      font-size: clamp(2.4rem, 5vw, 4.8rem);
      line-height: 0.97;
      font-weight: 600;
      max-width: 10ch;
    }}

    .hero-main p {{
      margin: 0;
      max-width: 52ch;
      color: var(--muted);
      font-size: 1.05rem;
      line-height: 1.8;
    }}

    .stat-grid {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;
    }}

    .stat {{
      padding: 16px 18px;
      border-radius: 18px;
      background:
        linear-gradient(135deg, rgba(255, 255, 255, 0.72), rgba(255, 255, 255, 0.28));
      border: 1px solid rgba(255, 255, 255, 0.54);
      box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.7), 0 14px 30px rgba(73, 48, 30, 0.08);
      -webkit-backdrop-filter: blur(16px) saturate(1.12);
      backdrop-filter: blur(16px) saturate(1.12);
    }}

    .stat strong {{
      display: block;
      font-size: clamp(1.4rem, 2vw, 2rem);
      font-weight: 600;
    }}

    .stat span {{
      color: var(--muted);
      font-size: 0.92rem;
    }}

    .hero-side {{
      padding: 18px;
      display: grid;
      gap: 14px;
      align-content: start;
    }}

    .section-title {{
      display: flex;
      align-items: baseline;
      justify-content: space-between;
      gap: 12px;
    }}

    .section-title h3 {{
      margin: 0;
      font-size: 1.15rem;
      font-weight: 600;
    }}

    .section-title span {{
      color: var(--muted);
      font-size: 0.92rem;
    }}

    .hero-card {{
      display: grid;
      grid-template-columns: 132px 1fr;
      gap: 14px;
      padding: 12px;
      border-radius: 20px;
      border: 1px solid rgba(255, 255, 255, 0.52);
      background:
        linear-gradient(135deg, rgba(255, 255, 255, 0.74), rgba(255, 255, 255, 0.3));
      box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.68);
      -webkit-backdrop-filter: blur(18px) saturate(1.16);
      backdrop-filter: blur(18px) saturate(1.16);
      cursor: pointer;
      transition: transform 180ms ease, box-shadow 180ms ease, border-color 180ms ease;
      animation: cardIn 700ms ease both;
    }}

    .hero-card:hover,
    .post-card:hover,
    .gallery-item:hover {{
      transform: translateY(-4px);
      box-shadow: 0 18px 38px rgba(73, 48, 30, 0.12);
      border-color: rgba(188, 108, 74, 0.28);
    }}

    .hero-thumb {{
      aspect-ratio: 1 / 1;
      border-radius: 16px;
      overflow: hidden;
      background: #eadfce;
    }}

    .hero-thumb img,
    .hero-thumb video {{
      height: 100%;
      object-fit: cover;
    }}

    .hero-copy {{
      display: grid;
      gap: 8px;
      align-content: start;
    }}

    .eyebrow {{
      margin: 0;
      color: var(--accent-deep);
      font-size: 0.82rem;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }}

    .hero-copy h3,
    .post-card h3 {{
      margin: 0;
      font-size: 1.08rem;
      line-height: 1.4;
    }}

    .hero-copy p,
    .post-card p,
    .meta-line,
    .timeline-copy {{
      margin: 0;
      color: var(--muted);
      line-height: 1.65;
    }}

    .filters {{
      display: grid;
      grid-template-columns: 1.15fr 0.85fr;
      gap: 22px;
      margin: 22px 0;
    }}

    .panel {{
      padding: 20px;
    }}

    .filter-row {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 14px;
    }}

    .chip,
    .year-pill,
    .theme-pill,
    .ghost-button,
    .solid-button {{
      border: 1px solid rgba(255, 255, 255, 0.56);
      border-radius: 999px;
      padding: 10px 14px;
      background:
        linear-gradient(135deg, rgba(255, 255, 255, 0.76), rgba(255, 255, 255, 0.3));
      color: var(--ink);
      cursor: pointer;
      transition: all 160ms ease;
      box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.72), 0 10px 22px rgba(73, 48, 30, 0.07);
      -webkit-backdrop-filter: blur(14px) saturate(1.12);
      backdrop-filter: blur(14px) saturate(1.12);
    }}

    .chip:hover,
    .year-pill:hover,
    .theme-pill:hover,
    .ghost-button:hover,
    .solid-button:hover {{
      border-color: rgba(188, 108, 74, 0.34);
      transform: translateY(-1px);
    }}

    .chip.active,
    .year-pill.active,
    .theme-pill.active {{
      color: white;
      background: linear-gradient(135deg, #b86847, #d68a62);
      border-color: transparent;
      box-shadow: 0 10px 28px rgba(188, 108, 74, 0.26);
    }}

    .chip span,
    .year-pill span,
    .theme-pill span {{
      color: inherit;
      opacity: 0.72;
      margin-left: 4px;
    }}

    .search-input {{
      width: 100%;
      border: 1px solid rgba(255, 255, 255, 0.58);
      border-radius: 18px;
      padding: 14px 16px;
      background:
        linear-gradient(135deg, rgba(255, 255, 255, 0.78), rgba(255, 255, 255, 0.36));
      color: var(--ink);
      outline: none;
      box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.72), 0 12px 26px rgba(73, 48, 30, 0.07);
      -webkit-backdrop-filter: blur(16px) saturate(1.12);
      backdrop-filter: blur(16px) saturate(1.12);
    }}

    .search-input:focus {{
      border-color: rgba(188, 108, 74, 0.38);
      box-shadow: 0 0 0 4px rgba(188, 108, 74, 0.1);
    }}

    .content-grid {{
      display: grid;
      grid-template-columns: minmax(250px, 0.72fr) minmax(460px, 1.08fr) minmax(360px, 0.98fr);
      gap: 22px;
      align-items: start;
    }}

    .sidebar-stack {{
      display: grid;
      gap: 22px;
      align-self: start;
    }}

    .timeline {{
      position: sticky;
      top: 16px;
      padding: 22px;
      max-height: calc(100vh - 32px);
      overflow: hidden;
    }}

    .timeline-scroll {{
      margin-top: 16px;
      max-height: calc(100vh - 170px);
      overflow-y: auto;
      padding-right: 8px;
      scrollbar-width: thin;
      scrollbar-color: rgba(188, 108, 74, 0.38) rgba(255, 255, 255, 0.3);
    }}

    .timeline-scroll::-webkit-scrollbar {{
      width: 8px;
    }}

    .timeline-scroll::-webkit-scrollbar-thumb {{
      background: rgba(188, 108, 74, 0.38);
      border-radius: 999px;
    }}

    .timeline-scroll::-webkit-scrollbar-track {{
      background: rgba(255, 255, 255, 0.32);
      border-radius: 999px;
    }}

    .timeline-list {{
      display: grid;
      gap: 14px;
    }}

    .memory-card {{
      padding: 18px;
      overflow: hidden;
      position: sticky;
      top: 16px;
    }}

    .memory-stage {{
      margin-top: 16px;
      border-radius: 24px;
      overflow: hidden;
      background:
        linear-gradient(135deg, rgba(255, 255, 255, 0.66), rgba(255, 255, 255, 0.24)),
        linear-gradient(180deg, rgba(245, 231, 218, 0.8), rgba(255, 251, 245, 0.72));
      border: 1px solid rgba(255, 255, 255, 0.52);
      box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.72), 0 18px 42px rgba(73, 48, 30, 0.1);
      -webkit-backdrop-filter: blur(18px) saturate(1.14);
      backdrop-filter: blur(18px) saturate(1.14);
    }}

    .memory-media {{
      aspect-ratio: 4 / 3;
      background: #e8dccd;
      overflow: hidden;
    }}

    .memory-media img,
    .memory-media video {{
      height: 100%;
      object-fit: cover;
    }}

    .memory-copy {{
      padding: 18px;
      display: grid;
      gap: 10px;
    }}

    .memory-copy h3 {{
      margin: 0;
      font-size: 1.15rem;
      line-height: 1.45;
    }}

    .memory-dots {{
      display: flex;
      gap: 8px;
      align-items: center;
      margin-top: 8px;
    }}

    .memory-dot {{
      width: 8px;
      height: 8px;
      border-radius: 999px;
      background: rgba(188, 108, 74, 0.22);
      transition: transform 160ms ease, background 160ms ease;
    }}

    .memory-dot.active {{
      background: var(--accent);
      transform: scale(1.2);
    }}

    .timeline-item {{
      display: grid;
      grid-template-columns: 48px 1fr;
      gap: 14px;
      position: relative;
      cursor: pointer;
      padding: 12px;
      border-radius: 18px;
      transition: background 160ms ease, transform 160ms ease;
    }}

    .timeline-item:hover {{
      background:
        linear-gradient(135deg, rgba(255, 255, 255, 0.68), rgba(255, 255, 255, 0.24));
      box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.64), 0 12px 28px rgba(73, 48, 30, 0.08);
      transform: translateX(4px);
    }}

    .timeline-item::before {{
      content: "";
      position: absolute;
      left: 35px;
      top: 10px;
      bottom: -10px;
      width: 1px;
      background: rgba(90, 62, 38, 0.12);
    }}

    .timeline-item:last-child::before {{
      display: none;
    }}

    .timeline-date {{
      position: relative;
      z-index: 1;
      width: 26px;
      height: 26px;
      border-radius: 50%;
      display: grid;
      place-items: center;
      margin-top: 2px;
      background: linear-gradient(135deg, #d68a62, #f3c18e);
      box-shadow: 0 10px 22px rgba(188, 108, 74, 0.22);
    }}

    .timeline-date::after {{
      content: "";
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: rgba(255, 249, 242, 0.96);
    }}

    .timeline-title {{
      margin: 0 0 6px;
      font-size: 1rem;
      line-height: 1.45;
    }}

    .posts-area {{
      display: grid;
      gap: 18px;
    }}

    .letter-card {{
      padding: 22px;
      position: sticky;
      top: 16px;
      overflow: hidden;
      background:
        radial-gradient(circle at 14% 16%, rgba(190, 218, 188, 0.38), transparent 16%),
        radial-gradient(circle at 85% 12%, rgba(223, 233, 250, 0.42), transparent 18%),
        radial-gradient(circle at 78% 90%, rgba(243, 217, 183, 0.5), transparent 18%),
        linear-gradient(135deg, rgba(255, 255, 255, 0.68), rgba(255, 255, 255, 0.22)),
        linear-gradient(180deg, rgba(255, 252, 247, 0.74), rgba(250, 244, 235, 0.72));
      min-height: 650px;
      display: grid;
      align-content: start;
      gap: 18px;
    }}

    .letter-card::before,
    .letter-card::after {{
      content: "";
      position: absolute;
      pointer-events: none;
      opacity: 0.38;
    }}

    .letter-card::before {{
      width: 132px;
      height: 132px;
      right: -20px;
      top: 34px;
      background:
        radial-gradient(circle at 30% 50%, rgba(118, 154, 120, 0.72) 0 22%, transparent 24%),
        radial-gradient(circle at 55% 35%, rgba(145, 183, 141, 0.72) 0 22%, transparent 24%),
        radial-gradient(circle at 70% 62%, rgba(169, 201, 157, 0.72) 0 22%, transparent 24%);
      filter: blur(0.2px);
      transform: rotate(22deg);
    }}

    .letter-card::after {{
      left: -18px;
      bottom: 34px;
      width: 174px;
      height: 88px;
      background:
        radial-gradient(circle at 20% 50%, rgba(221, 232, 248, 0.78) 0 18%, transparent 19%),
        radial-gradient(circle at 42% 40%, rgba(221, 232, 248, 0.78) 0 20%, transparent 21%),
        radial-gradient(circle at 64% 52%, rgba(221, 232, 248, 0.78) 0 22%, transparent 23%),
        radial-gradient(circle at 82% 45%, rgba(221, 232, 248, 0.78) 0 17%, transparent 18%);
    }}

    .letter-frame {{
      position: relative;
      z-index: 1;
      min-height: 558px;
      perspective: 1500px;
      transform-style: preserve-3d;
    }}

    .letter-paper {{
      position: absolute;
      inset: 0;
      z-index: 1;
      padding: 34px 32px;
      border-radius: 30px 36px 34px 26px;
      background:
        linear-gradient(92deg, rgba(112, 76, 48, 0.13), transparent 8%, transparent 91%, rgba(255, 255, 255, 0.5)),
        repeating-linear-gradient(
          180deg,
          rgba(145, 115, 88, 0.03) 0,
          rgba(145, 115, 88, 0.03) 34px,
          rgba(145, 115, 88, 0.08) 35px,
          rgba(145, 115, 88, 0.03) 36px
        ),
        rgba(255, 253, 249, 0.96);
      border: 1px solid rgba(255, 255, 255, 0.62);
      box-shadow: 0 22px 50px rgba(61, 38, 20, 0.16), inset 0 1px 0 rgba(255, 255, 255, 0.72);
      transform-origin: left center;
      transform-style: preserve-3d;
      backface-visibility: hidden;
      overflow: hidden;
    }}

    .letter-paper::before {{
      content: "";
      position: absolute;
      inset: 0;
      pointer-events: none;
      background:
        radial-gradient(circle at 18% 14%, rgba(255, 255, 255, 0.7), transparent 24%),
        linear-gradient(118deg, rgba(255, 255, 255, 0.42), transparent 34%, rgba(147, 102, 70, 0.08) 72%, transparent);
      mix-blend-mode: screen;
      opacity: 0.68;
    }}

    .letter-paper::after {{
      content: "";
      position: absolute;
      top: 0;
      bottom: 0;
      left: 0;
      width: 46px;
      pointer-events: none;
      background: linear-gradient(90deg, rgba(95, 63, 37, 0.18), rgba(255, 255, 255, 0.22), transparent);
      opacity: 0.78;
    }}

    .letter-page-current {{
      z-index: 3;
    }}

    .letter-page-next {{
      z-index: 2;
      transform: rotateY(-3deg) translateX(7px) scale(0.982);
      filter: brightness(0.98);
    }}

    .letter-page-turn {{
      animation: paperTurnOut 820ms cubic-bezier(0.2, 0.72, 0.2, 1) forwards;
    }}

    .letter-page-reveal {{
      animation: paperReveal 820ms cubic-bezier(0.2, 0.72, 0.2, 1) forwards;
    }}

    .letter-content {{
      position: relative;
      z-index: 1;
      min-height: 100%;
      display: grid;
      align-content: start;
      grid-template-rows: auto auto 1fr auto auto;
    }}

    .letter-kicker {{
      color: var(--accent-deep);
      letter-spacing: 0.12em;
      text-transform: uppercase;
      font-size: 0.8rem;
      opacity: 0.82;
    }}

    .letter-title {{
      margin: 10px 0 20px;
      font-size: clamp(1.75rem, 2.1vw, 2.18rem);
      line-height: 1.24;
      color: #2b2119;
    }}

    .letter-body {{
      margin: 0;
      color: #584536;
      line-height: 2.02;
      white-space: pre-line;
      font-size: 1.08rem;
      min-height: 13.2em;
      text-wrap: pretty;
    }}

    .letter-quote {{
      margin-top: 24px;
      padding: 18px 18px 0;
      border-top: 1px dashed rgba(90, 62, 38, 0.18);
      font-size: 1.08rem;
      line-height: 1.82;
      min-height: 5.8em;
      color: #3b2b21;
      background: linear-gradient(180deg, rgba(255, 255, 255, 0.32), transparent);
      border-radius: 0 0 18px 18px;
    }}

    .letter-content.lang-en .letter-body,
    .letter-content.lang-en .letter-quote,
    .letter-content.lang-ja .letter-body,
    .letter-content.lang-ja .letter-quote {{
      font-size: 0.98rem;
      line-height: 1.78;
    }}

    .letter-sign {{
      margin-top: 18px;
      text-align: right;
      color: var(--accent-deep);
      font-style: italic;
      font-size: 1.02rem;
    }}

    .letter-controls {{
      position: relative;
      z-index: 2;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
    }}

    .letter-dots {{
      display: flex;
      gap: 7px;
      align-items: center;
      min-width: 0;
      flex-wrap: wrap;
    }}

    .letter-dot {{
      width: 7px;
      height: 7px;
      border-radius: 999px;
      background: rgba(188, 108, 74, 0.22);
      transition: transform 160ms ease, background 160ms ease;
    }}

    .letter-dot.active {{
      background: var(--accent);
      transform: scale(1.24);
    }}

    .letter-next {{
      flex: 0 0 auto;
      border: 1px solid rgba(255, 255, 255, 0.58);
      border-radius: 999px;
      width: 48px;
      height: 48px;
      display: grid;
      place-items: center;
      color: var(--accent-deep);
      font-size: 1.55rem;
      background:
        linear-gradient(135deg, rgba(255, 255, 255, 0.74), rgba(255, 255, 255, 0.3));
      box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.72), 0 12px 24px rgba(73, 48, 30, 0.1);
      cursor: pointer;
      transition: transform 160ms ease, box-shadow 160ms ease;
    }}

    .letter-next:hover {{
      transform: translateY(-1px);
      box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.72), 0 16px 30px rgba(73, 48, 30, 0.14);
    }}

    .posts-head {{
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: flex-end;
      padding: 0 4px;
    }}

    .posts-head h3 {{
      margin: 0;
      font-size: 1.35rem;
    }}

    .post-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(min(100%, 280px), 1fr));
      gap: 18px;
    }}

    .post-card {{
      padding: 14px;
      border-radius: 24px;
      border: 1px solid rgba(90, 62, 38, 0.12);
      background: var(--card);
      box-shadow: var(--shadow);
      cursor: pointer;
      transition: transform 180ms ease, box-shadow 180ms ease, border-color 180ms ease;
      overflow: hidden;
      animation: cardIn 720ms ease both;
    }}

    .post-card:nth-child(2n) {{
      animation-delay: 50ms;
    }}

    .post-card:nth-child(3n) {{
      animation-delay: 90ms;
    }}

    .post-cover {{
      border-radius: 18px;
      aspect-ratio: 4 / 3;
      overflow: hidden;
      background: #e8dccd;
      margin-bottom: 14px;
      position: relative;
    }}

    .post-cover img,
    .post-cover video {{
      height: 100%;
      object-fit: cover;
      transition: transform 280ms ease;
    }}

    .post-card:hover .post-cover img,
    .post-card:hover .post-cover video {{
      transform: scale(1.03);
    }}

    .post-meta {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin: 10px 0 12px;
    }}

    .meta-pill {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 6px 10px;
      border-radius: 999px;
      background: rgba(242, 225, 208, 0.78);
      color: var(--accent-deep);
      font-size: 0.82rem;
    }}

    .meta-line {{
      font-size: 0.92rem;
    }}

    .empty-state {{
      display: none;
      padding: 42px 24px;
      text-align: center;
      border-radius: 24px;
      border: 1px dashed rgba(99, 72, 49, 0.2);
      background: rgba(255, 255, 255, 0.46);
      color: var(--muted);
    }}

    .modal {{
      position: fixed;
      inset: 0;
      display: none;
      place-items: center;
      padding: 22px;
      background: rgba(39, 24, 14, 0.48);
      backdrop-filter: blur(16px);
      z-index: 30;
    }}

    .modal.open {{
      display: grid;
    }}

    .modal-card {{
      width: min(1080px, 100%);
      max-height: min(88vh, 1100px);
      overflow: auto;
      background: rgba(255, 251, 245, 0.96);
      border-radius: 28px;
      border: 1px solid rgba(90, 62, 38, 0.12);
      box-shadow: 0 30px 100px rgba(20, 11, 7, 0.3);
      padding: 22px;
    }}

    .modal-head {{
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: start;
      margin-bottom: 18px;
    }}

    .modal-head h3 {{
      margin: 8px 0 10px;
      font-size: clamp(1.5rem, 3vw, 2.4rem);
      line-height: 1.25;
    }}

    .modal-close {{
      width: 42px;
      height: 42px;
      border-radius: 50%;
      border: 1px solid rgba(90, 62, 38, 0.16);
      background: rgba(255, 255, 255, 0.86);
      cursor: pointer;
      flex: 0 0 auto;
    }}

    .modal-grid {{
      display: grid;
      gap: 22px;
    }}

    .video-stack,
    .audio-stack,
    .gallery-grid {{
      display: grid;
      gap: 14px;
    }}

    .video-stack video,
    .gallery-item img {{
      border-radius: 18px;
      background: #e8dccd;
      overflow: hidden;
      border: 1px solid rgba(90, 62, 38, 0.08);
    }}

    .gallery-grid {{
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }}

    .gallery-item {{
      border-radius: 20px;
      overflow: hidden;
      transition: transform 180ms ease, box-shadow 180ms ease;
    }}

    .audio-card {{
      padding: 14px;
      border-radius: 18px;
      background: rgba(255, 255, 255, 0.72);
      border: 1px solid rgba(90, 62, 38, 0.08);
    }}

    audio {{
      width: 100%;
      margin-top: 10px;
    }}

    .footer-note {{
      margin-top: 34px;
      padding: 22px;
      text-align: center;
      color: var(--muted);
    }}

    .fade-in {{
      animation: rise 600ms ease both;
    }}

    @keyframes rise {{
      from {{
        opacity: 0;
        transform: translateY(22px);
      }}
      to {{
        opacity: 1;
        transform: translateY(0);
      }}
    }}

    @keyframes cloudFloat {{
      from {{
        transform: translate3d(var(--cloud-x), var(--cloud-y), 0);
      }}
      to {{
        transform: translate3d(calc(var(--cloud-x) + 42px), calc(var(--cloud-y) - 10px), 0);
      }}
    }}

    @keyframes sway {{
      0% {{
        transform: translate3d(var(--leaf-x), var(--leaf-y), 0) rotate(calc(var(--leaf-rotate) - 8deg));
      }}
      50% {{
        transform: translate3d(var(--leaf-x), calc(var(--leaf-y) + 8px), 0) rotate(calc(var(--leaf-rotate) + 5deg));
      }}
      100% {{
        transform: translate3d(var(--leaf-x), calc(var(--leaf-y) - 4px), 0) rotate(calc(var(--leaf-rotate) - 4deg));
      }}
    }}

    @keyframes drift {{
      from {{
        transform: translate3d(var(--glow-x), var(--glow-y), 0);
      }}
      to {{
        transform: translate3d(calc(var(--glow-x) - 28px), calc(var(--glow-y) + 18px), 0);
      }}
    }}

    @keyframes dayGlow {{
      0% {{
        opacity: 0.62;
        filter: saturate(1);
      }}
      50% {{
        opacity: 0.95;
        filter: saturate(1.08);
      }}
      100% {{
        opacity: 0.68;
        filter: saturate(0.96);
      }}
    }}

    @keyframes paperTurnOut {{
      0% {{
        opacity: 1;
        transform: rotateY(0deg) translateX(0) scale(1);
        box-shadow: 0 22px 50px rgba(61, 38, 20, 0.16), inset 0 1px 0 rgba(255, 255, 255, 0.72);
      }}
      46% {{
        opacity: 1;
        transform: rotateY(-76deg) translateX(-10px) scale(0.992);
        box-shadow: 18px 22px 44px rgba(61, 38, 20, 0.2), inset 20px 0 34px rgba(126, 82, 48, 0.16);
      }}
      100% {{
        opacity: 0;
        transform: rotateY(-118deg) translateX(-18px) scale(0.985);
        box-shadow: 24px 18px 34px rgba(61, 38, 20, 0.08), inset 34px 0 44px rgba(126, 82, 48, 0.2);
      }}
    }}

    @keyframes paperReveal {{
      0% {{
        opacity: 0.62;
        transform: rotateY(8deg) translateX(10px) scale(0.976);
        filter: brightness(0.96);
      }}
      48% {{
        opacity: 0.9;
        transform: rotateY(4deg) translateX(5px) scale(0.988);
        filter: brightness(0.98);
      }}
      100% {{
        opacity: 1;
        transform: rotateY(0deg) translateX(0) scale(1);
        filter: brightness(1);
      }}
    }}

    @keyframes cardIn {{
      from {{
        opacity: 0;
        transform: translateY(18px) scale(0.985);
      }}
      to {{
        opacity: 1;
        transform: translateY(0) scale(1);
      }}
    }}

    @media (max-width: 1100px) {{
      .hero,
      .filters,
      .content-grid {{
        grid-template-columns: 1fr;
      }}

      .hero-stage {{
        grid-template-columns: 1fr;
      }}

      .timeline {{
        position: static;
        max-height: none;
      }}

      .memory-card,
      .letter-card {{
        position: static;
      }}

      .timeline-scroll {{
        max-height: 520px;
      }}

      .letter-card {{
        min-height: 610px;
      }}

      .letter-frame {{
        min-height: 520px;
      }}
    }}

    @media (max-width: 780px) {{
      .site-shell {{
        width: min(calc(100% - 20px), var(--container));
        padding-top: 18px;
      }}

      .topbar,
      .posts-head,
      .modal-head {{
        flex-direction: column;
        align-items: stretch;
      }}

      .hero-card,
      .post-grid,
      .gallery-grid {{
        grid-template-columns: 1fr;
      }}

      .stat-grid {{
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }}

      .hero-main {{
        min-height: auto;
      }}

      .letter-card {{
        min-height: 580px;
      }}

      .letter-frame {{
        min-height: 492px;
      }}

      .letter-paper {{
        padding: 28px 22px;
      }}

      .letter-title {{
        font-size: 1.64rem;
      }}

    .letter-body,
    .letter-quote {{
      font-size: 1rem;
      }}
    }}

  </style>
</head>
<body>
  <div class="site-shell">
    <header class="topbar fade-in">
      <div class="brand">
        <div class="brand-mark" aria-hidden="true"></div>
        <div>
          <h1>半块脆脆鲨 · 影像手账</h1>
          <p>把零散的音视频，整理成一册可以慢慢翻的生活博客。</p>
        </div>
      </div>
      <p class="toolbar-note">影像故事 {summary["stats"]["stories"]} 篇 · 从 2021 到 2026</p>
    </header>

    <section class="hero fade-in">
      <div class="hero-main">
        <div class="hero-breath" aria-hidden="true"></div>
        <div class="hero-decor" aria-hidden="true">
          <div class="leaf-shadow leaf-a"></div>
          <div class="leaf-shadow leaf-b"></div>
        </div>
        <div class="hero-copy-wrap">
          <div>
            <div class="label">Visual Diary</div>
            <h2>把旅行、猫咪、城市与回忆，编成一页页可播放的生活杂志。</h2>
            <p>
              这批素材最适合做成偏杂志化的影像博客，而不是普通文件列表。它有明显的时间推进、反复出现的猫咪线索、
              高频旅行片段和个人节奏感，所以页面以「时间轴 + 主题筛选 + 文章式卡片」来承载这些内容。
            </p>
          </div>
          <div class="hero-stage">
            {hero_spot_markup}
            <div class="hero-note">
              <p>
                云层会缓慢移动，叶影在角落轻轻摇晃，像翻开一册被阳光照过的旧相簿。
                在这里，回忆不是归档后的冰冷文件，而是仍在呼吸、仍可停留的生活现场。
              </p>
            </div>
          </div>
          <div class="stat-grid">
            <div class="stat">
              <strong>{summary["stats"]["stories"]}</strong>
              <span>影像故事</span>
            </div>
            <div class="stat">
              <strong>{summary["stats"]["videos"]}</strong>
              <span>视频片段</span>
            </div>
            <div class="stat">
              <strong>{summary["stats"]["images"]}</strong>
              <span>封面图像</span>
            </div>
            <div class="stat">
              <strong>{summary["stats"]["audios"]}</strong>
              <span>音频记录</span>
            </div>
          </div>
        </div>
      </div>

      <aside class="hero-side">
        <div class="section-title">
          <h3>本册精选</h3>
          <span>最近更新的回忆页</span>
        </div>
        {"".join(hero_cards)}
      </aside>
    </section>

    <section class="filters fade-in">
      <div class="panel">
        <div class="section-title">
          <h3>年份与主题</h3>
          <span>最多产年份 {summary["busiestYear"]} · 主旋律 {summary["topTheme"]}</span>
        </div>
        <div class="filter-row">
          <button class="chip active" type="button" data-reset="all">全部内容</button>
          {"".join(year_links)}
        </div>
        <div class="filter-row">
          {"".join(theme_links)}
        </div>
      </div>

      <div class="panel">
        <div class="section-title">
          <h3>检索片段</h3>
          <span>支持按标题、主题、日期搜索</span>
        </div>
        <div class="filter-row">
          <input id="searchInput" class="search-input" type="search" placeholder="比如：青岛、猫咪、迪士尼、2025">
        </div>
      </div>
    </section>

    <section class="content-grid">
      <aside class="sidebar-stack fade-in">
        <section class="panel memory-card">
          <div class="section-title">
            <h3>今日翻到的一页</h3>
            <span>随机轮播影像文章</span>
          </div>
          <div id="memoryStage" class="memory-stage"></div>
        </section>

        <section class="panel timeline">
          <div class="section-title">
            <h3>时间轴速览</h3>
            <span>左侧可独立滚动</span>
          </div>
          <div class="timeline-scroll">
            <div id="timelineList" class="timeline-list"></div>
          </div>
        </section>
      </aside>

      <main class="posts-area fade-in">
        <div class="posts-head">
          <div>
            <h3>影像文章</h3>
            <p class="meta-line">每条记录都保留原始媒体文件，可在详情弹窗中直接播放和查看。</p>
          </div>
          <p id="resultCount" class="meta-line"></p>
        </div>
        <div id="postGrid" class="post-grid"></div>
        <div id="emptyState" class="empty-state">
          没有匹配到内容。可以试试清空筛选，或者搜索别的关键词。
        </div>
      </main>

      <aside class="panel letter-card fade-in">
        <div id="letterFrame" class="letter-frame">
          <article id="letterCurrent" class="letter-paper letter-page-current"></article>
          <article id="letterNext" class="letter-paper letter-page-next"></article>
        </div>
        <div class="letter-controls">
          <div id="letterDots" class="letter-dots" aria-hidden="true"></div>
          <button id="letterNextButton" class="letter-next" type="button" aria-label="翻到下一页">›</button>
        </div>
      </aside>
    </section>

    <footer class="footer-note fade-in">
      本页为本地静态展示站，直接打开 `index.html` 即可浏览全部内容。
    </footer>
  </div>

  <div id="postModal" class="modal" aria-hidden="true">
    <div class="modal-card">
      <div class="modal-head">
        <div>
          <p id="modalDate" class="eyebrow"></p>
          <h3 id="modalTitle"></h3>
          <p id="modalMeta" class="meta-line"></p>
        </div>
        <button id="modalClose" class="modal-close" type="button" aria-label="关闭">×</button>
      </div>
      <div id="modalBody" class="modal-grid"></div>
    </div>
  </div>

  <script>
    const SITE_DATA = {payload};

    const state = {{
      year: null,
      theme: null,
      query: "",
    }};

    const postGrid = document.getElementById("postGrid");
    const timelineList = document.getElementById("timelineList");
    const memoryStage = document.getElementById("memoryStage");
    const resultCount = document.getElementById("resultCount");
    const emptyState = document.getElementById("emptyState");
    const searchInput = document.getElementById("searchInput");
    const letterCurrent = document.getElementById("letterCurrent");
    const letterNext = document.getElementById("letterNext");
    const letterDots = document.getElementById("letterDots");
    const letterNextButton = document.getElementById("letterNextButton");
    const heroMain = document.querySelector(".hero-main");
    const heroStageCard = document.querySelector(".hero-stage-card");
    const modal = document.getElementById("postModal");
    const modalTitle = document.getElementById("modalTitle");
    const modalDate = document.getElementById("modalDate");
    const modalMeta = document.getElementById("modalMeta");
    const modalBody = document.getElementById("modalBody");
    const modalClose = document.getElementById("modalClose");
    let memoryIndex = 0;
    let memoryTimer = null;
    let letterIndex = 0;
    let letterTimer = null;
    let letterReady = false;
    let letterAnimating = false;

    function setHeroParallax(x = 0, y = 0) {{
      if (!heroMain) return;
      heroMain.style.setProperty("--cloud-x", `${{(-x * 18).toFixed(2)}}px`);
      heroMain.style.setProperty("--cloud-y", `${{(-y * 12).toFixed(2)}}px`);
      heroMain.style.setProperty("--glow-x", `${{(x * 10).toFixed(2)}}px`);
      heroMain.style.setProperty("--glow-y", `${{(y * 8).toFixed(2)}}px`);
      heroMain.style.setProperty("--leaf-a-x", `${{(x * 16).toFixed(2)}}px`);
      heroMain.style.setProperty("--leaf-a-y", `${{(y * 12).toFixed(2)}}px`);
      heroMain.style.setProperty("--leaf-b-x", `${{(-x * 20).toFixed(2)}}px`);
      heroMain.style.setProperty("--leaf-b-y", `${{(-y * 14).toFixed(2)}}px`);
      heroMain.style.setProperty("--hero-tilt-x", `${{(-y * 1.4).toFixed(2)}}deg`);
      heroMain.style.setProperty("--hero-tilt-y", `${{(x * 1.6).toFixed(2)}}deg`);
      if (heroStageCard) {{
        heroStageCard.style.setProperty("--stage-x", `${{(x * 12).toFixed(2)}}px`);
        heroStageCard.style.setProperty("--stage-y", `${{(y * 10).toFixed(2)}}px`);
        heroStageCard.style.setProperty("--stage-tilt-x", `${{(-y * 2.2).toFixed(2)}}deg`);
        heroStageCard.style.setProperty("--stage-tilt-y", `${{(x * 2.8).toFixed(2)}}deg`);
      }}
    }}

    function initHeroParallax() {{
      if (!heroMain || window.matchMedia("(pointer: coarse)").matches || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
      let frame = 0;
      heroMain.addEventListener("mousemove", (event) => {{
        if (frame) return;
        frame = window.requestAnimationFrame(() => {{
          const rect = heroMain.getBoundingClientRect();
          const x = ((event.clientX - rect.left) / rect.width - 0.5) * 2;
          const y = ((event.clientY - rect.top) / rect.height - 0.5) * 2;
          setHeroParallax(Math.max(-1, Math.min(1, x)), Math.max(-1, Math.min(1, y)));
          frame = 0;
        }});
      }});
      heroMain.addEventListener("mouseleave", () => {{
        if (frame) {{
          window.cancelAnimationFrame(frame);
          frame = 0;
        }}
        setHeroParallax(0, 0);
      }});
    }}

    function escapeHtml(value) {{
      return value
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;");
    }}

    function attachMediaFallbacks(root = document) {{
      root.querySelectorAll("img[data-fallback-media]").forEach((img) => {{
        if (img.dataset.fallbackBound === "1") return;
        img.dataset.fallbackBound = "1";

        let payload = {{ images: [], videos: [], title: "" }};
        try {{
          payload = JSON.parse(img.dataset.fallbackMedia || "{{}}");
        }} catch (_error) {{
          payload = {{ images: [], videos: [], title: "" }};
        }}

        const imageCandidates = [...new Set((payload.images || []).filter(Boolean))];
        const videoCandidates = [...new Set((payload.videos || []).filter(Boolean))];
        let imageIndex = imageCandidates.indexOf(img.getAttribute("src") || "");
        if (imageIndex < 0) imageIndex = 0;
        let videoIndex = 0;

        const showPlaceholder = () => {{
          const holder = document.createElement("div");
          holder.style.height = "100%";
          holder.style.display = "grid";
          holder.style.placeItems = "center";
          holder.style.color = "var(--muted)";
          holder.style.background = "#eadfce";
          holder.textContent = img.dataset.placeholderText || "图片加载失败";
          img.replaceWith(holder);
        }};

        const swapToVideo = () => {{
          if (!videoCandidates.length) {{
            showPlaceholder();
            return;
          }}
          const video = document.createElement("video");
          video.muted = true;
          video.playsInline = true;
          video.preload = "metadata";
          video.autoplay = true;
          video.loop = true;
          video.src = videoCandidates[videoIndex];
          video.onerror = () => {{
            videoIndex += 1;
            if (videoIndex < videoCandidates.length) {{
              video.src = videoCandidates[videoIndex];
            }} else {{
              showPlaceholder();
            }}
          }};
          img.replaceWith(video);
        }};

        img.onerror = () => {{
          imageIndex += 1;
          if (imageIndex < imageCandidates.length) {{
            img.src = imageCandidates[imageIndex];
          }} else {{
            swapToVideo();
          }}
        }};
      }});
    }}

    function activePosts() {{
      const query = state.query.trim().toLowerCase();
      return SITE_DATA.posts.filter((post) => {{
        const matchesYear = !state.year || post.year === state.year;
        const matchesTheme = !state.theme || post.themes.includes(state.theme);
        const blob = [post.title, post.rawTitle, post.displayDate, ...post.themes].join(" ").toLowerCase();
        const matchesQuery = !query || blob.includes(query);
        return matchesYear && matchesTheme && matchesQuery;
      }});
    }}

    function renderTimeline(posts) {{
      timelineList.innerHTML = posts.slice(0, 18).map((post) => `
        <article class="timeline-item" data-open-title="${{escapeHtml(post.title)}}">
          <div class="timeline-date"></div>
          <div>
            <p class="eyebrow">${{post.displayDate}}</p>
            <h4 class="timeline-title">${{escapeHtml(post.title)}}</h4>
            <p class="timeline-copy">${{escapeHtml(post.excerpt)}}</p>
          </div>
        </article>
      `).join("");
    }}

    function renderMemorySpotlight() {{
      const pool = SITE_DATA.posts.slice(0, Math.min(12, SITE_DATA.posts.length));
      if (!pool.length) return;
      const post = pool[memoryIndex % pool.length];
      const cover = post.coverUrl || "";
      const fallbackMedia = escapeHtml(JSON.stringify({{
        images: post.imageUrls || [],
        videos: post.videoUrls || [],
        title: post.title || ""
      }}));
      const media = post.coverType === "image"
        ? `<img src="${{escapeHtml(cover)}}" alt="${{escapeHtml(post.title)}}" loading="lazy" data-fallback-media="${{fallbackMedia}}" data-placeholder-text="轮播封面加载失败">`
        : post.coverType === "video"
          ? `<video muted playsinline autoplay loop preload="metadata" src="${{escapeHtml(cover)}}"></video>`
          : `<div style="height:100%;display:grid;place-items:center;color:var(--muted);background:#eadfce;">暂无封面</div>`;
      const dots = pool.map((_, index) => `<span class="memory-dot ${{index === (memoryIndex % pool.length) ? "active" : ""}}"></span>`).join("");
      memoryStage.innerHTML = `
        <article class="memory-slide" data-open-title="${{escapeHtml(post.title)}}">
          <div class="memory-media">${{media}}</div>
          <div class="memory-copy">
            <p class="eyebrow">${{post.displayDate}} · ${{post.themes.join(" · ")}}</p>
            <h3>${{escapeHtml(post.title)}}</h3>
            <p>${{escapeHtml(post.excerpt)}}</p>
            <p class="meta-line">${{post.counts.video}} 视频 · ${{post.counts.image}} 图像${{post.counts.audio ? ` · ${{post.counts.audio}} 音频` : ""}}</p>
            <div class="memory-dots">${{dots}}</div>
          </div>
        </article>
      `;
      attachMediaFallbacks(memoryStage);
      bindOpenEvents();
    }}

    function startMemoryCarousel() {{
      if (memoryTimer) clearInterval(memoryTimer);
      renderMemorySpotlight();
      memoryTimer = setInterval(() => {{
        memoryIndex = (memoryIndex + 1) % Math.max(1, Math.min(12, SITE_DATA.posts.length));
        renderMemorySpotlight();
      }}, 5200);
    }}

    function getLetterItems() {{
      return (SITE_DATA.blessings && SITE_DATA.blessings.items) || [];
    }}

    function letterPageMarkup(item) {{
      const title = item.title || "写给翻到这本影像手账的人";
      const lang = ["zh", "en", "ja"].includes(item.lang) ? item.lang : "zh";
      const body = escapeHtml(item.body || "").replaceAll("\\n", "<br>");
      const quote = escapeHtml(item.quote || "").replaceAll("\\n", "<br>");
      const author = item.author
        ? `<br><span class="eyebrow" style="display:inline-block;margin-top:8px;">${{escapeHtml(item.author)}}</span>`
        : "";
      return `
        <div class="letter-content lang-${{lang}}">
          <div class="letter-kicker">A Letter For You</div>
          <h3 class="letter-title">${{escapeHtml(title)}}</h3>
          <p class="letter-body">${{body}}</p>
          <div class="letter-quote">${{quote}}${{author}}</div>
          <div class="letter-sign">愿山高水长，常有回响。</div>
        </div>
      `;
    }}

    function renderLetterDots(items) {{
      if (!letterDots) return;
      const limit = Math.min(items.length, 12);
      letterDots.innerHTML = items.slice(0, limit).map((_, index) => `
        <span class="letter-dot ${{index === (letterIndex % items.length) ? "active" : ""}}"></span>
      `).join("");
    }}

    function flipLetterTo(index, animate = true) {{
      const items = getLetterItems();
      if (!items.length || !letterCurrent || !letterNext) return;
      const nextIndex = ((index % items.length) + items.length) % items.length;
      const nextItem = items[nextIndex];

      if (!letterReady || !animate || window.matchMedia("(prefers-reduced-motion: reduce)").matches) {{
        letterCurrent.innerHTML = letterPageMarkup(nextItem);
        letterCurrent.className = "letter-paper letter-page-current";
        const previewItem = items[(nextIndex + 1) % items.length] || nextItem;
        letterNext.innerHTML = letterPageMarkup(previewItem);
        letterNext.className = "letter-paper letter-page-next";
        letterIndex = nextIndex;
        letterReady = true;
        renderLetterDots(items);
        return;
      }}

      if (letterAnimating) return;
      letterAnimating = true;
      letterNext.innerHTML = letterPageMarkup(nextItem);
      letterNext.className = "letter-paper letter-page-next letter-page-reveal";
      letterCurrent.classList.add("letter-page-turn");

      window.setTimeout(() => {{
        letterCurrent.innerHTML = letterPageMarkup(nextItem);
        letterCurrent.className = "letter-paper letter-page-current";
        const previewItem = items[(nextIndex + 1) % items.length] || nextItem;
        letterNext.innerHTML = letterPageMarkup(previewItem);
        letterNext.className = "letter-paper letter-page-next";
        letterIndex = nextIndex;
        renderLetterDots(items);
        letterAnimating = false;
      }}, 840);
    }}

    async function loadRemoteBlessings() {{
      try {{
        const response = await fetch(`blessings.json?ts=${{Date.now()}}`, {{ cache: "no-store" }});
        if (!response.ok) return;
        const data = await response.json();
        if (Array.isArray(data.items) && data.items.length) {{
          SITE_DATA.blessings = data;
        }}
      }} catch (_error) {{
        return;
      }}
    }}

    function renderLetter() {{
      flipLetterTo(letterIndex, letterReady);
    }}

    function startLetterFlip() {{
      if (letterTimer) clearInterval(letterTimer);
      const items = getLetterItems();
      if (!items.length) return;
      letterReady = false;
      renderLetter();
      if (items.length <= 1) return;
      letterTimer = setInterval(() => {{
        flipLetterTo(letterIndex + 1);
      }}, 7600);
    }}

    function renderPosts() {{
      const posts = activePosts();
      resultCount.textContent = `当前展示 ${{posts.length}} / ${{SITE_DATA.posts.length}} 篇`;
      emptyState.style.display = posts.length ? "none" : "block";

      postGrid.innerHTML = posts.map((post) => {{
        const themePills = post.themes.map((theme) => `<span class="meta-pill">${{escapeHtml(theme)}}</span>`).join("");
        const mediaMeta = `${{post.counts.video}} 视频 · ${{post.counts.image}} 图像${{post.counts.audio ? ` · ${{post.counts.audio}} 音频` : ""}}`;
        const cover = post.coverUrl || "";
        const fallbackMedia = escapeHtml(JSON.stringify({{
          images: post.imageUrls || [],
          videos: post.videoUrls || [],
          title: post.title || ""
        }}));
        const coverMarkup = post.coverType === "image"
          ? `<img src="${{escapeHtml(cover)}}" alt="${{escapeHtml(post.title)}}" loading="lazy" data-fallback-media="${{fallbackMedia}}" data-placeholder-text="封面加载失败">`
          : post.coverType === "video"
            ? `<video muted playsinline preload="metadata" src="${{escapeHtml(cover)}}"></video>`
            : `<div style="height:100%;display:grid;place-items:center;color:var(--muted);background:#eadfce;">暂无封面</div>`;
        return `
          <article class="post-card" data-open-title="${{escapeHtml(post.title)}}">
            <div class="post-cover">
              ${{coverMarkup}}
            </div>
            <p class="eyebrow">${{post.displayDate}}</p>
            <h3>${{escapeHtml(post.title)}}</h3>
            <div class="post-meta">${{themePills}}</div>
            <p>${{escapeHtml(post.excerpt)}}</p>
            <p class="meta-line">${{mediaMeta}} · ${{post.size}}</p>
          </article>
        `;
      }}).join("");

      renderTimeline(posts);
      bindOpenEvents();
      attachMediaFallbacks(postGrid);
    }}

    function openPost(title) {{
      const post = SITE_DATA.posts.find((item) => item.title === title);
      if (!post) return;

      modalTitle.textContent = post.title;
      modalDate.textContent = post.displayDate;
      modalMeta.textContent = `${{post.themes.join(" · ")}} · ${{post.counts.video}} 视频 · ${{post.counts.image}} 图像${{post.counts.audio ? ` · ${{post.counts.audio}} 音频` : ""}} · ${{post.size}}`;

      const sections = [];

      if (post.videos.length) {{
        sections.push(`
          <section>
            <div class="section-title">
              <h3>视频片段</h3>
              <span>${{post.videos.length}} 个</span>
            </div>
            <div class="video-stack">
              ${{post.videoUrls.map((src) => `<video controls preload="metadata" src="${{escapeHtml(src)}}"></video>`).join("")}}
            </div>
          </section>
        `);
      }}

      if (post.audios.length) {{
        sections.push(`
          <section>
            <div class="section-title">
              <h3>声音记录</h3>
              <span>${{post.audios.length}} 段</span>
            </div>
            <div class="audio-stack">
              ${{post.audioUrls.map((src, index) => `
                <div class="audio-card">
                  <strong>音频 ${{index + 1}}</strong>
                  <audio controls preload="metadata" src="${{escapeHtml(src)}}"></audio>
                </div>
              `).join("")}}
            </div>
          </section>
        `);
      }}

      if (post.images.length) {{
        const fallbackMedia = escapeHtml(JSON.stringify({{
          images: post.imageUrls || [],
          videos: post.videoUrls || [],
          title: post.title || ""
        }}));
        sections.push(`
          <section>
            <div class="section-title">
              <h3>封面与图像</h3>
              <span>${{post.images.length}} 张</span>
            </div>
            <div class="gallery-grid">
              ${{post.imageUrls.map((src) => `
                <figure class="gallery-item">
                  <img loading="lazy" src="${{escapeHtml(src)}}" alt="${{escapeHtml(post.title)}}" data-fallback-media="${{fallbackMedia}}" data-placeholder-text="图片加载失败">
                </figure>
              `).join("")}}
            </div>
          </section>
        `);
      }}

      modalBody.innerHTML = sections.join("");
      attachMediaFallbacks(modalBody);
      modal.classList.add("open");
      modal.setAttribute("aria-hidden", "false");
      document.body.style.overflow = "hidden";
    }}

    function closeModal() {{
      modal.classList.remove("open");
      modal.setAttribute("aria-hidden", "true");
      modalBody.innerHTML = "";
      document.body.style.overflow = "";
    }}

    function setActiveButton(selector, value, attrName) {{
      document.querySelectorAll(selector).forEach((button) => {{
        button.classList.toggle("active", button.getAttribute(attrName) === value);
      }});
    }}

    function refreshButtonState() {{
      document.querySelector('[data-reset="all"]').classList.toggle("active", !state.year && !state.theme && !state.query);
      setActiveButton("[data-year-filter]", state.year, "data-year-filter");
      setActiveButton("[data-theme-filter]", state.theme, "data-theme-filter");
    }}

    function bindOpenEvents() {{
      document.querySelectorAll("[data-open-title]").forEach((node) => {{
        node.onclick = () => openPost(node.getAttribute("data-open-title"));
      }});
    }}

    document.querySelector('[data-reset="all"]').addEventListener("click", () => {{
      state.year = null;
      state.theme = null;
      state.query = "";
      searchInput.value = "";
      refreshButtonState();
      renderPosts();
    }});

    document.querySelectorAll("[data-year-filter]").forEach((button) => {{
      button.addEventListener("click", () => {{
        state.year = state.year === button.dataset.yearFilter ? null : button.dataset.yearFilter;
        refreshButtonState();
        renderPosts();
      }});
    }});

    document.querySelectorAll("[data-theme-filter]").forEach((button) => {{
      button.addEventListener("click", () => {{
        state.theme = state.theme === button.dataset.themeFilter ? null : button.dataset.themeFilter;
        refreshButtonState();
        renderPosts();
      }});
    }});

    searchInput.addEventListener("input", (event) => {{
      state.query = event.target.value;
      refreshButtonState();
      renderPosts();
    }});

    if (letterNextButton) {{
      letterNextButton.addEventListener("click", () => {{
        const items = getLetterItems();
        if (items.length <= 1 || letterAnimating) return;
        if (letterTimer) clearInterval(letterTimer);
        flipLetterTo(letterIndex + 1);
        letterTimer = setInterval(() => {{
          flipLetterTo(letterIndex + 1);
        }}, 7600);
      }});
    }}

    modalClose.addEventListener("click", closeModal);
    modal.addEventListener("click", (event) => {{
      if (event.target === modal) closeModal();
    }});
    document.addEventListener("keydown", (event) => {{
      if (event.key === "Escape") closeModal();
    }});

    attachMediaFallbacks(document.querySelector(".hero-main"));
    initHeroParallax();
    startMemoryCarousel();
    refreshButtonState();
    renderPosts();
    loadRemoteBlessings().finally(() => {{
      startLetterFlip();
    }});
  </script>
</body>
</html>
"""


def main() -> None:
    posts = read_posts()
    summary = build_summary(posts)
    OUTPUT.write_text(render_html(posts, summary), encoding="utf-8")
    print(f"Generated {OUTPUT.name} with {len(posts)} stories.")


if __name__ == "__main__":
    main()
