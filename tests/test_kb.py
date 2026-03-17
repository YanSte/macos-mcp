"""Tests for knowledge base loading and search."""

import json

from macos_automator_mcp.kb import get_script_by_id, list_categories, search


def test_load_all_scripts() -> None:
    """Knowledge base loads all 498 scripts."""
    from macos_automator_mcp.kb import _load

    scripts = _load()
    assert len(scripts) >= 490, f'Expected ~498 scripts, got {len(scripts)}'


def test_every_script_has_required_fields() -> None:
    from macos_automator_mcp.kb import _load

    required = {'id', 'title', 'category', 'language', 'script'}
    for entry in _load():
        missing = required - set(entry.keys())
        assert not missing, f'Script {entry.get("id")} missing fields: {missing}'


def test_known_script_id() -> None:
    entry = get_script_by_id('safari_get_front_tab_url')
    assert entry is not None
    assert entry['category'] == 'browsers'
    assert entry['language'] == 'applescript'
    assert 'Safari' in entry['script']


def test_unknown_script_id_returns_none() -> None:
    assert get_script_by_id('definitely_does_not_exist_xyz') is None


def test_list_categories_not_empty() -> None:
    cats = list_categories()
    assert len(cats) >= 10
    assert 'browsers' in cats
    assert 'productivity' in cats
    assert 'system' in cats


def test_search_by_term() -> None:
    result = search(search_term='send imessage', limit=5)
    assert 'messages' in result.lower() or 'message' in result.lower()


def test_search_by_category() -> None:
    result = search(category='system', limit=3)
    assert 'system' in result.lower()


def test_list_categories_only() -> None:
    result = search(list_categories_only=True)
    assert 'Categories' in result
    assert 'browsers' in result


def test_search_returns_results_for_common_term() -> None:
    """Fuzzy search should return results for a common macOS automation term."""
    result = search(search_term='safari', limit=5)
    assert '## ' in result  # at least one result header


def test_search_limit_respected() -> None:
    result = search(search_term='safari', limit=3)
    # Count "## " headers as results
    count = result.count('\n## ')
    assert count <= 3


def test_all_script_ids_unique() -> None:
    from macos_automator_mcp.kb import _load

    ids = [e['id'] for e in _load()]
    assert len(ids) == len(set(ids)), 'Duplicate script IDs found'


def test_kb_data_json_is_valid() -> None:
    from pathlib import Path

    path = Path(__file__).parent.parent / 'src' / 'macos_automator_mcp' / 'kb_data.json'
    assert path.exists()
    data = json.loads(path.read_text())
    assert isinstance(data, list)
    assert len(data) > 0
