"""Tests for MCP server tool registration."""

from macos_automator_mcp.server import _TOOLS


def test_all_eight_tools_registered() -> None:
    names = {t.name for t in _TOOLS}
    expected = {
        'macos_run_script',
        'macos_scripting_tips',
        'macos_screenshot',
        'macos_open',
        'macos_clipboard',
        'macos_notify',
        'macos_system',
        'macos_accessibility_query',
    }
    assert names == expected


def test_all_tools_have_descriptions() -> None:
    for t in _TOOLS:
        assert t.description, f'{t.name} has no description'
        assert len(t.description) > 20, f'{t.name} description too short'


def test_all_tools_have_input_schema() -> None:
    for t in _TOOLS:
        assert t.inputSchema is not None, f'{t.name} has no inputSchema'
        assert t.inputSchema.get('type') == 'object', f'{t.name} inputSchema is not object type'


def test_macos_run_script_schema() -> None:
    tool = next(t for t in _TOOLS if t.name == 'macos_run_script')
    props = tool.inputSchema['properties']
    assert 'script_content' in props
    assert 'language' in props
    assert 'kb_script_id' in props
    assert 'input_data' in props
    assert 'arguments' in props
    assert 'timeout_seconds' in props
    assert 'output_format_mode' in props


def test_macos_system_schema_has_all_actions() -> None:
    tool = next(t for t in _TOOLS if t.name == 'macos_system')
    action_prop = tool.inputSchema['properties']['action']
    assert 'enum' in action_prop
    actions = set(action_prop['enum'])
    assert 'volume_get' in actions
    assert 'volume_set' in actions
    assert 'lock_screen' in actions
    assert 'say' in actions
