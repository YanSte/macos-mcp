# macos-mcp

Python MCP server for macOS automation via AppleScript and JXA — 498-script knowledge base.

Works with any MCP client: Claude Desktop, OpenClaw, Cursor, Hermes Agent, and more.

## Features

- **8 tools** covering all macOS automation needs
- **498-script knowledge base** — system, browsers, terminal, editors, messaging, creative apps, Xcode/iOS Simulator, and more
- **AppleScript & JXA** — run inline scripts, execute script files, or look up pre-built scripts by ID
- **Placeholder substitution** — `--MCP_INPUT:key` and `--MCP_ARG_N` patterns for dynamic inputs
- **Accessibility control** — inspect and interact with any UI element in any app
- **Pydantic v2 schemas** — fully typed, validated parameters with rich descriptions for LLMs
- **Zero extra dependencies** — only `mcp` and `pydantic`; everything else is stdlib

## Tools

### `macos_run_script`
Run an AppleScript or JXA script inline, from a file path, or from the 498-script knowledge base. Controls any scriptable macOS app: Safari, Messages, Mail, Finder, Calendar, Terminal, Xcode, Spotify, and more.

**Parameters:**
- `script_content` — inline AppleScript or JXA source code
- `script_path` — absolute path to a `.applescript` or `.jxa` file
- `kb_script_id` — ID from the 498-script knowledge base (e.g. `messages_send_message`)
- `language` — `applescript` (default) or `javascript` (JXA)
- `input_data` — key/value pairs substituted into `--MCP_INPUT:key` placeholders
- `arguments` — positional args substituted into `--MCP_ARG_1`, `--MCP_ARG_2`, …
- `timeout_seconds` — max wait time (default 60, max 3600)
- `output_format_mode` — `auto`, `human_readable`, `structured_error`, `structured_output_and_error`, `direct`
- `include_executed_script_in_output` — append the final script text to the response
- `include_substitution_logs` — log every placeholder substitution performed
- `report_execution_time` — include script execution duration in response

---

### `macos_scripting_tips`
Fuzzy-search the 498-script AppleScript/JXA knowledge base by keyword or category, or list all categories. Use this to discover script IDs before calling `macos_run_script` with `kb_script_id`.

**Parameters:**
- `search_term` — natural language search (e.g. `"send imessage"`, `"battery level"`)
- `category` — filter by slug: `browsers`, `productivity`, `developer`, `system`, `terminal`, `editors`, `creative`, `files`, `advanced`, `as_core`, `jxa_core`, `network`
- `list_categories` — if true, return only category list with script counts
- `limit` — max results (default 10, max 100)
- `refresh_database` — force reload of knowledge base from disk

---

### `macos_screenshot`
Take a full-screen screenshot and return it as a base64-encoded PNG image.

> Requires **Screen Recording** permission in System Settings → Privacy & Security.

---

### `macos_open`
Open a macOS application, file, or URL using the system `open` command.

**Parameters:**
- `target` — app name (`"Safari"`), absolute file path (`"/Users/me/doc.pdf"`), or URL (`"https://github.com"`)

---

### `macos_clipboard`
Read from or write to the macOS system clipboard (pasteboard).

**Parameters:**
- `action` — `read` returns current clipboard text; `write` replaces it
- `text` — text to write (required when `action` is `write`)

---

### `macos_notify`
Send a macOS system notification that appears in Notification Center and as a banner.

**Parameters:**
- `title` — bold heading of the notification
- `message` — body text
- `subtitle` — optional subtitle shown between title and message

---

### `macos_system`
Control macOS system settings and perform system-level actions.

**Actions (`action` parameter):**
| Action | Description | `value` |
|---|---|---|
| `volume_get` | Return current output volume (0–100) | — |
| `volume_set` | Set output volume | `"0"` – `"100"` |
| `brightness_set` | Set display brightness | `"0.0"` – `"1.0"` |
| `dark_mode_toggle` | Toggle dark / light appearance | — |
| `sleep_display` | Turn off the display immediately | — |
| `lock_screen` | Lock the session | — |
| `list_apps` | Return names of all visible running apps | — |
| `quit_app` | Gracefully quit an app | app name |
| `say` | Speak text aloud via TTS | text to speak |
| `do_not_disturb_on` | Enable Do Not Disturb / Focus | — |
| `do_not_disturb_off` | Disable Do Not Disturb / Focus | — |

---

### `macos_accessibility_query`
Inspect or interact with any UI element in any macOS application using the Accessibility framework. Use `command="query"` to read UI state and `command="perform"` to click buttons or trigger actions.

> Requires the `ax` binary and **Accessibility** permission in System Settings → Privacy & Security.

**Parameters:**
- `command` — `query` (read elements) or `perform` (trigger action)
- `locator` — target element spec:
  - `app` — app name or bundle ID (e.g. `"Safari"`)
  - `role` — AX role (e.g. `"AXButton"`, `"AXTextField"`, `"AXWebArea"`)
  - `match` — attribute filters (e.g. `{"AXTitle": "Submit"}`)
  - `navigation_path_hint` — path to narrow search (e.g. `["window[1]", "toolbar[1]"]`)
- `return_all_matches` — return all matching elements (default: first only)
- `attributes_to_query` — specific AX attributes to include (e.g. `["AXValue", "AXTitle"]`)
- `required_action_name` — filter to elements supporting this action (e.g. `"AXPress"`)
- `action_to_perform` — action to execute when `command="perform"` (e.g. `"AXPress"`, `"AXFocus"`)
- `output_format` — `smart` (default), `verbose`, or `text_content`
- `limit` — max output lines (default 500)
- `max_elements` — max elements to process (default 200)
- `debug_logging` — include debug output from the ax binary
- `report_execution_time` — include query duration in response

---

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
      "command": "uv",
      "args": ["run", "--project", "/path/to/macos-mcp", "macos-mcp"]
    }
  }
}
```

Or if installed via pip:

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

### OpenClaw / Hermes Agent / Cursor

Same config format — replace the client config path as needed.

## macOS Permissions

Grant these in **System Settings → Privacy & Security**:

| Permission | Required for |
|---|---|
| **Automation** | All AppleScript/JXA tools — macOS auto-prompts on first use per target app |
| **Screen Recording** | `macos_screenshot` |
| **Accessibility** | `macos_accessibility_query` |

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

### Execute a script file

```python
macos_run_script(script_path='/Users/me/scripts/cleanup.applescript')
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
macos_system(action='list_apps')
```

### Accessibility — read a UI element

```python
macos_accessibility_query(
    command='query',
    locator={'app': 'Safari', 'role': 'AXTextField', 'match': {'AXFocused': 'true'}}
)
```

### Accessibility — click a button

```python
macos_accessibility_query(
    command='perform',
    locator={'app': 'Safari', 'role': 'AXButton', 'match': {'AXTitle': 'Go'}},
    action_to_perform='AXPress'
)
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
