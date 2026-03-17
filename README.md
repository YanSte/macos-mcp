# macos-mcp

Python MCP server for macOS automation via AppleScript and JXA — 498-script knowledge base.

Works with any MCP client: Claude Desktop, OpenClaw, Cursor, Hermes Agent, and more.

## Features

- **7 tools** covering all macOS automation needs
- **498-script knowledge base** — system, browsers, terminal, editors, messaging, creative apps, Xcode/iOS Simulator, and more
- **AppleScript & JXA** — run inline scripts or look up pre-built scripts by ID
- **Placeholder substitution** — `--MCP_INPUT:key` pattern for dynamic inputs
- **Zero extra dependencies** — only the `mcp` SDK; everything else is stdlib

## Tools

| Tool | Description |
|---|---|
| `macos_run_script` | Run AppleScript or JXA; supports 498 pre-built scripts via `kb_script_id` |
| `macos_scripting_tips` | Fuzzy-search the 498-script knowledge base by keyword or category |
| `macos_screenshot` | Take a screenshot → returns base64 PNG |
| `macos_open` | Open any app, file, or URL |
| `macos_clipboard` | Read or write the macOS clipboard |
| `macos_notify` | Send a macOS system notification |
| `macos_system` | Volume, brightness, dark mode, lock screen, list/quit apps, TTS |

## Installation

```bash
pip install macos-mcp
# or with uv:
uv add macos-mcp
```

## Configuration

### Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "macos": {
      "command": "python",
      "args": ["-m", "macos_automator_mcp"]
    }
  }
}
```

### OpenClaw / mcporter (`~/.mcporter/mcporter.json`)

```json
{
  "mcpServers": {
    "macos": {
      "command": "python",
      "args": ["-m", "macos_automator_mcp"]
    }
  }
}
```

### Hermes Agent

```json
{
  "mcpServers": {
    "macos": {
      "command": "python",
      "args": ["-m", "macos_automator_mcp"]
    }
  }
}
```

## macOS Permissions

Grant these in **System Settings → Privacy & Security**:

| Permission | Required for | Notes |
|---|---|---|
| **Automation** | All AppleScript tools | macOS auto-prompts on first use per target app |
| **Screen Recording** | `macos_screenshot` only | Must be added manually |

Grant permissions to the application that launches the MCP server (Terminal, Claude Desktop, etc.).

## Usage Examples

### Run inline AppleScript

```python
macos_run_script(script_content='tell application "Finder" to open home')
```

### Use a pre-built script with dynamic input

```python
macos_run_script(
    kb_script_id='messages_send_message',
    input_data={'recipient': 'Mom', 'message': 'I will be late'}
)
```

### Search the knowledge base

```python
macos_scripting_tips(search_term='send imessage', limit=5)
macos_scripting_tips(category='safari', limit=10)
macos_scripting_tips(list_categories=True)
```

### Screenshot

```python
macos_screenshot()  # returns base64 PNG
```

### System controls

```python
macos_system(action='volume_set', value='50')
macos_system(action='dark_mode_toggle')
macos_system(action='say', value='Hello from your AI agent')
```

## Development

```bash
make install    # install deps + pre-commit hooks
make lint       # ruff check + format
make typecheck  # pyright + mypy
make test       # pytest
make run        # start MCP server
```

## License

MIT
