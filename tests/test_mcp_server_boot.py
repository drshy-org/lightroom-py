"""Drift guard: the ``lightroom-mcp`` server must start and complete the
MCP ``initialize`` handshake with whatever ``mcp`` library is installed.

Why this exists: the ``[mcp]`` extra shipped unpinned, ``mcp`` 2.x removed
the low-level ``Server`` decorators the server is written against, and a
fresh ``pip install "lightroom-py[mcp]"`` produced a binary that crashed
on startup — silently, in MCP clients that tolerate startup failures.
The unit suite never imported the server, so nothing caught it.
"""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

pytest.importorskip("mcp", reason="[mcp] extra not installed")

_INIT = json.dumps(
    {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "lightroom-py-test", "version": "0"},
        },
    }
) + "\n"


def test_mcp_server_boots_and_answers_initialize() -> None:
    proc = subprocess.run(
        [sys.executable, "-c", "from lightroom.mcp_server import main; main()"],
        input=_INIT,
        capture_output=True,
        text=True,
        timeout=20,
    )
    # A crash before/at serve() exits non-zero with a traceback on stderr.
    assert "Traceback" not in proc.stderr, proc.stderr[-800:]
    lines = [ln for ln in proc.stdout.splitlines() if ln.strip()]
    assert lines, f"no JSON-RPC output; stderr={proc.stderr[-400:]}"
    reply = json.loads(lines[0])
    assert reply.get("id") == 1
    assert "result" in reply, reply
    assert reply["result"]["serverInfo"]["name"] == "lightroom-py"
    assert "tools" in reply["result"]["capabilities"]
