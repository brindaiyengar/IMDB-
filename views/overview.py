import streamlit as st

import analytics as an
import components as ui
import visualizations as viz


def render(cat, fdf, f):
    ui.page_head("Overview", ui.scope_text(f, len(fdf)))
    if fdf.empty:
        ui.empty_state()
        return

    k = an.kpis(fdf)
    best = k["best"]
    best_text = (f"{best['title']} ({int(best['year'])})" if best is not None else "—")
    best_note = (f"{best['rating']:.1f} · {ui.fmt_compact(best['votes'])} votes"
                 if best is not None else f"no title with {ui.fmt_compact(k['best_min_votes'])}+ votes")
    ui.kpi_strip([
        ("Titles", ui.fmt_int(k["titles"]), f"{len(cat.titles):,} in catalogue", ""),
        ("Movies", ui.fmt_int(k["movies"]),
         f"{k['movies'] / k['titles']:.0%} of selection", ""),
        ("Rated", ui.fmt_int(k["rated"]), f"{k['rated'] / k['titles']:.0%} have 5+ votes", ""),
        ("Average rating", "—" if k["avg_rating"] is None else f"{k['avg_rating']:.2f}",
         "mean over rated titles", "accent"),
        (f"Top rated · {ui.fmt_compact(k['best_min_votes'])}+ votes", best_text, best_note, "small"),
        ("Genres", str(k["genres"]), f"of {len(cat.genres)} on IMDb", ""),
    ])

    per_year = an.titles_per_year(fdf)
    partial = an.CURRENT_YEAR if f.years[1] >= an.CURRENT_YEAR else None
    ui.chart(viz.titles_per_year(per_year, partial))

    left, right = st.columns(2, gap="large")
    with left:
        dist = an.rating_distribution(fdf)
        ui.chart(viz.rating_histogram(dist, k["avg_rating"]) if len(dist)
                 else viz.empty_figure("No rated titles in this selection"))
    with right:
        genres = an.genre_summary(fdf, cat.genres)
        ui.chart(viz.genre_bars(genres, top=10, height=340))

    left, right = st.columns(2, gap="large")
    with left:
        rt = an.runtime_distribution(fdf)
        ui.chart(viz.runtime_histogram(rt) if len(rt)
                 else viz.empty_figure("No runtimes listed for this selection"))
    with right:
        ui.chart(viz.rating_vote_heatmap(an.rating_vote_density(fdf)))
