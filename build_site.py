from __future__ import annotations

import html
import json
import math
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path


ROOT = Path.cwd()
OUTPUT = ROOT / "index.html"
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
                "videos": video_files,
                "audios": audio_files,
                "images": image_files,
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


def render_html(posts: list[dict], summary: dict) -> str:
    payload = json.dumps({"posts": posts, "summary": summary}, ensure_ascii=False)
    featured = summary["featured"]

    def esc(value: str) -> str:
        return html.escape(value, quote=True)

    hero_cards = []
    for item in featured:
        thumb = esc(item["cover"])
        title = esc(item["title"])
        desc = esc(item["excerpt"])
        hero_cards.append(
            f"""
            <article class="hero-card" data-open-title="{title}">
              <div class="hero-thumb">
                <img src="{thumb}" alt="{title}" loading="lazy">
              </div>
              <div class="hero-copy">
                <p class="eyebrow">{esc(item["displayDate"])}</p>
                <h3>{title}</h3>
                <p>{desc}</p>
              </div>
            </article>
            """
        )

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
      --ink: #2f241b;
      --muted: #7a6554;
      --accent: #bc6c4a;
      --accent-soft: #f2d2bf;
      --accent-deep: #8f4930;
      --shadow: 0 24px 60px rgba(71, 44, 24, 0.12);
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
      min-height: 100vh;
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
    }}

    .hero-main,
    .hero-side,
    .panel {{
      backdrop-filter: blur(18px);
      background: var(--paper);
      border: 1px solid var(--line);
      border-radius: var(--radius-xl);
      box-shadow: var(--shadow);
    }}

    .hero-main {{
      padding: clamp(26px, 4vw, 42px);
      position: relative;
      overflow: hidden;
      min-height: 480px;
    }}

    .hero-main::after {{
      content: "";
      position: absolute;
      width: 280px;
      height: 280px;
      right: -70px;
      top: -70px;
      border-radius: 50%;
      background: radial-gradient(circle, rgba(214, 131, 82, 0.24), transparent 68%);
    }}

    .hero-copy-wrap {{
      position: relative;
      z-index: 1;
      display: grid;
      gap: 22px;
      align-content: start;
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
      background: rgba(255, 255, 255, 0.58);
      border: 1px solid rgba(101, 73, 49, 0.1);
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
      border: 1px solid rgba(90, 62, 38, 0.1);
      background: rgba(255, 255, 255, 0.58);
      cursor: pointer;
      transition: transform 180ms ease, box-shadow 180ms ease, border-color 180ms ease;
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

    .hero-thumb img {{
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
      border: 1px solid rgba(99, 72, 49, 0.12);
      border-radius: 999px;
      padding: 10px 14px;
      background: rgba(255, 255, 255, 0.72);
      color: var(--ink);
      cursor: pointer;
      transition: all 160ms ease;
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
      border: 1px solid rgba(90, 62, 38, 0.12);
      border-radius: 18px;
      padding: 14px 16px;
      background: rgba(255, 255, 255, 0.82);
      color: var(--ink);
      outline: none;
    }}

    .search-input:focus {{
      border-color: rgba(188, 108, 74, 0.38);
      box-shadow: 0 0 0 4px rgba(188, 108, 74, 0.1);
    }}

    .content-grid {{
      display: grid;
      grid-template-columns: 0.8fr 1.2fr;
      gap: 22px;
      align-items: start;
    }}

    .timeline {{
      position: sticky;
      top: 16px;
      padding: 22px;
    }}

    .timeline-list {{
      display: grid;
      gap: 14px;
      margin-top: 18px;
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
      background: rgba(255, 255, 255, 0.56);
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
      grid-template-columns: repeat(2, minmax(0, 1fr));
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
    }}

    .post-cover {{
      border-radius: 18px;
      aspect-ratio: 4 / 3;
      overflow: hidden;
      background: #e8dccd;
      margin-bottom: 14px;
      position: relative;
    }}

    .post-cover img {{
      height: 100%;
      object-fit: cover;
      transition: transform 280ms ease;
    }}

    .post-card:hover .post-cover img {{
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

    @media (max-width: 1100px) {{
      .hero,
      .filters,
      .content-grid {{
        grid-template-columns: 1fr;
      }}

      .timeline {{
        position: static;
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
        <div class="hero-copy-wrap">
          <div class="label">Visual Diary</div>
          <h2>把旅行、猫咪、城市与回忆，编成一页页可播放的生活杂志。</h2>
          <p>
            这批素材最适合做成偏杂志化的影像博客，而不是普通文件列表。它有明显的时间推进、反复出现的猫咪线索、
            高频旅行片段和个人节奏感，所以页面以「时间轴 + 主题筛选 + 文章式卡片」来承载这些内容。
          </p>
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
      <aside class="panel timeline fade-in">
        <div class="section-title">
          <h3>时间轴速览</h3>
          <span>点击可直达文章</span>
        </div>
        <div id="timelineList" class="timeline-list"></div>
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
    const resultCount = document.getElementById("resultCount");
    const emptyState = document.getElementById("emptyState");
    const searchInput = document.getElementById("searchInput");
    const modal = document.getElementById("postModal");
    const modalTitle = document.getElementById("modalTitle");
    const modalDate = document.getElementById("modalDate");
    const modalMeta = document.getElementById("modalMeta");
    const modalBody = document.getElementById("modalBody");
    const modalClose = document.getElementById("modalClose");

    function escapeHtml(value) {{
      return value
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;");
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

    function renderPosts() {{
      const posts = activePosts();
      resultCount.textContent = `当前展示 ${{posts.length}} / ${{SITE_DATA.posts.length}} 篇`;
      emptyState.style.display = posts.length ? "none" : "block";

      postGrid.innerHTML = posts.map((post) => {{
        const themePills = post.themes.map((theme) => `<span class="meta-pill">${{escapeHtml(theme)}}</span>`).join("");
        const mediaMeta = `${{post.counts.video}} 视频 · ${{post.counts.image}} 图像${{post.counts.audio ? ` · ${{post.counts.audio}} 音频` : ""}}`;
        const cover = post.cover || "";
        return `
          <article class="post-card" data-open-title="${{escapeHtml(post.title)}}">
            <div class="post-cover">
              <img src="${{escapeHtml(cover)}}" alt="${{escapeHtml(post.title)}}" loading="lazy">
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
              ${{post.videos.map((src) => `<video controls preload="metadata" src="${{escapeHtml(src)}}"></video>`).join("")}}
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
              ${{post.audios.map((src, index) => `
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
        sections.push(`
          <section>
            <div class="section-title">
              <h3>封面与图像</h3>
              <span>${{post.images.length}} 张</span>
            </div>
            <div class="gallery-grid">
              ${{post.images.map((src) => `
                <figure class="gallery-item">
                  <img loading="lazy" src="${{escapeHtml(src)}}" alt="${{escapeHtml(post.title)}}">
                </figure>
              `).join("")}}
            </div>
          </section>
        `);
      }}

      modalBody.innerHTML = sections.join("");
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

    modalClose.addEventListener("click", closeModal);
    modal.addEventListener("click", (event) => {{
      if (event.target === modal) closeModal();
    }});
    document.addEventListener("keydown", (event) => {{
      if (event.key === "Escape") closeModal();
    }});

    refreshButtonState();
    renderPosts();
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
