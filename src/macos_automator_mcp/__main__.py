"""Entry point: python -m macos_automator_mcp or macos-mcp CLI."""

import asyncio

from macos_automator_mcp.server import main


def run() -> None:
    asyncio.run(main())


if __name__ == '__main__':
    run()
