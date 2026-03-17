"""MCP server definition — registers all 8 macOS automation tools."""

from __future__ import annotations

import json
from typing import Any

from mcp import types
from mcp.server import Server
from mcp.server.stdio import stdio_server
from pydantic import BaseModel

from macos_automator_mcp import tools
from macos_automator_mcp.models import (
    AccessibilityQueryInput,
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
    types.Tool(
        name='macos_accessibility_query',
        description=_desc(AccessibilityQueryInput),
        inputSchema=_schema(AccessibilityQueryInput),
    ),
]


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


@app.list_tools()  # type: ignore[no-untyped-call, untyped-decorator]
async def list_tools() -> list[types.Tool]:
    """Return the 8 available macOS automation tools."""
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
    elif name == 'macos_accessibility_query':
        result = tools.macos_accessibility_query(**arguments)
    else:
        result = json.dumps({'success': False, 'error': f'Unknown tool: {name}'})

    return [types.TextContent(type='text', text=result)]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


async def main(host: str = '127.0.0.1', port: int = 8765, transport: str = 'stdio') -> None:
    """Start the MCP server on stdio, SSE, or streamable-http."""
    if transport in ('sse', 'streamable-http'):
        import uvicorn  # type: ignore[import-untyped]
        from starlette.applications import Starlette  # type: ignore[import-untyped]
        from starlette.routing import Mount, Route  # type: ignore[import-untyped]

        if transport == 'streamable-http':
            import contextlib

            from mcp.server.streamable_http_manager import StreamableHTTPSessionManager  # type: ignore[import-untyped]

            session_manager = StreamableHTTPSessionManager(
                app=app,
                event_store=None,
                json_response=False,
                stateless=False,
            )

            @contextlib.asynccontextmanager  # type: ignore[arg-type]
            async def lifespan(starlette_app: Any) -> Any:  # noqa: ANN401
                async with session_manager.run():
                    yield

            async def handle_mcp(scope: Any, receive: Any, send: Any) -> None:  # noqa: ANN401
                await session_manager.handle_request(scope, receive, send)

            starlette_app = Starlette(routes=[Mount('/mcp', app=handle_mcp)], lifespan=lifespan)
            print(f'macos-mcp streamable-http server running at http://{host}:{port}/mcp')
        else:
            from mcp.server.sse import SseServerTransport

            sse = SseServerTransport('/messages/')

            async def handle_sse(request: Any) -> Any:  # noqa: ANN401
                async with sse.connect_sse(request.scope, request.receive, request._send) as (r, w):
                    await app.run(r, w, app.create_initialization_options())

            starlette_app = Starlette(
                routes=[
                    Route('/sse', endpoint=handle_sse),
                    Mount('/messages/', app=sse.handle_post_message),
                ]
            )
            print(f'macos-mcp SSE server running at http://{host}:{port}/sse')

        uvicorn_config = uvicorn.Config(starlette_app, host=host, port=port, log_level='warning')
        server = uvicorn.Server(uvicorn_config)
        await server.serve()
    else:
        async with stdio_server() as (read_stream, write_stream):
            await app.run(read_stream, write_stream, app.create_initialization_options())
