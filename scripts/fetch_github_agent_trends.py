#!/usr/bin/env python3
"""
抓取 GitHub 上近期开启加速的 AI Agent / coding-agent 项目。

设计目标：
1. 复用 github-agent-trends 的核心策略
2. 只依赖标准库，方便在 ai-daily 内直接调用
3. 支持 JSON 输出，便于落入 output/raw 或继续加工成日报条目
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any


PERIOD_DAYS = {"daily": 1, "weekly": 7, "monthly": 30}


def iso_to_datetime(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value)


def gh_search(
    query: str,
    *,
    sort: str = "stars",
    order: str = "desc",
    per_page: int = 50,
    token: str | None = None,
) -> list[dict[str, Any]]:
    params = urllib.parse.urlencode(
        {"q": query, "sort": sort, "order": order, "per_page": per_page}
    )
    url = f"https://api.github.com/search/repositories?{params}"
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "ai-daily-github-agent-trends",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read())
    return payload.get("items", [])


def build_queries(since: str) -> list[str]:
    return [
        f"topic:ai-agent created:>={since} stars:>=10",
        f"topic:agentic-ai created:>={since}",
        f"topic:autonomous-agents created:>={since}",
        f"topic:llm-agents created:>={since}",
        f'"AI agent" in:name,description created:>={since} stars:>=20',
        f'"autonomous agent" in:name,description created:>={since} stars:>=20',
        f'"coding agent" in:name,description created:>={since} stars:>=20',
        f'"AI agent" in:name,description pushed:>={since} stars:>=50',
        f'"coding agent" in:name,description pushed:>={since} stars:>=50',
    ]


def fetch_agent_trends(
    *,
    period: str = "monthly",
    limit: int = 15,
    token: str | None = None,
) -> list[dict[str, Any]]:
    days = PERIOD_DAYS.get(period, PERIOD_DAYS["monthly"])
    since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    seen: set[str] = set()
    results: list[dict[str, Any]] = []

    for query in build_queries(since):
        try:
            items = gh_search(query, token=token)
        except Exception as exc:
            print(f"[WARN] GitHub API error for query {query!r}: {exc}", file=sys.stderr)
            continue

        for item in items:
            name = item.get("full_name")
            created_at = item.get("created_at")
            if not name or not created_at or name in seen:
                continue
            seen.add(name)

            created_dt = iso_to_datetime(created_at)
            days_old = max((datetime.now(timezone.utc) - created_dt).days, 1)
            stars = int(item.get("stargazers_count") or 0)
            pushed_at = item.get("pushed_at", "")

            results.append(
                {
                    "name": name,
                    "url": item.get("html_url", ""),
                    "stars": stars,
                    "daily_stars": round(stars / days_old, 2),
                    "days_old": days_old,
                    "created_at": created_at,
                    "pushed_at": pushed_at,
                    "language": item.get("language"),
                    "description": item.get("description"),
                    "topics": item.get("topics", [])[:5],
                }
            )

    results.sort(key=lambda item: item["daily_stars"], reverse=True)
    return results[:limit]


def format_markdown(repos: list[dict[str, Any]], period: str) -> str:
    label = {"daily": "日榜", "weekly": "周榜", "monthly": "月榜"}.get(period, period)
    now = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M")
    lines = [f"GitHub AI Agent 潜力新项目 - {label}", f"生成时间：{now}", ""]

    for idx, repo in enumerate(repos, start=1):
        lines.append(f"#{idx} {repo['name']}")
        lines.append(
            f"⭐ {repo['stars']:,} ({repo['daily_stars']:.0f}/天) | "
            f"{repo.get('language') or 'N/A'} | {repo['days_old']}天新"
        )
        if repo.get("description"):
            lines.append(repo["description"])
        if repo.get("topics"):
            lines.append("topics: " + ", ".join(repo["topics"]))
        lines.append(repo["url"])
        lines.append("")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch GitHub AI agent trend repos")
    parser.add_argument("--period", choices=["daily", "weekly", "monthly"], default="monthly")
    parser.add_argument("--limit", type=int, default=15)
    parser.add_argument("--token", default=os.environ.get("GITHUB_TOKEN"))
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    print(f"Fetching GitHub AI agent trends ({args.period})...", file=sys.stderr)
    repos = fetch_agent_trends(period=args.period, limit=args.limit, token=args.token)
    if not repos:
        print("No repos found.", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(repos, ensure_ascii=False, indent=2))
    else:
        print(format_markdown(repos, args.period))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
