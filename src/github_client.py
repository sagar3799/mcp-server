"""Plain functions that hit the GitHub REST API and return clean dicts.

No MCP here on purpose — this module is testable and usable on its own.
Auth is optional: set GITHUB_TOKEN in the environment for a higher rate
limit (5,000/hour instead of 60/hour). Every function works without it.
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone

import requests

GITHUB_API_BASE = "https://api.github.com"


class GitHubClientError(Exception):
    """Base error for all github_client failures. Message is user-facing."""


class RepoNotFoundError(GitHubClientError):
    pass


class RateLimitError(GitHubClientError):
    pass


def _headers() -> dict:
    headers = {"Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _get(path: str, params: dict | None = None) -> requests.Response:
    url = f"{GITHUB_API_BASE}{path}"
    response = requests.get(url, headers=_headers(), params=params, timeout=10)

    if response.status_code == 404:
        raise RepoNotFoundError(f"Not found: {path}. Check the owner/repo spelling and that it's public.")

    if response.status_code == 403 and response.headers.get("X-RateLimit-Remaining") == "0":
        reset_ts = int(response.headers.get("X-RateLimit-Reset", 0))
        minutes = max(0, round((reset_ts - time.time()) / 60))
        raise RateLimitError(
            f"GitHub rate limit hit, resets in {minutes} minute(s). "
            "Set GITHUB_TOKEN for a higher limit (5,000/hour vs 60/hour)."
        )

    response.raise_for_status()
    return response


def get_repo_summary(owner: str, repo: str) -> dict:
    """Fetch stars, language breakdown, description, and last commit date."""
    repo_data = _get(f"/repos/{owner}/{repo}").json()
    languages = _get(f"/repos/{owner}/{repo}/languages").json()

    return {
        "full_name": repo_data["full_name"],
        "description": repo_data.get("description"),
        "stars": repo_data["stargazers_count"],
        "forks": repo_data["forks_count"],
        "open_issues": repo_data["open_issues_count"],
        "default_branch": repo_data["default_branch"],
        "languages": languages,
        "last_commit_date": repo_data.get("pushed_at"),
        "url": repo_data["html_url"],
    }


def list_recent_commits(owner: str, repo: str, count: int = 10) -> list[dict]:
    """List the most recent commits with author and date."""
    commits = _get(f"/repos/{owner}/{repo}/commits", params={"per_page": count}).json()

    return [
        {
            "sha": commit["sha"][:7],
            "message": commit["commit"]["message"].split("\n")[0],
            "author": commit["commit"]["author"]["name"],
            "date": commit["commit"]["author"]["date"],
            "url": commit["html_url"],
        }
        for commit in commits
    ]


def list_open_issues(owner: str, repo: str, count: int = 10) -> list[dict]:
    """List open issues with labels and age in days. Excludes pull requests."""
    issues = _get(
        f"/repos/{owner}/{repo}/issues",
        params={"state": "open", "per_page": min(count * 2, 100)},
    ).json()

    now = datetime.now(timezone.utc)
    result = []
    for issue in issues:
        if "pull_request" in issue:
            continue
        created = datetime.fromisoformat(issue["created_at"].replace("Z", "+00:00"))
        result.append(
            {
                "number": issue["number"],
                "title": issue["title"],
                "labels": [label["name"] for label in issue["labels"]],
                "age_days": (now - created).days,
                "url": issue["html_url"],
            }
        )
        if len(result) >= count:
            break

    return result
