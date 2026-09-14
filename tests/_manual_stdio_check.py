"""Manual smoke test: spawn server.py as a real subprocess and talk MCP-over-stdio to it.

Not part of the pytest suite (hits the live GitHub API and spawns a process).
Run directly: python tests/_manual_stdio_check.py
"""

import asyncio
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

SRC_DIR = Path(__file__).resolve().parent.parent / "src"


async def main():
    params = StdioServerParameters(
        command=sys.executable,
        args=[str(SRC_DIR / "server.py")],
        cwd=str(SRC_DIR),
    )
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()

        tools = await session.list_tools()
        print("Discovered tools:")
        for t in tools.tools:
            print(f"  - {t.name}: {t.description}")

        print("\nCalling repo_summary(sagar3799, langgraph-report-agent)...")
        result = await session.call_tool(
            "repo_summary", {"owner": "sagar3799", "repo": "langgraph-report-agent"}
        )
        print("is_error:", result.is_error)
        print("content:", [c.text for c in result.content])

        print("\nCalling repo_summary on a nonexistent repo (checking clean error)...")
        result = await session.call_tool(
            "repo_summary", {"owner": "sagar3799", "repo": "definitely-does-not-exist-xyz"}
        )
        print("is_error:", result.is_error)
        print("content:", [c.text for c in result.content])

        for tool_name, args in [
            ("contributor_stats", {"owner": "sagar3799", "repo": "langgraph-report-agent", "count": 3}),
            ("codebase_insights", {"owner": "sagar3799", "repo": "langgraph-report-agent"}),
            ("commit_frequency", {"owner": "sagar3799", "repo": "langgraph-report-agent", "weeks": 4}),
            ("search_codebase", {"owner": "sagar3799", "repo": "langgraph-report-agent", "query": "def"}),
        ]:
            print(f"\nCalling {tool_name}({args})...")
            result = await session.call_tool(tool_name, args)
            print("is_error:", result.is_error)
            print("content:", [c.text for c in result.content])


if __name__ == "__main__":
    asyncio.run(main())
