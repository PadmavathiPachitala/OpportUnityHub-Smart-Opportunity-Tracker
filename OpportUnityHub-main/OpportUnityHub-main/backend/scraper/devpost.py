"""
Devpost Scraper
Scrapes hackathons from devpost.com/hackathons
"""
import requests
import time
import random
from bs4 import BeautifulSoup
from backend.cleaner import clean_all

BASE_URL  = "https://devpost.com"
LIST_URL  = "https://devpost.com/hackathons"
HEADERS   = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}


def _matches_domain(text: str, domain: str) -> bool:
    if not domain or domain == "general":
        return True
    kw_map = {
        "ai":     ["ai", "machine learning", "ml", "nlp", "deep learning"],
        "web":    ["web", "javascript", "frontend", "backend", "react", "node"],
        "data":   ["data", "analytics", "visualization"],
        "design": ["design", "ux", "ui"],
        "mobile": ["mobile", "android", "ios", "flutter"],
    }
    keywords = kw_map.get(domain.lower(), [])
    low = text.lower()
    return not keywords or any(kw in low for kw in keywords)


def scrape(filters: dict = None) -> list[dict]:
    filters = filters or {}
    domain   = filters.get("domain", "general")
    location = filters.get("location", "all")
    opp_type = filters.get("type", "all")

    if opp_type == "internship":
        return []  # Devpost is hackathons only

    params = {"challenge_type": "all", "open_to": "public"}
    if location == "remote":
        params["online_only"] = "true"

    results = []

    try:
        resp = requests.get(LIST_URL, headers=HEADERS, params=params, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        print(f"[devpost] Fetch error: {e}")
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    cards = soup.select(".hackathon-tile, [id^='featured-hackathon'], .challenge-listing")

    for card in cards:
        try:
            title_el    = card.select_one("h2, h3, .title, .hackathon-title")
            prize_el    = card.select_one(".prize-amount, .amount, .prize")
            deadline_el = card.select_one(".deadline, time, .submission-period")
            link_el     = card.select_one("a[href]") or card.find_parent("a")
            loc_el      = card.select_one(".hosted-by + span, .location, .online-only")

            title    = title_el.get_text(strip=True) if title_el else ""
            prize    = prize_el.get_text(strip=True) if prize_el else "N/A"
            deadline = deadline_el.get_text(strip=True) if deadline_el else "N/A"
            loc      = loc_el.get_text(strip=True) if loc_el else "Remote"
            href     = link_el["href"] if link_el and link_el.get("href") else ""
            if href and not href.startswith("http"):
                href = BASE_URL + href

            if not title:
                continue
            if not _matches_domain(title, domain):
                continue

            results.append({
                "title":        title,
                "role":         title,
                "organization": "Devpost",
                "type":         "hackathon",
                "location":     loc if loc else "Remote",
                "stipend":      prize,
                "deadline":     deadline,
                "apply_link":   href,
                "description":  f"Hackathon: {title}. Prize: {prize}. Register on Devpost.",
                "source":       "devpost",
                "domain":       domain,
                "verified":     True,
            })
        except Exception as e:
            print(f"[devpost] Card parse error: {e}")
            continue

    time.sleep(random.uniform(0.8, 1.5))
    print(f"[devpost] Scraped {len(results)} raw results")
    return clean_all(results)
