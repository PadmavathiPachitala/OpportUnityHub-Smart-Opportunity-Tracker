import time

# ============================================
# Simple in-memory TTL cache
# ============================================

_cache: dict[str, tuple[list, float]] = {}
TTL_SECONDS = 300   # 5 minutes cache per filter key


def make_key(filters: dict) -> str:
    return "|".join(f"{k}={v}" for k, v in sorted(filters.items()))


def get(filters: dict):
    key = make_key(filters)
    if key in _cache:
        data, ts = _cache[key]
        if time.time() - ts < TTL_SECONDS:
            print(f"[cache] HIT  key={key}")
            return data
        else:
            print(f"[cache] EXPIRED key={key}")
            del _cache[key]
    return None


def set(filters: dict, data: list):
    key = make_key(filters)
    _cache[key] = (data, time.time())
    print(f"[cache] SET  key={key}  size={len(data)}")


def clear():
    _cache.clear()
