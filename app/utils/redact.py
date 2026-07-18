"""
Strips anything that looks like a credential out of text before it's stored
or sent anywhere. Some database drivers echo the full connection string
(including the password) back inside their own exception messages -- without
this, that password could end up sitting in plaintext in the crawl_runs
table AND in a watchdog alert email. Cheap insurance, applied at the one
place all crawler/task error messages funnel through before they're
persisted or sent.
"""
import re

# postgresql://user:password@host  or postgres+asyncpg://user:password@host etc.
_CONNECTION_STRING_PATTERN = re.compile(r"(postgres(?:ql)?(?:\+\w+)?://[^:\s]+:)([^@\s]+)(@)")

# Generic "password=something" / "pwd=something" patterns some drivers use
_KEY_VALUE_SECRET_PATTERN = re.compile(r"(?i)(password|pwd|secret|token)=([^\s&;]+)")


def redact_secrets(text: str) -> str:
    if not text:
        return text
    text = _CONNECTION_STRING_PATTERN.sub(r"\1***REDACTED***\3", text)
    text = _KEY_VALUE_SECRET_PATTERN.sub(r"\1=***REDACTED***", text)
    return text
