"""
Internshala Scraper
Scrapes internships from internshala.com
Respects rate limits with delays between requests.
"""
import requests
import time
import random
from bs4 import BeautifulSoup
from backend.cleaner import clean_all

BASE_URL = "https://internshala.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://internshala.com/",
}

DOMAIN_KEYWORD_MAP = {
    "ai":           ["machine learning", "ai", "deep learning", "nlp", "artificial intelligence", "data science"],
    "web":          ["web", "frontend", "backend", "fullstack", "react", "node", "javascript"],
    "data":         ["data", "analytics", "sql", "tableau", "power bi", "python"],
    "design":       ["design", "ui", "ux", "figma", "graphic"],
    "mobile":       ["android", "ios", "flutter", "mobile", "react native"],
    "general":      [],
}


def _matches_domain(text: str, domain: str) -> bool:
    if not domain or domain == "general":
        return True
    keywords = DOMAIN_KEYWORD_MAP.get(domain.lower(), [])
    low = text.lower()
    return any(kw in low for kw in keywords)


def _matches_location(loc_text: str, location_filter: str) -> bool:
    if not location_filter or location_filter == "all":
        return True
    loc_low = loc_text.lower()
    if location_filter == "remote":
        return "work from home" in loc_low or "remote" in loc_low or "wfh" in loc_low
    if location_filter == "onsite":
        return "work from home" not in loc_low and "remote" not in loc_low
    return True


def scrape(filters: dict = None) -> list[dict]:
    filters = filters or {}
    domain   = filters.get("domain", "general")
    location = filters.get("location", "all")
    opp_type = filters.get("type", "all")

    if opp_type == "hackathon":
        return []   # Internshala has internships only

    # Build URL — work-from-home or all
    if location == "remote":
        url = f"{BASE_URL}/work-from-home"
    else:
        url = f"{BASE_URL}/internships"

    results = []
    pages = 2  # scrape first 2 pages

    for page in range(1, pages + 1):
        page_url = f"{url}/page-{page}" if page > 1 else url
        try:
            resp = requests.get(page_url, headers=HEADERS, timeout=15)
            resp.raise_for_status()
        except Exception as e:
            print(f"[internshala] Error fetching page {page}: {e}")
            break

        soup = BeautifulSoup(resp.text, "lxml")

        # Each internship card
        cards = soup.select(".internship_meta, .individual_internship")
        if not cards:
            # Try alternate selectors
            cards = soup.select("[id^='internshiplist']")

        for card in cards:
            try:
                title_el    = card.select_one(".job-title-href, .profile a, h3 a")
                company_el  = card.select_one(".company_name a, .company-name")
                stipend_el  = card.select_one(".stipend, .stipend_salary")
                loc_el      = card.select_one(".location_link, .location a, .cities_buttons a")
                deadline_el = card.select_one(".active_jobs_seen_button + div, [id^='application-deadline'] span, .deadline")
                link_el     = card.select_one(".job-title-href, .profile a")

                title   = title_el.get_text(strip=True) if title_el else ""
                company = company_el.get_text(strip=True) if company_el else ""
                stipend = stipend_el.get_text(strip=True) if stipend_el else "N/A"
                loc     = loc_el.get_text(strip=True) if loc_el else "India"
                deadline= deadline_el.get_text(strip=True) if deadline_el else "N/A"
                href    = link_el["href"] if link_el and link_el.get("href") else ""
                if href and not href.startswith("http"):
                    href = BASE_URL + href

                if not title or not company:
                    continue

                combined = f"{title} {company}"
                if not _matches_domain(combined, domain):
                    continue
                if not _matches_location(loc, location):
                    continue

                results.append({
                    "title":        title,
                    "role":         title,
                    "organization": company,
                    "type":         "internship",
                    "location":     loc,
                    "stipend":      stipend,
                    "deadline":     deadline,
                    "apply_link":   href,
                    "description":  f"Internship at {company} — {title}. Location: {loc}. Stipend: {stipend}.",
                    "source":       "internshala",
                    "domain":       domain if domain != "general" else "general",
                    "verified":     True,
                })
            except Exception as e:
                print(f"[internshala] Card parse error: {e}")
                continue

        time.sleep(random.uniform(1.0, 2.5))

    print(f"[internshala] Scraped {len(results)} raw results")
    return clean_all(results)
