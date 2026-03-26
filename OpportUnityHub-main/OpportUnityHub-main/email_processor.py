

from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime
from typing import Optional

# ─── HuggingFace ──────────────────────────────────────────────────────────────
from transformers import pipeline

# ─── spaCy ────────────────────────────────────────────────────────────────────
import spacy

# ─── Your existing Firebase module (no changes needed there) ──────────────────
from firebase_config import get_db   # uses the fixed get_db() from our last session

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 1 ── MODEL SETUP  (lazy-loaded singletons)
# ══════════════════════════════════════════════════════════════════════════════

_classifier = None   # HuggingFace zero-shot pipeline
_nlp        = None   # spaCy pipeline


def _load_classifier():
    """
    Load facebook/bart-large-mnli once and reuse it for every request.
    First call downloads ~1.6 GB; all subsequent calls return instantly.
    """
    global _classifier
    if _classifier is None:
        logger.info("Loading facebook/bart-large-mnli (first run may take ~30 s) ...")
        _classifier = pipeline(
            task="zero-shot-classification",
            model="facebook/bart-large-mnli",
            device=-1,   # CPU.  Change to device=0 if you have a GPU.
        )
        logger.info("Classifier loaded and ready.")
    return _classifier


def _load_spacy():
    """Load spaCy en_core_web_sm for NER (org names, dates)."""
    global _nlp
    if _nlp is None:
        try:
            _nlp = spacy.load("en_core_web_sm")
        except OSError:
            logger.warning(
                "spaCy model not found. "
                "Run:  python -m spacy download en_core_web_sm"
            )
            _nlp = None   # will fall back to regex-only extraction
    return _nlp


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 2 ── CLASSIFICATION LABELS
# ══════════════════════════════════════════════════════════════════════════════

# Exactly what we pass to the zero-shot model
CANDIDATE_LABELS = [
    "internship opportunity",
    "hackathon opportunity",
    "job opportunity",
    "spam",
    "promotion",
]

# Only emails matching these labels move to extraction
RELEVANT_LABELS = {"internship opportunity", "hackathon opportunity"}

# Emails below this confidence score are discarded even if label is relevant
CONFIDENCE_THRESHOLD = 0.45


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 3 ── EXTRACTION HELPERS
# ══════════════════════════════════════════════════════════════════════════════

# ── 3a. Links ─────────────────────────────────────────────────────────────────

_URL_RE = re.compile(r"https?://[^\s<>\"')]+")

def _extract_links(text: str) -> list[str]:
    """Return all URLs found in the text, longest first."""
    return sorted(set(_URL_RE.findall(text)), key=len, reverse=True)


# ── 3b. Dates ─────────────────────────────────────────────────────────────────

# Named months (full and abbreviated)
_MONTH_NAMES = (
    r"(?:January|February|March|April|May|June|July|August|"
    r"September|October|November|December|"
    r"Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
)

_DATE_PATTERNS: list[re.Pattern] = [
    # 2025-04-10
    re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b"),
    # April 10, 2025  |  Apr 10 2025
    re.compile(rf"\b({_MONTH_NAMES})\s+(\d{{1,2}}),?\s+(\d{{4}})\b", re.IGNORECASE),
    # 10 April 2025  |  10 Apr 2025
    re.compile(rf"\b(\d{{1,2}})\s+({_MONTH_NAMES})\s+(\d{{4}})\b", re.IGNORECASE),
    # 10/04/2025  |  04-10-2025
    re.compile(r"\b(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})\b"),
]

_MONTH_MAP: dict[str, int] = {
    "january":1, "february":2, "march":3,    "april":4,
    "may":5,     "june":6,     "july":7,     "august":8,
    "september":9,"october":10,"november":11,"december":12,
    "jan":1, "feb":2, "mar":3, "apr":4,
    "jun":6, "jul":7, "aug":8, "sep":9, "oct":10, "nov":11, "dec":12,
}

def _parse_date_groups(groups: tuple) -> Optional[str]:
    """Convert regex capture groups → ISO string YYYY-MM-DD, or None."""
    try:
        cleaned = [str(g).strip(" .,").lower() for g in groups if g]

        # Pattern: YYYY, MM, DD  (from ISO pattern)
        if len(cleaned) == 3 and len(cleaned[0]) == 4 and cleaned[0].isdigit():
            return f"{cleaned[0]}-{int(cleaned[1]):02d}-{int(cleaned[2]):02d}"

        # Pattern: MonthName, DD, YYYY  or  DD, MonthName, YYYY
        if len(cleaned) == 3:
            year_part  = next((g for g in cleaned if g.isdigit() and int(g) > 1000), None)
            month_part = next((g for g in cleaned if g in _MONTH_MAP), None)
            day_part   = next((g for g in cleaned if g.isdigit() and int(g) <= 31 and g != year_part), None)
            if year_part and month_part and day_part:
                return (
                    f"{year_part}-"
                    f"{_MONTH_MAP[month_part]:02d}-"
                    f"{int(day_part):02d}"
                )

        # Pattern: DD/MM/YYYY  (assume day-first for Indian dates)
        if len(cleaned) == 3 and all(g.isdigit() for g in cleaned):
            d, m, y = cleaned
            if int(m) <= 12:
                return f"{y}-{int(m):02d}-{int(d):02d}"

    except (ValueError, KeyError, IndexError):
        pass
    return None


def _extract_deadline(text: str) -> Optional[str]:
    """
    Find the most relevant date in the text.
    Priority: date near a deadline/apply keyword → first date in full text.
    """
    # First look for a date near a deadline signal
    deadline_window = re.search(
        r"(?:deadline|apply by|apply before|last date|closes?|due date|register by)"
        r"[^\n]{0,80}",
        text,
        re.IGNORECASE,
    )
    search_targets = [deadline_window.group(0), text] if deadline_window else [text]

    for search_text in search_targets:
        for pattern in _DATE_PATTERNS:
            m = pattern.search(search_text)
            if m:
                iso = _parse_date_groups(m.groups())
                if iso:
                    return iso

    return None


# ── 3c. Organization names ────────────────────────────────────────────────────

# Regex fallback: "at Google", "by Microsoft India", "from Razorpay"
_ORG_CONTEXT_RE = re.compile(
    r"\b(?:at|with|by|from|hosted by|organized by|presented by)\s+"
    r"([A-Z][A-Za-z0-9&'.\-](?:[A-Za-z0-9&'.\-\s]{0,38}[A-Za-z0-9])?)(?=[,.\n!]|\s{2}|$)",
    re.MULTILINE,
)
_SENDER_DOMAIN_RE  = re.compile(r"@([\w\-]+)\.")
_GENERIC_DOMAINS   = {"gmail", "yahoo", "hotmail", "outlook", "noreply", "no-reply",
                      "mail", "info", "support", "contact", "internshala", "devpost",
                      "linkedin", "unstop"}


def _extract_organization(subject: str, body: str, sender: str) -> str:
    """
    Try in order:
      1. spaCy ORG entity in subject line
      2. spaCy ORG entity in first 600 chars of body
      3. Regex context clue ("at Google", "by Razorpay")
      4. Sender domain (skipping generic ones)
      5. "Unknown Organization"
    """
    nlp = _load_spacy()

    if nlp is not None:
        for chunk in [subject, body[:600]]:
            doc  = nlp(chunk)
            orgs = [ent.text.strip() for ent in doc.ents if ent.label_ == "ORG"]
            if orgs:
                return orgs[0]

    # Regex context clue
    full = f"{subject}\n{body}"
    m = _ORG_CONTEXT_RE.search(full)
    if m:
        return m.group(1).strip()

    # Sender domain
    dm = _SENDER_DOMAIN_RE.search(sender or "")
    if dm:
        domain = dm.group(1).lower()
        if domain not in _GENERIC_DOMAINS:
            return domain.title()

    return "Unknown Organization"


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 4 ── CORE PUBLIC FUNCTION
# ══════════════════════════════════════════════════════════════════════════════

def process_opportunity_email(
    email_subject: str,
    email_body:    str,
    sender:        str = "",
    user_id:       str = "",
) -> Optional[dict]:
    """
    Classify one email and, if it is an opportunity, extract structured data
    and save it to Firestore.

    Parameters
    ----------
    email_subject : str   Subject line of the incoming email
    email_body    : str   Plain-text body of the email
    sender        : str   (optional) From address — used as org fallback
    user_id       : str   (optional) ID of the user who triggered the sync

    Returns
    -------
    dict   — the saved Firestore document, if the email was an opportunity
    None   — if the email was spam, a promotion, or below confidence threshold

    Firestore document shape
    ────────────────────────
    {
        "id":               str   (uuid)
        "title":            str   (subject line, max 200 chars)
        "organization":     str
        "type":             "internship" | "hackathon"
        "deadline":         str   (ISO date YYYY-MM-DD, or "" if not found)
        "application_link": str   (first URL found, or "")
        "source":           "email"
        "created_at":       str   (ISO datetime)
        "nlp_label":        str   (top predicted label)
        "nlp_confidence":   float (0–1)
        "extracted_by":     str   (user_id)
    }
    """

    # ── Step 1: Zero-shot classification ──────────────────────────────────────
    # Truncate to 512 chars so we stay within the model's token budget
    input_text = f"{email_subject}. {email_body[:512]}"

    classifier = _load_classifier()
    result     = classifier(input_text, candidate_labels=CANDIDATE_LABELS)

    top_label = result["labels"][0]
    top_score = result["scores"][0]

    logger.info(
        "Classified | subject='%s...' | label='%s' | score=%.3f",
        email_subject[:50], top_label, top_score,
    )

    # ── Step 2: Filter irrelevant emails ──────────────────────────────────────
    if top_label not in RELEVANT_LABELS:
        logger.info("Skipped — '%s' (not relevant)", top_label)
        return None

    if top_score < CONFIDENCE_THRESHOLD:
        logger.info(
            "Skipped — low confidence (%.3f < %.2f)", top_score, CONFIDENCE_THRESHOLD
        )
        return None

    # ── Step 3: Determine opportunity sub-type ────────────────────────────────
    opp_type = "hackathon" if top_label == "hackathon opportunity" else "internship"

    # ── Step 4: Extract structured fields ─────────────────────────────────────
    full_text        = f"{email_subject}\n{email_body}"
    organization     = _extract_organization(email_subject, email_body, sender)
    deadline         = _extract_deadline(full_text) or ""
    links            = _extract_links(full_text)
    application_link = links[0] if links else ""

    # ── Step 5: Build the Firestore document ──────────────────────────────────
    doc_id   = str(uuid.uuid4())
    now_iso  = datetime.utcnow().isoformat()

    document = {
        # Required fields (spec)
        "id":               doc_id,
        "title":            email_subject.strip()[:200],
        "organization":     organization,
        "deadline":         deadline,
        "application_link": application_link,
        "source":           "email",
        "created_at":       now_iso,
        # Extra fields (compatible with your existing opportunities schema)
        "type":             opp_type,
        "role":             email_subject.strip()[:200],
        "stipend":          "See listing",
        "eligibility":      "See listing",
        "applyLink":        application_link,
        "verified":         False,
        # NLP metadata (useful for debugging / dashboards)
        "nlp_label":        top_label,
        "nlp_confidence":   round(top_score, 4),
        "extracted_by":     user_id,
        "createdAt":        now_iso,
    }

    # ── Step 6: Save to Firestore ─────────────────────────────────────────────
    try:
        db = get_db()
        db.collection("opportunities").document(doc_id).set(document)
        logger.info("Saved to Firestore | id=%s | org=%s", doc_id, organization)
    except Exception as exc:
        logger.error("Firestore save failed: %s", exc)
        # Still return the document so the API response is useful
        # even if persistence failed

    return document


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 5 ── BATCH HELPER
# ══════════════════════════════════════════════════════════════════════════════

def process_email_batch(
    emails:  list[dict],
    user_id: str = "",
) -> list[dict]:
    """
    Run process_opportunity_email over a list of email dicts.

    Each dict must have:
        subject : str
        body    : str
        sender  : str  (optional)

    Returns only the emails that were classified as relevant opportunities.
    Individual errors are logged and skipped without crashing the batch.
    """
    results: list[dict] = []

    for i, email in enumerate(emails):
        try:
            opp = process_opportunity_email(
                email_subject = email.get("subject", ""),
                email_body    = email.get("body",    ""),
                sender        = email.get("sender",  ""),
                user_id       = user_id,
            )
            if opp is not None:
                results.append(opp)
        except Exception as exc:
            logger.error("Error processing email %d: %s", i, exc)

    logger.info(
        "Batch complete: %d scanned → %d opportunities", len(emails), len(results)
    )
    return results
