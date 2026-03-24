#!/usr/bin/env python3
"""
根据 profile.yaml 自动生成带日期过滤的搜索查询列表。

用法：
    python3 scripts/build_queries.py --date 2026-03-24 --window 3

输出每行一条查询，格式：
    [priority] topic_name | 查询文本
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path


def resolve_root_dir() -> Path:
    env_root = os.environ.get("DAILY_ROOT") or os.environ.get("AI_DAILY_ROOT")
    candidates = []
    if env_root:
        candidates.append(Path(env_root).expanduser())

    cwd = Path.cwd().resolve()
    candidates.extend([cwd, *cwd.parents])

    script_dir = Path(__file__).resolve().parent
    candidates.extend([script_dir, *script_dir.parents])

    seen: set[Path] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        if (candidate / "SKILL.md").exists() and (candidate / "config").is_dir():
            return candidate

    return script_dir.parent


def load_profile(root: Path) -> dict:
    config_path = root / "config" / "profile.yaml"
    if not config_path.exists():
        print(f"ERROR: {config_path} 不存在，请先运行 /daily-init", file=sys.stderr)
        sys.exit(1)

    try:
        import yaml
        with open(config_path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except ImportError:
        pass

    # Fallback: simple parser
    result: dict = {"topics": [], "sources": {"direct": [], "search_seeds": []}}
    text = config_path.read_text(encoding="utf-8")
    current_topic: dict | None = None
    in_keywords = False
    in_seeds = False
    in_direct = False

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        # strip inline comments
        if " #" in stripped:
            stripped = stripped[: stripped.index(" #")].rstrip()

        indent = len(line) - len(line.lstrip())

        if stripped.startswith("- name:"):
            if current_topic:
                result["topics"].append(current_topic)
            current_topic = {
                "name": stripped.split(":", 1)[1].strip().strip("'\""),
                "priority": "medium",
                "keywords": [],
            }
            in_keywords = False
            in_seeds = False
            in_direct = False
        elif stripped.startswith("priority:") and current_topic:
            current_topic["priority"] = stripped.split(":", 1)[1].strip().strip("'\"")
        elif stripped == "keywords:":
            in_keywords = True
            in_seeds = False
            in_direct = False
        elif stripped == "search_seeds:":
            if current_topic:
                result["topics"].append(current_topic)
                current_topic = None
            in_seeds = True
            in_keywords = False
            in_direct = False
        elif stripped == "direct:":
            if current_topic:
                result["topics"].append(current_topic)
                current_topic = None
            in_direct = True
            in_keywords = False
            in_seeds = False
        elif stripped.startswith("- ") and indent >= 4:
            val = stripped[2:].strip().strip("'\"")
            if in_keywords and current_topic:
                current_topic["keywords"].append(val)
            elif in_seeds:
                result["sources"].setdefault("search_seeds", []).append(val)
            elif in_direct:
                result["sources"].setdefault("direct", []).append(val)
        elif indent < 4 and not stripped.startswith("-"):
            if in_keywords:
                in_keywords = False
            if in_seeds:
                in_seeds = False
            if in_direct:
                in_direct = False
            if current_topic and not stripped.startswith("priority:"):
                result["topics"].append(current_topic)
                current_topic = None

    if current_topic:
        result["topics"].append(current_topic)

    return result


def build_date_range(date_str: str, window: int) -> tuple[str, str, str, str]:
    """Returns (start_cn, end_cn, start_iso, end_iso)."""
    end = datetime.strptime(date_str, "%Y-%m-%d")
    start = end - timedelta(days=window - 1)
    start_cn = f"{start.year}年{start.month}月{start.day}日"
    end_cn = f"{end.year}年{end.month}月{end.day}日"
    start_iso = start.strftime("%Y-%m-%d")
    end_iso = end.strftime("%Y-%m-%d")
    return start_cn, end_cn, start_iso, end_iso


def generate_queries(
    profile: dict, date_str: str, window: int
) -> list[tuple[str, str, str]]:
    """Generate (priority, topic_name, query) tuples."""
    start_cn, end_cn, start_iso, end_iso = build_date_range(date_str, window)
    queries: list[tuple[str, str, str]] = []

    topics = profile.get("topics", [])
    priority_order = {"high": 0, "medium": 1, "low": 2}
    topics_sorted = sorted(
        topics, key=lambda t: priority_order.get(t.get("priority", "medium"), 1)
    )

    # Per-topic queries
    for topic in topics_sorted:
        name = topic.get("name", "")
        priority = topic.get("priority", "medium")
        keywords = topic.get("keywords", [])
        if not name:
            continue

        # Determine query count by priority
        if priority == "high":
            max_queries = 3
        elif priority == "medium":
            max_queries = 2
        else:
            max_queries = 1

        generated = 0

        # Query 1: topic name + date range (Chinese)
        queries.append((priority, name, f"{name} {start_cn}-{end_cn}"))
        generated += 1

        # Query 2: first 2-3 keywords combined + date (Chinese)
        if generated < max_queries and len(keywords) >= 2:
            kw_combo = " ".join(keywords[:3])
            queries.append((priority, name, f"{kw_combo} 最新 {start_cn}"))
            generated += 1

        # Query 3: English keywords + after: date filter
        if generated < max_queries and keywords:
            en_kws = [k for k in keywords if any(c.isascii() and c.isalpha() for c in k)]
            if en_kws:
                en_combo = " ".join(en_kws[:3])
                queries.append(
                    (priority, name, f"{en_combo} news after:{start_iso}")
                )
                generated += 1

        # If still short, use topic name in English-style search
        if generated < max_queries:
            queries.append(
                (priority, name, f"{name} latest news {end_iso}")
            )

    # Search seeds from profile
    sources = profile.get("sources", {})
    seeds = sources.get("search_seeds", [])
    for seed in seeds:
        # Append date to each seed
        if any("\u4e00" <= c <= "\u9fff" for c in seed):
            # Chinese seed
            queries.append(("seed", "搜索种子", f"{seed} {start_cn}-{end_cn}"))
        else:
            # English seed
            queries.append(("seed", "搜索种子", f"{seed} after:{start_iso}"))

    # Direct sources to fetch
    direct = sources.get("direct", [])
    for url in direct:
        queries.append(("direct", "直抓来源", f"FETCH {url}"))

    return queries


def main() -> None:
    parser = argparse.ArgumentParser(
        description="根据 profile.yaml 生成带日期过滤的搜索查询列表"
    )
    parser.add_argument(
        "--date",
        default=datetime.now().strftime("%Y-%m-%d"),
        help="目标日期，格式 YYYY-MM-DD（默认今天）",
    )
    parser.add_argument(
        "--window",
        type=int,
        default=3,
        help="时间窗口天数（默认 3）",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="以 JSON 格式输出",
    )
    args = parser.parse_args()

    root = resolve_root_dir()
    profile = load_profile(root)
    queries = generate_queries(profile, args.date, args.window)

    if args.json:
        import json

        output = [
            {"priority": p, "topic": t, "query": q} for p, t, q in queries
        ]
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        print(f"# 日报搜索查询 — {args.date}（窗口 {args.window} 天）")
        print(f"# 共 {len(queries)} 条查询\n")
        current_section = None
        for priority, topic, query in queries:
            section = f"[{priority}] {topic}"
            if section != current_section:
                print(f"\n## {section}")
                current_section = section
            print(f"  {query}")


if __name__ == "__main__":
    main()
