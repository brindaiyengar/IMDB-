"""Shared UI pieces: styling, header, sidebar filters, KPI strip, formatting."""
from __future__ import annotations

import base64
import html
from pathlib import Path

import pandas as pd
import streamlit as st

import analytics as an
from analytics import Filters
from data_loader import TITLE_TYPES, TITLE_TYPE_LABELS, imdb_id

ASSETS = Path(__file__).parent / "assets"

CSS = """
<style>
:root { --ink: #222222; --muted: #666666; --faint: #8C8C8A; --line: #E8E8E8;
        --line-soft: #F0F0EE; --wash: #FAFAFA; --yellow: #F5C518; --ease: cubic-bezier(.2,.7,.2,1); }

/* Content starts below Streamlit's fixed 60px top bar. */
[data-testid="stMainBlockContainer"] { padding-top: 4.5rem; padding-bottom: 3rem; max-width: 1360px; }
[data-testid="stSidebarContent"] { padding-top: 0.4rem; }
[data-testid="stSidebar"] { border-right: 1px solid var(--line); }
[data-testid="stSidebar"] hr { margin: 0.6rem 0; }
[data-testid="stHeader"] { background: rgba(255,255,255,0.92); backdrop-filter: blur(6px); }
h1, h2, h3 { letter-spacing: -0.01em; color: var(--ink); }
.stPlotlyChart { border-top: 1px solid var(--line-soft); padding-top: 4px; }

/* Sidebar navigation: quiet hover, thin yellow marker on the active page. */
[data-testid="stSidebarNavLink"] { position: relative; border-radius: 4px;
    transition: background-color .18s ease, color .18s ease; }
[data-testid="stSidebarNavLink"]:hover { background: #F2F2F0; }
[data-testid="stSidebarNavLink"][aria-current="page"] { background: #FFFFFF;
    box-shadow: inset 0 0 0 1px var(--line); }
[data-testid="stSidebarNavLink"][aria-current="page"]::before { content: ""; position: absolute;
    left: 0; top: 7px; bottom: 7px; width: 2px; border-radius: 2px; background: var(--yellow); }
.stButton button, [data-testid="stBaseButton-secondary"] {
    transition: border-color .18s ease, background-color .18s ease, color .18s ease; }
[data-testid="stBaseButton-secondary"]:hover { border-color: var(--yellow); color: var(--ink); }
/* Yellow text is unreadable on white: keep the yellow on tracks and borders, not on text. */
[data-testid="stSliderThumbValue"], [data-testid="stSliderThumbValue"] *,
[data-testid="stSliderTickBarMin"], [data-testid="stSliderTickBarMax"],
button[data-variant="pills"][aria-pressed="true"], button[data-variant="pills"][aria-pressed="true"] * {
    color: var(--ink) !important; }
button[data-variant="pills"] { transition: border-color .18s ease; }
button[data-variant="pills"]:hover { border-color: var(--yellow); }

.app-header { position: relative; display: flex; flex-wrap: wrap; align-items: center;
              gap: 10px 18px; padding-bottom: 14px; border-bottom: 1px solid var(--line);
              margin-bottom: 18px; }
.app-header::after { content: ""; position: absolute; left: 0; bottom: -1px; width: 56px;
                     height: 2px; background: var(--yellow); transform-origin: left;
                     animation: grow-x .7s var(--ease) .15s both; }
.app-header img { height: 38px; width: auto; display: block; }
.app-header .badge { background: #F5C518; color: #000; font-weight: 800; font-size: 20px;
                     padding: 4px 9px; border-radius: 4px; letter-spacing: -0.02em; }
.app-header .titles { flex: 1 1 320px; min-width: 0; }
.app-header .name { color: var(--ink); font-size: 22px; font-weight: 650; line-height: 1.15; }
.app-header .sub { color: var(--muted); font-size: 13.5px; margin-top: 2px; }
.app-header .source { color: var(--faint); font-size: 12px; text-align: right; line-height: 1.5;
                       margin-left: auto; }
.app-header .source a { color: var(--muted); text-decoration: underline; text-underline-offset: 2px;
                         text-decoration-color: #CFCFCC; transition: text-decoration-color .18s ease; }
.app-header .source a:hover { text-decoration-color: var(--yellow); }
@media (max-width: 720px) { .app-header .source { display: none; } }

.page-head { margin: 4px 0 10px 0; }
.page-head .h { color: var(--ink); font-size: 26px; font-weight: 650; letter-spacing: -0.015em; }
.page-head .scope { color: var(--muted); font-size: 13px; margin-top: 4px; }
.page-head .scope b { color: var(--ink); font-weight: 600;
                      box-shadow: inset 0 -0.38em 0 rgba(245,197,24,.45); }

.kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
        border-top: 1px solid var(--line); border-bottom: 1px solid var(--line); margin: 6px 0 22px 0; }
.kpi { padding: 14px 18px 14px 18px; border-left: 1px solid var(--line); min-width: 0; }
.kpi:first-child { border-left: none; padding-left: 2px; }
.kpi .l { color: var(--muted); font-size: 11.5px; text-transform: uppercase; letter-spacing: 0.06em; }
.kpi .v { color: var(--ink); font-size: 26px; font-weight: 650; margin-top: 4px;
          font-variant-numeric: tabular-nums; white-space: nowrap; overflow: hidden;
          text-overflow: ellipsis; }
.kpi .v.accent { color: var(--ink); }
.kpi .v.accent::after { content: ""; display: block; width: 18px; height: 2px; margin-top: 5px;
                        background: var(--yellow); }
.kpi .v.small { font-size: 15px; line-height: 1.3; padding-top: 5px; white-space: normal;
                display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; }
.kpi .n { color: var(--faint); font-size: 12px; margin-top: 3px; }

.section { color: var(--ink); font-size: 17px; font-weight: 600; margin: 26px 0 2px 0; }
.section-note { color: var(--muted); font-size: 12.5px; margin-bottom: 8px; }

.detail-title { color: var(--ink); font-size: 24px; font-weight: 650; line-height: 1.2; }
.detail-meta { color: var(--muted); font-size: 13.5px; margin-top: 6px; }
.detail-rating { font-size: 34px; font-weight: 700; color: var(--ink);
                 font-variant-numeric: tabular-nums; line-height: 1; }
.detail-rating::before { content: "★"; color: var(--yellow); font-size: 26px; margin-right: 6px;
                         vertical-align: 3px; }
.detail-rating span { font-size: 15px; color: var(--muted); font-weight: 500; }
.tag { display: inline-block; margin-bottom: 12px; border: 1px solid #DDDDDA; color: #444444; border-radius: 3px;
       padding: 1px 7px; font-size: 12px; margin: 6px 6px 0 0; background: #FFFFFF; }
.credit-row { display: grid; grid-template-columns: 110px 1fr; gap: 10px; padding: 7px 0;
              border-bottom: 1px solid var(--line-soft); font-size: 13.5px; }
.credit-row .k { color: var(--muted); }
.credit-row .val { color: var(--ink); }
.credit-row .val i { color: var(--faint); font-style: normal; }

/* Entrance: a short fade-up when a block first mounts. Transform only, so no layout shift. */
.app-header, .page-head, .kpis, .section, .stPlotlyChart, [data-testid="stDataFrame"] {
    animation: rise .45s var(--ease) both; }
.kpis { animation-delay: .06s; }
@keyframes rise { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: none; } }
@keyframes grow-x { from { transform: scaleX(0); } to { transform: scaleX(1); } }

/* A few slow yellow shapes in the page margins; never on top of controls. */
.drift { position: fixed; inset: 0; pointer-events: none; z-index: 0; overflow: hidden; }
.drift i { position: absolute; display: block; border-radius: 50%; background: var(--yellow);
           opacity: .16; will-change: transform; animation: drift 26s ease-in-out infinite alternate; }
.drift i:nth-child(1) { width: 10px; height: 10px; right: 2.2%; top: 22%; }
.drift i:nth-child(2) { width: 6px;  height: 6px;  right: 4.5%; top: 64%; animation-duration: 34s;
                        animation-delay: -9s; }
.drift i:nth-child(3) { width: 14px; height: 14px; right: 1.2%; bottom: 8%; border-radius: 2px;
                        opacity: .10; animation-duration: 40s; animation-delay: -17s; }
@keyframes drift { from { transform: translate(0, 0) rotate(0deg); }
                   to   { transform: translate(-14px, -36px) rotate(40deg); } }
@media (max-width: 1100px) { .drift { display: none; } }

@media (prefers-reduced-motion: reduce) {
  .app-header, .page-head, .kpis, .section, .stPlotlyChart, [data-testid="stDataFrame"],
  .app-header::after { animation: none !important; }
  .drift { display: none; }
  * { transition: none !important; }
}
</style>
<div class="drift" aria-hidden="true"><i></i><i></i><i></i></div>
"""


def inject_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


@st.cache_data
def _logo_html() -> str:
    path = ASSETS / "imdb_logo.svg"
    if path.exists():
        data = base64.b64encode(path.read_bytes()).decode()
        return f'<img src="data:image/svg+xml;base64,{data}" alt="IMDb">'
    return '<span class="badge">IMDb</span>'  # fallback when the asset is missing


def header(snapshot: str) -> None:
    st.markdown(f"""
<div class="app-header">
  {_logo_html()}
  <div class="titles">
    <div class="name">Movie Analytics</div>
    <div class="sub">Ratings, genres, careers and release history across the IMDb catalogue.</div>
  </div>
  <div class="source">
    Source: <a href="https://developer.imdb.com/non-commercial-datasets/" target="_blank">IMDb non-commercial datasets</a><br>
    Files dated {html.escape(snapshot)} · personal, non-commercial use
  </div>
</div>""", unsafe_allow_html=True)


def page_head(title: str, scope: str) -> None:
    st.markdown(f'<div class="page-head"><div class="h">{html.escape(title)}</div>'
                f'<div class="scope">{scope}</div></div>', unsafe_allow_html=True)


def section(title: str, note: str | None = None) -> None:
    st.markdown(f'<div class="section">{html.escape(title)}</div>'
                + (f'<div class="section-note">{note}</div>' if note else ""),
                unsafe_allow_html=True)


def kpi_strip(items: list[tuple]) -> None:
    """items: (label, value, note, style) where style is '', 'accent' or 'small'."""
    cells = "".join(
        f'<div class="kpi"><div class="l">{html.escape(l)}</div>'
        f'<div class="v {s}" title="{html.escape(v)}">{html.escape(v)}</div>'
        f'<div class="n">{html.escape(n)}</div></div>'
        for l, v, n, s in items)
    st.markdown(f'<div class="kpis">{cells}</div>', unsafe_allow_html=True)


# ----------------------------------------------------------------- formatting

def fmt_int(v) -> str:
    return "—" if v is None or pd.isna(v) else f"{int(v):,}"


def fmt_compact(v) -> str:
    if v is None or pd.isna(v):
        return "—"
    v = float(v)
    for div, suffix in ((1e6, "M"), (1e3, "K")):
        if v >= div:
            return f"{v / div:.1f}{suffix}".replace(".0" + suffix, suffix)
    return f"{v:,.0f}"


def fmt_votes_step(v: int) -> str:
    return "Any" if v == 0 else fmt_compact(v)


def type_label(t: str) -> str:
    return TITLE_TYPE_LABELS.get(t, t)


def imdb_url(tid: int) -> str:
    return f"https://www.imdb.com/title/{imdb_id(tid)}/"


def person_url(nid: int) -> str:
    return f"https://www.imdb.com/name/{imdb_id(nid, 'nm')}/"


def scope_text(f: Filters, n: int) -> str:
    """One-line description of the active selection for page headers."""
    parts = [f"<b>{n:,}</b> titles"]
    parts.append(", ".join(type_label(t) for t in f.types) if f.types else "all types")
    parts.append(f"{f.years[0]}–{f.years[1]}")
    if f.genres:
        joiner = " + " if f.genre_match == "All" else " / "
        parts.append(joiner.join(f.genres))
    if f.min_votes:
        parts.append(f"{fmt_compact(f.min_votes)}+ votes")
    if f.rating_active:
        parts.append(f"rated {f.rating[0]:.1f}–{f.rating[1]:.1f}")
    if f.runtime_active:
        hi = "+" if f.runtime[1] >= an.RUNTIME_CAP else f"–{f.runtime[1]}"
        parts.append(f"{f.runtime[0]}{hi} min")
    return " · ".join(html.escape(p) if not p.startswith("<b>") else p for p in parts)


# ----------------------------------------------------------------- sidebar

DEFAULTS = {
    "f_types": list(Filters.types),
    "f_years": Filters.years,
    "f_genres": [],
    "f_genre_match": Filters.genre_match,
    "f_min_votes": Filters.min_votes,
    "f_rating": Filters.rating,
    "f_runtime": Filters.runtime,
}


def _reset_filters() -> None:
    for k, v in DEFAULTS.items():
        st.session_state[k] = v


def _filters_changed() -> bool:
    return any(st.session_state.get(k) != v for k, v in DEFAULTS.items())


def sidebar_filters(genres: tuple[str, ...], has_ratings: bool) -> Filters:
    for k, v in DEFAULTS.items():
        st.session_state.setdefault(k, v)

    with st.sidebar:
        st.divider()
        head, reset = st.columns([3, 2], vertical_alignment="center")
        head.markdown("**Filters**")
        reset.button("Reset", on_click=_reset_filters, disabled=not _filters_changed(),
                     width="stretch", type="tertiary",
                     help="Restore every filter to its default")

        st.pills("Title type", TITLE_TYPES, selection_mode="multi",
                 format_func=type_label, key="f_types",
                 help="Leave empty to include every type. TV episodes are not part "
                      "of this dashboard.")
        st.slider("Release year", an.FIRST_YEAR, an.CURRENT_YEAR, key="f_years",
                  help=f"Titles announced for after {an.CURRENT_YEAR} or without a "
                       "release year are not included.")
        st.multiselect("Genre", genres, key="f_genres", placeholder="All genres")
        if len(st.session_state["f_genres"]) > 1:
            st.segmented_control("Match", ["Any", "All"], key="f_genre_match", required=True,
                                 label_visibility="collapsed",
                                 help="Any: title has at least one selected genre. "
                                      "All: title has every selected genre.")
        if has_ratings:
            st.select_slider("Minimum votes", an.VOTE_STEPS, key="f_min_votes",
                             format_func=fmt_votes_step,
                             help="Anything above 'Any' also removes unrated titles.")
            st.slider("IMDb rating", 1.0, 10.0, step=0.1, key="f_rating",
                      help="Narrowing this range removes unrated titles.")
        st.slider("Runtime (minutes)", 0, an.RUNTIME_CAP, step=5, key="f_runtime",
                  help=f"{an.RUNTIME_CAP} means {an.RUNTIME_CAP} minutes or longer. "
                       "Narrowing the range removes titles without a runtime.")

    # The segmented control returns None when the active option is clicked again.
    match = st.session_state.get("f_genre_match") or "Any"
    return Filters(
        years=tuple(st.session_state["f_years"]),
        types=tuple(st.session_state["f_types"]),
        genres=tuple(st.session_state["f_genres"]),
        genre_match=match,
        min_votes=int(st.session_state["f_min_votes"]) if has_ratings else 0,
        rating=tuple(st.session_state["f_rating"]) if has_ratings else (1.0, 10.0),
        runtime=tuple(st.session_state["f_runtime"]),
    )


def empty_state(message: str = "No titles match these filters.") -> None:
    st.info(f"{message} Widen the year range, lower the vote threshold, or use "
            "**Reset** in the sidebar.")


def chart(fig, key: str | None = None, select: bool = False, mode=("points",)):
    """Render a Plotly figure with the app's own template (not Streamlit's theme)."""
    from visualizations import PLOTLY_CONFIG
    # Streamlit fills the plot area with its own background; keep it transparent.
    fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
    if not select:
        return st.plotly_chart(fig, theme=None, config=PLOTLY_CONFIG, key=key)
    return st.plotly_chart(fig, theme=None, config=PLOTLY_CONFIG, key=key,
                           on_select="rerun", selection_mode=mode)
