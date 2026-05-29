"""
update_readme.py
Fetches live data from the GitHub API and injects it into README.md
between special HTML comment markers.
"""

import os
import re
import requests
from datetime import datetime, timezone

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
        "PushEvent":        " Pushed to",
        "CreateEvent":      " Created",
        "PullRequestEvent": " Opened PR in",
        "IssuesEvent":      " Opened issue in",
        "WatchEvent":       " Starred",
        "ForkEvent":        " Forked",
        "ReleaseEvent":     " Released",
        "DeleteEvent":      " Deleted branch/tag in",
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
    # shields.io uses '-' as a delimiter, so we avoid dashes in the date value
    now = datetime.now(timezone.utc).strftime("%d %b %Y %H%MZ")
    value = now.replace(" ", "%20")
    return f"![Last Updated](https://img.shields.io/badge/Last%20Updated-{value}-brightgreen?style=flat-square)"


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

    content = replace_section(content, "LATEST_REPOS",    build_latest_repos_section(repos))
    content = replace_section(content, "STATS",           build_stats_section(stats))
    content = replace_section(content, "RECENT_ACTIVITY", build_activity_section(activity))
    content = replace_section(content, "LAST_UPDATED",    build_last_updated_section())

    with open(README_PATH, "w", encoding="utf-8") as f:
        f.write(content)

    print("README.md updated successfully.")


if __name__ == "__main__":
    main()
