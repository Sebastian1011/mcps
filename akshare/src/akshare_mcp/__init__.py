"""akshare-mcp: an MCP server exposing akshare as two tools -- realtime
quotes and multi-frequency history bars -- across 16 asset classes.

Set TQDM_DISABLE before anything imports akshare (which decides at import
time whether to wire up tqdm progress bars): akshare's multi-page fetchers
print progress bars to stderr by default, which is just noise for a server
process and actively corrupts stdio-transport framing.
"""

import os

os.environ.setdefault("TQDM_DISABLE", "1")

__version__ = "0.1.0"
