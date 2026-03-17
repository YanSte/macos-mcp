"""Pydantic input models for all 7 macOS MCP tools.

Each model is the single source of truth for:
- parameter names, types, defaults
- Field descriptions (shown to the LLM via JSON schema)
- validation rules (Literal enums, ge/le ranges, cross-field validators)
- tool description (model docstring → MCP tool.description)
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class RunScriptInput(BaseModel):
    """Run an AppleScript or JXA script inline, or execute a pre-built script from the 498-script knowledge base.
    Controls any scriptable macOS app: Safari, Messages, Mail, Finder, Calendar, Terminal, Xcode, Spotify, and more."""

    script_content: str | None = Field(
        default=None,
        description='Inline AppleScript or JXA source code to execute directly. Mutually exclusive with kb_script_id.',
    )
    language: Literal['applescript', 'javascript'] = Field(
        default='applescript',
        description='Script language. Use "applescript" (default) or "javascript" for JXA (JavaScript for Automation).',
    )
    kb_script_id: str | None = Field(
        default=None,
        description=(
            'ID of a pre-built script from the 498-script knowledge base '
            '(e.g. "messages_send_message", "safari_open_url", "calendar_create_event"). '
            'Use macos_scripting_tips to search and discover available IDs.'
        ),
    )
    input_data: dict[str, Any] | None = Field(
        default=None,
        description=(
            'Key/value pairs substituted into --MCP_INPUT:key placeholders in the script. '
            'Example: {"recipient": "Mom", "message": "I will be late"}'
        ),
    )
    arguments: list[Any] | None = Field(
        default=None,
        description='Positional arguments substituted into --MCP_ARG_1, --MCP_ARG_2, … placeholders in the script.',
    )
    timeout_seconds: int = Field(
        default=60,
        ge=1,
        le=3600,
        description='Maximum seconds to wait for the script to complete. Default 60, max 3600.',
    )
    output_format_mode: Literal['auto', 'human_readable', 'structured'] = Field(
        default='auto',
        description=(
            'Output formatting: '
            '"auto" returns the raw osascript output; '
            '"human_readable" adds -s h flag for human-readable output; '
            '"structured" adds -s s flag to parse output as structured data.'
        ),
    )

    @model_validator(mode='after')
    def requires_script_or_id(self) -> RunScriptInput:
        if not self.script_content and not self.kb_script_id:
            raise ValueError('Provide either script_content (inline code) or kb_script_id (knowledge base ID)')
        return self


class ScriptingTipsInput(BaseModel):
    """Fuzzy-search the 498-script AppleScript/JXA knowledge base by keyword or category, or list all categories.
    Use this to discover script IDs before calling macos_run_script with kb_script_id."""

    search_term: str | None = Field(
        default=None,
        description=(
            'Natural language or keyword search term. '
            'Examples: "send imessage", "open safari url", "battery level", "create calendar event".'
        ),
    )
    category: str | None = Field(
        default=None,
        description=(
            'Filter results to a specific category slug. '
            'Available: "browsers", "productivity", "developer", "system", "terminal", '
            '"editors", "creative", "files", "advanced", "as_core", "jxa_core", "network".'
        ),
    )
    list_categories: bool = Field(
        default=False,
        description=(
            'If true, return only the list of available categories with their script counts. '
            'Ignores search_term and category.'
        ),
    )
    limit: int = Field(
        default=10,
        ge=1,
        le=100,
        description='Maximum number of results to return. Default 10, max 100.',
    )


class ScreenshotInput(BaseModel):
    """Take a full-screen screenshot and return it as a base64-encoded PNG image.
    Requires Screen Recording permission granted to the parent application in System Settings → Privacy & Security."""


class OpenInput(BaseModel):
    """Open a macOS application, file, or URL using the system open command."""

    target: str = Field(
        description=(
            'What to open. Examples: '
            'app name — "Safari", "Calculator", "VS Code"; '
            'absolute file path — "/Users/me/Documents/report.pdf"; '
            'URL — "https://github.com".'
        ),
    )


class ClipboardInput(BaseModel):
    """Read from or write to the macOS system clipboard (pasteboard)."""

    action: Literal['read', 'write'] = Field(
        description=(
            '"read" returns the current clipboard text content; "write" replaces the clipboard with the provided text.'
        ),
    )
    text: str | None = Field(
        default=None,
        description='Text to write to the clipboard. Required when action is "write".',
    )

    @model_validator(mode='after')
    def write_requires_text(self) -> ClipboardInput:
        if self.action == 'write' and not self.text:
            raise ValueError('text is required when action is "write"')
        return self


class NotifyInput(BaseModel):
    """Send a macOS system notification that appears in Notification Center and as a banner."""

    title: str = Field(description='Bold heading of the notification banner.')
    message: str = Field(description='Body text shown below the title.')
    subtitle: str = Field(
        default='',
        description='Optional subtitle line shown between the title and message.',
    )


SystemAction = Literal[
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
]


class SystemInput(BaseModel):
    """Control macOS system settings and perform system-level actions: volume, brightness, dark mode,
    display, running apps, text-to-speech, and focus mode."""

    action: SystemAction = Field(
        description=(
            'System action to perform:\n'
            '  "volume_get" — return current output volume (0–100)\n'
            '  "volume_set" — set output volume; value="0" to "100"\n'
            '  "brightness_set" — set display brightness; value="0.0" to "1.0"\n'
            '  "dark_mode_toggle" — toggle between dark and light appearance\n'
            '  "sleep_display" — immediately turn off the display\n'
            '  "lock_screen" — lock the session (requires password to unlock)\n'
            '  "list_apps" — return names of all visible running applications\n'
            '  "quit_app" — gracefully quit an app; value=app name (e.g. "Safari")\n'
            '  "say" — speak text aloud via TTS; value=text to speak\n'
            '  "do_not_disturb_on" — enable Do Not Disturb / Focus mode\n'
            '  "do_not_disturb_off" — disable Do Not Disturb / Focus mode'
        ),
    )
    value: str | None = Field(
        default=None,
        description=(
            'Action-specific parameter. '
            'Required for: volume_set (0–100), brightness_set (0.0–1.0), quit_app (app name), say (text). '
            'Not used for: volume_get, dark_mode_toggle, sleep_display, lock_screen, list_apps, do_not_disturb_on/off.'
        ),
    )

    @model_validator(mode='after')
    def value_required_for_actions(self) -> SystemInput:
        needs_value = ('volume_set', 'brightness_set', 'quit_app', 'say')
        if self.action in needs_value and not self.value:
            raise ValueError(f'value is required for action="{self.action}"')
        return self
