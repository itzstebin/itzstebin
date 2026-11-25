#!/usr/bin/env python3
"""Automatic GitHub Profile README & Animated SVG Generator.

Generates three complete custom-designed themes (`aquarium`, `title-sequence`,
`repo-galaxy`) using live GitHub profile, repository, language, and contribution
data. Works locally (with HTML/REST fallback + snapshot cache) and automatically
inside GitHub Actions using `GITHUB_TOKEN` GraphQL API.

Zero external Python dependencies (standard library only).
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import math
import os
import random
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT_DIR / "profile.config.json"
SNAPSHOT_PATH = ROOT_DIR / "data" / "github_snapshot.json"
ASSETS_DIR = ROOT_DIR / "assets"
THEMES_DIR = ROOT_DIR / "themes"

LANG_COLORS: dict[str, str] = {
    "HTML": "#e34c26",
    "TypeScript": "#3178c6",
    "JavaScript": "#f7df1e",
    "Python": "#3776ab",
    "CSS": "#563d7c",
    "Kotlin": "#a97bff",
    "Java": "#b07219",
    "C": "#555555",
    "C++": "#f34b7d",
    "PLpgSQL": "#336790",
    "Dockerfile": "#384d54",
    "Shell": "#89e051",
    "Rust": "#dea584",
    "Go": "#00add8",
}

THEMES: dict[str, dict[str, Any]] = {
    "aquarium": {
        "title": "Aquarium",
        "subtitle": "Deep Ocean Telemetry",
        "bg": "#061826",
        "bg_alt": "#0a2236",
        "border": "#154463",
        "accent": "#22d3ee",
        "accent_soft": "#0e7490",
        "accent_2": "#34d399",
        "text": "#f0f9ff",
        "muted": "#8ab4cc",
        "dim": "#4c7691",
        "pill_bg": "#0c2d45",
        "heat": ["#0b2234", "#0e4b66", "#0891b2", "#22d3ee", "#67e8f9"],
        "footer_note": "Aquarium · fish are repos, seaweed is contributions",
    },
    "title-sequence": {
        "title": "Title Sequence",
        "subtitle": "Obsidian & Gold Opening Titles",
        "bg": "#0a0908",
        "bg_alt": "#14110d",
        "border": "#463517",
        "accent": "#f5c451",
        "accent_soft": "#a1751b",
        "accent_2": "#fbbf24",
        "text": "#fff8e7",
        "muted": "#c9b78f",
        "dim": "#7a6a4a",
        "pill_bg": "#1e180f",
        "heat": ["#171410", "#4d3812", "#8f6519", "#d49b27", "#fde073"],
        "footer_note": "Title Sequence · now showing · starring live repositories",
    },
    "repo-galaxy": {
        "title": "Repo Galaxy",
        "subtitle": "Cosmic Constellation Map",
        "bg": "#060919",
        "bg_alt": "#0d132e",
        "border": "#243063",
        "accent": "#60a5fa",
        "accent_soft": "#4f46e5",
        "accent_2": "#c084fc",
        "text": "#f8fafc",
        "muted": "#9fb1d6",
        "dim": "#586b94",
        "pill_bg": "#131c42",
        "heat": ["#0e1530", "#27246e", "#4338ca", "#3b82f6", "#7dd3fc"],
        "footer_note": "Repo Galaxy · each star is a repository, sized by stars",
    },
}

FONT_SANS = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif"
FONT_MONO = "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace"


def esc(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


def truncate(text: str, max_chars: int) -> str:
    text = re.sub(r"\s+", " ", (text or "").strip())
    if len(text) <= max_chars:
        return text
    return text[: max(1, max_chars - 1)].rstrip() + "…"


def wrap_lines(text: str, max_chars: int, max_lines: int = 2) -> list[str]:
    words = re.sub(r"\s+", " ", (text or "").strip()).split(" ")
    lines: list[str] = []
    cur = ""
    for word in words:
        if not word:
            continue
        candidate = f"{cur} {word}".strip()
        if len(candidate) <= max_chars:
            cur = candidate
        else:
            if cur:
                lines.append(cur)
                cur = word
            else:
                lines.append(truncate(word, max_chars))
                cur = ""
            if len(lines) >= max_lines:
                break
    if cur and len(lines) < max_lines:
        lines.append(cur)
    if len(lines) == max_lines and words:
        joined = " ".join(lines)
        full = " ".join(w for w in words if w)
        if len(joined) < len(full):
            lines[-1] = truncate(lines[-1], max_chars)
    return lines or [""]


def get_lang_color(lang: str | None) -> str:
    if not lang:
        return "#94a3b8"
    return LANG_COLORS.get(lang, "#94a3b8")


def http_json(url: str, headers: dict[str, str] | None = None, body: bytes | None = None) -> Any:
    req_headers = {"User-Agent": "itzstebin-profile-generator/1.0"}
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(url, data=body, headers=req_headers)
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def http_text(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read().decode("utf-8", "replace")


def compute_streaks(days: list[dict[str, Any]]) -> tuple[int, int, int]:
    if not days:
        return 0, 0, 0
    ordered = sorted(days, key=lambda d: d["date"])
    longest = 0
    run = 0
    active = 0
    for d in ordered:
        if d.get("count", 0) > 0:
            active += 1
            run += 1
            longest = max(longest, run)
        else:
            run = 0

    current = 0
    idx = len(ordered) - 1
    if idx >= 0 and ordered[idx].get("count", 0) == 0:
        idx -= 1
    while idx >= 0 and ordered[idx].get("count", 0) > 0:
        current += 1
        idx -= 1
    return longest, current, active


def fetch_contributions_html(username: str) -> dict[str, Any]:
    raw = http_text(f"https://github.com/users/{username}/contributions")
    day_map: dict[str, dict[str, Any]] = {}
    for m in re.finditer(
        r'<td[^>]*data-date="(\d{4}-\d{2}-\d{2})"[^>]*id="([^"]+)"[^>]*data-level="(\d)"',
        raw,
    ):
        date_str, comp_id, level = m.group(1), m.group(2), int(m.group(3))
        day_map[comp_id] = {"date": date_str, "level": level, "count": 0}

    # Handle attribute order differences safely
    if not day_map:
        for td_m in re.finditer(r"<td\b[^>]*ContributionCalendar-day[^>]*>", raw):
            tag = td_m.group(0)
            dm = re.search(r'data-date="(\d{4}-\d{2}-\d{2})"', tag)
            im = re.search(r'id="([^"]+)"', tag)
            lm = re.search(r'data-level="(\d)"', tag)
            if dm and im and lm:
                day_map[im.group(1)] = {
                    "date": dm.group(1),
                    "level": int(lm.group(1)),
                    "count": 0,
                }

    for tm in re.finditer(r'<tool-tip[^>]*for="([^"]+)"[^>]*>(.*?)</tool-tip>', raw, re.S):
        comp_id, text = tm.group(1), tm.group(2)
        if comp_id in day_map:
            cm = re.search(r"(\d+)\s+contribution", text)
            day_map[comp_id]["count"] = int(cm.group(1)) if cm else 0

    days = sorted(day_map.values(), key=lambda x: x["date"])
    total = sum(d["count"] for d in days)
    hm = re.search(r"([\d,]+)\s+contributions?\s+in\s+the\s+last\s+year", raw)
    if hm:
        total = max(total, int(hm.group(1).replace(",", "")))
    longest, current, active = compute_streaks(days)
    return {
        "total_year": total,
        "longest_streak": longest,
        "current_streak": current,
        "active_days": active,
        "days": days,
    }


def fetch_graphql(username: str, token: str) -> dict[str, Any]:
    query = """
    query($login: String!) {
      user(login: $login) {
        login
        name
        avatarUrl
        url
        bio
        websiteUrl
        location
        isHireable
        followers { totalCount }
        following { totalCount }
        contributionsCollection {
          contributionCalendar {
            totalContributions
            weeks {
              contributionDays {
                date
                contributionCount
                contributionLevel
              }
            }
          }
        }
        repositories(first: 100, ownerAffiliations: OWNER, privacy: PUBLIC, orderBy: {field: STARGAZERS, direction: DESC}) {
          totalCount
          nodes {
            name
            url
            description
            homepageUrl
            stargazerCount
            forkCount
            isFork
            updatedAt
            primaryLanguage { name }
            repositoryTopics(first: 10) {
              nodes { topic { name } }
            }
            languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
              edges {
                size
                node { name }
              }
            }
          }
        }
      }
    }
    """
    level_map = {
        "NONE": 0,
        "FIRST_QUARTILE": 1,
        "SECOND_QUARTILE": 2,
        "THIRD_QUARTILE": 3,
        "FOURTH_QUARTILE": 4,
    }
    payload = json.dumps({"query": query, "variables": {"login": username}}).encode("utf-8")
    res = http_json(
        "https://api.github.com/graphql",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        body=payload,
    )
    if "errors" in res:
        raise RuntimeError(f"GraphQL error: {res['errors']}")
    u = res["data"]["user"]
    days: list[dict[str, Any]] = []
    cal = u["contributionsCollection"]["contributionCalendar"]
    for week in cal["weeks"]:
        for d in week["contributionDays"]:
            days.append(
                {
                    "date": d["date"],
                    "count": d["contributionCount"],
                    "level": level_map.get(d["contributionLevel"], 0),
                }
            )
    longest, current, active = compute_streaks(days)
    repos = []
    for r in u["repositories"]["nodes"]:
        langs = {e["node"]["name"]: e["size"] for e in r["languages"]["edges"]}
        topics = [t["topic"]["name"] for t in r["repositoryTopics"]["nodes"]]
        repos.append(
            {
                "name": r["name"],
                "html_url": r["url"],
                "description": r["description"],
                "homepage": r["homepageUrl"],
                "stargazers_count": r["stargazerCount"],
                "forks_count": r["forkCount"],
                "fork": r["isFork"],
                "language": r["primaryLanguage"]["name"] if r["primaryLanguage"] else None,
                "topics": topics,
                "updated_at": r["updatedAt"],
                "languages": langs,
            }
        )
    return {
        "user": {
            "login": u["login"],
            "name": u["name"] or u["login"],
            "avatar_url": u["avatarUrl"],
            "html_url": u["url"],
            "bio": u["bio"],
            "blog": u["websiteUrl"],
            "location": u["location"],
            "hireable": u["isHireable"],
            "public_repos": u["repositories"]["totalCount"],
            "followers": u["followers"]["totalCount"],
            "following": u["following"]["totalCount"],
        },
        "repos": repos,
        "contributions": {
            "total_year": cal["totalContributions"],
            "longest_streak": longest,
            "current_streak": current,
            "active_days": active,
            "days": days,
        },
    }


def fetch_github_data(username: str, offline: bool = False) -> dict[str, Any]:
    snapshot: dict[str, Any] = {}
    if SNAPSHOT_PATH.exists():
        snapshot = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))

    if offline and snapshot:
        return snapshot

    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if token:
        try:
            data = fetch_graphql(username, token)
            SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
            SNAPSHOT_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
            return data
        except Exception as exc:
            print(f"[warn] GraphQL fetch failed ({exc}); falling back to REST/HTML.", file=sys.stderr)

    data = json.loads(json.dumps(snapshot)) if snapshot else {"user": {"login": username}, "repos": [], "contributions": {}}

    # Refresh contributions via public HTML (no API rate limit)
    try:
        data["contributions"] = fetch_contributions_html(username)
    except Exception as exc:
        print(f"[warn] Contribution HTML fetch failed ({exc}); keeping snapshot.", file=sys.stderr)

    # Refresh REST user & repos if rate limit permits, preserving cached language breakdowns
    cached_langs = {r["name"]: r.get("languages", {}) for r in data.get("repos", [])}
    try:
        user_raw = http_json(f"https://api.github.com/users/{username}")
        repos_raw = http_json(f"https://api.github.com/users/{username}/repos?per_page=100&sort=updated")
        data["user"] = {
            "login": user_raw.get("login", username),
            "name": user_raw.get("name") or username,
            "avatar_url": user_raw.get("avatar_url", ""),
            "html_url": user_raw.get("html_url", f"https://github.com/{username}"),
            "bio": user_raw.get("bio"),
            "blog": user_raw.get("blog", ""),
            "location": user_raw.get("location"),
            "hireable": user_raw.get("hireable", False),
            "public_repos": user_raw.get("public_repos", len(repos_raw)),
            "followers": user_raw.get("followers", 0),
            "following": user_raw.get("following", 0),
        }
        merged_repos = []
        for r in repos_raw:
            langs = cached_langs.get(r["name"], {})
            try:
                langs = http_json(r["languages_url"])
            except Exception:
                pass
            merged_repos.append(
                {
                    "name": r["name"],
                    "html_url": r["html_url"],
                    "description": r.get("description"),
                    "homepage": r.get("homepage"),
                    "stargazers_count": r.get("stargazers_count", 0),
                    "forks_count": r.get("forks_count", 0),
                    "fork": r.get("fork", False),
                    "language": r.get("language"),
                    "topics": r.get("topics", []),
                    "updated_at": r.get("updated_at", ""),
                    "languages": langs,
                }
            )
        data["repos"] = merged_repos
    except Exception as exc:
        print(f"[info] REST API skipped/rate-limited ({exc}); using cached repos + live contributions.", file=sys.stderr)

    if data:
        SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
        SNAPSHOT_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data


def prepare_metrics(data: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    user = data.get("user", {})
    all_repos = data.get("repos", [])
    excluded = set(config.get("excluded_repos", []))
    include_forks = config.get("include_forks", True)

    visible_repos = [
        r
        for r in all_repos
        if r["name"] not in excluded and (include_forks or not r.get("fork", False))
    ]

    order_map = {name: idx for idx, name in enumerate(config.get("featured_order", []))}
    visible_repos.sort(
        key=lambda r: (
            order_map.get(r["name"], 999),
            -r.get("stargazers_count", 0),
            r.get("updated_at", ""),
        )
    )

    overrides = config.get("repo_overrides", {})
    enriched_repos = []
    for r in visible_repos:
        ov = overrides.get(r["name"], {})
        display = ov.get("display_name") or r["name"]
        desc = r.get("description") or ov.get("summary") or "Open-source project on GitHub."
        badge = ov.get("badge") or (r.get("topics")[0] if r.get("topics") else "") or (
            "Live App" if r.get("homepage") and "github.com" not in r["homepage"] else ""
        )
        enriched_repos.append(
            {
                **r,
                "display_name": display,
                "summary": desc,
                "badge": badge,
            }
        )

    lang_bytes: dict[str, int] = {}
    for r in all_repos:
        if not include_forks and r.get("fork"):
            continue
        for lname, sz in (r.get("languages") or {}).items():
            lang_bytes[lname] = lang_bytes.get(lname, 0) + int(sz)

    total_bytes = sum(lang_bytes.values()) or 1
    top_langs = sorted(lang_bytes.items(), key=lambda x: -x[1])[:6]
    lang_list = [
        {
            "name": lname,
            "bytes": sz,
            "pct": round((sz / total_bytes) * 100, 1),
            "color": get_lang_color(lname),
        }
        for lname, sz in top_langs
    ]

    total_stars = sum(r.get("stargazers_count", 0) for r in all_repos)
    contrib = data.get("contributions", {})
    days = sorted(contrib.get("days", []), key=lambda d: d["date"])

    # Build last 26 weeks grid (columns = weeks, rows = days Sun..Sat)
    last_days = days[-182:] if len(days) >= 182 else days
    weeks: list[list[dict[str, Any]]] = []
    for i in range(0, len(last_days), 7):
        weeks.append(last_days[i : i + 7])
    weekly_totals = [sum(d.get("count", 0) for d in w) for w in weeks]

    return {
        "username": config.get("username") or user.get("login", "itzstebin"),
        "display_name": config.get("display_name") or user.get("name") or "Stebin S",
        "headline": config.get("headline", "Developer · Cybersecurity Learner"),
        "bio": config.get("bio", ""),
        "mantra": config.get("mantra", ""),
        "website": config.get("website", {}),
        "public_repos": user.get("public_repos", len(all_repos)),
        "total_stars": total_stars,
        "followers": user.get("followers", 0),
        "following": user.get("following", 0),
        "total_contributions": contrib.get("total_year", 0),
        "longest_streak": contrib.get("longest_streak", 0),
        "current_streak": contrib.get("current_streak", 0),
        "active_days": contrib.get("active_days", 0),
        "repos": enriched_repos,
        "languages": lang_list,
        "weeks": weeks,
        "weekly_totals": weekly_totals,
        "skills": config.get("skills", []),
        "beyond_code": config.get("beyond_code", []),
        "extra_highlights": config.get("extra_highlights", []),
        "updated_date": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d"),
    }


def svg_wrap(width: int, height: int, body: str, style: str = "", defs: str = "") -> str:
    style_block = f"<style>{style}</style>" if style else ""
    defs_block = f"<defs>{defs}</defs>" if defs else ""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img">\n'
        f"{defs_block}\n{style_block}\n{body}\n</svg>\n"
    )


# ---------------------------------------------------------------------------
# Theme 1: Aquarium
# ---------------------------------------------------------------------------

def render_aquarium_tank(m: dict[str, Any]) -> str:
    t = THEMES["aquarium"]
    w, h = 900, 400
    style = """
      @keyframes sway {
        0%, 100% { transform: rotate(-4deg); }
        50% { transform: rotate(5deg); }
      }
      @keyframes swimA {
        0%, 100% { transform: translate(0px, 0px); }
        50% { transform: translate(16px, -6px); }
      }
      @keyframes swimB {
        0%, 100% { transform: translate(0px, 0px); }
        50% { transform: translate(-16px, 5px); }
      }
      @keyframes bubbleRise {
        0% { transform: translateY(0px); opacity: 0.75; }
        80% { opacity: 0.55; }
        100% { transform: translateY(-145px); opacity: 0; }
      }
      @keyframes beamPulse {
        0%, 100% { opacity: 0.08; }
        50% { opacity: 0.16; }
      }
      .kelp { transform-box: fill-box; transform-origin: bottom center; animation: sway 4.8s ease-in-out infinite; }
      .fish-r { animation: swimA 6s ease-in-out infinite; }
      .fish-l { animation: swimB 6.6s ease-in-out infinite; }
      .bubble { animation: bubbleRise 6.5s linear infinite; }
      .beam { animation: beamPulse 7s ease-in-out infinite; }
    """
    defs = f"""
      <linearGradient id="oceanBg" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="#051c2e"/>
        <stop offset="55%" stop-color="#082c46"/>
        <stop offset="100%" stop-color="#0b3854"/>
      </linearGradient>
      <linearGradient id="sandGrad" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="#6b563c"/>
        <stop offset="100%" stop-color="#3e3121"/>
      </linearGradient>
      <linearGradient id="rayGrad" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="#67e8f9" stop-opacity="0.65"/>
        <stop offset="100%" stop-color="#0891b2" stop-opacity="0"/>
      </linearGradient>
      <linearGradient id="kelpGrad" x1="0" y1="1" x2="0" y2="0">
        <stop offset="0%" stop-color="#0f766e"/>
        <stop offset="100%" stop-color="#34d399"/>
      </linearGradient>
      <clipPath id="tankClip">
        <rect x="1" y="1" width="{w-2}" height="{h-2}" rx="18"/>
      </clipPath>
    """

    parts = [
        f'<g clip-path="url(#tankClip)">',
        f'<rect width="{w}" height="{h}" fill="url(#oceanBg)"/>',
        # Light beams
        '<polygon class="beam" points="110,0 205,0 320,350 185,350" fill="url(#rayGrad)"/>',
        '<polygon class="beam" points="355,0 465,0 595,350 440,350" fill="url(#rayGrad)" style="animation-delay: -2.3s;"/>',
        '<polygon class="beam" points="620,0 710,0 825,350 695,350" fill="url(#rayGrad)" style="animation-delay: -4.1s;"/>',
        # Water surface shimmer
        '<path d="M0,18 Q150,25 300,17 T600,19 T900,17 L900,0 L0,0 Z" fill="#22d3ee" opacity="0.12"/>',
    ]

    # Seaweed from last 26 weeks
    weekly = m["weekly_totals"] or [1] * 26
    if len(weekly) < 26:
        weekly = ([0] * (26 - len(weekly))) + weekly
    weekly = weekly[-26:]
    max_wk = max(weekly) or 1
    for i, cnt in enumerate(weekly):
        x = 44 + i * 32
        kelp_h = 62 + int((cnt / max_wk) * 112) if cnt > 0 else 44
        y_base = 346
        y_top = y_base - kelp_h
        delay = f"-{(i % 7) * 0.65:.2f}s"
        opacity = "0.92" if cnt > 0 else "0.52"
        d = (
            f"M{x},{y_base} C{x-8},{y_base - kelp_h*0.33} {x+9},{y_base - kelp_h*0.66} {x},{y_top} "
            f"C{x+7},{y_base - kelp_h*0.62} {x-6},{y_base - kelp_h*0.28} {x+7},{y_base} Z"
        )
        parts.append(
            f'<path class="kelp" d="{d}" fill="url(#kelpGrad)" opacity="{opacity}" '
            f'style="animation-delay:{delay};"/>'
        )
        if cnt > 0:
            parts.append(
                f'<circle cx="{x}" cy="{y_top+2}" r="2.6" fill="#67e8f9" opacity="0.78"/>'
            )

    # Bubbles tied to active weeks + ambient bubbles
    rng = random.Random(42)
    for i in range(20):
        bx = 60 + i * 41 + rng.randint(-8, 8)
        by = 285 + rng.randint(0, 48)
        br = rng.choice([2.2, 2.8, 3.5, 4.2])
        dur = 5.2 + (i % 5) * 0.9
        delay = -((i * 1.1) % dur)
        parts.append(
            f'<circle class="bubble" cx="{bx}" cy="{by}" r="{br}" fill="none" '
            f'stroke="#a5f3fc" stroke-width="1.2" '
            f'style="animation-duration:{dur:.1f}s; animation-delay:{delay:.1f}s;"/>'
        )

    # Seabed
    parts.append(
        '<path d="M0,342 Q180,331 360,344 T720,336 T900,342 L900,400 L0,400 Z" fill="url(#sandGrad)"/>'
    )
    parts.append(
        '<path d="M0,342 Q180,331 360,344 T720,336 T900,342" fill="none" stroke="#8c7250" stroke-width="1.5" opacity="0.6"/>'
    )

    # Fish placements (carefully spread so labels never overlap)
    fish_slots = [
        (225, 118, 1),   # Hero fish (Whoisit)
        (650, 108, -1),  # priyo-smp-tracker
        (455, 188, 1),   # Mail-Hunter
        (170, 232, 1),   # Shanks
        (725, 224, -1),  # Quantum Traffic
        (450, 278, -1),  # Guess-the-Number
    ]
    repos = m["repos"][: len(fish_slots)]
    max_stars = max((r.get("stargazers_count", 1) for r in repos), default=1) or 1

    for idx, repo in enumerate(repos):
        fx, fy, direction = fish_slots[idx]
        stars = repo.get("stargazers_count", 0)
        scale = 0.85 + 0.42 * (stars / max_stars)
        lang = repo.get("language") or "Code"
        color = get_lang_color(lang)
        cls = "fish-r" if direction > 0 else "fish-l"
        delay = f"-{idx * 1.1:.1f}s"
        label = truncate(repo["display_name"], 22)
        star_txt = f"★ {stars}" if stars else lang
        short_lang = (
            "JS" if lang == "JavaScript"
            else "TS" if lang == "TypeScript"
            else "PY" if lang == "Python"
            else lang[:4].upper()
        )

        # Fish SVG centered at (0,0), facing right when direction > 0
        flip = f"scale({direction * scale:.2f}, {scale:.2f})"
        parts.append(f'<g class="{cls}" style="animation-delay:{delay};">')
        parts.append(f'  <g transform="translate({fx},{fy}) {flip}">')
        # Tail
        parts.append(f'    <polygon points="-24,0 -40,-13 -37,0 -40,13" fill="{color}" opacity="0.88"/>')
        # Dorsal fin
        parts.append(f'    <path d="M-8,-14 Q2,-24 10,-12 Z" fill="{color}" opacity="0.82"/>')
        # Body
        parts.append(f'    <ellipse cx="0" cy="0" rx="28" ry="15" fill="{color}"/>')
        # Belly sheen
        parts.append('    <ellipse cx="2" cy="4" rx="20" ry="7" fill="#ffffff" opacity="0.16"/>')
        # Eye
        parts.append('    <circle cx="17" cy="-4" r="3.4" fill="#061826"/>')
        parts.append('    <circle cx="18" cy="-5" r="1.2" fill="#ffffff"/>')
        parts.append('  </g>')
        # Label pill beneath fish (unflipped so text always reads left-to-right!)
        pill_w = max(92, len(f"{label}  {star_txt}") * 6.5 + 22)
        px = fx - pill_w / 2
        py = fy + 22 * scale + 2
        parts.append(
            f'  <rect x="{px:.1f}" y="{py:.1f}" width="{pill_w:.1f}" height="20" rx="10" '
            f'fill="#041320" fill-opacity="0.78" stroke="{t["border"]}" stroke-width="1"/>'
        )
        parts.append(
            f'  <text x="{fx}" y="{py+13.5:.1f}" text-anchor="middle" fill="{t["text"]}" '
            f'font-family="{FONT_MONO}" font-size="10.5" font-weight="600">'
            f'{esc(label)} <tspan fill="{t["accent"]}">{esc(star_txt)}</tspan></text>'
        )
        parts.append(
            f'  <text x="{fx}" y="{fy+3.5}" text-anchor="middle" fill="#051624" '
            f'font-family="{FONT_MONO}" font-size="{9.5*scale:.1f}" font-weight="800">{esc(short_lang)}</text>'
        )
        parts.append('</g>')

    # Top HUD
    parts.append(
        f'<text x="34" y="34" fill="{t["accent"]}" font-family="{FONT_MONO}" font-size="12" '
        f'font-weight="700" letter-spacing="2">AQUARIUM · @{esc(m["username"].upper())}</text>'
    )
    parts.append(
        f'<text x="866" y="34" text-anchor="end" fill="{t["muted"]}" font-family="{FONT_MONO}" '
        f'font-size="11.5">{m["public_repos"]} repos · {m["total_stars"]} ★ · {m["total_contributions"]} contributions/yr</text>'
    )

    # Bottom Legend on seabed
    parts.append(
        f'<text x="450" y="379" text-anchor="middle" fill="#e2d5c1" font-family="{FONT_MONO}" '
        f'font-size="11" opacity="0.92">'
        f'fish = repositories (sized by stars)  ·  seaweed = 26w contributions  ·  bubbles = live activity'
        f'</text>'
    )
    parts.append('</g>')
    parts.append(f'<rect x="1" y="1" width="{w-2}" height="{h-2}" rx="18" fill="none" stroke="{t["border"]}" stroke-width="1.5"/>')

    return svg_wrap(w, h, "\n".join(parts), style=style, defs=defs)


# ---------------------------------------------------------------------------
# Theme 2: Title Sequence
# ---------------------------------------------------------------------------

def render_title_hero(m: dict[str, Any]) -> str:
    t = THEMES["title-sequence"]
    w, h = 900, 390
    style = """
      @keyframes shimmer {
        0%, 100% { opacity: 0.22; }
        50% { opacity: 0.42; }
      }
      .glow { animation: shimmer 5.5s ease-in-out infinite; }
    """
    defs = """
      <radialGradient id="stageGlow" cx="50%" cy="38%" r="60%">
        <stop offset="0%" stop-color="#4d3409" stop-opacity="0.72"/>
        <stop offset="55%" stop-color="#191309" stop-opacity="0.88"/>
        <stop offset="100%" stop-color="#070605" stop-opacity="1"/>
      </radialGradient>
      <linearGradient id="goldTitle" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="#fff7d6"/>
        <stop offset="45%" stop-color="#f7cb5c"/>
        <stop offset="100%" stop-color="#c28416"/>
      </linearGradient>
      <clipPath id="heroClip">
        <rect x="1" y="1" width="898" height="388" rx="18"/>
      </clipPath>
    """
    name_up = m["display_name"].upper()
    title_size = 64 if len(name_up) <= 12 else 50
    top_langs = " · ".join(l["name"].upper() for l in m["languages"][:3]) or "SOFTWARE DEVELOPER"
    parts = [
        '<g clip-path="url(#heroClip)">',
        f'<rect width="{w}" height="{h}" fill="#070605"/>',
        f'<rect width="{w}" height="{h}" fill="url(#stageGlow)" class="glow"/>',
        # Cinema letterbox bars
        '<rect x="0" y="0" width="900" height="28" fill="#020202"/>',
        '<rect x="0" y="362" width="900" height="28" fill="#020202"/>',
        '<line x1="0" y1="28" x2="900" y2="28" stroke="#3b2c12" stroke-width="1"/>',
        '<line x1="0" y1="362" x2="900" y2="362" stroke="#3b2c12" stroke-width="1"/>',
        # Kicker
        f'<text x="450" y="64" text-anchor="middle" fill="#c9ab67" font-family="{FONT_SANS}" '
        f'font-size="11.5" font-weight="600" letter-spacing="5">GITHUB PICTURES PRESENTS</text>',
        # Extruded 3D title
        f'<text x="454" y="138" text-anchor="middle" fill="#3a2705" font-family="{FONT_SANS}" '
        f'font-size="{title_size}" font-weight="900" letter-spacing="4">{esc(name_up)}</text>',
        f'<text x="452" y="135" text-anchor="middle" fill="#6b4a0d" font-family="{FONT_SANS}" '
        f'font-size="{title_size}" font-weight="900" letter-spacing="4">{esc(name_up)}</text>',
        f'<text x="450" y="132" text-anchor="middle" fill="url(#goldTitle)" font-family="{FONT_SANS}" '
        f'font-size="{title_size}" font-weight="900" letter-spacing="4">{esc(name_up)}</text>',
        # Subtitle
        f'<text x="450" y="166" text-anchor="middle" fill="#d9c698" font-family="{FONT_SANS}" '
        f'font-size="12" font-weight="600" letter-spacing="3.5">{esc(top_langs)} DEVELOPER</text>',
        '<line x1="250" y1="184" x2="650" y2="184" stroke="#4a3818" stroke-width="1"/>',
    ]

    # Starring list (top 4 repos)
    for idx, repo in enumerate(m["repos"][:4]):
        ry = 216 + idx * 28
        lang = repo.get("language") or "CODE"
        lcol = get_lang_color(lang)
        short = (
            "JS" if lang == "JavaScript"
            else "TS" if lang == "TypeScript"
            else "PY" if lang == "Python"
            else lang[:4].upper()
        )
        stars = repo.get("stargazers_count", 0)
        parts.append(
            f'<rect x="275" y="{ry-13}" width="32" height="17" rx="4" fill="{lcol}" fill-opacity="0.18" '
            f'stroke="{lcol}" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="291" y="{ry-1}" text-anchor="middle" fill="{lcol}" font-family="{FONT_MONO}" '
            f'font-size="9.5" font-weight="700">{esc(short)}</text>'
        )
        parts.append(
            f'<text x="319" y="{ry}" fill="#9a8b6c" font-family="{FONT_MONO}" font-size="12.5">'
            f'starring <tspan fill="#fff5d8" font-family="{FONT_SANS}" font-weight="700" font-size="14">{esc(truncate(repo["display_name"], 24))}</tspan></text>'
        )
        parts.append(
            f'<text x="625" y="{ry}" text-anchor="end" fill="#f5c451" font-family="{FONT_MONO}" '
            f'font-size="12.5" font-weight="700">★ {stars}</text>'
        )

    # Bottom billing bar
    parts.append(
        f'<text x="34" y="346" fill="#9a8b6c" font-family="{FONT_MONO}" font-size="11.5">'
        f'{m["total_contributions"]} contributions  ·  {m["followers"]} followers  ·  {m["public_repos"]} repositories  ·  {m["total_stars"]} ★'
        f'</text>'
    )
    parts.append(
        f'<text x="866" y="346" text-anchor="end" fill="#c9ab67" font-family="{FONT_MONO}" font-size="11.5">'
        f'@{esc(m["username"])} · LIVE PRODUCTION</text>'
    )
    parts.append('</g>')
    parts.append(f'<rect x="1" y="1" width="{w-2}" height="{h-2}" rx="18" fill="none" stroke="{t["border"]}" stroke-width="1.5"/>')
    return svg_wrap(w, h, "\n".join(parts), style=style, defs=defs)


def render_title_cast(m: dict[str, Any]) -> str:
    t = THEMES["title-sequence"]
    repos = m["repos"][:5]
    w = 900
    row_h = 44
    h = 74 + len(repos) * row_h + 18
    parts = [
        f'<rect x="1" y="1" width="{w-2}" height="{h-2}" rx="16" fill="{t["bg"]}" stroke="{t["border"]}" stroke-width="1.5"/>',
        f'<text x="28" y="36" fill="{t["accent"]}" font-family="{FONT_MONO}" font-size="11.5" font-weight="700" letter-spacing="2.5">STARRING · FEATURED CREDITS</text>',
        f'<text x="872" y="36" text-anchor="end" fill="{t["dim"]}" font-family="{FONT_MONO}" font-size="11">SORTED BY FEATURED &amp; STARS</text>',
        f'<line x1="28" y1="50" x2="872" y2="50" stroke="{t["border"]}" stroke-width="1"/>',
    ]
    for i, repo in enumerate(repos):
        ry = 64 + i * row_h
        lang = repo.get("language") or "Code"
        lcol = get_lang_color(lang)
        parts.append(
            f'<rect x="28" y="{ry}" width="844" height="36" rx="8" fill="{t["bg_alt"]}" stroke="{t["border"]}" stroke-opacity="0.55"/>'
        )
        parts.append(
            f'<text x="44" y="{ry+22}" fill="{t["dim"]}" font-family="{FONT_MONO}" font-size="11.5" font-weight="700">{i+1:02d}</text>'
        )
        parts.append(f'<circle cx="80" cy="{ry+18}" r="4.5" fill="{lcol}"/>')
        parts.append(
            f'<text x="94" y="{ry+22}" fill="{t["text"]}" font-family="{FONT_SANS}" font-size="13.5" font-weight="700">{esc(truncate(repo["display_name"], 24))}</text>'
        )
        parts.append(
            f'<text x="315" y="{ry+22}" fill="{t["muted"]}" font-family="{FONT_SANS}" font-size="12">{esc(truncate(repo["summary"], 64))}</text>'
        )
        parts.append(
            f'<text x="854" y="{ry+22}" text-anchor="end" fill="{t["accent"]}" font-family="{FONT_MONO}" font-size="12" font-weight="700">★ {repo.get("stargazers_count", 0)}</text>'
        )
    return svg_wrap(w, h, "\n".join(parts))


# ---------------------------------------------------------------------------
# Theme 3: Repo Galaxy
# ---------------------------------------------------------------------------

def render_repo_galaxy(m: dict[str, Any]) -> str:
    t = THEMES["repo-galaxy"]
    w, h = 900, 400
    style = """
      @keyframes twinkle {
        0%, 100% { opacity: 0.25; }
        50% { opacity: 0.95; }
      }
      @keyframes haloPulse {
        0%, 100% { transform: scale(1); opacity: 0.45; }
        50% { transform: scale(1.22); opacity: 0.85; }
      }
      .tw { animation: twinkle 4.2s ease-in-out infinite; }
      .halo { transform-box: fill-box; transform-origin: center; animation: haloPulse 3.8s ease-in-out infinite; }
    """
    defs = """
      <radialGradient id="nebula" cx="67%" cy="50%" r="55%">
        <stop offset="0%" stop-color="#312e81" stop-opacity="0.52"/>
        <stop offset="45%" stop-color="#1e1b4b" stop-opacity="0.28"/>
        <stop offset="100%" stop-color="#060919" stop-opacity="0"/>
      </radialGradient>
      <radialGradient id="coreGlow" cx="50%" cy="50%" r="50%">
        <stop offset="0%" stop-color="#e0f2fe" stop-opacity="0.95"/>
        <stop offset="35%" stop-color="#60a5fa" stop-opacity="0.45"/>
        <stop offset="100%" stop-color="#60a5fa" stop-opacity="0"/>
      </radialGradient>
      <clipPath id="galClip">
        <rect x="1" y="1" width="898" height="398" rx="18"/>
      </clipPath>
    """
    parts = [
        '<g clip-path="url(#galClip)">',
        f'<rect width="{w}" height="{h}" fill="{t["bg"]}"/>',
        f'<rect width="{w}" height="{h}" fill="url(#nebula)"/>',
    ]

    rng = random.Random(108)
    # Background starfield
    for i in range(65):
        sx = rng.randint(15, 885)
        sy = rng.randint(15, 385)
        sr = rng.choice([0.8, 1.1, 1.4])
        delay = f"-{(i % 9) * 0.45:.2f}s"
        parts.append(
            f'<circle class="tw" cx="{sx}" cy="{sy}" r="{sr}" fill="#cbd5e1" style="animation-delay:{delay};"/>'
        )

    # Galactic center at (590, 200)
    gx, gy = 590, 200
    parts.append(
        f'<g transform="translate({gx},{gy}) rotate(-14)">'
        '  <ellipse rx="235" ry="96" fill="none" stroke="#334155" stroke-width="1" stroke-dasharray="3 6" opacity="0.55"/>'
        '  <ellipse rx="158" ry="64" fill="none" stroke="#475569" stroke-width="1" opacity="0.45"/>'
        '  <ellipse rx="84" ry="34" fill="none" stroke="#64748b" stroke-width="1" opacity="0.4"/>'
        '</g>'
    )

    # Spiral arm dust particles colored by top languages
    langs = m["languages"] or [{"name": "TypeScript", "color": "#3178c6", "pct": 100.0}]
    for arm in range(2):
        for step in range(95):
            frac = step / 95.0
            theta = arm * math.pi + frac * 3.1 * math.pi + rng.uniform(-0.22, 0.22)
            rad = 22 + frac * 225
            px = gx + math.cos(theta) * rad * 1.05
            py = gy + math.sin(theta) * rad * 0.46
            # slight tilt -14 deg
            dx, dy = px - gx, py - gy
            ca, sa = math.cos(-0.24), math.sin(-0.24)
            rx = gx + dx * ca - dy * sa
            ry = gy + dx * sa + dy * ca
            col = langs[(step + arm) % len(langs)]["color"]
            rsize = rng.uniform(1.1, 2.3)
            op = rng.uniform(0.32, 0.78)
            parts.append(f'<circle cx="{rx:.1f}" cy="{ry:.1f}" r="{rsize:.1f}" fill="{col}" opacity="{op:.2f}"/>')

    # Galactic core
    parts.append(f'<circle cx="{gx}" cy="{gy}" r="36" fill="url(#coreGlow)"/>')
    parts.append(f'<circle cx="{gx}" cy="{gy}" r="4.5" fill="#ffffff"/>')

    # Repo star nodes positioned around well-spaced non-overlapping coordinates
    star_coords = [
        (465, 138),  # Top-left bright star (Whoisit)
        (765, 132),  # Top-right (priyo-smp-tracker)
        (445, 250),  # Bottom-left (Mail-Hunter)
        (735, 272),  # Bottom-right (Shanks)
        (600, 74),   # Top center (Quantum Traffic)
        (585, 336),  # Bottom center (Guess-the-Number)
    ]
    repos = m["repos"][: len(star_coords)]
    max_stars = max((r.get("stargazers_count", 1) for r in repos), default=1) or 1
    for idx, repo in enumerate(repos):
        sx, sy = star_coords[idx]
        stars = repo.get("stargazers_count", 0)
        lcol = get_lang_color(repo.get("language"))
        r_core = 4.2 + 3.4 * (stars / max_stars)
        r_halo = r_core * 2.5
        delay = f"-{idx * 0.6:.1f}s"
        parts.append(
            f'<circle class="halo" cx="{sx}" cy="{sy}" r="{r_halo:.1f}" fill="{lcol}" '
            f'fill-opacity="0.22" style="animation-delay:{delay};"/>'
        )
        parts.append(
            f'<circle cx="{sx}" cy="{sy}" r="{r_core:.1f}" fill="{lcol}" stroke="#ffffff" stroke-width="1.3"/>'
        )
        lbl = f"{truncate(repo['display_name'], 22)} ★ {stars}"
        pw = len(lbl) * 6.4 + 16
        # Place pill safely right/left depending on position
        lx = sx + 12 if sx < 650 else sx - pw - 12
        ly = sy - 10
        parts.append(
            f'<rect x="{lx:.1f}" y="{ly:.1f}" width="{pw:.1f}" height="20" rx="6" '
            f'fill="#070c22" fill-opacity="0.86" stroke="{t["border"]}" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{lx + pw/2:.1f}" y="{ly + 13.5:.1f}" text-anchor="middle" fill="{t["text"]}" '
            f'font-family="{FONT_MONO}" font-size="10.5" font-weight="600">{esc(lbl)}</text>'
        )

    # Left column telemetry
    parts.append(
        f'<text x="36" y="54" fill="{t["accent"]}" font-family="{FONT_MONO}" font-size="11.5" '
        f'font-weight="700" letter-spacing="2.8">REPO GALAXY</text>'
    )
    parts.append(
        f'<text x="36" y="88" fill="{t["text"]}" font-family="{FONT_SANS}" font-size="26" font-weight="800">'
        f'@{esc(m["username"])}</text>'
    )
    parts.append(
        f'<text x="36" y="114" fill="{t["muted"]}" font-family="{FONT_SANS}" font-size="13">'
        f'{m["total_stars"]} stars · {m["public_repos"]} repositories</text>'
    )
    parts.append(
        f'<text x="36" y="135" fill="{t["dim"]}" font-family="{FONT_SANS}" font-size="11.5">'
        f'Each star is a repository, sized by stars.</text>'
    )
    parts.append(
        f'<text x="36" y="182" fill="{t["accent"]}" font-family="{FONT_MONO}" font-size="11" '
        f'font-weight="700" letter-spacing="2">SPIRAL ARMS</text>'
    )
    for idx, lang in enumerate(m["languages"][:6]):
        ly = 210 + idx * 24
        parts.append(f'<circle cx="42" cy="{ly-4}" r="4.5" fill="{lang["color"]}"/>')
        parts.append(
            f'<text x="56" y="{ly}" fill="{t["text"]}" font-family="{FONT_SANS}" font-size="12.5" font-weight="600">'
            f'{esc(lang["name"])}</text>'
        )
        parts.append(
            f'<text x="236" y="{ly}" text-anchor="end" fill="{t["muted"]}" font-family="{FONT_MONO}" font-size="12">'
            f'{lang["pct"]:.1f}%</text>'
        )
    parts.append('</g>')
    parts.append(f'<rect x="1" y="1" width="{w-2}" height="{h-2}" rx="18" fill="none" stroke="{t["border"]}" stroke-width="1.5"/>')
    return svg_wrap(w, h, "\n".join(parts), style=style, defs=defs)


# ---------------------------------------------------------------------------
# Shared Thematic Section SVGs (About, Repo Cards, Stack, Activity Log)
# ---------------------------------------------------------------------------

def render_about_svg(m: dict[str, Any], theme_key: str) -> str:
    t = THEMES[theme_key]
    w, h = 900, 178
    kicker = {
        "aquarium": "OBSERVATION DECK · ABOUT",
        "title-sequence": "DIRECTOR'S LOGLINE · ABOUT",
        "repo-galaxy": "MISSION BRIEFING · ABOUT",
    }[theme_key]

    bio_lines = wrap_lines(m["bio"], 76, max_lines=2)
    stats = [
        ("REPOS", str(m["public_repos"])),
        ("STARS", str(m["total_stars"])),
        ("YEARLY", str(m["total_contributions"])),
        ("FOLLOWERS", str(m["followers"])),
    ]

    parts = [
        f'<rect x="1" y="1" width="{w-2}" height="{h-2}" rx="16" fill="{t["bg"]}" stroke="{t["border"]}" stroke-width="1.5"/>',
        f'<text x="28" y="34" fill="{t["accent"]}" font-family="{FONT_MONO}" font-size="11" font-weight="700" letter-spacing="2.2">{esc(kicker)}</text>',
        f'<text x="28" y="64" fill="{t["text"]}" font-family="{FONT_SANS}" font-size="22" font-weight="800">{esc(m["display_name"])} <tspan fill="{t["muted"]}" font-size="14" font-weight="500">· {esc(m["headline"])}</tspan></text>',
    ]
    for i, line in enumerate(bio_lines):
        parts.append(
            f'<text x="28" y="{92 + i*20}" fill="{t["muted"]}" font-family="{FONT_SANS}" font-size="13">{esc(line)}</text>'
        )
    parts.append(
        f'<rect x="28" y="132" width="465" height="26" rx="7" fill="{t["pill_bg"]}" stroke="{t["border"]}" stroke-width="1"/>'
    )
    parts.append(
        f'<text x="42" y="149" fill="{t["accent"]}" font-family="{FONT_MONO}" font-size="11.5" font-weight="600">$ {esc(m["mantra"])}</text>'
    )

    # 4 stat tiles on the right
    for i, (lbl, val) in enumerate(stats):
        bx = 532 + i * 86
        by = 46
        parts.append(
            f'<rect x="{bx}" y="{by}" width="78" height="86" rx="11" fill="{t["bg_alt"]}" stroke="{t["border"]}" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{bx+39}" y="{by+42}" text-anchor="middle" fill="{t["text"]}" font-family="{FONT_SANS}" font-size="23" font-weight="800">{esc(val)}</text>'
        )
        parts.append(
            f'<text x="{bx+39}" y="{by+66}" text-anchor="middle" fill="{t["dim"]}" font-family="{FONT_MONO}" font-size="10" font-weight="700" letter-spacing="1">{lbl}</text>'
        )

    parts.append(
        f'<text x="872" y="152" text-anchor="end" fill="{t["dim"]}" font-family="{FONT_MONO}" font-size="10.5">Auto-synced · {esc(m["updated_date"])}</text>'
    )
    return svg_wrap(w, h, "\n".join(parts))


def render_card_svg(repo: dict[str, Any], idx: int, theme_key: str) -> str:
    t = THEMES[theme_key]
    w, h = 440, 174
    lang = repo.get("language") or "Code"
    lcol = get_lang_color(lang)
    stars = repo.get("stargazers_count", 0)
    prefix = "SPECIMEN" if theme_key == "aquarium" else "STAR"
    lines = wrap_lines(repo["summary"], 62, max_lines=2)
    badge = repo.get("badge") or ("Fork" if repo.get("fork") else "Public")

    parts = [
        f'<rect x="1" y="1" width="{w-2}" height="{h-2}" rx="15" fill="{t["bg"]}" stroke="{t["border"]}" stroke-width="1.5"/>',
        f'<rect x="1" y="1" width="{w-2}" height="4" rx="2" fill="{lcol}" opacity="0.85"/>',
        f'<text x="22" y="32" fill="{t["accent"]}" font-family="{FONT_MONO}" font-size="10.5" font-weight="700" letter-spacing="2">{prefix} {idx+1:02d}</text>',
    ]

    # Small thematic emblem on top-right
    if theme_key == "aquarium":
        parts.append(
            f'<g transform="translate(396,28)">'
            f'  <polygon points="-14,0 -23,-7 -21,0 -23,7" fill="{lcol}" opacity="0.85"/>'
            f'  <ellipse cx="0" cy="0" rx="15" ry="8" fill="{lcol}"/>'
            f'  <circle cx="8" cy="-2" r="2" fill="#061826"/>'
            f'</g>'
        )
    else:
        parts.append(
            f'<g transform="translate(398,28)">'
            f'  <circle cx="0" cy="0" r="11" fill="{lcol}" fill-opacity="0.22"/>'
            f'  <circle cx="0" cy="0" r="5" fill="{lcol}" stroke="#ffffff" stroke-width="1"/>'
            f'</g>'
        )

    parts.append(
        f'<text x="22" y="60" fill="{t["text"]}" font-family="{FONT_SANS}" font-size="19" font-weight="800">'
        f'{esc(truncate(repo["display_name"], 28))}</text>'
    )
    for li, line in enumerate(lines):
        parts.append(
            f'<text x="22" y="{86 + li*20}" fill="{t["muted"]}" font-family="{FONT_SANS}" font-size="12">{esc(line)}</text>'
        )

    # Bottom pills
    parts.append(f'<circle cx="28" cy="146" r="5" fill="{lcol}"/>')
    parts.append(
        f'<text x="40" y="150" fill="{t["text"]}" font-family="{FONT_MONO}" font-size="11.5" font-weight="600">{esc(lang)}</text>'
    )
    parts.append(
        f'<text x="155" y="150" fill="{t["accent"]}" font-family="{FONT_MONO}" font-size="11.5" font-weight="700">★ {stars}</text>'
    )
    bw = max(72, len(badge) * 6.8 + 18)
    parts.append(
        f'<rect x="{w - 22 - bw:.1f}" y="133" width="{bw:.1f}" height="24" rx="12" fill="{t["pill_bg"]}" stroke="{t["border"]}" stroke-width="1"/>'
    )
    parts.append(
        f'<text x="{w - 22 - bw/2:.1f}" y="149" text-anchor="middle" fill="{t["muted"]}" font-family="{FONT_MONO}" font-size="10.5">{esc(truncate(badge, 18))}</text>'
    )
    return svg_wrap(w, h, "\n".join(parts))


def render_stack_svg(m: dict[str, Any], theme_key: str) -> str:
    t = THEMES[theme_key]
    w, h = 900, 236
    heading = {
        "aquarium": "WATER CHEMISTRY · LANGUAGE STACK",
        "title-sequence": "THE CAST · LANGUAGES & PRODUCTION GEAR",
        "repo-galaxy": "ELEMENTS · LANGUAGE COMPOSITION",
    }[theme_key]

    parts = [
        f'<rect x="1" y="1" width="{w-2}" height="{h-2}" rx="16" fill="{t["bg"]}" stroke="{t["border"]}" stroke-width="1.5"/>',
        f'<text x="28" y="34" fill="{t["accent"]}" font-family="{FONT_MONO}" font-size="11" font-weight="700" letter-spacing="2.2">{esc(heading)}</text>',
        f'<line x1="468" y1="54" x2="468" y2="210" stroke="{t["border"]}" stroke-width="1" stroke-dasharray="3 4"/>',
    ]

    # Left: Language bars (max 6)
    for i, lang in enumerate(m["languages"][:6]):
        ly = 68 + i * 26
        bar_max = 225
        bw = max(6, int((lang["pct"] / 100.0) * bar_max))
        parts.append(f'<circle cx="34" cy="{ly-4}" r="4.5" fill="{lang["color"]}"/>')
        parts.append(
            f'<text x="48" y="{ly}" fill="{t["text"]}" font-family="{FONT_SANS}" font-size="12.5" font-weight="600">{esc(lang["name"])}</text>'
        )
        parts.append(
            f'<rect x="155" y="{ly-10}" width="{bar_max}" height="9" rx="4.5" fill="{t["pill_bg"]}"/>'
        )
        parts.append(
            f'<rect x="155" y="{ly-10}" width="{bw}" height="9" rx="4.5" fill="{lang["color"]}"/>'
        )
        parts.append(
            f'<text x="442" y="{ly}" text-anchor="end" fill="{t["muted"]}" font-family="{FONT_MONO}" font-size="11.5">{lang["pct"]:.1f}%</text>'
        )

    # Right: Skills & focus pills
    parts.append(
        f'<text x="494" y="66" fill="{t["muted"]}" font-family="{FONT_MONO}" font-size="11" font-weight="700" letter-spacing="1.8">TOOLKIT &amp; FOCUS AREAS</text>'
    )
    cx, cy = 494, 84
    max_x = 874
    for skill in m["skills"]:
        pw = len(skill) * 6.8 + 20
        if cx + pw > max_x:
            cx = 494
            cy += 32
        if cy > 195:
            break
        parts.append(
            f'<rect x="{cx:.1f}" y="{cy}" width="{pw:.1f}" height="24" rx="7" fill="{t["bg_alt"]}" stroke="{t["border"]}" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{cx + pw/2:.1f}" y="{cy + 16}" text-anchor="middle" fill="{t["text"]}" font-family="{FONT_MONO}" font-size="11">{esc(skill)}</text>'
        )
        cx += pw + 8

    return svg_wrap(w, h, "\n".join(parts))


def render_log_svg(m: dict[str, Any], theme_key: str) -> str:
    t = THEMES[theme_key]
    w, h = 900, 222
    heading = {
        "aquarium": "DEPTH LOG · LAST 26 WEEKS",
        "title-sequence": "BOX OFFICE · 26-WEEK PRODUCTION LOG",
        "repo-galaxy": "ORBITAL ACTIVITY · LAST 26 WEEKS",
    }[theme_key]

    parts = [
        f'<rect x="1" y="1" width="{w-2}" height="{h-2}" rx="16" fill="{t["bg"]}" stroke="{t["border"]}" stroke-width="1.5"/>',
        f'<text x="28" y="34" fill="{t["accent"]}" font-family="{FONT_MONO}" font-size="11" font-weight="700" letter-spacing="2.2">{esc(heading)}</text>',
        f'<text x="872" y="34" text-anchor="end" fill="{t["muted"]}" font-family="{FONT_MONO}" font-size="11">LIVE CONTRIBUTION HEATMAP</text>',
    ]

    weeks = m["weeks"]
    if not weeks:
        weeks = [[{"level": 0, "count": 0} for _ in range(7)] for _ in range(26)]
    weeks = weeks[-26:]

    ox, oy = 30, 62
    cell, gap = 15, 4
    heat = t["heat"]
    last_month = ""
    last_month_wi = -99
    for wi, week in enumerate(weeks):
        if week and week[0].get("date"):
            try:
                d_obj = dt.date.fromisoformat(week[0]["date"])
                m_lbl = d_obj.strftime("%b")
                if m_lbl != last_month and wi < len(weeks) - 1 and (wi - last_month_wi) >= 2:
                    last_month = m_lbl
                    last_month_wi = wi
                    mx = ox + wi * (cell + gap)
                    parts.append(
                        f'<text x="{mx}" y="53" fill="{t["dim"]}" font-family="{FONT_MONO}" font-size="9.5">{esc(m_lbl)}</text>'
                    )
            except ValueError:
                pass
        for di, day in enumerate(week[:7]):
            lvl = max(0, min(4, int(day.get("level", 0))))
            x = ox + wi * (cell + gap)
            y = oy + di * (cell + gap)
            parts.append(
                f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="3.5" fill="{heat[lvl]}"/>'
            )

    # Legend below grid
    parts.append(
        f'<text x="30" y="207" fill="{t["dim"]}" font-family="{FONT_MONO}" font-size="10">Less</text>'
    )
    for li, col in enumerate(heat):
        parts.append(
            f'<rect x="{62 + li*16}" y="197" width="11" height="11" rx="2.5" fill="{col}"/>'
        )
    parts.append(
        f'<text x="148" y="207" fill="{t["dim"]}" font-family="{FONT_MONO}" font-size="10">More</text>'
    )

    # Right summary panel
    metrics = [
        ("YEARLY", f'{m["total_contributions"]}', "contributions"),
        ("ACTIVE DAYS", f'{m["active_days"]}', "in last year"),
        ("LONGEST STREAK", f'{m["longest_streak"]}d', "consecutive"),
        ("CURRENT STREAK", f'{m["current_streak"]}d', "active run"),
    ]
    for i, (lbl, val, sub) in enumerate(metrics):
        col_i = i % 2
        row_i = i // 2
        bx = 550 + col_i * 165
        by = 54 + row_i * 68
        parts.append(
            f'<rect x="{bx}" y="{by}" width="152" height="58" rx="10" fill="{t["bg_alt"]}" stroke="{t["border"]}" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{bx+14}" y="{by+20}" fill="{t["dim"]}" font-family="{FONT_MONO}" font-size="9.5" font-weight="700" letter-spacing="1">{lbl}</text>'
        )
        parts.append(
            f'<text x="{bx+14}" y="{by+44}" fill="{t["text"]}" font-family="{FONT_SANS}" font-size="20" font-weight="800">{esc(val)}</text>'
        )
        parts.append(
            f'<text x="{bx+138}" y="{by+43}" text-anchor="end" fill="{t["muted"]}" font-family="{FONT_MONO}" font-size="10">{sub}</text>'
        )

    return svg_wrap(w, h, "\n".join(parts))


# ---------------------------------------------------------------------------
# README & Preview HTML Builders
# ---------------------------------------------------------------------------

def render_readme(m: dict[str, Any], theme_key: str, asset_prefix: str, root_prefix: str, config: dict[str, Any]) -> str:
    t = THEMES[theme_key]
    u = m["username"]
    ap = f"{asset_prefix}/{theme_key}"

    lines: list[str] = ['<div align="center">', ""]

    if theme_key == "aquarium":
        lines.append(f'<picture><img src="{ap}/tank.svg" width="100%" alt="{esc(m["display_name"])} repository aquarium"></picture>')
        lines.append("")
        lines.append("<sub>Every fish is a repository sized by stars; swaying seaweed tracks 26 weeks of commits.</sub>")
        lines.append("")
        lines.append(f'<picture><img src="{ap}/about.svg" width="100%" alt="About {esc(m["display_name"])}"></picture>')
        lines.append("")
        lines.append("## 🐠 Featured Specimens")
        lines.append("")
        lines.append("<p>")
        for i, repo in enumerate(m["repos"][:4]):
            lines.append(
                f'  <a href="{repo["html_url"]}"><picture><img src="{ap}/card-{i}.svg" width="49%" alt="{esc(repo["display_name"])}"></picture></a>'
            )
        lines.append("</p>")
    elif theme_key == "title-sequence":
        lines.append(f'<picture><img src="{ap}/hero.svg" width="100%" alt="{esc(m["display_name"])} opening titles"></picture>')
        lines.append("")
        lines.append(f'<picture><img src="{ap}/about.svg" width="100%" alt="About {esc(m["display_name"])}"></picture>')
        lines.append("")
        lines.append(f'<picture><img src="{ap}/cast.svg" width="100%" alt="Featured repositories"></picture>')
        lines.append("")
        repo_links = " · ".join(f'<a href="{r["html_url"]}">{esc(r["display_name"])}</a>' for r in m["repos"][:6])
        lines.append(f"<p>{repo_links}</p>")
    else:  # repo-galaxy
        lines.append(f'<picture><img src="{ap}/galaxy.svg" width="100%" alt="{esc(m["display_name"])} repo galaxy"></picture>')
        lines.append("")
        lines.append(f'<picture><img src="{ap}/about.svg" width="100%" alt="About {esc(m["display_name"])}"></picture>')
        lines.append("")
        lines.append("## ✦ Brightest Stars")
        lines.append("")
        lines.append("<p>")
        for i, repo in enumerate(m["repos"][:4]):
            lines.append(
                f'  <a href="{repo["html_url"]}"><picture><img src="{ap}/card-{i}.svg" width="49%" alt="{esc(repo["display_name"])}"></picture></a>'
            )
        lines.append("</p>")

    lines.extend([
        "",
        f'<picture><img src="{ap}/stack.svg" width="100%" alt="Language stack and focus areas"></picture>',
        "",
        f'<picture><img src="{ap}/log.svg" width="100%" alt="26-week contribution log"></picture>',
        "",
        "</div>",
        "",
        "---",
        "",
        "### 🚀 What I'm Building & Exploring",
        "",
    ])

    for item in m["extra_highlights"]:
        tag = f' `{item["tag"]}`' if item.get("tag") else ""
        if item.get("url"):
            lines.append(f'- **[{item["name"]}]({item["url"]})**{tag} — {item["summary"]}')
        else:
            lines.append(f'- **{item["name"]}**{tag} — {item["summary"]}')

    if m["beyond_code"]:
        beyond = " · ".join(m["beyond_code"])
        lines.extend(["", f"**Beyond Code:** {beyond}"])

    # Preserve integration with existing automated 3D contrib & snake workflows
    if config.get("include_3d_contrib") or config.get("include_snake"):
        lines.extend([
            "",
            "<details>",
            "<summary><b>✨ 3D Contribution Skyline &amp; Contribution Snake (Auto-Updated)</b></summary>",
            "",
            '<div align="center">',
            "",
        ])
        if config.get("include_3d_contrib"):
            lines.append(
                f'<img src="{root_prefix}/profile-3d-contrib/profile-night-view.svg" width="100%" alt="3D Contribution Graph"/>'
            )
            lines.append("")
        if config.get("include_snake"):
            lines.append(
                f'<img src="https://raw.githubusercontent.com/{u}/{u}/output/github-contribution-grid-snake-dark.svg" width="95%" alt="Contribution Snake"/>'
            )
            lines.append("")
        lines.extend(["</div>", "", "</details>"])

    # Footer links
    web = m.get("website", {})
    web_link = f' · <a href="{web["url"]}">{esc(web["label"])}</a>' if web.get("url") else ""
    lines.extend([
        "",
        "---",
        "",
        '<div align="center">',
        "",
        f'<p><a href="https://github.com/{u}">GitHub (@{u})</a>{web_link}</p>',
        "",
        f'<sub>{esc(t["footer_note"])} · auto-updated via GitHub Actions on {m["updated_date"]}</sub>',
        "",
        "</div>",
        "",
    ])
    return "\n".join(lines)


def render_preview_html(m: dict[str, Any]) -> str:
    sections_html = {}
    for key in THEMES:
        ap = f"./assets/{key}"
        if key == "aquarium":
            body = f"""
              <img class="full" src="{ap}/tank.svg" alt="Tank">
              <p class="caption">Every fish is a repository sized by stars; swaying seaweed tracks 26 weeks of commits.</p>
              <img class="full" src="{ap}/about.svg" alt="About">
              <h3>Featured Specimens</h3>
              <div class="grid2">
                {"".join(f'<a href="{r["html_url"]}" target="_blank"><img src="{ap}/card-{i}.svg" alt="{esc(r["display_name"])}"></a>' for i, r in enumerate(m["repos"][:4]))}
              </div>
              <img class="full" src="{ap}/stack.svg" alt="Stack">
              <img class="full" src="{ap}/log.svg" alt="Log">
            """
        elif key == "title-sequence":
            body = f"""
              <img class="full" src="{ap}/hero.svg" alt="Hero">
              <img class="full" src="{ap}/about.svg" alt="About">
              <img class="full" src="{ap}/cast.svg" alt="Cast">
              <p class="links">{" · ".join(f'<a href="{r["html_url"]}" target="_blank">{esc(r["display_name"])}</a>' for r in m["repos"][:6])}</p>
              <img class="full" src="{ap}/stack.svg" alt="Stack">
              <img class="full" src="{ap}/log.svg" alt="Log">
            """
        else:
            body = f"""
              <img class="full" src="{ap}/galaxy.svg" alt="Galaxy">
              <img class="full" src="{ap}/about.svg" alt="About">
              <h3>Brightest Stars</h3>
              <div class="grid2">
                {"".join(f'<a href="{r["html_url"]}" target="_blank"><img src="{ap}/card-{i}.svg" alt="{esc(r["display_name"])}"></a>' for i, r in enumerate(m["repos"][:4]))}
              </div>
              <img class="full" src="{ap}/stack.svg" alt="Stack">
              <img class="full" src="{ap}/log.svg" alt="Log">
            """
        sections_html[key] = body

    highlights = "".join(
        f'<li><strong>{esc(x["name"])}</strong> <code>{esc(x["tag"])}</code> — {esc(x["summary"])}</li>'
        for x in m["extra_highlights"]
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>@{esc(m["username"])} · GitHub Profile README Theme Preview</title>
  <style>
    :root {{ color-scheme: dark; }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0; padding: 28px 18px 64px;
      background: #0d1117; color: #e6edf3;
      font-family: {FONT_SANS};
    }}
    .wrap {{ max-width: 940px; margin: 0 auto; }}
    .bar {{
      display: flex; flex-wrap: wrap; gap: 10px; align-items: center; justify-content: space-between;
      margin-bottom: 20px; padding: 14px 18px;
      background: #161b22; border: 1px solid #30363d; border-radius: 12px;
    }}
    .tabs {{ display: flex; gap: 8px; flex-wrap: wrap; }}
    button {{
      cursor: pointer; border: 1px solid #30363d; background: #21262d; color: #c9d1d9;
      padding: 8px 14px; border-radius: 8px; font-weight: 600; font-size: 13px;
    }}
    button.active {{ background: #1f6feb; border-color: #388bfd; color: #fff; }}
    .gh-card {{
      background: #0d1117; border: 1px solid #30363d; border-radius: 12px; padding: 26px;
    }}
    .panel {{ display: none; }}
    .panel.active {{ display: block; }}
    img.full {{ width: 100%; height: auto; display: block; margin: 12px 0; }}
    .grid2 {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; margin: 12px 0; }}
    .grid2 img {{ width: 100%; height: auto; display: block; }}
    .caption {{ text-align: center; color: #8b949e; font-size: 12.5px; margin: 4px 0 14px; }}
    .links {{ text-align: center; font-size: 13px; margin: 10px 0 16px; }}
    a {{ color: #58a6ff; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    h3 {{ text-align: center; margin: 20px 0 8px; font-size: 16px; color: #f0f6fc; }}
    hr {{ border: 0; border-top: 1px solid #21262d; margin: 22px 0; }}
    ul {{ line-height: 1.7; color: #c9d1d9; }}
    code {{ background: #161b22; padding: 2px 6px; border-radius: 5px; font-size: 12px; }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="bar">
      <div>
        <strong>@{esc(m["username"])}</strong> · GitHub Profile README Preview
      </div>
      <div class="tabs">
        <button class="active" data-tab="aquarium" onclick="showTab('aquarium', this)">Aquarium</button>
        <button data-tab="title-sequence" onclick="showTab('title-sequence', this)">Title Sequence</button>
        <button data-tab="repo-galaxy" onclick="showTab('repo-galaxy', this)">Repo Galaxy</button>
      </div>
    </div>
    <div class="gh-card">
      <div id="tab-aquarium" class="panel active">{sections_html["aquarium"]}</div>
      <div id="tab-title-sequence" class="panel">{sections_html["title-sequence"]}</div>
      <div id="tab-repo-galaxy" class="panel">{sections_html["repo-galaxy"]}</div>
      <hr/>
      <h3>What I'm Building &amp; Exploring</h3>
      <ul>{highlights}</ul>
      <p style="color:#8b949e;font-size:13px;"><strong>Beyond Code:</strong> {esc(" · ".join(m["beyond_code"]))}</p>
    </div>
  </div>
  <script>
    function showTab(name, btn) {{
      document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
      document.querySelectorAll('button[data-tab]').forEach(b => b.classList.remove('active'));
      document.getElementById('tab-' + name).classList.add('active');
      if (btn) btn.classList.add('active');
    }}
  </script>
</body>
</html>
"""


def write_all_themes(m: dict[str, Any], active_theme: str, config: dict[str, Any]) -> None:
    # 1. Aquarium SVGs
    aq_dir = ASSETS_DIR / "aquarium"
    aq_dir.mkdir(parents=True, exist_ok=True)
    (aq_dir / "tank.svg").write_text(render_aquarium_tank(m), encoding="utf-8")
    (aq_dir / "about.svg").write_text(render_about_svg(m, "aquarium"), encoding="utf-8")
    for i, repo in enumerate(m["repos"][:4]):
        (aq_dir / f"card-{i}.svg").write_text(render_card_svg(repo, i, "aquarium"), encoding="utf-8")
    (aq_dir / "stack.svg").write_text(render_stack_svg(m, "aquarium"), encoding="utf-8")
    (aq_dir / "log.svg").write_text(render_log_svg(m, "aquarium"), encoding="utf-8")

    # 2. Title Sequence SVGs
    ts_dir = ASSETS_DIR / "title-sequence"
    ts_dir.mkdir(parents=True, exist_ok=True)
    (ts_dir / "hero.svg").write_text(render_title_hero(m), encoding="utf-8")
    (ts_dir / "about.svg").write_text(render_about_svg(m, "title-sequence"), encoding="utf-8")
    (ts_dir / "cast.svg").write_text(render_title_cast(m), encoding="utf-8")
    (ts_dir / "stack.svg").write_text(render_stack_svg(m, "title-sequence"), encoding="utf-8")
    (ts_dir / "log.svg").write_text(render_log_svg(m, "title-sequence"), encoding="utf-8")

    # 3. Repo Galaxy SVGs
    rg_dir = ASSETS_DIR / "repo-galaxy"
    rg_dir.mkdir(parents=True, exist_ok=True)
    (rg_dir / "galaxy.svg").write_text(render_repo_galaxy(m), encoding="utf-8")
    (rg_dir / "about.svg").write_text(render_about_svg(m, "repo-galaxy"), encoding="utf-8")
    for i, repo in enumerate(m["repos"][:4]):
        (rg_dir / f"card-{i}.svg").write_text(render_card_svg(repo, i, "repo-galaxy"), encoding="utf-8")
    (rg_dir / "stack.svg").write_text(render_stack_svg(m, "repo-galaxy"), encoding="utf-8")
    (rg_dir / "log.svg").write_text(render_log_svg(m, "repo-galaxy"), encoding="utf-8")

    # Write theme READMEs + active root README
    for key in THEMES:
        t_dir = THEMES_DIR / key
        t_dir.mkdir(parents=True, exist_ok=True)
        (t_dir / "README.md").write_text(
            render_readme(m, key, asset_prefix="../../assets", root_prefix="../..", config=config),
            encoding="utf-8",
        )

    (ROOT_DIR / "README.md").write_text(
        render_readme(m, active_theme, asset_prefix="./assets", root_prefix=".", config=config),
        encoding="utf-8",
    )
    (ROOT_DIR / "preview.html").write_text(render_preview_html(m), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate animated GitHub profile SVGs & READMEs.")
    parser.add_argument("--theme", choices=[*THEMES.keys(), "keep-current"], default="keep-current")
    parser.add_argument("--offline", action="store_true", help="Use cached data/github_snapshot.json without network calls.")
    args = parser.parse_args()

    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    active_theme = config.get("active_theme", "aquarium")
    if args.theme != "keep-current":
        active_theme = args.theme
        config["active_theme"] = active_theme
        CONFIG_PATH.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")

    data = fetch_github_data(config.get("username", "itzstebin"), offline=args.offline)
    metrics = prepare_metrics(data, config)
    write_all_themes(metrics, active_theme, config)
    print(f"Generated 3 themes + root README.md (active={active_theme}, repos={len(metrics['repos'])}, contributions={metrics['total_contributions']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
