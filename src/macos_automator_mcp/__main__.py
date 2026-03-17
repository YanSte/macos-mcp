"""Entry point: python -m macos_automator_mcp or macos-mcp CLI."""

import argparse
import asyncio

from macos_automator_mcp.server import main


def run() -> None:
    parser = argparse.ArgumentParser(description='macOS MCP server')
    parser.add_argument('--http', action='store_true', help='Run SSE HTTP server instead of stdio')
    parser.add_argument('--host', default='127.0.0.1', help='Host for HTTP mode (default: 127.0.0.1)')
    parser.add_argument('--port', type=int, default=8765, help='Port for HTTP mode (default: 8765)')
    args = parser.parse_args()

    transport = 'sse' if args.http else 'stdio'
    asyncio.run(main(host=args.host, port=args.port, transport=transport))


if __name__ == '__main__':
    run()
