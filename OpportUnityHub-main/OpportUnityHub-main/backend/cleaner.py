import re
import hashlib
from datetime import datetime

# ============================================
# Data Cleaning & Deduplication
# ============================================

SCAM_KEYWORDS = [
    "pay to apply", "registration fee", "processing fee", "pay now to join",
    "send money", "wire transfer", "upfront payment", "joining fee"
]


def strip_html(text: str) -> str:
    """Remove HTML tags from a string."""
    return re.sub(r"<[^>]+>", "", text or "").strip()


def normalize_text(text: str) -> str:
    """Normalize whitespace."""
    return re.sub(r"\s+", " ", strip_html(text)).strip()


def normalize_date(date_str: str) -> str:
    """Try to parse various date formats into YYYY-MM-DD."""
    if not date_str or date_str in ("N/A", "—", ""):
        return "N/A"
    formats = [
        "%d %b %Y", "%b %d, %Y", "%Y-%m-%d", "%d/%m/%Y",
        "%d-%m-%Y", "%B %d, %Y", "%d %B %Y"
    ]
    clean = date_str.strip()
    for fmt in formats:
        try:
            return datetime.strptime(clean, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return clean  # return as-is if unparseable


def make_id(org: str, title: str) -> str:
    """Stable ID from organization + title."""
    raw = f"{org.lower().strip()}|{title.lower().strip()}"
    return "opp_" + hashlib.md5(raw.encode()).hexdigest()[:8]


def is_scam(text: str) -> bool:
    low = text.lower()
    return any(kw in low for kw in SCAM_KEYWORDS)


def deduplicate(opportunities: list[dict]) -> list[dict]:
    seen = set()
    result = []
    for opp in opportunities:
        key = make_id(opp.get("organization", ""), opp.get("title", opp.get("role", "")))
        if key not in seen:
            seen.add(key)
            result.append(opp)
    return result


def clean_opportunity(raw: dict) -> dict:
    """Clean and normalize a raw opportunity dict."""
    title = normalize_text(raw.get("title", raw.get("role", "")))
    org   = normalize_text(raw.get("organization", raw.get("company", "")))
    desc  = normalize_text(raw.get("description", ""))

    # Scam check
    if is_scam(title + " " + desc):
        return None

    return {
        **raw,
        "id":           make_id(org, title),
        "title":        title,
        "organization": org,
        "role":         title,
        "description":  desc[:300] + ("…" if len(desc) > 300 else ""),
        "deadline":     normalize_date(raw.get("deadline", "N/A")),
        "location":     normalize_text(raw.get("location", "Remote")),
        "stipend":      normalize_text(raw.get("stipend", "N/A")),
    }


def clean_all(opportunities: list[dict]) -> list[dict]:
    cleaned = [clean_opportunity(o) for o in opportunities]
    cleaned = [o for o in cleaned if o is not None]
    return deduplicate(cleaned)
