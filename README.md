# mcp-github-server

An [MCP](https://modelcontextprotocol.io) server exposing GitHub repository data —
commits, issues, contributor activity — as typed, callable tools that any
MCP-compatible LLM client (Claude Desktop, Claude Code, others) can discover and use.

## Tools

| Tool | Description |
|---|---|
| `repo_summary(owner, repo)` | Stars, language breakdown, description, last commit date |
| `recent_commits(owner, repo, count=10)` | Recent commit messages, authors, dates |
| `open_issues(owner, repo, count=10)` | Open issue titles, labels, age in days |

All three work against any public GitHub repo with **zero setup** — no token,
no auth, no config beyond pointing a client at this server.

## Setup

```bash
python -m venv .venv
.venv/Scripts/activate   # .venv/bin/activate on macOS/Linux
pip install -e ".[dev]"
```

### Optional: higher rate limit

Unauthenticated requests are capped at 60/hour by GitHub, which is fine for a demo.
Set `GITHUB_TOKEN` (copy `.env.example` to `.env`) for 5,000/hour — never required.

## Running

```bash
python src/server.py
```

The server communicates over stdio — it's meant to be launched as a subprocess by
an MCP client, not run standalone for interactive use.

### Connect to Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "github-intelligence": {
      "command": "/absolute/path/to/.venv/Scripts/python.exe",
      "args": ["/absolute/path/to/src/server.py"]
    }
  }
}
```

Restart Claude Desktop, then ask something like *"what are the 5 most recent
commits on \<owner\>/\<repo\>?"*

## Tests

```bash
pytest tests/
```

GitHub's API is fully mocked — no live network or token needed to run the suite.

## Why MCP instead of a REST API

A REST API requires the caller to already know its exact endpoints and response
shapes ahead of time — someone has to read docs and write integration code for
that specific API before anything can use it. An MCP server instead *advertises*
its own tools, descriptions, and expected inputs at runtime, so any compatible
client can discover and call them without custom integration code being written
per API. This project is a callable capability an LLM can reason about choosing
to use, not a fixed endpoint a human developer wires up by hand once.
