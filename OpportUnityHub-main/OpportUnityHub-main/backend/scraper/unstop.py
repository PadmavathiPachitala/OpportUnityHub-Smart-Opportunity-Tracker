"""
Unstop Scraper
Scrapes competitions and internships from unstop.com
"""
import requests
import time
import random
from bs4 import BeautifulSoup
from backend.cleaner import clean_all

BASE_URL = "https://unstop.com"
HEADERS  = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://unstop.com/",
}


def _matches_type(opp_type_filter: str, card_type: str) -> bool:
    if opp_type_filter == "all":
        return True
    if opp_type_filter == "hackathon":
        return card_type in ("hackathon", "competition")
    if opp_type_filter == "internship":
        return card_type == "internship"
    return True


def scrape(filters: dict = None) -> list[dict]:
    filters  = filters or {}
    domain   = filters.get("domain", "general")
    location = filters.get("location", "all")
    opp_type = filters.get("type", "all")

    url = "https://unstop.com/competitions" if opp_type == "hackathon" else "https://unstop.com/internships"

    results = []

    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        print(f"[unstop] Fetch error: {e}")
        return []

    soup = BeautifulSoup(resp.text, "lxml")

    # Unstop uses Angular SSR; try to grab server-side rendered cards
    cards = soup.select(".opportunity-card, .card--opportunity, article.oppr-card, .single_profile")
    if not cards:
        cards = soup.select("[class*='card']")

    for card in cards:
        try:
            title_el    = card.select_one("h2, h3, .title, [class*='title']")
            company_el  = card.select_one(".company, .org-name, [class*='company']")
            prize_el    = card.select_one(".prize, .reward, [class*='prize']")
            deadline_el = card.select_one(".deadline, time, [class*='deadline'], [class*='date']")
            link_el     = card.select_one("a[href]") or card.find_parent("a")

            title    = title_el.get_text(strip=True) if title_el else ""
            company  = company_el.get_text(strip=True) if company_el else "Unstop"
            prize    = prize_el.get_text(strip=True) if prize_el else "N/A"
            deadline = deadline_el.get_text(strip=True) if deadline_el else "N/A"
            href     = link_el["href"] if link_el and link_el.get("href") else url
            if href and not href.startswith("http"):
                href = BASE_URL + href

            if not title:
                continue

            determined_type = "hackathon" if "competition" in url else "internship"
            if not _matches_type(opp_type, determined_type):
                continue

            results.append({
                "title":        title,
                "role":         title,
                "organization": company,
                "type":         determined_type,
                "location":     "India / Remote",
                "stipend":      prize,
                "deadline":     deadline,
                "apply_link":   href,
                "description":  f"{determined_type.capitalize()} opportunity: {title} by {company}.",
                "source":       "unstop",
                "domain":       domain,
                "verified":     True,
            })
        except Exception as e:
            print(f"[unstop] Card parse error: {e}")
            continue

    time.sleep(random.uniform(0.8, 1.5))
    print(f"[unstop] Scraped {len(results)} raw results")
    return clean_all(results)
