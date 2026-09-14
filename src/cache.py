"""In-memory TTL cache for GitHub API calls.

This server runs as a local subprocess an MCP client starts and stops —
there's nothing to persist across restarts, so a plain process-lifetime
cache is all that's needed. Cuts repeated identical calls (e.g. asking
about the same repo twice in a conversation) down to zero extra API hits.
"""

import functools

from cachetools import TTLCache

repo_cache = TTLCache(maxsize=100, ttl=300)


def cached(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        key = (func.__name__, args, tuple(sorted(kwargs.items())))
        if key in repo_cache:
            return repo_cache[key]
        result = func(*args, **kwargs)
        repo_cache[key] = result
        return result

    return wrapper
