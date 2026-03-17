"""Entry point: python -m macos_automator_mcp or macos-mcp CLI."""

import argparse
import asyncio

from macos_automator_mcp.server import main


def run() -> None:
    parser = argparse.ArgumentParser(description='macOS MCP server')
    parser.add_argument(
        '--transport',
        choices=['stdio', 'sse', 'streamable-http'],
        default='stdio',
        help='Transport mode (default: stdio)',
    )
    parser.add_argument('--host', default='127.0.0.1', help='Host for HTTP modes (default: 127.0.0.1)')
    parser.add_argument('--port', type=int, default=8765, help='Port for HTTP modes (default: 8765)')
    args = parser.parse_args()

    asyncio.run(main(host=args.host, port=args.port, transport=args.transport))


if __name__ == '__main__':
    run()
