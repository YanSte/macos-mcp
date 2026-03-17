"""macOS tool implementations — osascript, screencapture, pbpaste/pbcopy, open, etc."""

from __future__ import annotations

import base64
import json
import platform
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any


def is_macos() -> bool:
    """Return True if running on macOS."""
    return platform.system() == 'Darwin'


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _coerce_to_applescript(value: Any) -> str:  # noqa: ANN401
    """Convert a Python value to an AppleScript literal."""
    if value is None:
        return 'missing value'
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        items = ', '.join(_coerce_to_applescript(v) for v in value)
        return f'{{{items}}}'
    # Default: string
    escaped = str(value).replace('\\', '\\\\').replace('"', '\\"')
    return f'"{escaped}"'


def _coerce_to_jxa(value: Any) -> str:  # noqa: ANN401
    """Convert a Python value to a JXA (JavaScript) literal."""
    if value is None:
        return 'null'
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        items = ', '.join(_coerce_to_jxa(v) for v in value)
        return f'[{items}]'
    escaped = str(value).replace('\\', '\\\\').replace('"', '\\"')
    return f'"{escaped}"'


def _substitute_placeholders(
    script: str,
    language: str,
    input_data: dict[str, Any] | None,
    arguments: list[Any] | None,
) -> str:
    """Replace --MCP_INPUT:key and --MCP_ARG_N placeholders in script."""
    is_js = language == 'javascript'

    def coerce(v: Any) -> str:  # noqa: ANN401
        return _coerce_to_jxa(v) if is_js else _coerce_to_applescript(v)

    if input_data:
        for key, val in input_data.items():
            literal = coerce(val)
            # Quoted placeholder variants
            script = script.replace(f'"--MCP_INPUT:{key}"', literal)
            script = script.replace(f"'--MCP_INPUT:{key}'", literal)
            # JS template literal style
            script = re.sub(rf'\$\{{inputData\.{re.escape(key)}\}}', literal, script)
            # Bare expression context: (--MCP_INPUT:key) or =--MCP_INPUT:key
            script = re.sub(rf'\(--MCP_INPUT:{re.escape(key)}\)', f'({literal})', script)
            script = re.sub(rf'=--MCP_INPUT:{re.escape(key)}', f'={literal}', script)

    if arguments:
        for idx, val in enumerate(arguments, 1):
            literal = coerce(val)
            script = script.replace(f'"--MCP_ARG_{idx}"', literal)
            script = script.replace(f"'--MCP_ARG_{idx}'", literal)
            script = re.sub(rf'\$\{{arguments\[{idx - 1}\]\}}', literal, script)

    return script


def _run_osascript(
    script: str,
    language: str = 'applescript',
    timeout: int = 60,
    output_format: str = 'auto',
) -> dict[str, Any]:
    """Execute script via osascript. Returns {success, output, error}."""
    lang_flag = 'JavaScript' if language == 'javascript' else 'AppleScript'
    cmd = ['osascript', '-l', lang_flag]
    if output_format == 'human_readable':
        cmd += ['-s', 'h']
    elif output_format == 'structured':
        cmd += ['-s', 's']
    cmd += ['-e', script]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if result.returncode == 0:
            return {'success': True, 'output': result.stdout.strip()}
        return {'success': False, 'error': result.stderr.strip() or f'Exit code {result.returncode}'}
    except subprocess.TimeoutExpired:
        return {'success': False, 'error': f'Script timed out after {timeout}s'}
    except FileNotFoundError:
        return {'success': False, 'error': 'osascript not found — only available on macOS'}
    except Exception as e:
        return {'success': False, 'error': str(e)}


# ---------------------------------------------------------------------------
# Public tool functions
# ---------------------------------------------------------------------------


def macos_run_script(
    script_content: str | None = None,
    language: str = 'applescript',
    kb_script_id: str | None = None,
    input_data: dict[str, Any] | None = None,
    arguments: list[Any] | None = None,
    timeout_seconds: int = 60,
    output_format_mode: str = 'auto',
    **_kwargs: Any,
) -> str:
    """Run AppleScript or JXA, optionally using a knowledge base script by ID.

    Args:
        script_content: Inline script code. Mutually exclusive with kb_script_id.
        language: 'applescript' (default) or 'javascript'.
        kb_script_id: ID of a pre-built script from the knowledge base.
        input_data: Dict of {key: value} for --MCP_INPUT:key placeholder substitution.
        arguments: List of positional args for --MCP_ARG_1..N substitution.
        timeout_seconds: Execution timeout in seconds (default 60).
        output_format_mode: 'auto', 'human_readable', or 'structured'.

    Returns:
        JSON string with {success, output} or {success: false, error}.
    """
    if not script_content and not kb_script_id:
        return json.dumps({'success': False, 'error': 'Provide script_content or kb_script_id'})

    if kb_script_id:
        from macos_automator_mcp.kb import get_script_by_id

        entry = get_script_by_id(kb_script_id)
        if not entry:
            return json.dumps({'success': False, 'error': f'Unknown kb_script_id: {kb_script_id!r}'})
        script_content = entry['script']
        language = entry.get('language', 'applescript')  # type: ignore[assignment]

    script = _substitute_placeholders(str(script_content), language, input_data, arguments)
    result = _run_osascript(script, language, timeout_seconds, output_format_mode)
    return json.dumps(result)


def macos_screenshot(**_kwargs: Any) -> str:
    """Take a screenshot and return it as a base64-encoded PNG.

    Returns:
        JSON string with {success, image_base64, format} or {success: false, error}.
    """
    try:
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
            tmp = f.name
        subprocess.run(['screencapture', '-x', tmp], check=True, timeout=15)
        data = Path(tmp).read_bytes()
        b64 = base64.b64encode(data).decode()
        Path(tmp).unlink(missing_ok=True)
        return json.dumps({'success': True, 'image_base64': b64, 'format': 'png'})
    except subprocess.CalledProcessError as e:
        return json.dumps({'success': False, 'error': f'screencapture failed: {e}'})
    except Exception as e:
        return json.dumps({'success': False, 'error': str(e)})


def macos_open(target: str, **_kwargs: Any) -> str:
    """Open an application, file, or URL using the macOS `open` command.

    Args:
        target: App name (e.g. 'Calculator'), file path, or URL.

    Returns:
        JSON string with {success, opened} or {success: false, error}.
    """
    try:
        subprocess.run(['open', target], check=True, timeout=15)
        return json.dumps({'success': True, 'opened': target})
    except subprocess.CalledProcessError as e:
        return json.dumps({'success': False, 'error': str(e)})
    except Exception as e:
        return json.dumps({'success': False, 'error': str(e)})


def macos_clipboard(action: str, text: str | None = None, **_kwargs: Any) -> str:
    """Read from or write to the macOS clipboard.

    Args:
        action: 'read' to get clipboard contents, 'write' to set clipboard.
        text: Text to write (required when action='write').

    Returns:
        JSON string with {success, text} or {success: false, error}.
    """
    if action == 'read':
        try:
            result = subprocess.run(['pbpaste'], capture_output=True, text=True, timeout=5)
            return json.dumps({'success': True, 'text': result.stdout})
        except Exception as e:
            return json.dumps({'success': False, 'error': str(e)})
    elif action == 'write':
        if text is None:
            return json.dumps({'success': False, 'error': "text is required for action='write'"})
        try:
            subprocess.run(['pbcopy'], input=text, text=True, check=True, timeout=5)
            return json.dumps({'success': True, 'text': text})
        except Exception as e:
            return json.dumps({'success': False, 'error': str(e)})
    else:
        return json.dumps({'success': False, 'error': f"Unknown action {action!r}. Use 'read' or 'write'."})


def macos_notify(title: str, message: str, subtitle: str = '', **_kwargs: Any) -> str:
    """Send a macOS system notification.

    Args:
        title: Notification title.
        message: Notification body text.
        subtitle: Optional subtitle.

    Returns:
        JSON string with {success} or {success: false, error}.
    """
    subtitle_part = f' subtitle "{subtitle}"' if subtitle else ''
    script = f'display notification "{message}" with title "{title}"{subtitle_part}'
    result = _run_osascript(script)
    return json.dumps(result)


_SYSTEM_ACTIONS = {
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
}


def macos_system(action: str, value: str | None = None, **_kwargs: Any) -> str:
    """Perform macOS system-level actions.

    Args:
        action: One of: volume_get, volume_set, brightness_set, dark_mode_toggle,
                sleep_display, lock_screen, list_apps, quit_app, say,
                do_not_disturb_on, do_not_disturb_off.
        value: Numeric or string parameter (e.g. volume level 0-100, app name, text to speak).

    Returns:
        JSON string with action result.
    """
    if action not in _SYSTEM_ACTIONS:
        return json.dumps(
            {
                'success': False,
                'error': f'Unknown action {action!r}. Valid: {sorted(_SYSTEM_ACTIONS)}',
            }
        )

    if action == 'volume_get':
        script = 'output volume of (get volume settings)'
        result = _run_osascript(script)
        if result.get('success'):
            try:
                result['volume'] = int(result['output'])
            except (ValueError, KeyError):
                pass
        return json.dumps(result)

    if action == 'volume_set':
        level = int(value or '50')
        level = max(0, min(100, level))
        return json.dumps(_run_osascript(f'set volume output volume {level}'))

    if action == 'brightness_set':
        level = float(value or '0.5')
        level = max(0.0, min(1.0, level))
        script = (
            'tell application "System Events" to tell process "SystemUIServer" '
            f'to set value of slider 1 of menu bar item "Displays" of menu bar 2 to {level}'
        )
        return json.dumps(_run_osascript(script))

    if action == 'dark_mode_toggle':
        script = 'tell application "System Events" to tell appearance preferences to set dark mode to not dark mode'
        return json.dumps(_run_osascript(script))

    if action == 'sleep_display':
        try:
            subprocess.run(['pmset', 'displaysleepnow'], check=True, timeout=5)
            return json.dumps({'success': True})
        except Exception as e:
            return json.dumps({'success': False, 'error': str(e)})

    if action == 'lock_screen':
        script = 'tell application "System Events" to keystroke "q" using {command down, control down}'
        return json.dumps(_run_osascript(script))

    if action == 'list_apps':
        script = 'tell application "System Events" to get name of every process where background only is false'
        return json.dumps(_run_osascript(script))

    if action == 'quit_app':
        app = value or ''
        if not app:
            return json.dumps({'success': False, 'error': 'value (app name) is required for quit_app'})
        script = f'tell application "{app}" to quit'
        return json.dumps(_run_osascript(script))

    if action == 'say':
        text = value or ''
        if not text:
            return json.dumps({'success': False, 'error': 'value (text) is required for say'})
        try:
            subprocess.run(['say', text], check=True, timeout=60)
            return json.dumps({'success': True, 'spoken': text})
        except Exception as e:
            return json.dumps({'success': False, 'error': str(e)})

    if action == 'do_not_disturb_on':
        script = 'tell application "System Events" to tell do not disturb of (get focus) to set enabled to true'
        return json.dumps(_run_osascript(script))

    if action == 'do_not_disturb_off':
        script = 'tell application "System Events" to tell do not disturb of (get focus) to set enabled to false'
        return json.dumps(_run_osascript(script))

    return json.dumps({'success': False, 'error': f'Unhandled action: {action}'})
