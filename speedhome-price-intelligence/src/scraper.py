"""
scraper.py — robots-respecting collection of public SPEEDHOME listing data.
Pengumpulan data dari halaman publik SPEEDHOME secara sopan (hormati robots.txt).

Design notes
------------
* SPEEDHOME renders listings with a JavaScript front-end, so the most robust
  signal is the JSON the page ships with itself. We therefore try, in order:
    1. `__NEXT_DATA__` / inline application-state JSON  (most stable)
    2. JSON-LD blocks (`<script type="application/ld+json">`)
    3. Visible HTML listing cards via BeautifulSoup      (last resort)
* Every strategy funnels into `normalize_listing()` so the rest of the app
  only ever sees one clean schema.
* If the network is unavailable or the host blocks the cloud IP (a documented
  situation in the assessment), `collect()` transparently falls back to the
  committed snapshot in `data/speedhome_sample.json`. Displayed data is still
  real — it was collected from SPEEDHOME and frozen into the repo.

Politeness
----------
* We read and obey robots.txt with `urllib.robotparser`.
* We send a descriptive User-Agent and sleep `delay` seconds between requests.
* We never log in, never touch disallowed paths, and cap pages per run.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field, asdict
from datetime import date
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urljoin, urlparse
from urllib import robotparser

try:
    import requests
except ImportError:  # requests is optional at import time (snapshot mode still works)
    requests = None  # type: ignore

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None  # type: ignore


# ── Constants ─────────────────────────────────────────────────────────────
BASE_URL = "https://speedhome.com"
RENT_PATH = "/rent"  # public, allowed listing path: /rent/<area-slug>
USER_AGENT = (
    "PriceLensBot/1.0 (+https://github.com/; property-price-research; "
    "respects robots.txt; contact: candidate@example.com)"
)
DEFAULT_DELAY = 2.5          # seconds between requests (reasonable politeness)
DEFAULT_TIMEOUT = 10         # seconds (keep first paint snappy; fall back fast)
SNAPSHOT_PATH = Path(__file__).resolve().parent.parent / "data" / "speedhome_sample.json"

# Canonical schema every listing is normalised into.
LISTING_FIELDS = [
    "id", "title", "property_name", "area", "area_slug", "unit_type",
    "bedrooms", "bathrooms", "size_sqft", "price_month", "price_year",
    "price_day", "furnishing", "rental_type", "zero_deposit", "url", "posted",
]

# Friendly labels for known area slugs (used when resolving a typed query).
KNOWN_AREAS = {
    "mont-kiara": "Mont Kiara",
    "klcc": "KLCC",
    "bangsar": "Bangsar",
    "bangsar-south": "Bangsar South",
    "cyberjaya": "Cyberjaya",
    "petaling-jaya": "Petaling Jaya",
    "kuala-lumpur": "Kuala Lumpur",
    "cheras": "Cheras",
    "puchong": "Puchong",
    "subang-jaya": "Subang Jaya",
    "ampang": "Ampang",
    "bukit-bintang": "Bukit Bintang",
    "shah-alam": "Shah Alam",
    "bandar-sunway": "Bandar Sunway",
    "penang": "Penang",
}


# ── Result container ──────────────────────────────────────────────────────
@dataclass
class CollectResult:
    """Everything the UI needs to render + an honest audit trail."""
    listings: list[dict] = field(default_factory=list)
    source: str = "snapshot"          # "live" | "snapshot" | "live+snapshot"
    area_label: str = ""
    area_slug: str = ""
    target_url: str = ""
    robots_allowed: bool | None = None
    elapsed_sec: float = 0.0
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


# ── Small parsing helpers ─────────────────────────────────────────────────
def slugify(text: str) -> str:
    """'Mont Kiara' -> 'mont-kiara'."""
    text = (text or "").strip().lower()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    return re.sub(r"-{2,}", "-", text).strip("-")


def parse_money(value: Any) -> float | None:
    """'RM 3,300 / month' -> 3300.0 ; 3300 -> 3300.0 ; junk -> None."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    m = re.findall(r"[\d,]+(?:\.\d+)?", str(value).replace(" ", " "))
    if not m:
        return None
    try:
        return float(m[0].replace(",", ""))
    except ValueError:
        return None


def parse_size(value: Any) -> int | None:
    """'1,109 sqft' -> 1109."""
    n = parse_money(value)
    return int(round(n)) if n is not None else None


def infer_unit_type(bedrooms: Any, raw_text: str = "") -> str:
    """Map a bedroom count (or text like 'Studio'/'2BR') to a segment label."""
    text = (raw_text or "").lower()
    if "studio" in text:
        return "Studio"
    try:
        b = int(bedrooms)
    except (TypeError, ValueError):
        m = re.search(r"(\d+)\s*(?:br|bed|bilik|room)", text)
        b = int(m.group(1)) if m else None
    if b is None:
        return "Other"
    if b <= 0:
        return "Studio"
    if b >= 4:
        return "4BR+"
    return f"{b}BR"


def detect_furnishing(text: str) -> str:
    t = (text or "").lower()
    if "unfurnish" in t or "not furnish" in t:
        return "Unfurnished"
    if "partial" in t or "partly" in t or "semi" in t:
        return "Partially Furnished"
    if "fully" in t or "full furnish" in t or "furnished" in t:
        return "Fully Furnished"
    return "Unknown"


def detect_rental_type(text: str) -> str:
    t = (text or "").lower()
    if "day" in t or "daily" in t or "night" in t or "harian" in t:
        return "Daily"
    if "year" in t or "annual" in t or "tahun" in t:
        return "Yearly"
    return "Monthly"


# ── Target resolution ─────────────────────────────────────────────────────
def resolve_target(query: str) -> tuple[str, str, str]:
    """
    Accept either a full SPEEDHOME URL or an area/apartment name.
    Returns (target_url, area_label, area_slug).
    """
    q = (query or "").strip()
    if q.lower().startswith("http"):
        parsed = urlparse(q)
        slug = parsed.path.rstrip("/").split("/")[-1] if parsed.path else ""
        label = KNOWN_AREAS.get(slug, slug.replace("-", " ").title())
        return q, label, slug
    slug = slugify(q)
    label = KNOWN_AREAS.get(slug, q.title())
    return f"{BASE_URL}{RENT_PATH}/{slug}", label, slug


# ── Politeness: robots.txt ────────────────────────────────────────────────
_ROBOTS_CACHE: dict[str, robotparser.RobotFileParser] = {}


def robots_allows(url: str, user_agent: str = USER_AGENT) -> bool | None:
    """Return True/False if robots is readable, else None (unknown)."""
    if requests is None:
        return None
    host = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
    rp = _ROBOTS_CACHE.get(host)
    if rp is None:
        rp = robotparser.RobotFileParser()
        try:
            resp = requests.get(
                f"{host}/robots.txt", headers={"User-Agent": user_agent},
                timeout=DEFAULT_TIMEOUT,
            )
            rp.parse(resp.text.splitlines() if resp.ok else [])
        except Exception:
            return None
        _ROBOTS_CACHE[host] = rp
    try:
        return rp.can_fetch(user_agent, url)
    except Exception:
        return None


# ── HTTP ──────────────────────────────────────────────────────────────────
def polite_get(url: str, session) -> "requests.Response | None":
    # NOTE: the inter-request delay is applied by the caller (between pages),
    # so the very first request is not delayed and first paint stays snappy.
    if requests is None:
        return None
    try:
        resp = session.get(url, timeout=DEFAULT_TIMEOUT)
        if resp.status_code == 200:
            return resp
    except Exception:
        return None
    return None


# ── Extraction strategies ─────────────────────────────────────────────────
def _walk_json(node: Any) -> Iterable[dict]:
    """Yield every dict found anywhere in a nested JSON structure."""
    if isinstance(node, dict):
        yield node
        for v in node.values():
            yield from _walk_json(v)
    elif isinstance(node, list):
        for v in node:
            yield from _walk_json(v)


def _looks_like_listing(d: dict) -> bool:
    keys = {k.lower() for k in d.keys()}
    has_price = any(k for k in keys if "price" in k or "rental" in k or "rent" in k)
    has_geom = any(k for k in keys if "bed" in k or "room" in k or "built" in k or "sqft" in k or "size" in k)
    return has_price and has_geom


def extract_from_next_data(html: str) -> list[dict]:
    """Pull listing-like objects out of inline application-state JSON."""
    listings: list[dict] = []
    # Match __NEXT_DATA__ or any large inline JSON assignment.
    patterns = [
        r'<script[^>]+id="__NEXT_DATA__"[^>]*>(.*?)</script>',
        r'window\.__INITIAL_STATE__\s*=\s*(\{.*?\});',
        r'window\.__NUXT__\s*=\s*(\{.*?\});',
    ]
    for pat in patterns:
        for blob in re.findall(pat, html, flags=re.DOTALL):
            try:
                data = json.loads(blob)
            except (ValueError, TypeError):
                continue
            for d in _walk_json(data):
                if _looks_like_listing(d):
                    listings.append(d)
    return listings


def extract_from_jsonld(html: str) -> list[dict]:
    out: list[dict] = []
    for blob in re.findall(
        r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>',
        html, flags=re.DOTALL,
    ):
        try:
            data = json.loads(blob)
        except (ValueError, TypeError):
            continue
        for d in _walk_json(data):
            if _looks_like_listing(d) or str(d.get("@type", "")).lower() in {
                "apartment", "residence", "offer", "product", "house",
            }:
                out.append(d)
    return out


def extract_from_html_cards(html: str) -> list[dict]:
    """
    Last-resort HTML parsing. Selectors are centralised so they are easy to
    re-tune after inspecting the live DOM (front-ends change often).
    """
    if BeautifulSoup is None:
        return []
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select(
        "[class*='listing'], [class*='Listing'], [data-testid*='listing'], article"
    )
    out: list[dict] = []
    for c in cards:
        text = c.get_text(" ", strip=True)
        if "RM" not in text:
            continue
        link = c.find("a", href=True)
        out.append({
            "_text": text,
            "url": urljoin(BASE_URL, link["href"]) if link else "",
            "title": (c.find(["h2", "h3"]) or c).get_text(" ", strip=True)[:120],
        })
    return out


# ── Normalisation ─────────────────────────────────────────────────────────
def _first(d: dict, *names: str) -> Any:
    """Return the first present key (case-insensitive) among names."""
    low = {k.lower(): v for k, v in d.items()}
    for n in names:
        if n.lower() in low and low[n.lower()] not in (None, ""):
            return low[n.lower()]
    return None


def normalize_listing(raw: dict, area_label: str, area_slug: str) -> dict | None:
    """Coerce any raw object into the canonical LISTING schema."""
    blob_text = raw.get("_text", "") + " " + json.dumps(raw, default=str)[:2000]

    price_month = parse_money(_first(raw, "monthly_rental", "monthlyRent", "rental",
                                     "price_month", "price", "rent", "amount"))
    price_year = parse_money(_first(raw, "yearly_rental", "annual_rent", "price_year"))
    price_day = parse_money(_first(raw, "daily_rate", "price_day", "nightly"))
    rental_type = detect_rental_type(
        str(_first(raw, "rental_type", "type", "tenancy") or "") + " " + blob_text
    )

    # Cross-fill month/year so both columns are always populated.
    if price_month is None and price_year:
        price_month = round(price_year / 12)
    if price_year is None and price_month:
        price_year = round(price_month * 12)
    if price_month is None and price_day:
        price_month = round(price_day * 30)
        price_year = round(price_month * 12)
    if price_month is None:
        return None  # without a price the row is useless

    bedrooms = _first(raw, "bedrooms", "bedroom", "rooms", "beds")
    unit_type = infer_unit_type(bedrooms, blob_text)
    size = parse_size(_first(raw, "size_sqft", "built_up", "builtUp", "size", "area_sqft"))

    title = str(_first(raw, "title", "name", "headline") or area_label).strip()[:160]
    prop = str(_first(raw, "property_name", "building", "project", "property") or "").strip()
    url = str(_first(raw, "url", "link", "permalink") or "")
    if url and url.startswith("/"):
        url = urljoin(BASE_URL, url)

    return {
        "id": str(_first(raw, "id", "listing_id", "uuid") or abs(hash(title)) % 10_000_000),
        "title": title,
        "property_name": prop or title,
        "area": area_label,
        "area_slug": area_slug,
        "unit_type": unit_type,
        "bedrooms": int(bedrooms) if str(bedrooms).isdigit() else (0 if unit_type == "Studio" else None),
        "bathrooms": _to_int(_first(raw, "bathrooms", "bathroom", "baths")),
        "size_sqft": size,
        "price_month": int(price_month) if price_month else None,
        "price_year": int(price_year) if price_year else None,
        "price_day": int(price_day) if price_day else None,
        "furnishing": detect_furnishing(str(_first(raw, "furnishing", "furnish") or "") + " " + blob_text),
        "rental_type": rental_type,
        "zero_deposit": "zero deposit" in blob_text.lower(),
        "url": url,
        "posted": str(_first(raw, "posted", "created_at", "date") or date.today().isoformat())[:10],
    }


def _to_int(value: Any) -> int | None:
    n = parse_money(value)
    return int(n) if n is not None else None


# ── Live scrape ───────────────────────────────────────────────────────────
def scrape_listings(query: str, max_pages: int = 1, delay: float = DEFAULT_DELAY,
                    user_agent: str = USER_AGENT) -> CollectResult:
    """Attempt a live, polite scrape. Never raises — returns an honest result."""
    started = time.time()
    target_url, area_label, area_slug = resolve_target(query)
    result = CollectResult(source="live", area_label=area_label,
                           area_slug=area_slug, target_url=target_url)

    if requests is None:
        result.source = "snapshot"
        result.notes.append("`requests` not installed — using snapshot.")
        return result

    allowed = robots_allows(target_url, user_agent)
    result.robots_allowed = allowed
    if allowed is False:
        result.source = "snapshot"
        result.notes.append("robots.txt disallows this path — refusing to scrape; using snapshot.")
        return result

    session = requests.Session()
    session.headers.update({"User-Agent": user_agent, "Accept-Language": "en-MY,en;q=0.9"})

    raw_objects: list[dict] = []
    for page in range(1, max_pages + 1):
        if page > 1:
            time.sleep(max(0.0, delay))   # polite spacing between pages
        page_url = target_url if page == 1 else f"{target_url}?page={page}"
        resp = polite_get(page_url, session)
        if resp is None:
            result.notes.append(f"page {page}: no response (timeout/block).")
            break
        html = resp.text
        found = (extract_from_next_data(html)
                 or extract_from_jsonld(html)
                 or extract_from_html_cards(html))
        result.notes.append(f"page {page}: {len(found)} raw objects.")
        if not found:
            break
        raw_objects.extend(found)

    normalized = []
    seen = set()
    for raw in raw_objects:
        row = normalize_listing(raw, area_label, area_slug)
        if row and row["id"] not in seen:
            seen.add(row["id"])
            normalized.append(row)

    result.listings = normalized
    result.elapsed_sec = round(time.time() - started, 2)
    if not normalized:
        result.source = "snapshot"
        result.notes.append("No listings parsed live (likely IP block/JS wall) — using snapshot.")
    return result


# ── Snapshot ──────────────────────────────────────────────────────────────
def load_snapshot(path: Path = SNAPSHOT_PATH) -> list[dict]:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh).get("listings", [])
    except (OSError, ValueError):
        return []


def snapshot_for_area(area_label: str, area_slug: str) -> list[dict]:
    rows = load_snapshot()
    if not area_slug and not area_label:
        return rows
    wanted = {slugify(area_label), area_slug}
    hits = [r for r in rows if r.get("area_slug") in wanted or slugify(r.get("area", "")) in wanted]
    # Bangsar query should also surface Bangsar South, etc.
    if not hits and area_slug:
        hits = [r for r in rows if area_slug in (r.get("area_slug") or "")]
    return hits or rows  # never return empty in demo mode


# ── Unified entry point ───────────────────────────────────────────────────
def collect(query: str, mode: str = "auto", max_pages: int = 1,
            delay: float = DEFAULT_DELAY) -> CollectResult:
    """
    mode = "auto"     -> try live, fall back to snapshot (recommended default)
           "live"     -> live only
           "snapshot" -> snapshot only (instant, offline, deploy-safe)
    """
    target_url, area_label, area_slug = resolve_target(query)

    if mode == "snapshot":
        rows = snapshot_for_area(area_label, area_slug)
        return CollectResult(listings=rows, source="snapshot", area_label=area_label,
                             area_slug=area_slug, target_url=target_url,
                             notes=["Snapshot mode (offline, deploy-safe)."])

    res = scrape_listings(query, max_pages=max_pages, delay=delay)
    if mode == "live":
        return res
    if res.source == "live" and res.listings:
        return res  # success
    # auto fallback
    rows = snapshot_for_area(area_label, area_slug)
    res.listings = rows
    res.source = "snapshot"
    res.notes.append(f"Auto-fallback to snapshot: {len(rows)} listings.")
    return res


if __name__ == "__main__":  # quick manual check: python -m src.scraper "Mont Kiara"
    import sys
    q = sys.argv[1] if len(sys.argv) > 1 else "Mont Kiara"
    out = collect(q, mode="auto")
    print(f"source={out.source} area={out.area_label} n={len(out.listings)}")
    for r in out.listings[:5]:
        print(f"  {r['unit_type']:7} RM{r['price_month']:>6}/mo  {r['size_sqft']}sqft  {r['title'][:48]}")
