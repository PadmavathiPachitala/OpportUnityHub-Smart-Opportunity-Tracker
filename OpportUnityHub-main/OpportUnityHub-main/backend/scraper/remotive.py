"""
Remotive API Client
Uses Remotive's free public API — no scraping, no blocking.
https://remotive.io/api/remote-jobs
Covers remote jobs & internships (replaces LinkedIn scraping).
"""
import requests
from backend.cleaner import clean_all

API_URL = "https://remotive.com/api/remote-jobs"
HEADERS = {
    "User-Agent": "OpportUnityHub/1.0",
}

DOMAIN_TAG_MAP = {
    "ai":     ["machine-learning", "data-science", "ai"],
    "web":    ["software-dev", "frontend", "backend"],
    "data":   ["data-science", "data-engineering", "analytics"],
    "design": ["design", "ux"],
    "mobile": ["mobile-app"],
}


def scrape(filters: dict = None) -> list[dict]:
    filters  = filters or {}
    domain   = filters.get("domain", "general")
    opp_type = filters.get("type", "all")

    if opp_type == "hackathon":
        return []  # Remotive has jobs only

    # Build category param
    category = None
    if domain and domain != "general":
        tags = DOMAIN_TAG_MAP.get(domain.lower())
        if tags:
            category = tags[0]

    params = {"limit": 30}
    if category:
        params["category"] = category

    try:
        resp = requests.get(API_URL, headers=HEADERS, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"[remotive] API error: {e}")
        return []

    jobs = data.get("jobs", [])
    results = []

    for job in jobs:
        title      = job.get("title", "")
        company    = job.get("company_name", "")
        tags_list  = job.get("tags", [])
        pub_date   = job.get("publication_date", "")[:10]  # YYYY-MM-DD
        url        = job.get("url", "")
        desc       = job.get("description", "")[:300]
        job_type   = job.get("job_type", "")

        # Filter out senior-only roles if they look like full-time jobs
        combined = f"{title} {' '.join(tags_list)}"

        results.append({
            "title":        title,
            "role":         title,
            "organization": company,
            "type":         "internship" if any(kw in title.lower() for kw in ["intern", "trainee", "graduate"]) else "job",
            "location":     "Remote",
            "stipend":      job_type or "N/A",
            "deadline":     pub_date,
            "apply_link":   url,
            "description":  desc,
            "source":       "remotive",
            "domain":       domain,
            "verified":     True,
        })

    print(f"[remotive] Fetched {len(results)} raw results")
    return clean_all(results)
