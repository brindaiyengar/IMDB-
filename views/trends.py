import streamlit as st

import analytics as an
import components as ui
import visualizations as viz


def render(cat, fdf, f):
    ui.page_head("Trends over time", ui.scope_text(f, len(fdf)))
    if fdf.empty:
        ui.empty_state()
        return

    per_year = an.titles_per_year(fdf)
    partial = an.CURRENT_YEAR if f.years[1] >= an.CURRENT_YEAR else None
    ui.chart(viz.released_vs_rated(per_year, partial))
    note = ("The gap between the lines is titles nobody has rated yet; it is widest "
            "for old and obscure titles and for the last few years.")
    if partial:
        note += (f" {an.CURRENT_YEAR} is only partly recorded, and recent years keep "
                 "gaining titles and votes as IMDb is updated.")
    st.caption(note)

    c1, _ = st.columns([2, 3])
    min_votes = c1.select_slider(
        "Ratings chart: count a title once it has", [5, 100, 1_000, 10_000], value=100,
        key="tr_votes", format_func=lambda v: f"{v:,}+ votes")
    left, right = st.columns(2, gap="large")
    with left:
        ratings = an.rating_by_year(fdf, max(min_votes, f.min_votes))
        ui.chart(viz.band_line(ratings, "median", "Ratings by release year",
                               "Median and middle 50% of rated titles; years with "
                               "fewer than 20 are hidden", "IMDb rating", ".1f")
                 if len(ratings) else viz.empty_figure("Too few rated titles per year"))
    with right:
        runtimes = an.runtime_by_year(fdf)
        ui.chart(viz.band_line(runtimes, "median", "Runtime by release year",
                               "Median and middle 50%; years with fewer than 20 "
                               "runtimes are hidden", "Minutes", ".0f")
                 if len(runtimes) else viz.empty_figure("Too few runtimes per year"))

    summary = an.genre_summary(fdf, cat.genres)
    default = list(summary["genre"].head(4))
    genres = st.multiselect("Genres to compare", list(summary["genre"]), default=default,
                            max_selections=6, key="tr_genres",
                            help="Up to six genres. Colours stay with the genre you pick.")
    if genres:
        share = an.genre_share_by_year(fdf, cat.genres, genres)
        ui.chart(viz.genre_share_lines(share, genres, cat.genres))
        st.caption("Shares are noisy for early years with only a handful of titles.")
