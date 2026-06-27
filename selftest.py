"""
selftest.py — a tiny, dependency-light sanity check (no pytest needed).
Run:  python selftest.py

Validates the analytics, autocomplete, and export logic against the committed
snapshot so a reviewer can confirm the core is sound in one command.
"""

from __future__ import annotations

import re
import sys

from src import analytics, areas, exporter, scraper

PASS, FAIL = "✓ PASS", "✗ FAIL"
results: list[tuple[bool, str]] = []


def check(name: str, cond: bool) -> None:
    results.append((bool(cond), name))
    print(f"{PASS if cond else FAIL}  {name}")


# 1) Snapshot loads and is well-formed
snap = scraper.load_snapshot()
check("snapshot loads 62 listings", len(snap) == 62)
required = {"title", "area", "unit_type", "price_month", "price_year", "size_sqft",
            "furnishing", "rental_type", "url"}
check("every listing has required fields", all(required <= set(r) for r in snap))

# 2) Area collection (snapshot mode) returns Mont Kiara units
mk = scraper.collect("Mont Kiara", mode="snapshot").listings
check("collect('Mont Kiara') returns 18 units", len(mk) == 18)

# 3) Price summary structure + fair price sits inside the segment range
summary = analytics.price_summary(mk)
segs = {r["segment"] for r in summary}
check("summary includes an 'All units' total row", "All units" in segs)
ok_fair = True
for r in summary:
    if r["fair_price"] and r["min"] and r["max"]:
        ok_fair &= (r["min"] - 50) <= r["fair_price"] <= (r["max"] + 50)
check("fair price within segment min..max", ok_fair)

# 4) Studio median is sensible (3 Mont Kiara studios: 1950/2000/2100 -> 2000)
studio = [r for r in summary if r["segment"] == "Studio"]
check("Studio median == RM2,000", bool(studio) and studio[0]["median"] == 2000)

# 5) Rental-type coverage: monthly present, daily absent for Mont Kiara
cov = analytics.rental_type_coverage(mk)
check("coverage: Monthly available", cov["Monthly"]["available"])
check("coverage: Daily not available in Mont Kiara", not cov["Daily"]["available"])

# 6) Autocomplete: typing 'Mont' surfaces Mont Kiara (+ siblings)
sugg = [s["label"] for s in areas.suggest("Mont", limit=6)]
check("autocomplete('Mont') includes 'Mont Kiara'", "Mont Kiara" in sugg)
check("autocomplete returns several suggestions", len(sugg) >= 3)

# 7) Export filename convention
fn = exporter.build_filename("Mont Kiara", "xlsx")
check("filename matches SPEEDHOME_<Area>_<YYYYMMDD>.xlsx",
      bool(re.match(r"^SPEEDHOME_Mont_Kiara_\d{8}\.xlsx$", fn)))

# 8) xlsx + csv export produce non-empty bytes
ldf = exporter.listings_dataframe(mk)
sdf = exporter.summary_dataframe(summary)
check("xlsx export is non-empty", len(exporter.to_xlsx_bytes(ldf, sdf)) > 1000)
check("csv export is non-empty", len(exporter.to_csv_bytes(ldf)) > 200)

# 9) ROI math
roi = analytics.roi_estimate(3000, 750000, 1.5)
check("ROI gross yield ≈ 4.8%", abs(roi["gross_yield_pct"] - 4.8) < 0.05)

# Summary
passed = sum(1 for ok, _ in results if ok)
print(f"\n{passed}/{len(results)} checks passed.")
sys.exit(0 if passed == len(results) else 1)
