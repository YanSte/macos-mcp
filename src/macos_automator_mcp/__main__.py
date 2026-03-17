"""Entry point: python -m macos_automator_mcp."""

import asyncio

from macos_automator_mcp.server import main

if __name__ == '__main__':
    asyncio.run(main())
