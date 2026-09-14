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

from cache import cached
from schemas import (
    CodebaseInsights,
    CodeSearchResult,
    Commit,
    Contributor,
    Issue,
    RepoSummary,
    WeeklyCommitCount,
)

GITHUB_API_BASE = "https://api.github.com"


class GitHubClientError(Exception):
    """Base error for all github_client failures. Message is user-facing."""


class RepoNotFoundError(GitHubClientError):
    pass


class RateLimitError(GitHubClientError):
    pass


class CodeSearchAuthRequiredError(GitHubClientError):
    pass


def _headers() -> dict:
    headers = {"Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _get(path: str, params: dict | None = None, extra_headers: dict | None = None) -> requests.Response:
    url = f"{GITHUB_API_BASE}{path}"
    headers = _headers()
    if extra_headers:
        headers.update(extra_headers)
    response = requests.get(url, headers=headers, params=params, timeout=10)

    if response.status_code == 404:
        raise RepoNotFoundError(f"Not found: {path}. Check the owner/repo spelling and that it's public.")

    if response.status_code in (403, 429) and "Retry-After" in response.headers:
        minutes = max(1, round(int(response.headers["Retry-After"]) / 60))
        raise RateLimitError(
            f"GitHub rate limit hit, resets in {minutes} minute(s). "
            "Set GITHUB_TOKEN for a higher limit (5,000/hour vs 60/hour)."
        )

    if response.status_code == 403 and response.headers.get("X-RateLimit-Remaining") == "0":
        reset_ts = int(response.headers.get("X-RateLimit-Reset", 0))
        minutes = max(0, round((reset_ts - time.time()) / 60))
        raise RateLimitError(
            f"GitHub rate limit hit, resets in {minutes} minute(s). "
            "Set GITHUB_TOKEN for a higher limit (5,000/hour vs 60/hour)."
        )

    response.raise_for_status()
    return response


@cached
def get_repo_summary(owner: str, repo: str) -> RepoSummary:
    """Fetch stars, language breakdown, description, and last commit date."""
    repo_data = _get(f"/repos/{owner}/{repo}").json()
    languages = _get(f"/repos/{owner}/{repo}/languages").json()

    return RepoSummary(
        full_name=repo_data["full_name"],
        description=repo_data.get("description"),
        stars=repo_data["stargazers_count"],
        forks=repo_data["forks_count"],
        open_issues=repo_data["open_issues_count"],
        default_branch=repo_data["default_branch"],
        languages=languages,
        last_commit_date=repo_data.get("pushed_at"),
        url=repo_data["html_url"],
    )


@cached
def list_recent_commits(owner: str, repo: str, count: int = 10) -> list[Commit]:
    """List the most recent commits with author and date."""
    commits = _get(f"/repos/{owner}/{repo}/commits", params={"per_page": count}).json()

    return [
        Commit(
            sha=commit["sha"][:7],
            message=commit["commit"]["message"].split("\n")[0],
            author=commit["commit"]["author"]["name"],
            date=commit["commit"]["author"]["date"],
            url=commit["html_url"],
        )
        for commit in commits
    ]


@cached
def list_open_issues(owner: str, repo: str, count: int = 10) -> list[Issue]:
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
            Issue(
                number=issue["number"],
                title=issue["title"],
                labels=[label["name"] for label in issue["labels"]],
                age_days=(now - created).days,
                url=issue["html_url"],
            )
        )
        if len(result) >= count:
            break

    return result


@cached
def get_contributor_stats(owner: str, repo: str, count: int = 10) -> list[Contributor]:
    """Top contributors by commit count on the default branch."""
    contributors = _get(f"/repos/{owner}/{repo}/contributors", params={"per_page": count}).json()

    return [
        Contributor(
            login=c["login"],
            contributions=c["contributions"],
            profile_url=c["html_url"],
        )
        for c in contributors
    ]


@cached
def get_codebase_insights(owner: str, repo: str) -> CodebaseInsights:
    """Language breakdown as percentages of the codebase, plus total repo size in KB."""
    repo_data = _get(f"/repos/{owner}/{repo}").json()
    languages = _get(f"/repos/{owner}/{repo}/languages").json()

    total_bytes = sum(languages.values()) or 1
    percentages = {lang: round(count / total_bytes * 100, 1) for lang, count in languages.items()}

    return CodebaseInsights(size_kb=repo_data["size"], languages=percentages)


@cached
def get_commit_frequency(owner: str, repo: str, weeks: int = 12) -> list[WeeklyCommitCount]:
    """Weekly commit counts for the last `weeks` weeks (max 52). Pure counting —
    no keyword-based categorization, no LLM call involved."""
    response = _get(f"/repos/{owner}/{repo}/stats/commit_activity")
    if response.status_code == 202:
        raise GitHubClientError(
            "GitHub is still computing commit statistics for this repo — try again in a few seconds."
        )

    weekly = response.json()
    weeks = max(1, min(weeks, 52))

    return [
        WeeklyCommitCount(
            week_start=datetime.fromtimestamp(entry["week"], tz=timezone.utc).date().isoformat(),
            commit_count=entry["total"],
        )
        for entry in weekly[-weeks:]
    ]


@cached
def search_codebase(owner: str, repo: str, query: str, count: int = 10) -> list[CodeSearchResult]:
    """Search code within a repo's default branch. Requires GITHUB_TOKEN — GitHub's
    code search sits in its own, much stricter rate-limit bucket that unauthenticated
    requests can't use reliably. Only indexes the default branch and excludes some
    large files and forks, so an empty result doesn't necessarily mean the code
    doesn't exist elsewhere in the repo."""
    if not os.environ.get("GITHUB_TOKEN"):
        raise CodeSearchAuthRequiredError(
            "search_codebase requires GITHUB_TOKEN. GitHub's code search has its own, "
            "much stricter rate limit that doesn't work reliably unauthenticated."
        )

    response = _get(
        "/search/code",
        params={"q": f"{query} repo:{owner}/{repo}", "per_page": count},
        extra_headers={"Accept": "application/vnd.github.text-match+json"},
    )

    results = []
    for item in response.json().get("items", []):
        matches = item.get("text_matches") or []
        results.append(
            CodeSearchResult(
                path=item["path"],
                url=item["html_url"],
                snippet=matches[0]["fragment"] if matches else None,
                score=item.get("score", 0.0),
            )
        )

    return results
