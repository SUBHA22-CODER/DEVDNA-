"""Secret detection and redaction.

Everything that leaves the analyzer (UI evidence snippets, reports, AI prompts)
passes through `redact()` first. Values are replaced, never stored.
"""
from __future__ import annotations

import re

REDACTED = "***REDACTED***"

_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?(-----END [A-Z ]*PRIVATE KEY-----|$)")),
    ("aws_access_key", re.compile(r"\b(AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("google_api_key", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b")),
    ("github_token", re.compile(r"\b(ghp|gho|ghu|ghs|ghr|github_pat)_[A-Za-z0-9_]{20,}\b")),
    ("slack_token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b")),
    ("openai_style_key", re.compile(r"\bsk-[A-Za-z0-9_\-]{20,}\b")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\b")),
    ("bearer_token", re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._\-]{16,}")),
]

# key = "value" style assignments where the key name looks sensitive
_ASSIGNMENT = re.compile(
    r"""(?ix)
    (?P<key>[A-Za-z0-9_]*(?:password|passwd|pwd|secret|token|api[_-]?key|apikey|access[_-]?key|private[_-]?key|client[_-]?secret)[A-Za-z0-9_]*)
    (?P<sep>\s*[:=]\s*)
    (?P<q>['"])(?P<val>[^'"\n]{4,})(?P=q)
    """
)
# scheme://user:password@host
_URL_CREDS = re.compile(r"(?P<pre>[a-z][a-z0-9+.\-]*://[^:/\s@]+:)(?P<pw>[^@\s/]+)(?P<at>@)", re.I)


def redact(text: str) -> tuple[str, int]:
    """Return (redacted_text, number_of_redactions)."""
    if not text:
        return text, 0
    count = 0

    def _sub_all(m):
        nonlocal count
        count += 1
        return REDACTED

    for _, pat in _PATTERNS:
        text = pat.sub(_sub_all, text)

    def _sub_assign(m):
        nonlocal count
        val = m.group("val")
        if val == REDACTED or val.startswith("${") or val.lower() in {"changeme", "your-key-here", "placeholder"}:
            return m.group(0)
        count += 1
        return f"{m.group('key')}{m.group('sep')}{m.group('q')}{REDACTED}{m.group('q')}"

    text = _ASSIGNMENT.sub(_sub_assign, text)

    def _sub_url(m):
        nonlocal count
        count += 1
        return f"{m.group('pre')}{REDACTED}{m.group('at')}"

    text = _URL_CREDS.sub(_sub_url, text)
    return text, count


def find_secrets(text: str) -> list[dict]:
    """Locate likely secrets by line (values are not returned)."""
    hits = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        _, n = redact(line)
        if n:
            hits.append({"line": lineno, "count": n})
    return hits
