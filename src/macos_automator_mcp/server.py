"""MCP server definition — registers all 7 macOS automation tools."""

from __future__ import annotations

import json
from typing import Any

from mcp import types
from mcp.server import Server
from mcp.server.stdio import stdio_server

from macos_automator_mcp import tools
from macos_automator_mcp.kb import search as kb_search

app = Server('macos-automator')

# ---------------------------------------------------------------------------
# Tool schemas
# ---------------------------------------------------------------------------

_TOOLS: list[types.Tool] = [
    types.Tool(
        name='macos_run_script',
        description=(
            'Run AppleScript or JXA (JavaScript for Automation) on macOS. '
            'Provide script_content for inline code, or kb_script_id to run one of 498 pre-built scripts. '
            'Supports --MCP_INPUT:key placeholder substitution via input_data. '
            'Controls Safari, Messages, Mail, Finder, Calendar, Terminal, Xcode, Spotify, and any scriptable app. '
            'Only available on macOS.'
        ),
        inputSchema={
            'type': 'object',
            'properties': {
                'script_content': {'type': 'string', 'description': 'Inline AppleScript or JXA code.'},
                'language': {
                    'type': 'string',
                    'enum': ['applescript', 'javascript'],
                    'default': 'applescript',
                    'description': "Script language: 'applescript' (default) or 'javascript' (JXA).",
                },
                'kb_script_id': {'type': 'string', 'description': 'ID of a pre-built script from the knowledge base.'},
                'input_data': {
                    'type': 'object',
                    'description': 'Key-value pairs for --MCP_INPUT:key placeholder substitution.',
                    'additionalProperties': True,
                },
                'arguments': {
                    'type': 'array',
                    'description': 'Positional arguments for --MCP_ARG_1..N substitution.',
                    'items': {},
                },
                'timeout_seconds': {'type': 'integer', 'default': 60, 'description': 'Execution timeout in seconds.'},
                'output_format_mode': {
                    'type': 'string',
                    'enum': ['auto', 'human_readable', 'structured'],
                    'default': 'auto',
                    'description': 'Output format: auto, human_readable (-s h), or structured (-s s).',
                },
            },
        },
    ),
    types.Tool(
        name='macos_scripting_tips',
        description=(
            'Search or browse the 498-script macOS automation knowledge base. '
            'Find ready-to-use AppleScript/JXA scripts by keyword or category. '
            'Categories: system, browsers, terminal, editors, productivity, creative, developer, and more.'
        ),
        inputSchema={
            'type': 'object',
            'properties': {
                'search_term': {
                    'type': 'string',
                    'description': 'Fuzzy search term (e.g. "send imessage", "safari screenshot").',
                },
                'category': {
                    'type': 'string',
                    'description': 'Filter by category slug (e.g. "safari", "messages", "system", "terminal").',
                },
                'list_categories': {
                    'type': 'boolean',
                    'default': False,
                    'description': 'If true, return only the list of available categories.',
                },
                'limit': {'type': 'integer', 'default': 10, 'description': 'Maximum number of results.'},
            },
        },
    ),
    types.Tool(
        name='macos_screenshot',
        description=(
            'Take a screenshot of the macOS screen. '
            'Returns a base64-encoded PNG image. '
            'Requires Screen Recording permission for the parent application. '
            'Only available on macOS.'
        ),
        inputSchema={'type': 'object', 'properties': {}},
    ),
    types.Tool(
        name='macos_open',
        description=(
            'Open a macOS application, file, or URL using the `open` command. '
            "Examples: 'Calculator', '/path/to/file.pdf', 'https://example.com'. "
            'Only available on macOS.'
        ),
        inputSchema={
            'type': 'object',
            'properties': {
                'target': {'type': 'string', 'description': 'App name, file path, or URL to open.'},
            },
            'required': ['target'],
        },
    ),
    types.Tool(
        name='macos_clipboard',
        description='Read from or write to the macOS clipboard. Only available on macOS.',
        inputSchema={
            'type': 'object',
            'properties': {
                'action': {
                    'type': 'string',
                    'enum': ['read', 'write'],
                    'description': "'read' to get clipboard contents, 'write' to set clipboard.",
                },
                'text': {'type': 'string', 'description': "Text to write (required when action='write')."},
            },
            'required': ['action'],
        },
    ),
    types.Tool(
        name='macos_notify',
        description='Send a macOS system notification that appears in Notification Center. Only available on macOS.',
        inputSchema={
            'type': 'object',
            'properties': {
                'title': {'type': 'string', 'description': 'Notification title.'},
                'message': {'type': 'string', 'description': 'Notification body text.'},
                'subtitle': {'type': 'string', 'description': 'Optional subtitle.', 'default': ''},
            },
            'required': ['title', 'message'],
        },
    ),
    types.Tool(
        name='macos_system',
        description=(
            'Perform macOS system-level actions: control volume, brightness, dark mode, '
            'screen lock, display sleep, list/quit running apps, or speak text. '
            'Only available on macOS.'
        ),
        inputSchema={
            'type': 'object',
            'properties': {
                'action': {
                    'type': 'string',
                    'enum': [
                        'volume_get',
                        'volume_set',
                        'brightness_set',
                        'dark_mode_toggle',
                        'sleep_display',
                        'lock_screen',
                        'list_apps',
                        'quit_app',
                        'say',
                        'do_not_disturb_on',
                        'do_not_disturb_off',
                    ],
                    'description': 'System action to perform.',
                },
                'value': {
                    'type': 'string',
                    'description': (
                        'Parameter for the action: '
                        'volume level 0-100 (volume_set), '
                        'brightness 0.0-1.0 (brightness_set), '
                        'app name (quit_app), '
                        'text to speak (say).'
                    ),
                },
            },
            'required': ['action'],
        },
    ),
]


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


@app.list_tools()
async def list_tools() -> list[types.Tool]:
    """Return available tools (all 7 if on macOS, or all with macOS note)."""
    return _TOOLS


@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
    """Dispatch tool calls to the appropriate handler."""
    if not tools.is_macos():
        err = json.dumps({'success': False, 'error': 'This tool only works on macOS.'})
        return [types.TextContent(type='text', text=err)]

    result: str
    if name == 'macos_run_script':
        result = tools.macos_run_script(**arguments)
    elif name == 'macos_scripting_tips':
        result = kb_search(
            search_term=arguments.get('search_term'),
            category=arguments.get('category'),
            list_categories_only=bool(arguments.get('list_categories', False)),
            limit=int(arguments.get('limit', 10)),
        )
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
