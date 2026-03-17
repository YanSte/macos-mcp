"""macOS tool implementations — osascript, screencapture, pbpaste/pbcopy, open, etc."""

from __future__ import annotations

import base64
import json
import platform
import re
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from pydantic import ValidationError

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
) -> tuple[str, list[str]]:
    """Replace --MCP_INPUT:key and --MCP_ARG_N placeholders in script.

    Returns (substituted_script, substitution_logs).
    """
    is_js = language == 'javascript'
    logs: list[str] = []

    def coerce(v: Any) -> str:  # noqa: ANN401
        return _coerce_to_jxa(v) if is_js else _coerce_to_applescript(v)

    if input_data:
        for key, val in input_data.items():
            literal = coerce(val)
            patterns = [
                f'"--MCP_INPUT:{key}"',
                f"'--MCP_INPUT:{key}'",
                rf'${{inputData\.{re.escape(key)}}}',
                rf'\(--MCP_INPUT:{re.escape(key)}\)',
                rf'=--MCP_INPUT:{re.escape(key)}',
            ]
            did_sub = False
            new_script = script.replace(f'"--MCP_INPUT:{key}"', literal)
            if new_script != script:
                did_sub = True
            script = new_script
            new_script = script.replace(f"'--MCP_INPUT:{key}'", literal)
            if new_script != script:
                did_sub = True
            script = new_script
            new_script = re.sub(rf'\$\{{inputData\.{re.escape(key)}\}}', literal, script)
            if new_script != script:
                did_sub = True
            script = new_script
            new_script = re.sub(rf'\(--MCP_INPUT:{re.escape(key)}\)', f'({literal})', script)
            if new_script != script:
                did_sub = True
            script = new_script
            new_script = re.sub(rf'=--MCP_INPUT:{re.escape(key)}', f'={literal}', script)
            if new_script != script:
                did_sub = True
            script = new_script
            _ = patterns  # referenced above; kept to satisfy linters
            if did_sub:
                logs.append(f'Substituted input_data[{key!r}] → {literal}')
            else:
                logs.append(f'No placeholder found for input_data[{key!r}]')

    if arguments:
        for idx, val in enumerate(arguments, 1):
            literal = coerce(val)
            did_sub = False
            new_script = script.replace(f'"--MCP_ARG_{idx}"', literal)
            if new_script != script:
                did_sub = True
            script = new_script
            new_script = script.replace(f"'--MCP_ARG_{idx}'", literal)
            if new_script != script:
                did_sub = True
            script = new_script
            new_script = re.sub(rf'\$\{{arguments\[{idx - 1}\]\}}', literal, script)
            if new_script != script:
                did_sub = True
            script = new_script
            if did_sub:
                logs.append(f'Substituted arguments[{idx - 1}] → {literal}')
            else:
                logs.append(f'No placeholder found for arguments[{idx - 1}]')

    return script, logs


def _run_osascript(
    script: str,
    language: str = 'applescript',
    timeout: int = 60,
    output_format: str = 'auto',
) -> dict[str, Any]:
    """Execute script via osascript. Returns {success, output, error}."""
    lang_flag = 'JavaScript' if language == 'javascript' else 'AppleScript'
    cmd = ['osascript', '-l', lang_flag]

    # Determine -s flags
    if output_format == 'human_readable':
        cmd += ['-s', 'h']
    elif output_format == 'structured_error':
        cmd += ['-s', 's']
    elif output_format == 'structured_output_and_error':
        cmd += ['-s', 'ss']
    elif output_format == 'auto':
        # AppleScript gets human-readable by default; JXA gets direct (no flags)
        if language != 'javascript':
            cmd += ['-s', 'h']
    # 'direct' and JXA auto → no flags

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


def _run_osascript_file(
    script_path: str,
    language: str = 'applescript',
    arguments: list[Any] | None = None,
    timeout: int = 60,
) -> dict[str, Any]:
    """Execute a script file via osascript. Returns {success, output, error}."""
    lang_flag = 'JavaScript' if language == 'javascript' else 'AppleScript'
    cmd = ['osascript', '-l', lang_flag, script_path]
    if arguments:
        cmd += [str(a) for a in arguments]
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
    result: dict[str, Any]

    # --- script_path branch: execute file directly ---
    if inp.script_path:
        path = Path(inp.script_path)
        if not path.exists():
            return json.dumps({'success': False, 'error': f'script_path not found: {inp.script_path!r}'})
        # Infer language from extension if needed
        if path.suffix.lower() in ('.js', '.jxa'):
            language = 'javascript'
        t0 = time.monotonic() if inp.report_execution_time else 0.0
        result = _run_osascript_file(inp.script_path, language, inp.arguments, inp.timeout_seconds)
        if inp.report_execution_time:
            result['execution_time_seconds'] = round(time.monotonic() - t0, 3)
        return json.dumps(result)

    # --- kb_script_id branch ---
    if inp.kb_script_id:
        from macos_automator_mcp.kb import get_script_by_id

        entry = get_script_by_id(inp.kb_script_id)
        if not entry:
            return json.dumps({'success': False, 'error': f'Unknown kb_script_id: {inp.kb_script_id!r}'})
        script_content = str(entry['script'])
        raw_lang = str(entry.get('language', 'applescript'))
        language = raw_lang if raw_lang in ('applescript', 'javascript') else 'applescript'

    # --- inline script_content branch ---
    final_script, sub_logs = _substitute_placeholders(str(script_content), language, inp.input_data, inp.arguments)

    t0 = time.monotonic() if inp.report_execution_time else 0.0
    result = _run_osascript(final_script, language, inp.timeout_seconds, inp.output_format_mode)
    if inp.report_execution_time:
        result['execution_time_seconds'] = round(time.monotonic() - t0, 3)

    if inp.include_executed_script_in_output:
        result['executed_script'] = final_script

    if inp.include_substitution_logs and sub_logs:
        result['substitution_logs'] = sub_logs

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
        refresh_first=inp.refresh_database,
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


def macos_accessibility_query(**kwargs: Any) -> str:
    """Inspect or interact with macOS UI elements via the Accessibility framework."""
    try:
        inp = AccessibilityQueryInput(**kwargs)
    except ValidationError as e:
        return _validation_error(e)

    # Build ax binary command
    # ax <app> <role> [--match key=value ...] [--action <action>] [--all] [--format smart|verbose|text]
    cmd = ['ax', inp.locator.app, inp.locator.role]

    # Match attributes
    for k, v in inp.locator.match.items():
        cmd += ['--match', f'{k}={v}']

    # Navigation path hint
    if inp.locator.navigation_path_hint:
        for segment in inp.locator.navigation_path_hint:
            cmd += ['--path', segment]

    # Output format
    cmd += ['--format', inp.output_format]

    # Return all matches
    if inp.return_all_matches:
        cmd += ['--all']

    # Max elements
    cmd += ['--max-elements', str(inp.max_elements)]

    # Attributes to query
    if inp.attributes_to_query:
        for attr in inp.attributes_to_query:
            cmd += ['--attr', attr]

    # Required action filter
    if inp.required_action_name:
        cmd += ['--required-action', inp.required_action_name]

    # Debug logging
    if inp.debug_logging:
        cmd += ['--debug']

    # Perform action
    if inp.command == 'perform' and inp.action_to_perform:
        cmd += ['--action', inp.action_to_perform]

    t0 = time.monotonic() if inp.report_execution_time else 0.0

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        output = result.stdout
        # Truncate to limit lines
        lines = output.splitlines()
        truncated = len(lines) > inp.limit
        if truncated:
            lines = lines[: inp.limit]
        response: dict[str, Any] = {
            'success': result.returncode == 0,
            'output': '\n'.join(lines),
        }
        if truncated:
            response['truncated'] = True
            response['total_lines'] = len(output.splitlines())
        if result.returncode != 0:
            response['error'] = result.stderr.strip() or f'ax exited with code {result.returncode}'
        if inp.debug_logging and result.stderr:
            response['debug'] = result.stderr.strip()
        if inp.report_execution_time:
            response['execution_time_seconds'] = round(time.monotonic() - t0, 3)
        return json.dumps(response)
    except FileNotFoundError:
        return json.dumps(
            {
                'success': False,
                'error': (
                    'ax binary not found. Install it or grant Accessibility permission. '
                    'See: System Settings → Privacy & Security → Accessibility'
                ),
            }
        )
    except subprocess.TimeoutExpired:
        return json.dumps({'success': False, 'error': 'Accessibility query timed out after 30s'})
    except Exception as e:
        return json.dumps({'success': False, 'error': str(e)})
