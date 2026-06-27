# PriceLens ◍ — SPEEDHOME Property Price Intelligence

> Quiet clarity for rental pricing. · _Kejelasan harga sewa, tanpa kebisingan._

A web app that collects public rental-listing data from **SPEEDHOME.com** (Malaysia) and turns
it into clear pricing intelligence — a per-segment **price summary** (average, median, mode,
**fair price**, average size), a full **listings table**, rental-type coverage, **Excel/CSV
export**, charts, auto-insights, an ROI calculator and area comparison — in a calm,
mobile-friendly, Muji-minimalist interface.

Built for the **Jendela360 — CEO Office** technical (vibe-coding) assessment, with heavy,
deliberate use of AI tooling. Style: Japanese — _kanso_ (simplicity), _ma_ (space), _kaizen_
(continuous refinement). Language: bilingual EN + ID.

---

## ✦ Try it in 30 seconds

- **No setup:** open [`demo/index.html`](demo/index.html) in any browser. It runs entirely client-side
  on a committed SPEEDHOME snapshot — real autocomplete, summary, filters, CSV export.
- **Full app (live scraping + .xlsx):** see [Run locally](#-run-locally) below.
- **Read the thinking:** [`docs/index.html`](docs/index.html) (senior-team dossier) ·
  [`docs/design-system.html`](docs/design-system.html) (Tatami design system).

---

## ✦ Features

**Required (all six met):**

1. **Search by URL _or_ area/apartment** with a live autocomplete dropdown (type “Mont” → Mont Kiara, Mont Kiara Aman, Mont Kiara Bayu …).
2. **Price Summary** per unit type (Studio/1BR/2BR/3BR/4BR+): count · average · median · mode · **fair price** · avg sqft.
3. **Unit Listings** table: title, property/area, bedrooms, RM/month, RM/year, sqft, furnishing, and a clickable **listing link** to verify.
4. **Rental types** — Daily / Monthly / Yearly with a clear “not available” notice (SPEEDHOME is mostly monthly & yearly).
5. **Download** as **.xlsx** or **.csv**, filename `SPEEDHOME_<Area>_<YYYYMMDD>.xlsx`.
6. **Responsive / mobile-friendly** layout (scrollable tables, stacking cards).

**Bonus:** interactive charts (bar / box / scatter) · auto-insights (bilingual) · ROI / rental-yield calculator · multi-area comparison · filter & sort · caching + offline demo.

---

## ✦ Run locally

```bash
# 1) clone / open this folder, then:
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 2) run
streamlit run app.py
```

Open the URL Streamlit prints (usually `http://localhost:8501`).

Quick sanity check without the UI:

```bash
python -m src.scraper "Mont Kiara"     # prints source + first listings
python selftest.py                     # validates the analytics on the snapshot
```

---

## ✦ Data modes (sidebar)

| Mode | Behaviour |
|------|-----------|
| **Auto** _(default)_ | Polite **live** scrape of SPEEDHOME; if the host blocks the server IP (common on free clouds — explicitly allowed by the brief), it falls back to the committed **snapshot** and says so. |
| **Live** | Live scrape only. |
| **Snapshot** | Instant, offline, deploy-safe — the dated dataset of record. |

The status bar always shows **live vs snapshot**, robots status, and unit count — no silent fakery.

### Politeness / ethics
- Reads and obeys **robots.txt** (`urllib.robotparser`).
- **Reasonable delay** between requests (configurable, default 2.5 s) and a per-run page cap.
- Descriptive **User-Agent**; never logs in; only touches public `/rent` paths.

---

## ✦ Deploy (public link, no login)

**Streamlit Community Cloud (recommended, free):**
1. Push this folder to a **public GitHub repo**.
2. Go to share.streamlit.io → **New app** → pick the repo → main file `app.py` → **Deploy**.
3. Share the resulting `https://<you>-….streamlit.app` link.

> If live scraping is blocked from the cloud IP, set the sidebar to **Snapshot** (or rely on Auto’s
> fallback). Per the brief, displaying data scraped earlier and frozen into the app is fully accepted.

**Render / Railway:** start command
`streamlit run app.py --server.port $PORT --server.address 0.0.0.0`.

---

## ✦ Project structure

```
speedhome-price-intelligence/
├── app.py                  # Streamlit app (all 6 requirements + bonus)
├── requirements.txt
├── selftest.py             # runnable analytics sanity check (no pytest needed)
├── .streamlit/config.toml  # Muji theme
├── src/
│   ├── scraper.py          # robots-respecting collection + snapshot fallback
│   ├── analytics.py        # avg / median / mode / fair price / insights / ROI
│   ├── areas.py            # autocomplete index
│   └── exporter.py         # .xlsx / .csv with dated filename
├── data/
│   └── speedhome_sample.json   # 62-unit snapshot of record (5 areas)
├── demo/
│   └── index.html          # zero-setup offline demo (same features)
└── docs/
    ├── index.html          # senior-team project dossier
    └── design-system.html  # Tatami design system
```

---

## ✦ How “fair price” is computed

The outlier-trimmed mean of monthly rent in a segment (drop the top & bottom 10%), rounded to RM50;
the median is used when there are fewer than 5 units. It’s a defensible “middle” that ignores
penthouses and fire-sales — documented, not a black box. Daily short-stays are excluded from monthly
stats (they’d inflate them) but still counted under rental-type coverage.

---

## ✦ AI usage (as the brief requires)

This is a vibe-coding test: the skill is **directing AI well**. Architecture, scraper heuristics,
statistics, UI, and bilingual copy were produced with AI pair-programming; the human set the scope,
the data schema, the fair-price method, the design tokens, and verified every requirement. Full log:
[`docs/index.html` → §12 AI Collaboration](docs/index.html).

---

## ✦ Tech stack

Python · Streamlit · requests · BeautifulSoup (stdlib `html.parser`) · pandas · openpyxl · Plotly.

## ✦ Disclaimer

Figures are indicative; always verify via the listing link before acting. Not investment advice.
Data belongs to SPEEDHOME; this tool reads only public pages, respectfully.
