"""
analytics.py — per-segment price statistics & auto-insights.
Statistik harga per segmen tipe unit + insight otomatis (bilingual).

Everything here is pure functions over a list of normalised listing dicts,
so it is trivial to unit-test and reuse from both the Streamlit app and the
static HTML demo logic.
"""

from __future__ import annotations

import statistics
from collections import Counter
from typing import Any

SEGMENT_ORDER = ["Studio", "1BR", "2BR", "3BR", "4BR+", "Other"]


# ── filters ────────────────────────────────────────────────────────────────
def monthly_basis(listings: list[dict]) -> list[dict]:
    """Rows usable for monthly price stats (exclude daily short-stay outliers)."""
    return [
        r for r in listings
        if r.get("price_month") and (r.get("rental_type") in (None, "Monthly", "Yearly"))
    ]


def _prices(rows: list[dict]) -> list[float]:
    return [float(r["price_month"]) for r in rows if r.get("price_month")]


def _sizes(rows: list[dict]) -> list[float]:
    return [float(r["size_sqft"]) for r in rows if r.get("size_sqft")]


# ── central-tendency helpers ────────────────────────────────────────────────
def robust_mode(values: list[float]) -> float | None:
    """
    Most frequently occurring price. If no exact value repeats, fall back to
    the most common RM100 bucket (so the figure stays meaningful on small,
    high-variance samples).
    """
    if not values:
        return None
    counts = Counter(values)
    top_val, top_n = counts.most_common(1)[0]
    if top_n > 1:
        # smallest value among the joint-most-frequent (stable + conservative)
        return float(min(v for v, c in counts.items() if c == top_n))
    buckets = Counter(round(v / 100) * 100 for v in values)
    b_val, b_n = buckets.most_common(1)[0]
    return float(b_val) if b_n > 1 else None


def trimmed_mean(values: list[float], trim: float = 0.1) -> float | None:
    """Mean after dropping the lowest/highest `trim` fraction (outlier-robust)."""
    if not values:
        return None
    s = sorted(values)
    k = int(len(s) * trim)
    core = s[k: len(s) - k] if len(s) - 2 * k >= 1 else s
    return statistics.fmean(core)


def fair_price(values: list[float]) -> float | None:
    """
    'Harga wajar' — a representative central estimate.
    Uses the outlier-trimmed mean (>=5 pts) else the median, rounded to RM50.
    """
    if not values:
        return None
    base = trimmed_mean(values) if len(values) >= 5 else statistics.median(values)
    return float(round(base / 50) * 50)


# ── core summary ────────────────────────────────────────────────────────────
def _row_stats(segment: str, rows: list[dict]) -> dict:
    prices = _prices(rows)
    sizes = _sizes(rows)
    avg = statistics.fmean(prices) if prices else None
    avg_sqft = statistics.fmean(sizes) if sizes else None
    psf = (avg / avg_sqft) if (avg and avg_sqft) else None
    return {
        "segment": segment,
        "count": len(rows),
        "average": round(avg) if avg else None,
        "median": round(statistics.median(prices)) if prices else None,
        "mode": round(robust_mode(prices)) if robust_mode(prices) else None,
        "fair_price": fair_price(prices),
        "avg_sqft": round(avg_sqft) if avg_sqft else None,
        "price_psf": round(psf, 2) if psf else None,
        "min": round(min(prices)) if prices else None,
        "max": round(max(prices)) if prices else None,
    }


def price_summary(listings: list[dict]) -> list[dict]:
    """
    Returns one row per unit-type segment (only those present), plus a final
    'All units' total row. Monthly basis (RM/month).
    """
    base = monthly_basis(listings)
    by_seg: dict[str, list[dict]] = {}
    for r in base:
        by_seg.setdefault(r.get("unit_type", "Other"), []).append(r)

    out: list[dict] = []
    for seg in SEGMENT_ORDER:
        if by_seg.get(seg):
            out.append(_row_stats(seg, by_seg[seg]))
    # any unexpected segment labels
    for seg in by_seg:
        if seg not in SEGMENT_ORDER:
            out.append(_row_stats(seg, by_seg[seg]))
    if base:
        out.append(_row_stats("All units", base))
    return out


# ── rental-type coverage ────────────────────────────────────────────────────
def rental_type_coverage(listings: list[dict]) -> dict[str, dict[str, Any]]:
    """Counts + availability for Daily / Monthly / Yearly (spec requirement 4)."""
    counts = Counter(r.get("rental_type", "Monthly") for r in listings)
    out = {}
    for t in ["Daily", "Monthly", "Yearly"]:
        out[t] = {"available": counts.get(t, 0) > 0, "count": counts.get(t, 0)}
    return out


# ── comparison mode (bonus) ─────────────────────────────────────────────────
def area_overview(listings: list[dict]) -> dict[str, Any]:
    base = monthly_basis(listings)
    prices = _prices(base)
    sizes = _sizes(base)
    return {
        "count": len(base),
        "median": round(statistics.median(prices)) if prices else None,
        "average": round(statistics.fmean(prices)) if prices else None,
        "fair_price": fair_price(prices),
        "avg_sqft": round(statistics.fmean(sizes)) if sizes else None,
        "price_psf": round(statistics.fmean(prices) / statistics.fmean(sizes), 2)
        if prices and sizes else None,
        "min": round(min(prices)) if prices else None,
        "max": round(max(prices)) if prices else None,
    }


# ── auto-insights (bonus, bilingual) ────────────────────────────────────────
def insights(listings: list[dict], area_label: str = "this area") -> list[str]:
    """Human-readable observations. EN line + ID line per insight."""
    base = monthly_basis(listings)
    if not base:
        return ["No data to analyse. / Tidak ada data untuk dianalisis."]

    msgs: list[str] = []
    prices = _prices(base)
    ov = area_overview(base)

    # 1) headline fair price
    msgs.append(
        f"**Fair monthly rent in {area_label} ≈ RM{ov['fair_price']:,.0f}** "
        f"(median RM{ov['median']:,.0f}, range RM{ov['min']:,.0f}–RM{ov['max']:,.0f} "
        f"across {ov['count']} units).  \n"
        f"_Harga sewa wajar di {area_label} ≈ RM{ov['fair_price']:,.0f} per bulan "
        f"(median RM{ov['median']:,.0f})._"
    )

    # 2) most common segment
    seg_counts = Counter(r["unit_type"] for r in base)
    seg, n = seg_counts.most_common(1)[0]
    msgs.append(
        f"**{seg} is the most available layout** ({n} of {len(base)} units).  \n"
        f"_Tipe {seg} paling banyak tersedia ({n} dari {len(base)} unit)._"
    )

    # 3) best value (lowest RM/sqft)
    psf_rows = [(r, r["price_month"] / r["size_sqft"]) for r in base if r.get("size_sqft")]
    if psf_rows:
        best, psf = min(psf_rows, key=lambda x: x[1])
        msgs.append(
            f"**Best value: {best['title']}** — RM{psf:,.2f}/sqft "
            f"(RM{best['price_month']:,.0f}/mo, {best['size_sqft']:,} sqft).  \n"
            f"_Paling worth it: {best['property_name']} — RM{psf:,.2f}/sqft._"
        )

    # 4) furnishing premium
    full = _prices([r for r in base if r.get("furnishing") == "Fully Furnished"])
    other = _prices([r for r in base if r.get("furnishing") in ("Partially Furnished", "Unfurnished")])
    if full and other:
        diff = (statistics.fmean(full) / statistics.fmean(other) - 1) * 100
        msgs.append(
            f"**Fully-furnished units rent ~{diff:.0f}% higher** than partial/unfurnished.  \n"
            f"_Unit fully furnished ~{diff:.0f}% lebih mahal dari yang tidak._"
        )

    # 5) price dispersion
    if len(prices) > 2:
        cv = statistics.pstdev(prices) / statistics.fmean(prices) * 100
        tone = "tight" if cv < 25 else ("moderate" if cv < 50 else "wide")
        msgs.append(
            f"**Price spread is {tone}** (variation ≈ {cv:.0f}%).  \n"
            f"_Sebaran harga tergolong {('rapat' if cv<25 else 'sedang' if cv<50 else 'lebar')} (~{cv:.0f}%)._"
        )
    return msgs


def roi_estimate(monthly_rent: float, purchase_price: float,
                 annual_costs_pct: float = 1.5) -> dict[str, float]:
    """
    Bonus: simple gross & net rental-yield calculator.
    annual_costs_pct = maintenance + assessment + vacancy buffer as % of price.
    """
    annual_rent = monthly_rent * 12
    gross = annual_rent / purchase_price * 100 if purchase_price else 0.0
    net_income = annual_rent - purchase_price * (annual_costs_pct / 100)
    net = net_income / purchase_price * 100 if purchase_price else 0.0
    payback = purchase_price / annual_rent if annual_rent else 0.0
    return {
        "annual_rent": round(annual_rent),
        "gross_yield_pct": round(gross, 2),
        "net_yield_pct": round(net, 2),
        "payback_years": round(payback, 1),
    }
