from __future__ import annotations

import glob
import json
import os
import re
import shutil
import subprocess
import tempfile
from typing import Any, Dict

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False


DEFAULT_MODEL = "openai/gpt-4o-mini"
SYSTEM_PROMPT = "You are a professional outreach assistant. Return only a JSON object."


def _is_placeholder_key(key: str | None) -> bool:
    value = (key or "").strip()
    return not value or value.lower().startswith(("your", "sk-xxx", "changeme")) or value.endswith("_here")


def find_claude_binary() -> str | None:
    """The Claude Code CLI: $REACHAI_CLAUDE_BIN, `claude` on PATH, or the VS Code extension's copy."""
    configured = os.getenv("REACHAI_CLAUDE_BIN", "").strip()
    if configured:
        return configured if os.path.exists(configured) else None
    on_path = shutil.which("claude")
    if on_path:
        return on_path
    bundled = sorted(glob.glob(os.path.expanduser(
        "~/.vscode/extensions/anthropic.claude-code-*/resources/native-binary/claude"
    )))
    return bundled[-1] if bundled else None


def _parse_json_object(content: str) -> Dict[str, Any]:
    # Models often wrap JSON in a ```json fence; take the outermost object.
    match = re.search(r"\{.*\}", content or "", re.DOTALL)
    try:
        parsed = json.loads(match.group(0) if match else content)
    except (ValueError, TypeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


class LLMClient:
    """Draft-writing LLM. Backends:

    - ``claude-code`` (default): headless Claude Code (`claude -p`) on the user's own
      login, with every tool disabled so untrusted input can only produce text.
    - ``openrouter``: OpenAI-compatible API (needs OPENROUTER_API_KEY).
    - ``none``: no LLM; the deterministic template draft is used.

    ``generate`` returns an empty dict on any failure; callers must keep the
    deterministic draft rather than send placeholder text.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        backend: str | None = None,
    ):
        self.backend = (backend or os.getenv("REACHAI_LLM_BACKEND", "claude-code")).strip().lower()
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
        self.base_url = base_url or os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
        self.client: Any = None
        self.last_error: str | None = None

        if self.backend == "claude-code":
            self.model = os.getenv("REACHAI_CLAUDE_MODEL", "sonnet")
            self.client = find_claude_binary()
        elif self.backend == "openrouter":
            self.model = model or os.getenv("LLM_MODEL") or DEFAULT_MODEL
            if OPENAI_AVAILABLE and not _is_placeholder_key(self.api_key):
                self.client = OpenAI(api_key=self.api_key, base_url=self.base_url, timeout=30.0, max_retries=1)
        else:
            self.model = ""

    def describe(self) -> str:
        if not self.client:
            return f"{self.backend} (not available)"
        return f"{self.backend}:{self.model}"

    def generate(self, prompt: str) -> Dict[str, Any]:
        """Generate a JSON response, or ``{}`` if unavailable."""
        if not self.client:
            self.last_error = f"LLM backend '{self.backend}' is not available"
            return {}
        if self.backend == "claude-code":
            content = self._generate_claude_code(prompt)
        else:
            content = self._generate_openrouter(prompt)
        if content is None:
            return {}
        parsed = _parse_json_object(content)
        self.last_error = None if parsed else "LLM response was not a JSON object"
        return parsed

    def _generate_claude_code(self, prompt: str) -> str | None:
        command = [
            str(self.client), "-p",
            "--model", self.model,
            "--tools", "",
            "--strict-mcp-config",
            "--no-session-persistence",
            "--output-format", "json",
            "--system-prompt", SYSTEM_PROMPT,
        ]
        try:
            with tempfile.TemporaryDirectory(prefix="reachai-llm-") as workdir:
                completed = subprocess.run(
                    command, input=prompt, capture_output=True, text=True, timeout=180, cwd=workdir,
                )
        except (OSError, subprocess.TimeoutExpired) as exc:
            self.last_error = f"Claude Code failed: {exc}"
            return None
        try:
            envelope = json.loads(completed.stdout)
        except ValueError:
            self.last_error = f"Claude Code exited {completed.returncode}: {(completed.stderr or completed.stdout)[:200]}"
            return None
        if envelope.get("is_error") or completed.returncode != 0:
            self.last_error = f"Claude Code error: {str(envelope.get('result'))[:200]}"
            return None
        return str(envelope.get("result") or "")

    def _generate_openrouter(self, prompt: str) -> str | None:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=500,
            )
        except Exception as exc:
            self.last_error = str(exc)
            return None
        return response.choices[0].message.content or ""
