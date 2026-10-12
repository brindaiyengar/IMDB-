import streamlit as st

import analytics as an
import components as ui
import visualizations as viz

THRESHOLDS = [1_000, 5_000, 10_000, 25_000, 50_000, 100_000, 250_000, 500_000]


def render(cat, fdf, f):
    ui.page_head("Ratings & rankings", ui.scope_text(f, len(fdf)))
    if not cat.has.get("ratings"):
        st.info("title.ratings.tsv was not found, so rankings are unavailable.")
        return

    c1, c2, c3 = st.columns([3, 1.3, 2.2], vertical_alignment="bottom")
    min_votes = c1.select_slider(
        "Minimum votes to be ranked", THRESHOLDS, value=25_000, key="rk_votes",
        format_func=ui.fmt_compact,
        help="Ratings built on a handful of votes are unreliable, so titles below "
             "this count are left out of every ranking on this page.")
    n = c2.selectbox("Show top", [10, 20, 30], key="rk_n")
    measure = c3.segmented_control(
        "Rank by", ["Rating", "Weighted rating"], key="rk_measure",
        default="Rating", required=True)

    min_votes = max(min_votes, f.min_votes)
    elig = an.eligible_titles(fdf, min_votes)
    if elig.empty:
        ui.empty_state(f"No titles in this selection have {min_votes:,}+ votes.")
        return

    mean = elig["rating"].mean()
    if measure == "Weighted rating":
        st.caption(
            f"Weighted rating = v/(v+m)·R + m/(v+m)·C, where R is the title's rating, "
            f"v its votes, m = {min_votes:,} (the threshold) and C = {mean:.2f} (mean "
            "rating of the eligible titles). Titles with fewer votes are pulled "
            "toward the mean; it is the formula IMDb publishes for its Top 250.")

    top = an.top_rated(elig, n, measure, min_votes)
    voted = an.most_voted(elig, n)
    top_ids, voted_ids = set(top["tid"]), set(voted["tid"])
    overlap = len(top_ids & voted_ids)

    ui.kpi_strip([
        ("Eligible titles", ui.fmt_int(len(elig)), f"{min_votes:,}+ votes", ""),
        ("Mean rating", f"{mean:.2f}", "across eligible titles", "accent"),
        ("Median votes", ui.fmt_compact(elig["votes"].median()), "across eligible titles", ""),
        ("In both top lists", f"{overlap} of {n}", "highest rated and most voted", ""),
    ])

    left, right = st.columns(2, gap="large")
    with left:
        value = "score" if measure == "Weighted rating" else "rating"
        ui.chart(viz.ranked_bars(top, value, "Highest rated",
                                 "Quality: the audience's average score", fmt=".2f"
                                 if value == "score" else ".1f"))
    with right:
        ui.chart(viz.ranked_bars(voted, "votes", "Most voted",
                                 "Reach: how many people rated it", color=viz.SERIES[1],
                                 fmt="votes"))
    st.caption(
        f"Votes measure how widely a title was seen and rated, not how good it is. "
        f"The most-voted list has a mean rating of {voted['rating'].mean():.2f}; the "
        f"highest-rated list has a median of {ui.fmt_compact(top['votes'].median())} votes.")

    fig, sampled = viz.rating_vote_scatter(elig, top_ids, voted_ids)
    event = ui.chart(fig, key="rk_scatter", select=True, mode=("box", "points"))
    if sampled:
        st.caption(f"Grey points are a random sample of 12,000 of {len(elig):,} titles "
                   "for drawing speed; highlighted titles are always shown and every "
                   "number on this page uses the full set.")

    picked = _selected_ids(event)
    if picked:
        sel = elig[elig["tid"].isin(picked)].sort_values("votes", ascending=False)
        ui.section(f"{len(sel):,} selected titles")
        st.dataframe(
            sel.assign(type=sel["title_type"].map(ui.type_label))[
                ["title", "year", "type", "rating", "votes"]],
            hide_index=True, height=min(36 * len(sel) + 40, 400),
            column_config={"title": "Title",
                           "year": st.column_config.NumberColumn("Year", format="%d"),
                           "type": "Type",
                           "rating": st.column_config.NumberColumn("Rating", format="%.1f"),
                           "votes": st.column_config.NumberColumn("Votes", format="localized")})


def _selected_ids(event) -> set[int]:
    if not event or not event.selection:
        return set()
    return {int(p["customdata"][2]) for p in event.selection.get("points", [])
            if p.get("customdata") is not None}
