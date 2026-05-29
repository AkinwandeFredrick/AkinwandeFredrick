"""
update_readme.py
Fetches live data from the GitHub API and injects it into README.md
between special HTML comment markers.
"""

import os
import re
import requests
from datetime import datetime, timezone
from collections import defaultdict

USERNAME = os.environ.get("GITHUB_USERNAME", "AkinwandeFredrick")
TOKEN    = os.environ.get("GITHUB_TOKEN", "")

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}

README_PATH = "README.md"


# ─── Helpers ────────────────────────────────────────────────────────────────

def gh_get(url: str, params: dict = None):
    r = requests.get(url, headers=HEADERS, params=params, timeout=15)
    r.raise_for_status()
    return r.json()


def replace_section(content: str, marker: str, new_block: str) -> str:
    """Replace content between <!-- START:marker --> and <!-- END:marker -->."""
    pattern = rf"(<!-- START:{marker} -->).*?(<!-- END:{marker} -->)"
    replacement = rf"\1\n{new_block}\n\2"
    return re.sub(pattern, replacement, content, flags=re.DOTALL)


# ─── Data Fetchers ───────────────────────────────────────────────────────────

def fetch_latest_repos(n: int = 5) -> list[dict]:
    """Return the n most recently pushed public repos."""
    repos = gh_get(
        f"https://api.github.com/users/{USERNAME}/repos",
        params={"sort": "pushed", "direction": "desc", "per_page": n, "type": "owner"},
    )
    return [
        {
            "name": r["name"],
            "description": r["description"] or "No description",
            "url": r["html_url"],
            "stars": r["stargazers_count"],
            "forks": r["forks_count"],
            "language": r["language"] or "N/A",
        }
        for r in repos
    ]


def fetch_user_stats() -> dict:
    """Return public stats for the user."""
    u = gh_get(f"https://api.github.com/users/{USERNAME}")
    return {
        "public_repos": u["public_repos"],
        "followers": u["followers"],
        "following": u["following"],
    }


def fetch_recent_activity(n: int = 5) -> list[str]:
    """Return the n most recent public events as plain strings."""
    events = gh_get(
        f"https://api.github.com/users/{USERNAME}/events/public",
        params={"per_page": 30},
    )
    lines = []
    type_map = {
        "PushEvent":        "🔨 Pushed to",
        "CreateEvent":      "🌱 Created",
        "PullRequestEvent": "🔀 Opened PR in",
        "IssuesEvent":      "🐛 Opened issue in",
        "WatchEvent":       "⭐ Starred",
        "ForkEvent":        "🍴 Forked",
        "ReleaseEvent":     "🚀 Released",
        "DeleteEvent":      "🗑️ Deleted branch/tag in",
    }
    seen = set()
    for e in events:
        etype = e.get("type", "")
        repo  = e["repo"]["name"]
        key   = f"{etype}:{repo}"
        if key in seen:
            continue
        seen.add(key)
        verb = type_map.get(etype, f"📌 {etype} in")
        lines.append(f"- {verb} [{repo}](https://github.com/{repo})")
        if len(lines) >= n:
            break
    return lines


def fetch_github_stats() -> dict:
    """
    Fetch real commit counts, PRs, issues, stars, and top languages
    directly from the GitHub API — no third-party services.
    """
    # All repos
    repos = gh_get(
        f"https://api.github.com/users/{USERNAME}/repos",
        params={"per_page": 100, "type": "owner"},
    )

    total_stars = sum(r["stargazers_count"] for r in repos)
    total_forks = sum(r["forks_count"] for r in repos)

    # Language byte counts across all repos
    lang_bytes: dict[str, int] = defaultdict(int)
    for repo in repos:
        if repo["language"]:
            try:
                langs = gh_get(repo["languages_url"])
                for lang, count in langs.items():
                    lang_bytes[lang] += count
            except Exception:
                pass

    total_bytes = sum(lang_bytes.values()) or 1
    top_langs = sorted(lang_bytes.items(), key=lambda x: x[1], reverse=True)[:6]
    top_langs_pct = [(lang, round(count / total_bytes * 100, 1)) for lang, count in top_langs]

    # PRs authored by user
    pr_data = gh_get(
        "https://api.github.com/search/issues",
        params={"q": f"type:pr author:{USERNAME}", "per_page": 1},
    )
    total_prs = pr_data.get("total_count", 0)

    # Issues authored by user
    issue_data = gh_get(
        "https://api.github.com/search/issues",
        params={"q": f"type:issue author:{USERNAME}", "per_page": 1},
    )
    total_issues = issue_data.get("total_count", 0)

    # Commits in the last year across all repos (best effort via events)
    commit_events = gh_get(
        f"https://api.github.com/users/{USERNAME}/events",
        params={"per_page": 100},
    )
    total_commits = sum(
        len(e.get("payload", {}).get("commits", []))
        for e in commit_events
        if e.get("type") == "PushEvent"
    )

    return {
        "total_stars":   total_stars,
        "total_forks":   total_forks,
        "total_prs":     total_prs,
        "total_issues":  total_issues,
        "total_commits": total_commits,
        "top_langs":     top_langs_pct,
        "total_repos":   len(repos),
    }


# ─── Section Builders ────────────────────────────────────────────────────────

def build_latest_repos_section(repos: list[dict]) -> str:
    rows = "\n".join(
        f"| [{r['name']}]({r['url']}) | {r['description']} | {r['language']} | ⭐ {r['stars']} | 🍴 {r['forks']} |"
        for r in repos
    )
    return (
        "| Repository | Description | Language | Stars | Forks |\n"
        "|------------|-------------|----------|-------|-------|\n"
        + rows
    )


def build_stats_section(stats: dict) -> str:
    return (
        f"![Repos](https://img.shields.io/badge/Public%20Repos-{stats['public_repos']}-FF6B6B?style=flat-square) "
        f"![Followers](https://img.shields.io/badge/Followers-{stats['followers']}-4ECDC4?style=flat-square) "
        f"![Following](https://img.shields.io/badge/Following-{stats['following']}-45B7D1?style=flat-square)"
    )


def build_activity_section(activity: list[str]) -> str:
    return "\n".join(activity)


def build_last_updated_section() -> str:
    now = datetime.now(timezone.utc).strftime("%d %b %Y at %H:%M UTC")
    return f'<sub>🕐 Last updated: <b>{now}</b></sub>'


def build_github_stats_section(stats: dict) -> str:
    """Build a clean stats table and language bar from real API data."""

    # Language bar — each language gets a proportional block
    lang_bar = ""
    bar_chars = 40
    for lang, pct in stats["top_langs"]:
        block_count = max(1, round(pct / 100 * bar_chars))
        lang_bar += f"`{'█' * block_count}` {lang} {pct}%&nbsp;&nbsp;"

    lines = [
        "| Metric | Count |",
        "|--------|-------|",
        f"| ⭐ Total Stars Earned | {stats['total_stars']} |",
        f"| 🔨 Recent Commits (last 100 events) | {stats['total_commits']} |",
        f"| 🔀 Total PRs | {stats['total_prs']} |",
        f"| 🐛 Total Issues | {stats['total_issues']} |",
        f"| 📁 Public Repos | {stats['total_repos']} |",
        f"| 🍴 Total Forks Received | {stats['total_forks']} |",
        "",
        "**🗣️ Most Used Languages**",
        "",
        lang_bar,
    ]
    return "\n".join(lines)


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    with open(README_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    print("Fetching latest repos…")
    repos    = fetch_latest_repos(5)
    print("Fetching user stats…")
    stats    = fetch_user_stats()
    print("Fetching recent activity…")
    activity = fetch_recent_activity(5)
    print("Fetching GitHub stats…")
    gh_stats = fetch_github_stats()

    content = replace_section(content, "LATEST_REPOS",    build_latest_repos_section(repos))
    content = replace_section(content, "STATS",           build_stats_section(stats))
    content = replace_section(content, "RECENT_ACTIVITY", build_activity_section(activity))
    content = replace_section(content, "LAST_UPDATED",    build_last_updated_section())
    content = replace_section(content, "GITHUB_STATS",    build_github_stats_section(gh_stats))

    with open(README_PATH, "w", encoding="utf-8") as f:
        f.write(content)

    print("README.md updated successfully.")


if __name__ == "__main__":
    main()
