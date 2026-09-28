import hashlib
import re
import unicodedata

# Bare domains ("abc.ai") are only recognised for these TLDs, so "e.g." or "v1.2" is not
# mistaken for a website. URLs with a scheme and "www." hosts are accepted for any TLD.
_BARE_TLDS = (
    "com|io|ai|co|net|org|app|dev|tech|xyz|de|eu|uk|fr|nl|se|no|dk|fi|es|it|pt|at|ch|be|ie|pl"
)

_URL_RE = re.compile(r"https?://[^\s<>\"'\)\]]+", re.IGNORECASE)
_WWW_RE = re.compile(r"(?<![\w.@/-])www\.[a-z0-9-]+(?:\.[a-z0-9-]+)+", re.IGNORECASE)
_BARE_RE = re.compile(
    rf"(?<![\w.@/-])[a-z0-9][a-z0-9-]*(?:\.[a-z0-9-]+)*\.(?:{_BARE_TLDS})(?![\w@-])",
    re.IGNORECASE,
)

_LEGAL_SUFFIXES = {
    "gmbh", "ag", "inc", "incorporated", "ltd", "limited", "llc", "llp", "sas", "sarl",
    "bv", "nv", "oy", "ab", "as", "aps", "plc", "corp", "corporation", "co", "sa",
    "srl", "spa", "ug", "kg", "se",
}  # fmt: skip


def normalize_domain(value: str | None) -> str | None:
    """Lowercase, strip scheme / path / port / 'www.'. Returns None if it is not a domain."""
    if not value:
        return None
    v = value.strip().lower()
    v = re.sub(r"^[a-z][a-z0-9+.-]*://", "", v)
    v = re.split(r"[/?#]", v, maxsplit=1)[0]
    v = v.rsplit("@", 1)[-1]
    v = v.split(":", 1)[0].strip(".")
    if v.startswith("www."):
        v = v[4:]
    if "." not in v or ".." in v or not re.fullmatch(r"[a-z0-9.-]+", v):
        return None
    if v.startswith("-") or v.endswith("-"):
        return None
    return v


def normalize_name(name: str | None) -> str:
    """Fold case, accents, punctuation and trailing legal suffixes ('GmbH', 'Inc')."""
    if not name:
        return ""
    decomposed = unicodedata.normalize("NFKD", name)
    folded = "".join(ch for ch in decomposed if not unicodedata.combining(ch)).casefold()
    tokens = re.sub(r"[\W_]+", " ", folded).split()
    while len(tokens) > 1 and tokens[-1] in _LEGAL_SUFFIXES:
        tokens.pop()
    return " ".join(tokens)


def find_domains(text: str) -> list[str]:
    """Domains mentioned in free text, in order of appearance, without duplicates."""
    found: list[tuple[int, str]] = []
    for regex in (_URL_RE, _WWW_RE, _BARE_RE):
        for match in regex.finditer(text or ""):
            domain = normalize_domain(match.group().rstrip(".,;:!?"))
            if domain:
                found.append((match.start(), domain))
    found.sort(key=lambda item: item[0])
    seen: list[str] = []
    for _, domain in found:
        if domain not in seen:
            seen.append(domain)
    return seen


def first_domain(text: str) -> str | None:
    domains = find_domains(text)
    return domains[0] if domains else None


def _squash(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").strip()).lower()


def idempotency_key(
    source: str, sender: str | None, subject: str | None, body: str
) -> str:
    """Stable hash of a pitch. Whitespace and case differences do not change it."""
    payload = "\x1f".join(_squash(part) for part in (source, sender, subject, body))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_pitch_text(subject: str | None, body: str) -> str:
    subject = (subject or "").strip()
    body = body.strip()
    return f"Subject: {subject}\n\n{body}" if subject else body
