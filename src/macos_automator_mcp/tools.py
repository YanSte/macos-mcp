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

from pydantic import ValidationError

from macos_automator_mcp.models import (
    ClipboardInput,
    NotifyInput,
    OpenInput,
    RunScriptInput,
    ScreenshotInput,
    ScriptingTipsInput,
    SystemInput,
)


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
            script = script.replace(f'"--MCP_INPUT:{key}"', literal)
            script = script.replace(f"'--MCP_INPUT:{key}'", literal)
            script = re.sub(rf'\$\{{inputData\.{re.escape(key)}\}}', literal, script)
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


def _validation_error(e: ValidationError) -> str:
    """Serialize a Pydantic ValidationError to a JSON error response."""
    errors = []
    for err in e.errors(include_url=False):
        # ctx may contain non-serializable exceptions — convert to string
        if 'ctx' in err:
            err = {**err, 'ctx': {k: str(v) for k, v in err['ctx'].items()}}
        errors.append(err)
    return json.dumps({'success': False, 'error': errors})


# ---------------------------------------------------------------------------
# Public tool functions
# ---------------------------------------------------------------------------


def macos_run_script(**kwargs: Any) -> str:
    """Run AppleScript or JXA, optionally using a knowledge base script by ID."""
    try:
        inp = RunScriptInput(**kwargs)
    except ValidationError as e:
        return _validation_error(e)

    script_content = inp.script_content
    language: str = inp.language

    if inp.kb_script_id:
        from macos_automator_mcp.kb import get_script_by_id

        entry = get_script_by_id(inp.kb_script_id)
        if not entry:
            return json.dumps({'success': False, 'error': f'Unknown kb_script_id: {inp.kb_script_id!r}'})
        script_content = str(entry['script'])
        raw_lang = str(entry.get('language', 'applescript'))
        language = raw_lang if raw_lang in ('applescript', 'javascript') else 'applescript'

    script = _substitute_placeholders(str(script_content), language, inp.input_data, inp.arguments)
    result = _run_osascript(script, language, inp.timeout_seconds, inp.output_format_mode)
    return json.dumps(result)


def macos_scripting_tips(**kwargs: Any) -> str:
    """Search the knowledge base. Returns formatted markdown results."""
    try:
        inp = ScriptingTipsInput(**kwargs)
    except ValidationError as e:
        return _validation_error(e)

    from macos_automator_mcp.kb import search

    return search(
        search_term=inp.search_term,
        category=inp.category,
        list_categories_only=inp.list_categories,
        limit=inp.limit,
    )


def macos_screenshot(**kwargs: Any) -> str:
    """Take a screenshot and return it as a base64-encoded PNG."""
    try:
        ScreenshotInput(**kwargs)
    except ValidationError as e:
        return _validation_error(e)

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


def macos_open(**kwargs: Any) -> str:
    """Open an application, file, or URL using the macOS open command."""
    try:
        inp = OpenInput(**kwargs)
    except ValidationError as e:
        return _validation_error(e)

    try:
        target = inp.target
        is_url = target.startswith('http://') or target.startswith('https://')
        is_path = target.startswith('/') or '.' in target.split('/')[-1]
        if is_url or is_path:
            cmd = ['open', target]
        else:
            cmd = ['open', '-a', target]
        subprocess.run(cmd, check=True, timeout=15)
        return json.dumps({'success': True, 'opened': target})
    except subprocess.CalledProcessError as e:
        return json.dumps({'success': False, 'error': str(e)})
    except Exception as e:
        return json.dumps({'success': False, 'error': str(e)})


def macos_clipboard(**kwargs: Any) -> str:
    """Read from or write to the macOS clipboard."""
    try:
        inp = ClipboardInput(**kwargs)
    except ValidationError as e:
        return _validation_error(e)

    if inp.action == 'read':
        try:
            result = subprocess.run(['pbpaste'], capture_output=True, text=True, timeout=5)
            return json.dumps({'success': True, 'text': result.stdout})
        except Exception as e:
            return json.dumps({'success': False, 'error': str(e)})
    else:
        # inp.text is guaranteed non-None for 'write' by model_validator
        try:
            subprocess.run(['pbcopy'], input=inp.text, text=True, check=True, timeout=5)
            return json.dumps({'success': True, 'text': inp.text})
        except Exception as e:
            return json.dumps({'success': False, 'error': str(e)})


def macos_notify(**kwargs: Any) -> str:
    """Send a macOS system notification."""
    try:
        inp = NotifyInput(**kwargs)
    except ValidationError as e:
        return _validation_error(e)

    subtitle_part = f' subtitle "{inp.subtitle}"' if inp.subtitle else ''
    script = f'display notification "{inp.message}" with title "{inp.title}"{subtitle_part}'
    result = _run_osascript(script)
    return json.dumps(result)


def macos_system(**kwargs: Any) -> str:
    """Perform macOS system-level actions."""
    try:
        inp = SystemInput(**kwargs)
    except ValidationError as e:
        return _validation_error(e)

    action = inp.action
    value = inp.value

    if action == 'volume_get':
        result = _run_osascript('output volume of (get volume settings)')
        if result.get('success'):
            try:
                result['volume'] = int(result['output'])
            except (ValueError, KeyError):
                pass
        return json.dumps(result)

    if action == 'volume_set':
        level = max(0, min(100, int(value or '50')))
        return json.dumps(_run_osascript(f'set volume output volume {level}'))

    if action == 'brightness_set':
        level_f = max(0.0, min(1.0, float(value or '0.5')))
        script = (
            'tell application "System Events" to tell process "SystemUIServer" '
            f'to set value of slider 1 of menu bar item "Displays" of menu bar 2 to {level_f}'
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
        script = f'tell application "{value}" to quit'
        return json.dumps(_run_osascript(script))

    if action == 'say':
        try:
            subprocess.run(['say', str(value)], check=True, timeout=60)
            return json.dumps({'success': True, 'spoken': value})
        except Exception as e:
            return json.dumps({'success': False, 'error': str(e)})

    if action == 'do_not_disturb_on':
        script = 'tell application "System Events" to tell do not disturb of (get focus) to set enabled to true'
        return json.dumps(_run_osascript(script))

    if action == 'do_not_disturb_off':
        script = 'tell application "System Events" to tell do not disturb of (get focus) to set enabled to false'
        return json.dumps(_run_osascript(script))

    return json.dumps({'success': False, 'error': f'Unhandled action: {action}'})
