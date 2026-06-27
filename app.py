"""
PriceLens — SPEEDHOME Property Price Intelligence
=================================================
A calm, Muji-minimalist Streamlit app that collects public rental-listing data
from SPEEDHOME.com and turns it into clear pricing intelligence.

Run locally:    streamlit run app.py
Deploy:         Streamlit Cloud / Render / Railway  (see README.md)

Design language: kanso (simplicity), ma (negative space), kaizen (refinement).
UI text is bilingual — English primary, Bahasa Indonesia in captions.

Built with heavy AI-tooling assistance, as the assessment intends.
"""

from __future__ import annotations

import datetime as dt

import pandas as pd
import streamlit as st

from src import analytics, areas, exporter, scraper

try:
    import plotly.express as px
    import plotly.graph_objects as go
    HAS_PLOTLY = True
except Exception:
    HAS_PLOTLY = False


# ── Page config ────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="PriceLens · SPEEDHOME Price Intelligence",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Muji palette
PAPER, CARD, INK = "#F5F2EC", "#FBF9F4", "#23211E"
MUTED, LINE, CLAY = "#7C766B", "#E4DED2", "#9A5B3D"
PALETTE = ["#9A5B3D", "#6E7B6A", "#3E4C5E", "#B08968", "#A8A29E", "#8C7B6B"]


# ── Styling (the "Japanese-style", style-only) ─────────────────────────────
def inject_css() -> None:
    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&family=Spectral:wght@300;400;500&display=swap');

        html, body, [class*="css"], .stApp {{
            background: {PAPER};
            color: {INK};
            font-family: 'Inter', -apple-system, system-ui, sans-serif;
        }}
        .block-container {{ padding-top: 2.2rem; padding-bottom: 4rem; max-width: 1180px; }}

        /* Wordmark */
        .pl-mark {{ font-weight: 600; letter-spacing: .42em; text-transform: uppercase;
                    font-size: .82rem; color: {CLAY}; }}
        .pl-title {{ font-family: 'Spectral', serif; font-weight: 400; font-size: 2.15rem;
                     line-height: 1.15; margin: .15rem 0 .1rem; letter-spacing: .01em; }}
        .pl-sub {{ color: {MUTED}; font-size: .96rem; font-weight: 300; }}
        .pl-rule {{ height: 1px; background: {LINE}; border: 0; margin: 1.3rem 0 1.6rem; }}

        /* Section headers with a quiet kicker */
        .pl-kicker {{ text-transform: uppercase; letter-spacing: .24em; font-size: .68rem;
                      color: {CLAY}; font-weight: 600; }}
        .pl-h {{ font-family: 'Spectral', serif; font-size: 1.42rem; font-weight: 400;
                 margin: .1rem 0 .2rem; }}
        .pl-hsub {{ color: {MUTED}; font-size: .86rem; font-weight: 300; margin-bottom: .6rem; }}

        /* Cards / metrics */
        div[data-testid="stMetric"] {{
            background: {CARD}; border: 1px solid {LINE}; border-radius: 14px;
            padding: 1rem 1.15rem; box-shadow: 0 1px 0 rgba(0,0,0,.02);
        }}
        div[data-testid="stMetricLabel"] p {{ color: {MUTED}; font-size: .78rem;
            letter-spacing: .04em; text-transform: uppercase; }}
        div[data-testid="stMetricValue"] {{ font-family: 'Spectral', serif; color: {INK}; }}

        /* Chips */
        .pl-chip {{ display:inline-block; padding:.18rem .6rem; border:1px solid {LINE};
            border-radius: 999px; font-size:.74rem; color:{MUTED}; background:{CARD}; margin-right:.3rem; }}
        .pl-chip.on {{ color:{PAPER}; background:{CLAY}; border-color:{CLAY}; }}
        .pl-chip.off {{ color:#A6422F; border-color:#E7C8BE; background:#FBEFEA; }}

        /* Buttons -> quiet, flat */
        .stButton > button {{
            background: {CARD}; color: {INK}; border: 1px solid {LINE};
            border-radius: 10px; font-weight: 500; font-size: .82rem;
            padding: .35rem .8rem; transition: all .15s ease;
        }}
        .stButton > button:hover {{ border-color: {CLAY}; color: {CLAY}; }}
        div[data-testid="stFormSubmitButton"] button, .pl-primary .stButton > button {{
            background: {CLAY}; color: {PAPER}; border-color: {CLAY}; }}

        /* Dataframe */
        [data-testid="stDataFrame"] {{ border: 1px solid {LINE}; border-radius: 12px; }}

        /* Sidebar */
        section[data-testid="stSidebar"] {{ background: {CARD}; border-right: 1px solid {LINE}; }}
        section[data-testid="stSidebar"] .pl-mark {{ font-size: .72rem; }}

        /* Tabs */
        button[data-baseweb="tab"] {{ font-weight: 500; }}
        .stTabs [data-baseweb="tab-list"] {{ gap: .2rem; }}

        a {{ color: {CLAY}; }}
        .pl-note {{ background:{CARD}; border:1px solid {LINE}; border-left:3px solid {CLAY};
            border-radius:10px; padding:.7rem .9rem; font-size:.85rem; color:{INK}; }}

        @media (max-width: 640px) {{
            .block-container {{ padding-left: .8rem; padding-right: .8rem; }}
            .pl-title {{ font-size: 1.7rem; }}
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def style_fig(fig):
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif", color=INK, size=12),
        margin=dict(l=10, r=10, t=40, b=10), legend=dict(font=dict(size=11)),
        colorway=PALETTE, title=dict(font=dict(family="Spectral, serif", size=16)),
    )
    fig.update_xaxes(gridcolor=LINE, zeroline=False)
    fig.update_yaxes(gridcolor=LINE, zeroline=False)
    return fig


# ── Cached data access (bonus: caching) ────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def get_results(query: str, mode: str, max_pages: int, delay: float) -> dict:
    return scraper.collect(query, mode=mode, max_pages=max_pages, delay=delay).to_dict()


@st.cache_data(ttl=3600, show_spinner=False)
def get_area_overview(area_label: str) -> dict:
    res = scraper.collect(area_label, mode="snapshot")
    return analytics.area_overview(res.listings)


# ── Header ─────────────────────────────────────────────────────────────────
def header() -> None:
    st.markdown('<div class="pl-mark">PriceLens ◍</div>', unsafe_allow_html=True)
    st.markdown('<div class="pl-title">Property Price Intelligence</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="pl-sub">Quiet clarity for SPEEDHOME rental pricing · '
        '<i>Kejelasan harga sewa, tanpa kebisingan.</i></div>',
        unsafe_allow_html=True,
    )
    st.markdown('<hr class="pl-rule">', unsafe_allow_html=True)


def section(kicker: str, title: str, sub: str = "") -> None:
    st.markdown(f'<div class="pl-kicker">{kicker}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="pl-h">{title}</div>', unsafe_allow_html=True)
    if sub:
        st.markdown(f'<div class="pl-hsub">{sub}</div>', unsafe_allow_html=True)


# ── Sidebar ────────────────────────────────────────────────────────────────
def sidebar() -> dict:
    with st.sidebar:
        st.markdown('<div class="pl-mark">PriceLens ◍</div>', unsafe_allow_html=True)
        st.caption("SPEEDHOME Price Intelligence")
        st.markdown("---")

        st.markdown("**Data mode** · _Mode data_")
        mode = st.radio(
            "Data mode", ["auto", "live", "snapshot"], index=0, label_visibility="collapsed",
            format_func=lambda m: {
                "auto": "Auto — live, fallback to snapshot",
                "live": "Live — scrape SPEEDHOME now",
                "snapshot": "Snapshot — instant, offline",
            }[m],
        )
        st.caption(
            "Auto tries a polite live scrape, then falls back to the committed "
            "snapshot if the host blocks the server IP (allowed by the brief). "
            "_Snapshot = data nyata yang sudah disimpan._"
        )

        with st.expander("Politeness settings · Kesopanan"):
            delay = st.slider("Delay between requests (sec)", 0.5, 6.0, 2.5, 0.5)
            max_pages = st.slider("Max pages per run", 1, 5, 1)
            st.caption("Respects robots.txt · reasonable delay · descriptive User-Agent.")

        st.markdown("---")
        st.markdown("**How we use AI** · _Pemanfaatan AI_")
        st.caption(
            "Architecture, scraper heuristics, stats, and this UI were built with "
            "AI pair-programming (Claude). Prompts & approach are logged in "
            "`docs/` → AI Collaboration Log."
        )
        st.markdown("---")
        st.caption(f"v1.0 · {dt.date.today():%d %b %Y} · made with 間 (ma)")
    return {"mode": mode, "delay": delay, "max_pages": max_pages}


# ── Search + autocomplete (requirement #1) ─────────────────────────────────
def _set_query(value: str) -> None:
    st.session_state["query"] = value
    st.session_state["go"] = True


def _trigger() -> None:
    # fired when the user presses Enter / leaves the search box
    st.session_state["go"] = True


def render_search() -> bool:
    section("01 · Search", "Find an area or apartment",
            "Paste a SPEEDHOME URL, or type a name and pick a suggestion. "
            "_Tempel URL SPEEDHOME, atau ketik nama lalu pilih saran._")

    st.session_state.setdefault("query", "Mont Kiara")
    col_in, col_btn = st.columns([5, 1])
    with col_in:
        st.text_input(
            "Area / Apartment / URL", key="query", label_visibility="collapsed",
            on_change=_trigger,
            placeholder="e.g. Mont Kiara  ·  KLCC  ·  https://speedhome.com/rent/mont-kiara",
        )
    with col_btn:
        st.markdown('<div class="pl-primary">', unsafe_allow_html=True)
        collect_clicked = st.button("Collect", use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    q = st.session_state["query"].strip()
    if q and not q.lower().startswith("http"):
        sugg = areas.suggest(q, limit=6)
        # hide the trivial "exact single match" case
        if not (len(sugg) == 1 and sugg[0]["label"].lower() == q.lower()):
            st.markdown('<div class="pl-hsub">Suggestions · Saran</div>', unsafe_allow_html=True)
            cols = st.columns(min(len(sugg), 6) or 1)
            for i, item in enumerate(sugg):
                tag = "·area" if item["kind"] == "area" else "·apt"
                cols[i % len(cols)].button(
                    f"{item['label']}", key=f"sg_{i}_{item['slug']}",
                    on_click=_set_query, args=(item["label"],), use_container_width=True,
                    help=f"{tag} → {item['url']}",
                )

    triggered = collect_clicked or st.session_state.pop("go", False)
    return triggered


# ── Status banner ──────────────────────────────────────────────────────────
def render_status(res: dict) -> None:
    src = res["source"]
    icon = {"live": "🟢 Live", "snapshot": "🗂 Snapshot", "live+snapshot": "🟢 Live + 🗂"}.get(src, src)
    robots = {True: "allowed", False: "disallowed", None: "n/a"}[res.get("robots_allowed")]
    n = len(res["listings"])
    st.markdown(
        f'<span class="pl-chip on">{icon}</span>'
        f'<span class="pl-chip">{n} units</span>'
        f'<span class="pl-chip">robots: {robots}</span>'
        f'<span class="pl-chip">{res.get("area_label","")}</span>',
        unsafe_allow_html=True,
    )
    if res.get("notes"):
        with st.expander("Collection log · Catatan pengumpulan"):
            st.caption(f"Target: {res.get('target_url','')}")
            for note in res["notes"]:
                st.write("•", note)


# ── Price summary (requirement #2) ─────────────────────────────────────────
def render_summary(listings: list[dict], area_label: str) -> None:
    section("02 · Price Summary", "Resume harga per segmen tipe unit",
            "Average · Median · Mode · Fair Price · Avg Size — per Studio / 1BR / 2BR / 3BR …")

    ov = analytics.area_overview(listings)
    c = st.columns(4)
    c[0].metric("Fair price / mo", f"RM {ov['fair_price']:,.0f}" if ov['fair_price'] else "—",
                help="Representative central rent (outlier-trimmed). _Harga wajar._")
    c[1].metric("Median / mo", f"RM {ov['median']:,.0f}" if ov['median'] else "—")
    c[2].metric("Units found", f"{len(listings)}",
                help="Total units collected. Price stats use monthly/yearly units "
                     "(daily short-stays excluded). _Statistik harga memakai unit bulanan/tahunan._")
    c[3].metric("Avg size", f"{ov['avg_sqft']:,} sqft" if ov['avg_sqft'] else "—")

    summary = analytics.price_summary(listings)
    df = exporter.summary_dataframe(summary)
    st.dataframe(
        df, use_container_width=True, hide_index=True,
        column_config={
            "Average (RM)": st.column_config.NumberColumn(format="RM %d"),
            "Median (RM)": st.column_config.NumberColumn(format="RM %d"),
            "Mode (RM)": st.column_config.NumberColumn(format="RM %d"),
            "Fair Price (RM)": st.column_config.NumberColumn(format="RM %d"),
            "Avg Size (sqft)": st.column_config.NumberColumn(format="%d"),
            "RM / sqft": st.column_config.NumberColumn(format="RM %.2f"),
        },
    )
    st.caption("Mode = most frequent price (falls back to nearest RM100 bucket on "
               "small samples). Fair Price = outlier-trimmed central estimate.")

    # Rental-type coverage (requirement #4)
    cov = analytics.rental_type_coverage(listings)
    chips = []
    for t in ["Daily", "Monthly", "Yearly"]:
        info = cov[t]
        if info["available"]:
            chips.append(f'<span class="pl-chip on">{t}: {info["count"]} ✓</span>')
        else:
            chips.append(f'<span class="pl-chip off">{t}: not available ✕</span>')
    st.markdown("**Rental types covered · Tipe sewa**  " + " ".join(chips),
                unsafe_allow_html=True)
    if not cov["Daily"]["available"]:
        st.caption("Note: SPEEDHOME is dominated by monthly & yearly tenancies; "
                   "daily stays are rare. _Catatan: harian jarang tersedia._")


# ── Charts (bonus) ─────────────────────────────────────────────────────────
def render_charts(listings: list[dict]) -> None:
    if not HAS_PLOTLY:
        st.info("Install plotly to see charts · `pip install plotly`")
        return
    base = analytics.monthly_basis(listings)
    if not base:
        return
    df = pd.DataFrame(base)

    section("03 · Visual analysis", "Charts & distribution", "Bonus · visualisasi interaktif")
    t1, t2, t3 = st.tabs(["Average by type", "Price distribution", "Price vs size"])

    with t1:
        summ = [r for r in analytics.price_summary(listings) if r["segment"] != "All units"]
        sdf = pd.DataFrame(summ)
        fig = px.bar(sdf, x="segment", y="average", text="average",
                     labels={"segment": "Unit type", "average": "Avg rent (RM/mo)"})
        fig.update_traces(texttemplate="RM%{text:,.0f}", textposition="outside",
                          marker_line_width=0)
        st.plotly_chart(style_fig(fig), use_container_width=True)

    with t2:
        fig = px.box(df, x="unit_type", y="price_month", points="all",
                     category_orders={"unit_type": analytics.SEGMENT_ORDER},
                     labels={"unit_type": "Unit type", "price_month": "Rent (RM/mo)"})
        st.plotly_chart(style_fig(fig), use_container_width=True)

    with t3:
        sized = df[df["size_sqft"].notna()]
        if not sized.empty:
            fig = px.scatter(
                sized, x="size_sqft", y="price_month", color="furnishing",
                hover_name="title", size="price_month", size_max=18,
                labels={"size_sqft": "Size (sqft)", "price_month": "Rent (RM/mo)",
                        "furnishing": "Furnishing"},
            )
            st.plotly_chart(style_fig(fig), use_container_width=True)
        else:
            st.caption("No size data to plot.")


# ── Auto-insights (bonus) ──────────────────────────────────────────────────
def render_insights(listings: list[dict], area_label: str) -> None:
    section("04 · Insights", "What the numbers say", "Auto-generated · insight otomatis")
    cols = st.columns(2)
    for i, msg in enumerate(analytics.insights(listings, area_label)):
        with cols[i % 2]:
            st.markdown(f'<div class="pl-note">{msg}</div>', unsafe_allow_html=True)
            st.write("")


# ── Listings + filters + download (requirements #3, #5, #6) ────────────────
def render_listings(listings: list[dict], area_label: str) -> None:
    section("05 · Unit Listings", "Every unit found",
            "Filter, sort, click through to verify, then export. "
            "_Saring, urutkan, verifikasi, lalu unduh._")

    df_all = pd.DataFrame(listings)

    # Filters (bonus)
    with st.expander("Filters & sorting · Filter & urutan", expanded=True):
        f1, f2, f3 = st.columns([2, 2, 3])
        types = sorted(df_all["unit_type"].dropna().unique(),
                       key=lambda x: analytics.SEGMENT_ORDER.index(x)
                       if x in analytics.SEGMENT_ORDER else 99)
        sel_types = f1.multiselect("Unit type", types, default=types)
        furn = sorted(df_all["furnishing"].dropna().unique())
        sel_furn = f2.multiselect("Furnishing", furn, default=furn)
        pmin, pmax = int(df_all["price_month"].min()), int(df_all["price_month"].max())
        if pmin == pmax:
            pmax = pmin + 1
        sel_price = f3.slider("Rent / month (RM)", pmin, pmax, (pmin, pmax), step=100)

        s1, s2 = st.columns([2, 1])
        sort_key = s1.selectbox("Sort by", ["Price / Month", "Price / Year", "Size (sqft)",
                                            "Unit type", "Property"], index=0)
        ascending = s2.radio("Order", ["Asc", "Desc"], horizontal=True) == "Asc"

    f = df_all[
        df_all["unit_type"].isin(sel_types)
        & df_all["furnishing"].isin(sel_furn)
        & df_all["price_month"].between(sel_price[0], sel_price[1])
    ].copy()

    sort_map = {"Price / Month": "price_month", "Price / Year": "price_year",
                "Size (sqft)": "size_sqft", "Unit type": "unit_type", "Property": "property_name"}
    f = f.sort_values(sort_map[sort_key], ascending=ascending, na_position="last")

    st.caption(f"Showing **{len(f)}** of {len(df_all)} units · _{len(f)} dari {len(df_all)} unit_")

    show = exporter.listings_dataframe(f.to_dict("records"))
    st.dataframe(
        show, use_container_width=True, hide_index=True, height=460,
        column_config={
            "Price / Month (RM)": st.column_config.NumberColumn(format="RM %d"),
            "Price / Year (RM)": st.column_config.NumberColumn(format="RM %d"),
            "Price / Day (RM)": st.column_config.NumberColumn(format="RM %d"),
            "Size (sqft)": st.column_config.NumberColumn(format="%d"),
            "Zero Deposit": st.column_config.CheckboxColumn(),
            "Listing URL": st.column_config.LinkColumn("Listing URL", display_text="open ↗"),
        },
    )

    # Downloads (requirement #5) — built from the *filtered* view
    full_df = exporter.listings_dataframe(f.to_dict("records"))
    summary_df = exporter.summary_dataframe(analytics.price_summary(f.to_dict("records")))
    meta = {"area_label": area_label, "snapshot": dt.date.today().isoformat()}
    d1, d2, _ = st.columns([1, 1, 3])
    d1.download_button(
        "⬇ Excel (.xlsx)", data=exporter.to_xlsx_bytes(full_df, summary_df, meta),
        file_name=exporter.build_filename(area_label, "xlsx"),
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )
    d2.download_button(
        "⬇ CSV (.csv)", data=exporter.to_csv_bytes(full_df),
        file_name=exporter.build_filename(area_label, "csv"),
        mime="text/csv", use_container_width=True,
    )


# ── ROI calculator (bonus) ─────────────────────────────────────────────────
def render_roi(listings: list[dict]) -> None:
    with st.expander("💹 Rental-yield / ROI calculator · Kalkulator imbal hasil"):
        ov = analytics.area_overview(listings)
        c1, c2, c3 = st.columns(3)
        rent = c1.number_input("Monthly rent (RM)", min_value=0,
                               value=int(ov["fair_price"] or 2500), step=100)
        price = c2.number_input("Purchase price (RM)", min_value=0, value=750000, step=10000)
        costs = c3.slider("Annual costs (% of price)", 0.0, 5.0, 1.5, 0.1,
                          help="Maintenance + assessment + vacancy buffer.")
        r = analytics.roi_estimate(rent, price, costs)
        m = st.columns(4)
        m[0].metric("Annual rent", f"RM {r['annual_rent']:,}")
        m[1].metric("Gross yield", f"{r['gross_yield_pct']}%")
        m[2].metric("Net yield", f"{r['net_yield_pct']}%")
        m[3].metric("Payback", f"{r['payback_years']} yrs")
        st.caption("Indicative only — not investment advice. _Estimasi, bukan nasihat investasi._")


# ── Comparison mode (bonus) ────────────────────────────────────────────────
def render_compare() -> None:
    with st.expander("⚖ Compare areas · Bandingkan area"):
        picks = st.multiselect(
            "Pick areas to compare", ["Mont Kiara", "KLCC", "Bangsar South",
                                      "Cyberjaya", "Petaling Jaya", "Bangsar"],
            default=["Mont Kiara", "KLCC", "Cyberjaya"],
        )
        rows = []
        for a in picks:
            ov = get_area_overview(a)
            rows.append({"Area": a, "Units": ov["count"], "Median (RM)": ov["median"],
                         "Fair (RM)": ov["fair_price"], "RM/sqft": ov["price_psf"],
                         "Min": ov["min"], "Max": ov["max"]})
        if rows:
            cdf = pd.DataFrame(rows)
            st.dataframe(cdf, use_container_width=True, hide_index=True,
                         column_config={
                             "Median (RM)": st.column_config.NumberColumn(format="RM %d"),
                             "Fair (RM)": st.column_config.NumberColumn(format="RM %d"),
                             "Min": st.column_config.NumberColumn(format="RM %d"),
                             "Max": st.column_config.NumberColumn(format="RM %d"),
                             "RM/sqft": st.column_config.NumberColumn(format="RM %.2f"),
                         })
            if HAS_PLOTLY and len(rows) > 1:
                fig = px.bar(cdf, x="Area", y="RM/sqft", text="RM/sqft",
                             labels={"RM/sqft": "Rent per sqft (RM)"})
                fig.update_traces(texttemplate="RM%{text:.2f}", textposition="outside")
                st.plotly_chart(style_fig(fig), use_container_width=True)


# ── Main ───────────────────────────────────────────────────────────────────
def main() -> None:
    inject_css()
    header()
    settings = sidebar()

    triggered = render_search()

    # Collect only on an explicit action (button / suggestion / Enter), on first
    # load, or when the data mode changes — NOT on every keystroke. Filters and
    # sorting then operate on the cached result without re-scraping.
    need = (
        triggered
        or "result" not in st.session_state
        or st.session_state.get("result_mode") != settings["mode"]
    )
    if need:
        with st.spinner("Collecting public listing data · mengumpulkan data…"):
            st.session_state["result"] = get_results(
                st.session_state["query"], settings["mode"],
                settings["max_pages"], settings["delay"],
            )
            st.session_state["result_query"] = st.session_state["query"]
            st.session_state["result_mode"] = settings["mode"]

    res = st.session_state["result"]
    listings = res["listings"]
    area_label = res.get("area_label") or st.session_state["query"]

    st.write("")
    render_status(res)

    if not listings:
        st.warning("No listings found. Try another area or switch to Snapshot mode. "
                   "_Tidak ada unit. Coba area lain atau mode Snapshot._")
        return

    st.markdown('<hr class="pl-rule">', unsafe_allow_html=True)
    render_summary(listings, area_label)
    st.markdown('<hr class="pl-rule">', unsafe_allow_html=True)
    render_charts(listings)
    st.markdown('<hr class="pl-rule">', unsafe_allow_html=True)
    render_insights(listings, area_label)
    st.markdown('<hr class="pl-rule">', unsafe_allow_html=True)
    render_listings(listings, area_label)
    st.write("")
    render_roi(listings)
    render_compare()

    st.markdown('<hr class="pl-rule">', unsafe_allow_html=True)
    st.caption(
        "PriceLens · built for the Jendela360 CEO Office technical assessment. "
        "Data from SPEEDHOME public pages, collected respectfully (robots.txt + delays). "
        "Verify any figure via the listing link before acting. "
        "_Selalu verifikasi lewat tautan listing sebelum mengambil keputusan._"
    )


if __name__ == "__main__":
    main()
