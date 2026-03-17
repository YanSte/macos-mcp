"""Tests for tool implementations."""

import json
import platform

import pytest
from pydantic import ValidationError

from macos_automator_mcp import tools
from macos_automator_mcp.models import (
    ClipboardInput,
    NotifyInput,
    OpenInput,
    RunScriptInput,
    ScriptingTipsInput,
    SystemInput,
)


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
    assert result['error']  # validation errors list is non-empty


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
    assert result['error']


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


def test_macos_system_quit_app_requires_value() -> None:
    result = json.loads(tools.macos_system(action='quit_app'))
    assert result['success'] is False


def test_macos_system_say_requires_value() -> None:
    result = json.loads(tools.macos_system(action='say'))
    assert result['success'] is False


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


# ---------------------------------------------------------------------------
# Pydantic model validation tests
# ---------------------------------------------------------------------------


def test_model_run_script_requires_content_or_id() -> None:
    with pytest.raises(ValidationError):
        RunScriptInput()


def test_model_run_script_valid_with_content() -> None:
    inp = RunScriptInput(script_content='return 1')
    assert inp.script_content == 'return 1'
    assert inp.language == 'applescript'
    assert inp.timeout_seconds == 60


def test_model_run_script_timeout_too_high() -> None:
    with pytest.raises(ValidationError):
        RunScriptInput(script_content='x', timeout_seconds=9999)


def test_model_run_script_timeout_too_low() -> None:
    with pytest.raises(ValidationError):
        RunScriptInput(script_content='x', timeout_seconds=0)


def test_model_run_script_invalid_language() -> None:
    with pytest.raises(ValidationError):
        RunScriptInput(script_content='x', language='python')  # type: ignore[arg-type]


def test_model_scripting_tips_limit_range() -> None:
    with pytest.raises(ValidationError):
        ScriptingTipsInput(limit=0)
    with pytest.raises(ValidationError):
        ScriptingTipsInput(limit=200)


def test_model_scripting_tips_defaults() -> None:
    inp = ScriptingTipsInput()
    assert inp.limit == 10
    assert inp.list_categories is False


def test_model_open_requires_target() -> None:
    with pytest.raises(ValidationError):
        OpenInput()  # type: ignore[call-arg]


def test_model_clipboard_invalid_action() -> None:
    with pytest.raises(ValidationError):
        ClipboardInput(action='copy')  # type: ignore[arg-type]


def test_model_clipboard_write_requires_text() -> None:
    with pytest.raises(ValidationError):
        ClipboardInput(action='write')


def test_model_clipboard_read_no_text_needed() -> None:
    inp = ClipboardInput(action='read')
    assert inp.action == 'read'
    assert inp.text is None


def test_model_clipboard_write_valid() -> None:
    inp = ClipboardInput(action='write', text='hello')
    assert inp.text == 'hello'


def test_model_notify_requires_title_and_message() -> None:
    with pytest.raises(ValidationError):
        NotifyInput(title='hi')  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        NotifyInput(message='hi')  # type: ignore[call-arg]


def test_model_notify_subtitle_optional() -> None:
    inp = NotifyInput(title='T', message='M')
    assert inp.subtitle == ''


def test_model_system_invalid_action() -> None:
    with pytest.raises(ValidationError):
        SystemInput(action='not_valid')  # type: ignore[arg-type]


def test_model_system_say_requires_value() -> None:
    with pytest.raises(ValidationError):
        SystemInput(action='say')


def test_model_system_quit_app_requires_value() -> None:
    with pytest.raises(ValidationError):
        SystemInput(action='quit_app')


def test_model_system_volume_set_requires_value() -> None:
    with pytest.raises(ValidationError):
        SystemInput(action='volume_set')


def test_model_system_no_value_actions_valid() -> None:
    for action in ('volume_get', 'dark_mode_toggle', 'list_apps', 'lock_screen', 'do_not_disturb_on'):
        inp = SystemInput(action=action)  # type: ignore[arg-type]
        assert inp.action == action


def test_model_schema_has_descriptions() -> None:
    schema = RunScriptInput.model_json_schema()
    props = schema['properties']
    assert 'description' in props['language']
    assert 'description' in props['kb_script_id']
    assert 'description' in props['timeout_seconds']
