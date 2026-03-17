"""Pydantic input models for all 8 macOS MCP tools.

Each model is the single source of truth for:
- parameter names, types, defaults
- Field descriptions (shown to the LLM via JSON schema)
- validation rules (Literal enums, ge/le ranges, cross-field validators)
- tool description (model docstring → MCP tool.description)
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

OutputFormatMode = Literal[
    'auto',
    'human_readable',
    'structured_error',
    'structured_output_and_error',
    'direct',
]


class RunScriptInput(BaseModel):
    """Run an AppleScript or JXA script inline, from a file path, or from the 498-script knowledge base.
    Controls any scriptable macOS app: Safari, Messages, Mail, Finder, Calendar, Terminal, Xcode, Spotify, and more."""

    script_content: str | None = Field(
        default=None,
        description='Inline AppleScript or JXA source code to execute directly.',
    )
    script_path: str | None = Field(
        default=None,
        description=(
            'Absolute path to an AppleScript or JXA file to execute '
            '(e.g. "/Users/me/scripts/my_script.applescript"). '
            'Mutually exclusive with script_content and kb_script_id.'
        ),
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
        description=(
            'Positional arguments substituted into --MCP_ARG_1, --MCP_ARG_2, … placeholders. '
            "For script_path, passed as argv to the script's on run handler."
        ),
    )
    timeout_seconds: int = Field(
        default=60,
        ge=1,
        le=3600,
        description='Maximum seconds to wait for the script to complete. Default 60, max 3600.',
    )
    output_format_mode: OutputFormatMode = Field(
        default='auto',
        description=(
            'osascript output formatting:\n'
            '  "auto" — AppleScript gets -s h (human-readable), JXA gets no flags (direct)\n'
            '  "human_readable" — force -s h\n'
            '  "structured_error" — force -s s (structured error reporting)\n'
            '  "structured_output_and_error" — force -s ss (structured output + errors)\n'
            '  "direct" — no -s flags (recommended for JXA)'
        ),
    )
    include_executed_script_in_output: bool = Field(
        default=False,
        description='If true, append the full executed script text to the response (useful for debugging).',
    )
    include_substitution_logs: bool = Field(
        default=False,
        description='If true, include detailed logs of placeholder substitutions performed on the script.',
    )
    report_execution_time: bool = Field(
        default=False,
        description='If true, include the script execution duration in the response.',
    )

    @model_validator(mode='after')
    def requires_one_source(self) -> RunScriptInput:
        sources = [self.script_content, self.script_path, self.kb_script_id]
        if not any(sources):
            raise ValueError(
                'Provide exactly one of: script_content (inline code), '
                'script_path (file path), or kb_script_id (knowledge base ID)'
            )
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
    refresh_database: bool = Field(
        default=False,
        description='If true, force a reload of the knowledge base from disk before searching.',
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


# ---------------------------------------------------------------------------
# Accessibility query
# ---------------------------------------------------------------------------


class AccessibilityLocator(BaseModel):
    """Specifies which UI element(s) to target in the accessibility tree."""

    app: str = Field(
        description='Application to target by display name or bundle ID (e.g. "Safari", "com.apple.Safari").',
    )
    role: str = Field(
        description=(
            'Accessibility role of the target element (e.g. "AXButton", "AXStaticText", "AXTextField", "AXWebArea").'
        ),
    )
    match: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            'Key/value pairs of AX attributes to match. '
            'Use {} to match any element with the given role. '
            'Example: {"AXTitle": "Submit"} or {"AXFocused": "true"}.'
        ),
    )
    navigation_path_hint: list[str] | None = Field(
        default=None,
        description=(
            'Optional path within the app hierarchy to narrow the search. '
            'Example: ["window[1]", "toolbar[1]"]. Speeds up queries on complex UIs.'
        ),
    )


class AccessibilityQueryInput(BaseModel):
    """Inspect or interact with any UI element in any macOS application using the Accessibility framework.
    Requires the ax binary and Accessibility permission in System Settings → Privacy & Security → Accessibility.
    Use command="query" to read UI state and command="perform" to click buttons or trigger actions."""

    command: Literal['query', 'perform'] = Field(
        description=(
            '"query" — retrieve attributes and properties of matching UI elements; '
            '"perform" — execute an action on a matched element (e.g. click a button).'
        ),
    )
    locator: AccessibilityLocator = Field(
        description='Specifies the app, role, and attribute filters to find the target UI element(s).',
    )
    return_all_matches: bool = Field(
        default=False,
        description='If true, return all matching elements. If false (default), return only the first match.',
    )
    attributes_to_query: list[str] | None = Field(
        default=None,
        description=(
            'Specific AX attributes to include in the response. '
            'If omitted, common attributes are returned. '
            'Examples: ["AXRole", "AXTitle", "AXValue", "AXDescription", "AXPosition", "AXSize"].'
        ),
    )
    required_action_name: str | None = Field(
        default=None,
        description=(
            'Filter results to only elements that support this action. '
            'Example: "AXPress" to find only clickable elements.'
        ),
    )
    action_to_perform: str | None = Field(
        default=None,
        description=(
            'The accessibility action to execute when command is "perform". '
            'Common values: "AXPress" (click), "AXFocus", "AXShowMenu".'
        ),
    )
    output_format: Literal['smart', 'verbose', 'text_content'] = Field(
        default='smart',
        description=(
            'Controls verbosity of the ax binary output:\n'
            '  "smart" — readable key/value pairs, omits empty attributes (default)\n'
            '  "verbose" — all attributes including empty ones, best for debugging\n'
            '  "text_content" — compact text extraction only (AXValue, AXTitle); ignores attributes_to_query'
        ),
    )
    limit: int = Field(
        default=500,
        ge=1,
        description='Maximum number of output lines to return. Output is truncated if it exceeds this.',
    )
    max_elements: int = Field(
        default=200,
        ge=1,
        description='Maximum number of UI elements to process when return_all_matches is true.',
    )
    debug_logging: bool = Field(
        default=False,
        description='If true, include debug output from the ax binary in the response.',
    )
    report_execution_time: bool = Field(
        default=False,
        description='If true, include the query execution duration in the response.',
    )

    @model_validator(mode='after')
    def perform_requires_action(self) -> AccessibilityQueryInput:
        if self.command == 'perform' and not self.action_to_perform:
            raise ValueError('action_to_perform is required when command is "perform"')
        return self
