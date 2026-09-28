import pytest

from app.normalize import (
    build_pitch_text,
    find_domains,
    first_domain,
    idempotency_key,
    normalize_domain,
    normalize_name,
)


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("https://www.ABC-AI.example/about?x=1", "abc-ai.example"),
        ("abc.ai", "abc.ai"),
        ("WWW.Abc.AI", "abc.ai"),
        ("http://abc.ai:8080/path", "abc.ai"),
        ("john@abc.ai", "abc.ai"),
        ("abc.ai.", "abc.ai"),
        ("", None),
        (None, None),
        ("localhost", None),
        ("not a domain", None),
        ("-bad-.com", None),
    ],
)
def test_normalize_domain(raw, expected):
    assert normalize_domain(raw) == expected


def test_normalize_name_folds_case_accents_punctuation_and_suffixes():
    assert normalize_name("ABC AI") == "abc ai"
    assert normalize_name("  Abc-AI, Inc. ") == "abc ai"
    assert normalize_name("Müller Robotik GmbH") == "muller robotik"
    assert normalize_name("Nova Labs") == "nova labs"


def test_normalize_name_keeps_a_lone_suffix_word():
    assert normalize_name("Inc") == "inc"
    assert normalize_name(None) == ""


def test_find_domains_from_free_text():
    text = (
        "Contact john@abc.ai. Site: https://abc-ai.example/team, also www.other.example. "
        "See e.g. section 2 or v1.2 for details."
    )
    assert find_domains(text) == ["abc-ai.example", "other.example"]


def test_find_domains_ignores_email_domains_and_finds_bare_domains():
    assert find_domains("write to founder@mail.example") == []
    assert first_domain("Our site is abc.ai, thanks") == "abc.ai"
    assert first_domain("no website here") is None


def test_idempotency_key_ignores_case_and_whitespace():
    a = idempotency_key("email", "a@b.c", "Hello  World", "Body\ntext  here")
    b = idempotency_key("EMAIL", "A@B.C", "hello world", "body text here")
    assert a == b


def test_idempotency_key_changes_with_content():
    base = idempotency_key("email", "a@b.c", "s", "body")
    assert base != idempotency_key("email", "a@b.c", "s", "other body")
    assert base != idempotency_key("form", "a@b.c", "s", "body")
    assert base != idempotency_key("email", "x@b.c", "s", "body")


def test_build_pitch_text():
    assert build_pitch_text("Hi", " body ") == "Subject: Hi\n\nbody"
    assert build_pitch_text(None, " body ") == "body"
