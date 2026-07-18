"""
Tests the secret-redaction utility that stands between a raw exception
message and anywhere that message gets stored or emailed. This one matters
more than most tests here -- a bug in this specific function means a real
credential leak, not just a wrong answer.
"""
from app.utils.redact import redact_secrets


def test_redacts_connection_string_password():
    text = "connection failed: postgresql+asyncpg://postgres.abc123:A%23secret%401.@aws-0-ap.pooler.supabase.com:5432/postgres"
    result = redact_secrets(text)
    assert "A%23secret%401" not in result
    assert "REDACTED" in result
    # Host and username should survive -- only the password is sensitive.
    assert "aws-0-ap.pooler.supabase.com" in result
    assert "postgres.abc123" in result


def test_redacts_generic_password_key_value_pairs():
    text = "auth failed, password=hunter2secret token=abc123xyz"
    result = redact_secrets(text)
    assert "hunter2secret" not in result
    assert "abc123xyz" not in result


def test_leaves_ordinary_text_unchanged():
    text = "GeM search timed out after 30000ms waiting for selector"
    assert redact_secrets(text) == text


def test_handles_empty_and_none_input_without_raising():
    assert redact_secrets("") == ""
    assert redact_secrets(None) is None
