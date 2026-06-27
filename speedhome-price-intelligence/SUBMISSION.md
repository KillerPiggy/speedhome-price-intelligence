# Submission checklist · Daftar pengumpulan

Brief: **Tes Kemampuan Teknis — CEO Office — Jendela360** · Deadline: 7 days from receipt.
Form: **bit.ly/ttceoofficej360** · Questions: Faqih (HR Jendela360) on WhatsApp.

---

## 1. Required deliverables · _Yang wajib dikumpulkan_

- [ ] **App link (deployed, public, no login).**
  Deploy `app.py` to **Streamlit Community Cloud** (free) — steps in [`README`](README.md#-deploy-public-link-no-login).
  If the cloud IP is blocked by SPEEDHOME, set the sidebar to **Snapshot** or rely on **Auto** fallback
  (showing pre-scraped data is explicitly allowed by the brief). Paste the `*.streamlit.app` URL into the form.

- [ ] **Source code link.**
  Push this folder to a **public GitHub repo**; paste the repo URL into the form.

- [ ] **App explanation (optional — bonus).**
  Already prepared: open [`docs/index.html`](docs/index.html) (project dossier) and/or
  [`demo/index.html`](demo/index.html), then **Print → Save as PDF** for an attachable file. A 60-sec
  screen recording of the demo is a nice extra.

---

## 2. Requirement coverage · _Sudah lengkap_

| # | Requirement | Status |
|---|-------------|--------|
| 1 | URL / area search **+ autocomplete dropdown** | ✅ |
| 2 | Price summary: count, average, median, mode, **fair price**, avg sqft | ✅ |
| 3 | Listings table: title, property/area, beds, RM/mo, RM/yr, sqft, furnishing, **link** | ✅ |
| 4 | Rental types Daily/Monthly/Yearly + clear “not available” | ✅ |
| 5 | Download **.xlsx**/**.csv**, filename `SPEEDHOME_<Area>_<YYYYMMDD>` | ✅ |
| 6 | Responsive / mobile-friendly | ✅ |
| + | Charts · insights · ROI · compare · filter/sort · caching · offline demo | ✅ Bonus |

---

## 3. Pre-submit self-test · _Uji coba mandiri_

- [ ] `pip install -r requirements.txt` then `streamlit run app.py` — runs with **no errors**.
- [ ] `python selftest.py` — all checks pass.
- [ ] Open the **deployed** link in an **incognito** window — loads with no login, no error.
- [ ] Open it on a **phone** — tables scroll, nothing overlaps or is cut off.
- [ ] Type “Mont” → suggestions appear → pick one → summary + listings render.
- [ ] Click a listing link → opens the SPEEDHOME page.
- [ ] Download `.xlsx` → filename includes area + today’s date → opens in Excel.

---

## 4. Notes honoured from the brief · _Catatan penting_

- **AI tooling used throughout** — documented in [`docs/index.html` §12](docs/index.html).
- **robots.txt respected**, reasonable delay between requests, descriptive User-Agent.
- **No restricted tech** — Python + Streamlit, free to deploy.
- Data shown is real SPEEDHOME data (live, or a dated snapshot frozen into the app — accepted by the brief).
