"""MCP server definition and tool registration.

Runs over stdio — an MCP client (Claude Desktop, Claude Code, the MCP
Inspector) launches this as a subprocess and talks to it over stdin/stdout.
"""

from mcp.server.mcpserver import MCPServer

from github_client import GitHubClientError, get_repo_summary, list_open_issues, list_recent_commits
from schemas import Commit, Issue, RepoSummary

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


if __name__ == "__main__":
    mcp.run()
