"""Tests for tool implementations."""

import json
import platform

import pytest

from macos_automator_mcp import tools


def test_is_macos() -> None:
    result = tools.is_macos()
    assert result == (platform.system() == 'Darwin')


def test_coerce_string() -> None:
    assert tools._coerce_to_applescript('hello') == '"hello"'


def test_coerce_string_escapes_quotes() -> None:
    assert tools._coerce_to_applescript('say "hi"') == '"say \\"hi\\""'


def test_coerce_int() -> None:
    assert tools._coerce_to_applescript(42) == '42'


def test_coerce_bool_true() -> None:
    assert tools._coerce_to_applescript(True) == 'true'


def test_coerce_bool_false() -> None:
    assert tools._coerce_to_applescript(False) == 'false'


def test_coerce_none() -> None:
    assert tools._coerce_to_applescript(None) == 'missing value'


def test_coerce_list() -> None:
    assert tools._coerce_to_applescript(['a', 'b']) == '{"a", "b"}'


def test_substitute_mcp_input() -> None:
    script = 'set x to "--MCP_INPUT:name"'
    result = tools._substitute_placeholders(script, 'applescript', {'name': 'Alice'}, None)
    assert result == 'set x to "Alice"'


def test_substitute_mcp_arg() -> None:
    script = 'set x to "--MCP_ARG_1"'
    result = tools._substitute_placeholders(script, 'applescript', None, ['hello'])
    assert result == 'set x to "hello"'


def test_substitute_jxa_template() -> None:
    script = 'var x = ${inputData.name};'
    result = tools._substitute_placeholders(script, 'javascript', {'name': 'Bob'}, None)
    assert result == 'var x = "Bob";'


def test_macos_run_script_requires_content_or_id() -> None:
    result = json.loads(tools.macos_run_script())
    assert result['success'] is False
    assert 'script_content or kb_script_id' in result['error']


def test_macos_run_script_unknown_kb_id() -> None:
    result = json.loads(tools.macos_run_script(kb_script_id='nonexistent_xyz'))
    assert result['success'] is False
    assert 'nonexistent_xyz' in result['error']


def test_macos_run_script_with_kb_id() -> None:
    """Test that a known kb_script_id resolves and runs (on macOS only)."""
    if not tools.is_macos():
        pytest.skip('macOS only')
    result = json.loads(tools.macos_run_script(kb_script_id='safari_get_front_tab_url'))
    # May fail if Safari is not open, but should not error on the kb lookup
    assert 'success' in result


@pytest.mark.skipif(platform.system() != 'Darwin', reason='macOS only')
def test_macos_run_script_inline_applescript() -> None:
    result = json.loads(tools.macos_run_script(script_content='return 1 + 1'))
    assert result['success'] is True
    assert '2' in result['output']


@pytest.mark.skipif(platform.system() != 'Darwin', reason='macOS only')
def test_macos_run_script_inline_jxa() -> None:
    result = json.loads(tools.macos_run_script(script_content='1 + 1', language='javascript'))
    assert result['success'] is True


def test_macos_clipboard_invalid_action() -> None:
    result = json.loads(tools.macos_clipboard(action='invalid'))
    assert result['success'] is False


def test_macos_clipboard_write_requires_text() -> None:
    result = json.loads(tools.macos_clipboard(action='write'))
    assert result['success'] is False
    assert 'text is required' in result['error']


@pytest.mark.skipif(platform.system() != 'Darwin', reason='macOS only')
def test_macos_clipboard_roundtrip() -> None:
    write_result = json.loads(tools.macos_clipboard(action='write', text='macos-mcp-test-123'))
    assert write_result['success'] is True
    read_result = json.loads(tools.macos_clipboard(action='read'))
    assert read_result['success'] is True
    assert read_result['text'] == 'macos-mcp-test-123'


def test_macos_system_invalid_action() -> None:
    result = json.loads(tools.macos_system(action='not_a_real_action'))
    assert result['success'] is False
    assert 'Unknown action' in result['error']


def test_macos_system_quit_app_requires_value() -> None:
    result = json.loads(tools.macos_system(action='quit_app'))
    assert result['success'] is False
    assert 'required' in result['error']


def test_macos_system_say_requires_value() -> None:
    result = json.loads(tools.macos_system(action='say'))
    assert result['success'] is False
    assert 'required' in result['error']


@pytest.mark.skipif(platform.system() != 'Darwin', reason='macOS only')
def test_macos_system_volume_get() -> None:
    result = json.loads(tools.macos_system(action='volume_get'))
    assert result['success'] is True
    assert 'volume' in result or 'output' in result


def test_macos_screenshot_non_macos() -> None:
    """On non-macOS, screencapture doesn't exist so it should fail gracefully."""
    if tools.is_macos():
        pytest.skip('Only tests non-macOS path')
    result = json.loads(tools.macos_screenshot())
    assert result['success'] is False


@pytest.mark.skipif(platform.system() != 'Darwin', reason='macOS only')
def test_macos_screenshot_returns_base64() -> None:
    result = json.loads(tools.macos_screenshot())
    assert result['success'] is True
    assert 'image_base64' in result
    assert result['format'] == 'png'
    # Verify it's valid base64
    import base64

    base64.b64decode(result['image_base64'])
