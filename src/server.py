"""MCP server definition and tool registration.

Runs over stdio — an MCP client (Claude Desktop, Claude Code, the MCP
Inspector) launches this as a subprocess and talks to it over stdin/stdout.
"""

from mcp.server.mcpserver import MCPServer

from github_client import (
    GitHubClientError,
    get_codebase_insights,
    get_commit_frequency,
    get_contributor_stats,
    get_repo_summary,
    list_open_issues,
    list_recent_commits,
)
from github_client import search_codebase as search_codebase_client
from schemas import (
    CodebaseInsights,
    CodeSearchResult,
    Commit,
    Contributor,
    Issue,
    RepoSummary,
    WeeklyCommitCount,
)

mcp = MCPServer("github-intelligence")


@mcp.tool()
def repo_summary(owner: str, repo: str) -> RepoSummary | dict:
    """Get stars, language breakdown, description, and last commit date for a GitHub repo."""
    try:
        return get_repo_summary(owner, repo)
    except GitHubClientError as e:
        return {"error": str(e)}


@mcp.tool()
def recent_commits(owner: str, repo: str, count: int = 10) -> list[Commit] | list[dict]:
    """List the most recent commits to a GitHub repo, with author and date."""
    try:
        return list_recent_commits(owner, repo, count)
    except GitHubClientError as e:
        return [{"error": str(e)}]


@mcp.tool()
def open_issues(owner: str, repo: str, count: int = 10) -> list[Issue] | list[dict]:
    """List open issues on a GitHub repo, with labels and age in days."""
    try:
        return list_open_issues(owner, repo, count)
    except GitHubClientError as e:
        return [{"error": str(e)}]


@mcp.tool()
def contributor_stats(owner: str, repo: str, count: int = 10) -> list[Contributor] | list[dict]:
    """List top contributors to a GitHub repo by commit count on the default branch."""
    try:
        return get_contributor_stats(owner, repo, count)
    except GitHubClientError as e:
        return [{"error": str(e)}]


@mcp.tool()
def codebase_insights(owner: str, repo: str) -> CodebaseInsights | dict:
    """Get language breakdown (as percentages) and total repo size in KB."""
    try:
        return get_codebase_insights(owner, repo)
    except GitHubClientError as e:
        return {"error": str(e)}


@mcp.tool()
def commit_frequency(owner: str, repo: str, weeks: int = 12) -> list[WeeklyCommitCount] | list[dict]:
    """Weekly commit counts for the last N weeks (max 52) on a GitHub repo. Pure
    activity counting, not a summary or categorization of what the commits contain."""
    try:
        return get_commit_frequency(owner, repo, weeks)
    except GitHubClientError as e:
        return [{"error": str(e)}]


@mcp.tool()
def search_codebase(owner: str, repo: str, query: str, count: int = 10) -> list[CodeSearchResult] | list[dict]:
    """Search code within a GitHub repo's default branch. Requires GITHUB_TOKEN to
    be set — GitHub's code search has its own, much stricter rate limit than the
    other tools here. Only indexes the default branch and excludes some large files
    and forks, so an empty result doesn't necessarily mean the code doesn't exist."""
    try:
        return search_codebase_client(owner, repo, query, count)
    except GitHubClientError as e:
        return [{"error": str(e)}]


if __name__ == "__main__":
    mcp.run()
