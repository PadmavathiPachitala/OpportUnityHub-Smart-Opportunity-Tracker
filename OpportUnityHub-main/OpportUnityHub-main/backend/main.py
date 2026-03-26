"""
OpportUnity Hub — FastAPI Backend
Endpoints:
  GET  /api/opportunities  →  return cached/stored data
  POST /api/scrape         →  trigger fresh scrape with filters
  GET  /api/health         →  health check
"""
import asyncio
from fastapi import FastAPI, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import Optional

from backend import cache as cache_store
from backend.scraper import internshala, devpost, unstop, remotive

app = FastAPI(title="OpportUnity Hub API", version="1.0.0")

# ── CORS — allow the frontend (local file or any origin) ──────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory store of last scraped results (across all cache misses)
_last_results: list[dict] = []


# ── Helper ────────────────────────────────────────────────────────────────────

def _run_all_scrapers(filters: dict) -> list[dict]:
    """Run all scrapers concurrently (thread-based, safe for sync scrapers)."""
    results = []
    scrapers = [internshala, devpost, unstop, remotive]
    for s in scrapers:
        try:
            data = s.scrape(filters)
            results.extend(data)
            print(f"[main] {s.__name__.split('.')[-1]}: {len(data)} results")
        except Exception as e:
            print(f"[main] Scraper {s.__name__} failed: {e}")
    return results


def _apply_filters(data: list[dict], filters: dict) -> list[dict]:
    opp_type = filters.get("type", "all")
    domain   = filters.get("domain", "general")
    location = filters.get("location", "all")

    def matches(o: dict) -> bool:
        if opp_type not in ("all", "") and o.get("type", "") != opp_type:
            return False
        if domain not in ("general", "all", "") and o.get("domain", "") not in ("general", "", domain):
            return False
        if location not in ("all", "") :
            loc_low = o.get("location", "").lower()
            if location == "remote" and "remote" not in loc_low and "work from home" not in loc_low:
                return False
            if location == "onsite" and ("remote" in loc_low or "work from home" in loc_low):
                return False
        return True

    return [o for o in data if matches(o)]


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/api/health")
def health():
    return {"status": "ok", "service": "OpportUnity Hub API"}


@app.get("/api/opportunities")
def get_opportunities(
    type:     Optional[str] = Query(None),
    domain:   Optional[str] = Query(None),
    location: Optional[str] = Query(None),
):
    """Return last cached opportunities with optional filter query params."""
    filters = {
        "type":     type     or "all",
        "domain":   domain   or "general",
        "location": location or "all",
    }

    # Check cache first
    cached = cache_store.get(filters)
    if cached:
        return JSONResponse({"source": "cache", "count": len(cached), "opportunities": cached})

    # Fall back to last full results with filter applied
    if _last_results:
        filtered = _apply_filters(_last_results, filters)
        return JSONResponse({"source": "memory", "count": len(filtered), "opportunities": filtered})

    return JSONResponse({"source": "empty", "count": 0, "opportunities": [],
                         "message": "No data yet — call POST /api/scrape to fetch."})


@app.post("/api/scrape")
def trigger_scrape(body: dict = None):
    """
    Trigger a fresh scrape. Accepts JSON body:
    { "type": "all|internship|hackathon|job",
      "domain": "general|ai|web|data|design|mobile",
      "location": "all|remote|onsite" }
    """
    global _last_results
    body = body or {}
    filters = {
        "type":     body.get("type",     "all"),
        "domain":   body.get("domain",   "general"),
        "location": body.get("location", "all"),
    }

    # Serve from cache if fresh
    cached = cache_store.get(filters)
    if cached:
        return JSONResponse({
            "source":        "cache",
            "count":         len(cached),
            "opportunities": cached,
            "message":       "Served from cache (< 5 min old)"
        })

    # Run scrapers
    print(f"[main] Starting scrape with filters: {filters}")
    raw = _run_all_scrapers(filters)

    if not raw:
        return JSONResponse({
            "source": "empty", "count": 0, "opportunities": [],
            "message": "Scrapers returned no results. Sites may be blocking requests."
        })

    # Store & cache
    _last_results = raw
    filtered = _apply_filters(raw, filters)
    cache_store.set(filters, filtered)

    print(f"[main] Scrape complete: {len(raw)} total, {len(filtered)} after filter")
    return JSONResponse({
        "source":        "fresh",
        "count":         len(filtered),
        "opportunities": filtered,
        "message":       f"Scraped {len(raw)} total — {len(filtered)} match your filters."
    })


@app.delete("/api/cache")
def clear_cache():
    """Clear the in-memory cache (force re-scrape on next request)."""
    cache_store.clear()
    return {"message": "Cache cleared."}
