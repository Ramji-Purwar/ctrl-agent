"""
MCP Server for ctrl-agent.

Exposes all ctrl-agent tools (file system, git, gmail) via the
Model Context Protocol so that LLMs like Claude Desktop can use them natively.

Communicates with the running ctrl-agent UI via HTTP to show live tool events.
"""

import asyncio
import json
import logging
import sys
import os

# ── Redirect stderr BEFORE any imports that might write to it ────
# MCP stdio transport uses stdin/stdout for JSON-RPC.
# Any stray output on stderr can crash the connection on Windows.
_PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
_LOG_FILE = os.path.join(_PROJECT_ROOT, "data", "mcp_server.log")
os.makedirs(os.path.dirname(_LOG_FILE), exist_ok=True)

# Redirect stderr to log file so it doesn't interfere with stdio transport
_log_fh = open(_LOG_FILE, "a", encoding="utf-8")
sys.stderr = _log_fh

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=_log_fh,
)
logger = logging.getLogger("mcp_server")

# ── Add project to path and import tools ─────────────────────────
sys.path.insert(0, _PROJECT_ROOT)

# Change working directory so .env and data/ are found
os.chdir(_PROJECT_ROOT)

import requests
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from tools.registry import TOOL_REGISTRY, TOOL_SCHEMAS
from core.agent_loop import _coerce_args
from config.settings import FLASK_HOST, FLASK_PORT

_UI_HOST = FLASK_HOST or "127.0.0.1"
_UI_PORT = FLASK_PORT or 9999

app = Server(
    "ctrl-agent-mcp",
    instructions=(
        "You are ctrl-agent, a personal assistant with tools for file system, Git, and Gmail. "
        f"The user's base directory is: {os.environ.get('BASE_DIR', os.path.expanduser('~'))}. "
        f"The user's GitHub username is: {os.environ.get('GIT_USERNAME', 'unknown')}. "
        "STRICT RULES — follow these every time: "
        "1. Never guess a full path. If you don't know the exact path, call find_folder or find_file first. "
        "2. For open_folder: ALWAYS call find_folder first to get the real path, then call open_folder with that path. "
        "3. For make_folder inside X: always call find_folder to locate X, then make the folder inside the result. "
        "4. For find_file: return the location only. Do NOT call read_file unless the user asked to read the file. "
        "5. For git_push: always call git_push_dry_run first, show the user the preview, and wait for confirmation. "
        "6. Never read or reveal secret files such as .env files, API keys, tokens, or credentials. "
        "7. For Gmail: to find emails from a specific sender, use search_emails with query='from:sender@domain.com'. "
        "8. For git_clone: NEVER guess the dest_path. Call find_folder first to resolve any named folder. "
        "9. When a tool returns requires_confirmation=true, relay the message to the user and wait. "
    ),
)

# ── Build MCP tool list from existing OpenAI-style schemas ───────
mcp_tools = []
for schema in TOOL_SCHEMAS:
    func = schema.get("function", {})
    mcp_tools.append(Tool(
        name=func.get("name"),
        description=func.get("description", ""),
        inputSchema=func.get("parameters", {}),
    ))

logger.info(f"Loaded {len(mcp_tools)} tools from ctrl-agent registry")


@app.list_tools()
async def list_tools() -> list[Tool]:
    return mcp_tools


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name not in TOOL_REGISTRY:
        return [TextContent(type="text", text=f"Error: Unknown tool '{name}'")]

    tool_fn = TOOL_REGISTRY[name]
    logger.info(f"Executing tool {name} with args {arguments}")

    try:
        tool_args = _coerce_args(tool_fn, arguments)
        result = tool_fn(**tool_args)
        success = result.get("success", False)

        # Determine string representation of result
        if not success:
            res_str = f"Tool failed with error: {result.get('error', 'Unknown error')}"
        elif name == "find_file":
            matches = result.get("matches", [])
            if not matches:
                res_str = "No matching files found."
            else:
                heading = f"Found {len(matches)} matching file{'s' if len(matches) != 1 else ''}:"
                res_str = heading + "\n" + "\n".join(matches)
        else:
            res_str = json.dumps(result, indent=2)

    except Exception as e:
        logger.error(f"Error in tool {name}: {e}", exc_info=True)
        success = False
        result = {"error": str(e)}
        res_str = f"Exception occurred: {e}"

    # Notify the running ctrl-agent UI (fire-and-forget, short timeout)
    try:
        payload = {
            "type": "mcp_tool_call",
            "tool": name,
            "args": arguments,
            "result": result,
            "success": success,
        }
        requests.post(
            f"http://{_UI_HOST}:{_UI_PORT}/mcp-event",
            json=payload,
            timeout=2,
        )
    except Exception:
        pass  # ctrl-agent UI might not be running — that's OK

    # Return result to Claude Desktop
    return [TextContent(type="text", text=res_str)]


async def main():
    logger.info("Starting ctrl-agent MCP server on stdio...")
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())
