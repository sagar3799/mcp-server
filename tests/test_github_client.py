"""Tests for github_client. GitHub API is fully mocked — no live network or token needed."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from github_client import (
    RateLimitError,
    RepoNotFoundError,
    get_repo_summary,
    list_open_issues,
    list_recent_commits,
)


class FakeResponse:
    def __init__(self, status_code=200, json_data=None, headers=None):
        self.status_code = status_code
        self._json_data = json_data or {}
        self.headers = headers or {}

    def json(self):
        return self._json_data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")


def test_get_repo_summary_success(mocker):
    repo_response = FakeResponse(
        json_data={
            "full_name": "octocat/hello-world",
            "description": "A test repo",
            "stargazers_count": 42,
            "forks_count": 7,
            "open_issues_count": 3,
            "default_branch": "main",
            "pushed_at": "2026-01-01T00:00:00Z",
            "html_url": "https://github.com/octocat/hello-world",
        }
    )
    languages_response = FakeResponse(json_data={"Python": 1000, "JavaScript": 200})
    mocker.patch("requests.get", side_effect=[repo_response, languages_response])

    result = get_repo_summary("octocat", "hello-world")

    assert result["full_name"] == "octocat/hello-world"
    assert result["stars"] == 42
    assert result["languages"] == {"Python": 1000, "JavaScript": 200}
    assert result["last_commit_date"] == "2026-01-01T00:00:00Z"


def test_get_repo_summary_not_found(mocker):
    mocker.patch("requests.get", return_value=FakeResponse(status_code=404))

    with pytest.raises(RepoNotFoundError):
        get_repo_summary("octocat", "does-not-exist")


def test_get_repo_summary_rate_limited(mocker):
    response = FakeResponse(
        status_code=403,
        headers={"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "9999999999"},
    )
    mocker.patch("requests.get", return_value=response)

    with pytest.raises(RateLimitError, match="rate limit"):
        get_repo_summary("octocat", "hello-world")


def test_list_recent_commits(mocker):
    commits_response = FakeResponse(
        json_data=[
            {
                "sha": "abc1234567890",
                "commit": {
                    "message": "Fix bug\n\nLonger description here",
                    "author": {"name": "Alice", "date": "2026-01-01T00:00:00Z"},
                },
                "html_url": "https://github.com/octocat/hello-world/commit/abc1234567890",
            }
        ]
    )
    mocker.patch("requests.get", return_value=commits_response)

    result = list_recent_commits("octocat", "hello-world", count=1)

    assert len(result) == 1
    assert result[0]["sha"] == "abc1234"
    assert result[0]["message"] == "Fix bug"
    assert result[0]["author"] == "Alice"


def test_list_open_issues_excludes_pull_requests(mocker):
    issues_response = FakeResponse(
        json_data=[
            {
                "number": 1,
                "title": "Real issue",
                "labels": [{"name": "bug"}],
                "created_at": "2020-01-01T00:00:00Z",
                "html_url": "https://github.com/octocat/hello-world/issues/1",
            },
            {
                "number": 2,
                "title": "This is actually a PR",
                "labels": [],
                "created_at": "2020-01-01T00:00:00Z",
                "html_url": "https://github.com/octocat/hello-world/pull/2",
                "pull_request": {"url": "https://api.github.com/..."},
            },
        ]
    )
    mocker.patch("requests.get", return_value=issues_response)

    result = list_open_issues("octocat", "hello-world", count=10)

    assert len(result) == 1
    assert result[0]["number"] == 1
    assert result[0]["labels"] == ["bug"]
    assert result[0]["age_days"] > 0
