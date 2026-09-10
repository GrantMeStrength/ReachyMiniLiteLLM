#!/usr/bin/env python3
"""Announce newly created issues and pull requests in selected public repos."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from karl_config import ROOT


REPOSITORIES = (
    "microsoftdocs/windows-dev-docs",
    "microsoftdocs/windows-ai-docs",
    "microsoftdocs/win32",
    "microsoftdocs/sdk-api",
)
POLL_SECONDS = 10 * 60
STATE_PATH = Path(
    os.environ.get(
        "KARL_GITHUB_WATCHER_STATE",
        Path.home() / ".local/state/karl/github-watcher.json",
    )
)
USER_AGENT = "Karl-Public-Repo-Watcher/1.0"


def fetch_recent(repo: str) -> list[dict]:
    query = urllib.parse.urlencode(
        {
            "state": "all",
            "sort": "created",
            "direction": "desc",
            "per_page": 30,
        }
    )
    request = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/issues?{query}",
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": USER_AGENT,
        },
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.load(response)


def load_seen() -> set[str] | None:
    try:
        data = json.loads(STATE_PATH.read_text())
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"Could not read watcher state: {error}") from error
    return set(data.get("seen", []))


def save_seen(seen: set[str]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = STATE_PATH.with_suffix(".tmp")
    temporary.write_text(json.dumps({"seen": sorted(seen)}, indent=2) + "\n")
    temporary.replace(STATE_PATH)


def item_key(repo: str, item: dict) -> str:
    kind = "pull" if "pull_request" in item else "issue"
    return f"{repo}:{kind}:{item['number']}"


def announcement(repo: str, item: dict) -> str:
    repository = repo.rsplit("/", 1)[-1].replace("-", " ")
    kind = "pull request" if "pull_request" in item else "issue"
    title = " ".join(str(item.get("title", "")).split())[:180]
    return f"New {kind} {item['number']} in {repository}: {title}"


def speak(text: str) -> None:
    result = subprocess.run(
        [str(ROOT / "karlctl"), "speak", "--no-move", text],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=90,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(detail or "Karl speech command failed")


def poll_once() -> int:
    seen = load_seen()
    recent = {repo: fetch_recent(repo) for repo in REPOSITORIES}

    if seen is None:
        save_seen(
            {
                item_key(repo, item)
                for repo, items in recent.items()
                for item in items
            }
        )
        print("Baseline saved; future issues and pull requests will be announced.")
        return 0

    pending = [
        (repo, item)
        for repo, items in recent.items()
        for item in reversed(items)
        if item_key(repo, item) not in seen
    ]
    for repo, item in pending:
        text = announcement(repo, item)
        speak(text)
        seen.add(item_key(repo, item))
        save_seen(seen)
        print(text, flush=True)
    return len(pending)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Watch Karl's selected public GitHub repositories."
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Poll once, then exit.",
    )
    args = parser.parse_args()

    while True:
        try:
            poll_once()
        except (OSError, RuntimeError, urllib.error.URLError) as error:
            print(f"GitHub watcher error: {error}", file=sys.stderr, flush=True)
            if args.once:
                return 1
        if args.once:
            return 0
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    raise SystemExit(main())
