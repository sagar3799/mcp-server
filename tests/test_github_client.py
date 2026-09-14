"""Tests for github_client. GitHub API is fully mocked — no live network or token needed."""

import sys
from pathlib import Path

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from cache import repo_cache
from github_client import (
    CodeSearchAuthRequiredError,
    GitHubClientError,
    RateLimitError,
    RepoNotFoundError,
    get_codebase_insights,
    get_commit_frequency,
    get_contributor_stats,
    get_repo_summary,
    list_open_issues,
    list_recent_commits,
    search_codebase,
)


@pytest.fixture(autouse=True)
def clear_cache():
    repo_cache.clear()
    yield
    repo_cache.clear()


class FakeResponse:
    def __init__(self, status_code=200, json_data=None, headers=None):
        self.status_code = status_code
        self._json_data = json_data or {}
        self.headers = headers or {}

    def json(self):
        return self._json_data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


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

    assert result.full_name == "octocat/hello-world"
    assert result.stars == 42
    assert result.languages == {"Python": 1000, "JavaScript": 200}
    assert result.last_commit_date == "2026-01-01T00:00:00Z"


def test_get_repo_summary_not_found(mocker):
    mocker.patch("requests.get", return_value=FakeResponse(status_code=404))

    with pytest.raises(RepoNotFoundError):
        get_repo_summary("octocat", "does-not-exist")


def test_get_repo_summary_rate_limited_primary(mocker):
    response = FakeResponse(
        status_code=403,
        headers={"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "9999999999"},
    )
    mocker.patch("requests.get", return_value=response)

    with pytest.raises(RateLimitError, match="rate limit"):
        get_repo_summary("octocat", "hello-world")


def test_get_repo_summary_rate_limited_secondary_retry_after(mocker):
    response = FakeResponse(status_code=403, headers={"Retry-After": "120"})
    mocker.patch("requests.get", return_value=response)

    with pytest.raises(RateLimitError, match="2 minute"):
        get_repo_summary("octocat", "hello-world")


def test_get_repo_summary_caches_repeated_calls(mocker):
    repo_response = FakeResponse(
        json_data={
            "full_name": "octocat/hello-world",
            "description": None,
            "stargazers_count": 1,
            "forks_count": 0,
            "open_issues_count": 0,
            "default_branch": "main",
            "pushed_at": "2026-01-01T00:00:00Z",
            "html_url": "https://github.com/octocat/hello-world",
        }
    )
    languages_response = FakeResponse(json_data={"Python": 1000})
    mock_get = mocker.patch("requests.get", side_effect=[repo_response, languages_response])

    first = get_repo_summary("octocat", "hello-world")
    second = get_repo_summary("octocat", "hello-world")

    assert first == second
    assert mock_get.call_count == 2  # repo + languages, once — not four times


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
    assert result[0].sha == "abc1234"
    assert result[0].message == "Fix bug"
    assert result[0].author == "Alice"


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
    assert result[0].number == 1
    assert result[0].labels == ["bug"]
    assert result[0].age_days > 0


def test_get_contributor_stats(mocker):
    response = FakeResponse(
        json_data=[
            {"login": "alice", "contributions": 42, "html_url": "https://github.com/alice"},
            {"login": "bob", "contributions": 10, "html_url": "https://github.com/bob"},
        ]
    )
    mocker.patch("requests.get", return_value=response)

    result = get_contributor_stats("octocat", "hello-world", count=2)

    assert len(result) == 2
    assert result[0].login == "alice"
    assert result[0].contributions == 42


def test_get_codebase_insights(mocker):
    repo_response = FakeResponse(json_data={"size": 500})
    languages_response = FakeResponse(json_data={"Python": 3000, "JavaScript": 1000})
    mocker.patch("requests.get", side_effect=[repo_response, languages_response])

    result = get_codebase_insights("octocat", "hello-world")

    assert result.size_kb == 500
    assert result.languages == {"Python": 75.0, "JavaScript": 25.0}


def test_get_commit_frequency_success(mocker):
    weekly_data = [{"week": 1735689600 + i * 604800, "total": i, "days": [0] * 7} for i in range(5)]
    mocker.patch("requests.get", return_value=FakeResponse(json_data=weekly_data))

    result = get_commit_frequency("octocat", "hello-world", weeks=3)

    assert len(result) == 3
    assert result[-1].commit_count == 4


def test_get_commit_frequency_still_computing(mocker):
    mocker.patch("requests.get", return_value=FakeResponse(status_code=202, json_data=[]))

    with pytest.raises(GitHubClientError, match="computing"):
        get_commit_frequency("octocat", "hello-world")


def test_search_codebase_requires_token(mocker):
    mocker.patch.dict("os.environ", {}, clear=True)

    with pytest.raises(CodeSearchAuthRequiredError, match="GITHUB_TOKEN"):
        search_codebase("octocat", "hello-world", "StateGraph")


def test_search_codebase_success_with_token(mocker):
    mocker.patch.dict("os.environ", {"GITHUB_TOKEN": "fake-token"})
    response = FakeResponse(
        json_data={
            "items": [
                {
                    "path": "src/graph.py",
                    "html_url": "https://github.com/octocat/hello-world/blob/main/src/graph.py",
                    "score": 1.0,
                    "text_matches": [{"fragment": "class StateGraph:"}],
                }
            ]
        }
    )
    mocker.patch("requests.get", return_value=response)

    result = search_codebase("octocat", "hello-world", "StateGraph")

    assert len(result) == 1
    assert result[0].path == "src/graph.py"
    assert result[0].snippet == "class StateGraph:"
