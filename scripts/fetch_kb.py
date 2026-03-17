"""Build kb_data.json from locally cloned steipete/macos-automator-mcp knowledge_base."""

import json
import re
from pathlib import Path

KB_DIR = Path('/tmp/macos-automator-mcp-src/knowledge_base')
OUTPUT = Path(__file__).parent.parent / 'src' / 'macos_automator_mcp' / 'kb_data.json'


def parse_frontmatter(content: str) -> tuple[dict[str, object], str]:
    """Parse YAML frontmatter. Returns (meta, body)."""
    if not content.startswith('---'):
        return {}, content
    end = content.find('\n---', 3)
    if end == -1:
        return {}, content
    fm_text = content[3:end].strip()
    body = content[end + 4 :].strip()
    meta: dict[str, object] = {}
    current_key = ''
    list_items: list[str] = []
    in_list = False

    for line in fm_text.splitlines():
        stripped = line.strip()
        # List item continuation
        if in_list and stripped.startswith('- '):
            list_items.append(stripped[2:].strip().strip('"\''))
            continue
        if in_list and stripped.startswith('-'):
            list_items.append(stripped[1:].strip().strip('"\''))
            continue
        # Flush list
        if in_list and ':' in stripped:
            meta[current_key] = list_items
            in_list = False
            list_items = []

        if ':' not in stripped:
            continue
        key, _, val = stripped.partition(':')
        key = key.strip()
        val = val.strip()
        if not key:
            continue
        if val.startswith('[') and val.endswith(']'):
            items = [x.strip().strip('"\'') for x in val[1:-1].split(',') if x.strip()]
            meta[key] = items
        elif val == '' or val == '[]':
            # Might be a multiline list
            current_key = key
            in_list = True
            list_items = []
        elif val:
            meta[key] = val.strip('"\'')

    if in_list and list_items:
        meta[current_key] = list_items

    return meta, body


def extract_script(body: str) -> str:
    """Extract fenced code block content."""
    m = re.search(r'```(?:applescript|javascript|bash|shell|js|jxa|as)?\s*\n(.*?)```', body, re.DOTALL)
    if m:
        return m.group(1).rstrip()
    m = re.search(r'```\s*\n(.*?)```', body, re.DOTALL)
    if m:
        return m.group(1).rstrip()
    return ''


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    # Collect all .md files in category order
    all_files: list[tuple[str, Path]] = []
    cat_dirs = sorted(d for d in KB_DIR.iterdir() if d.is_dir() and not d.name.startswith('_'))

    for cat_dir in cat_dirs:
        cat_slug = re.sub(r'^\d+_', '', cat_dir.name)
        for md_file in sorted(cat_dir.rglob('*.md')):
            if md_file.name == '_category_info.md':
                continue
            all_files.append((cat_slug, md_file))

    print(f'Found {len(all_files)} .md files')

    scripts: list[dict[str, object]] = []
    seen_ids: set[str] = set()

    for cat_slug, md_file in all_files:
        stem = md_file.stem
        content = md_file.read_text(encoding='utf-8')
        meta, body = parse_frontmatter(content)
        script_text = extract_script(body)

        script_id = str(meta.get('id', stem)) or stem
        original_id = script_id
        if script_id in seen_ids:
            suffix = 2
            while f'{original_id}_{suffix}' in seen_ids:
                suffix += 1
            script_id = f'{original_id}_{suffix}'
        seen_ids.add(script_id)

        language = str(meta.get('language', 'applescript')).lower()
        if language not in ('applescript', 'javascript'):
            language = 'applescript'

        raw_kw = meta.get('keywords', [])
        if isinstance(raw_kw, list):
            keywords = [str(k) for k in raw_kw]
        elif isinstance(raw_kw, str):
            keywords = [k.strip() for k in raw_kw.split(',') if k.strip()]
        else:
            keywords = []

        entry: dict[str, object] = {
            'id': script_id,
            'title': str(meta.get('title', stem.replace('_', ' ').title())),
            'category': cat_slug,
            'language': language,
            'description': str(meta.get('description', '')),
            'keywords': keywords,
            'script': script_text,
            'has_mcp_input': '--MCP_INPUT:' in script_text or '--MCP_ARG_' in script_text,
        }
        scripts.append(entry)

    print(f'Built {len(scripts)} script entries')

    # Stats
    cats: dict[str, int] = {}
    for s in scripts:
        c = str(s['category'])
        cats[c] = cats.get(c, 0) + 1
    for c, n in sorted(cats.items()):
        print(f'  {c}: {n}')

    OUTPUT.write_text(json.dumps(scripts, indent=2, ensure_ascii=False))
    size_kb = OUTPUT.stat().st_size / 1024
    print(f'\nWritten {len(scripts)} scripts ({size_kb:.0f} KB) → {OUTPUT}')


if __name__ == '__main__':
    main()
