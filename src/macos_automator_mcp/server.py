"""MCP server definition — registers all 7 macOS automation tools."""

from __future__ import annotations

import json
from typing import Any

from mcp import types
from mcp.server import Server
from mcp.server.stdio import stdio_server
from pydantic import BaseModel

from macos_automator_mcp import tools
from macos_automator_mcp.models import (
    ClipboardInput,
    NotifyInput,
    OpenInput,
    RunScriptInput,
    ScreenshotInput,
    ScriptingTipsInput,
    SystemInput,
)

app = Server('macos-automator')


# ---------------------------------------------------------------------------
# Schema helpers
# ---------------------------------------------------------------------------


def _schema(model: type[BaseModel]) -> dict[str, Any]:
    """Generate a JSON schema dict from a Pydantic model, dropping the title."""
    s = model.model_json_schema()
    s.pop('title', None)
    return s


def _desc(model: type[BaseModel]) -> str:
    """Extract the tool description from the model's docstring."""
    return (model.__doc__ or '').strip()


# ---------------------------------------------------------------------------
# Tool registry — schemas and descriptions auto-generated from Pydantic models
# ---------------------------------------------------------------------------

_TOOLS: list[types.Tool] = [
    types.Tool(
        name='macos_run_script',
        description=_desc(RunScriptInput),
        inputSchema=_schema(RunScriptInput),
    ),
    types.Tool(
        name='macos_scripting_tips',
        description=_desc(ScriptingTipsInput),
        inputSchema=_schema(ScriptingTipsInput),
    ),
    types.Tool(
        name='macos_screenshot',
        description=_desc(ScreenshotInput),
        inputSchema=_schema(ScreenshotInput),
    ),
    types.Tool(
        name='macos_open',
        description=_desc(OpenInput),
        inputSchema=_schema(OpenInput),
    ),
    types.Tool(
        name='macos_clipboard',
        description=_desc(ClipboardInput),
        inputSchema=_schema(ClipboardInput),
    ),
    types.Tool(
        name='macos_notify',
        description=_desc(NotifyInput),
        inputSchema=_schema(NotifyInput),
    ),
    types.Tool(
        name='macos_system',
        description=_desc(SystemInput),
        inputSchema=_schema(SystemInput),
    ),
]


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


@app.list_tools()  # type: ignore[no-untyped-call, untyped-decorator]
async def list_tools() -> list[types.Tool]:
    """Return the 7 available macOS automation tools."""
    return _TOOLS


@app.call_tool()  # type: ignore[untyped-decorator]
async def call_tool(name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
    """Dispatch tool calls to the appropriate handler."""
    if not tools.is_macos():
        err = json.dumps({'success': False, 'error': 'This tool only works on macOS.'})
        return [types.TextContent(type='text', text=err)]

    result: str
    if name == 'macos_run_script':
        result = tools.macos_run_script(**arguments)
    elif name == 'macos_scripting_tips':
        result = tools.macos_scripting_tips(**arguments)
    elif name == 'macos_screenshot':
        result = tools.macos_screenshot(**arguments)
    elif name == 'macos_open':
        result = tools.macos_open(**arguments)
    elif name == 'macos_clipboard':
        result = tools.macos_clipboard(**arguments)
    elif name == 'macos_notify':
        result = tools.macos_notify(**arguments)
    elif name == 'macos_system':
        result = tools.macos_system(**arguments)
    else:
        result = json.dumps({'success': False, 'error': f'Unknown tool: {name}'})

    return [types.TextContent(type='text', text=result)]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


async def main() -> None:
    """Start the MCP server on stdio."""
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())
