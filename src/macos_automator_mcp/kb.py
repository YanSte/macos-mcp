"""Knowledge base loader and fuzzy search over the 498-script library."""

from __future__ import annotations

import difflib
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

_KB_PATH = Path(__file__).parent / 'kb_data.json'


@lru_cache(maxsize=1)
def _load() -> list[dict[str, Any]]:
    """Load and cache the knowledge base from disk."""
    return json.loads(_KB_PATH.read_text(encoding='utf-8'))  # type: ignore[return-value]


def get_script_by_id(script_id: str) -> dict[str, Any] | None:
    """Look up a script by its exact ID."""
    for entry in _load():
        if entry['id'] == script_id:
            return entry
    return None


def list_categories() -> list[str]:
    """Return sorted unique category slugs."""
    return sorted({str(e['category']) for e in _load()})


def _score(entry: dict[str, Any], term: str) -> float:
    """Compute a weighted similarity score for a knowledge base entry."""
    term_lower = term.lower()

    def sim(text: str) -> float:
        return difflib.SequenceMatcher(None, term_lower, text.lower()).ratio()

    title_score = sim(str(entry.get('title', '')))
    id_score = sim(str(entry.get('id', '')).replace('_', ' '))
    kw_score = max((sim(str(k)) for k in (entry.get('keywords') or [])), default=0.0)
    desc_score = sim(str(entry.get('description', '')))
    # Partial match in script content (cheaper: just substring check)
    script_score = 0.3 if term_lower in str(entry.get('script', '')).lower() else 0.0

    return title_score * 0.4 + id_score * 0.3 + kw_score * 0.2 + desc_score * 0.1 + script_score * 0.05


def search(
    search_term: str | None = None,
    category: str | None = None,
    list_categories_only: bool = False,
    limit: int = 10,
) -> str:
    """Search the knowledge base and return formatted markdown results.

    Args:
        search_term: Fuzzy search string.
        category: Filter by category slug (e.g. 'safari', 'messages').
        list_categories_only: If True, return only the category list.
        limit: Maximum number of results to return.

    Returns:
        Formatted markdown string with matching scripts.
    """
    all_scripts = _load()

    if list_categories_only:
        cats = list_categories()
        lines = ['# macOS Automation Script Categories\n']
        for c in cats:
            count = sum(1 for e in all_scripts if e['category'] == c)
            lines.append(f'- **{c}** ({count} scripts)')
        return '\n'.join(lines)

    # Filter by category
    pool = all_scripts
    if category:
        cat_lower = category.lower()
        pool = [e for e in pool if cat_lower in str(e['category']).lower()]

    if not search_term:
        # Return first N in category
        results = pool[:limit]
    else:
        # Score and sort
        scored = [(e, _score(e, search_term)) for e in pool]
        scored.sort(key=lambda x: x[1], reverse=True)
        results = [e for e, s in scored if s > 0.1][:limit]

    if not results:
        cat_part = f' in category {category}' if category else ''
        term_part = f' matching {search_term!r}' if search_term else ''
        return f'No scripts found{cat_part}{term_part}.'

    lines: list[str] = [f'# macOS Scripts ({len(results)} results)\n']
    for entry in results:
        lang = entry.get('language', 'applescript')
        has_input = entry.get('has_mcp_input', False)
        lines.append(f'## {entry["title"]}')
        lines.append(f'**ID:** `{entry["id"]}` | **Category:** {entry["category"]} | **Language:** {lang}')
        if has_input:
            lines.append('**Note:** Supports `input_data` placeholder substitution')
        if entry.get('description'):
            lines.append(f'\n{entry["description"]}\n')
        lines.append(f'```{lang}')
        lines.append(str(entry.get('script', '')))
        lines.append('```')
        lines.append(f'\nTo run: use `macos_run_script` with `kb_script_id="{entry["id"]}"`\n')

    return '\n'.join(lines)
