import streamlit as st

import analytics as an
import components as ui
import visualizations as viz

MIN_RATED = 50


def render(cat, fdf, f):
    ui.page_head("Genre analysis", ui.scope_text(f, len(fdf)))
    if fdf.empty:
        ui.empty_state()
        return
    st.caption("A title with three genres counts once in each of them, so genre "
               "totals add up to more than the number of titles. Rating averages "
               "use rated titles only.")

    summary = an.genre_summary(fdf, cat.genres)
    if summary.empty:
        ui.empty_state("None of these titles has a genre listed.")
        return

    picked = st.session_state.get("gn_pick")
    if picked not in set(summary["genre"]):
        picked = None

    left, right = st.columns(2, gap="large")
    with left:
        event = ui.chart(viz.genre_bars(summary, top=len(summary), title="Titles per genre",
                                        subtitle="Click a bar to list that genre's best titles",
                                        highlight=picked),
                         key=f"gn_bars_{st.session_state.get('gn_gen', 0)}", select=True)
        points = event.selection.get("points", []) if event and event.selection else []
        if points:
            clicked = points[0]["y"]
            if clicked != picked:
                st.session_state["gn_pick"] = clicked
                st.rerun()
    with right:
        rated = fdf["rating"].dropna()
        ui.chart(viz.genre_rating_dots(summary, rated.mean() if len(rated) else None,
                                       MIN_RATED))

    c1, _ = st.columns([2, 3])
    metric = c1.segmented_control(
        "Heatmap shows", ["Share of titles", "Titles", "Mean rating"], key="gn_metric",
        default="Share of titles", required=True)
    metric_key = {"Share of titles": "share", "Titles": "titles", "Mean rating": "avg_rating"}[metric]
    by_decade = an.genre_by_period(fdf, cat.genres, period=10)
    ui.chart(viz.genre_heatmap(by_decade, metric_key, 10))
    if f.years[1] >= an.CURRENT_YEAR - 5:
        st.caption(f"The {an.CURRENT_YEAR // 10 * 10}s are still in progress, so their "
                   "counts are not comparable with complete decades.")

    if picked:
        _drilldown(fdf, cat, picked)


def _drilldown(fdf, cat, genre: str):
    head, clear = st.columns([5, 1], vertical_alignment="bottom")
    with head:
        ui.section(f"Best rated {genre} titles",
                   "Rated titles with 10,000+ votes in the current selection, by rating")
    clear.button("Clear", key="gn_clear", width="stretch",
                 on_click=_clear_pick)
    bit = an.genre_bit(genre, cat.genres)
    sub = fdf[((fdf["genre_mask"] & bit) != 0) & (fdf["votes"] >= 10_000)]
    if sub.empty:
        st.caption("No titles in this genre have 10,000+ votes in the current selection.")
        return
    sub = sub.sort_values(["rating", "votes"], ascending=False).head(25)
    st.dataframe(
        sub.assign(type=sub["title_type"].map(ui.type_label),
                   genres=sub["genres"].str.replace(",", ", "))[
            ["title", "year", "type", "genres", "rating", "votes"]],
        hide_index=True,
        column_config={"title": st.column_config.TextColumn("Title", width="large"),
                       "year": st.column_config.NumberColumn("Year", format="%d"),
                       "type": "Type", "genres": "Genres",
                       "rating": st.column_config.NumberColumn("Rating", format="%.1f"),
                       "votes": st.column_config.NumberColumn("Votes", format="localized")})


def _clear_pick():
    st.session_state.pop("gn_pick", None)
    # A new chart key drops the bar selection along with the pick.
    st.session_state["gn_gen"] = st.session_state.get("gn_gen", 0) + 1
