import html

import pandas as pd
import streamlit as st

import analytics as an
import components as ui
import visualizations as viz


@st.cache_data(show_spinner="Counting credits...", max_entries=32)
def _top_people(_fdf: pd.DataFrame, key, role: str, sort: str, min_titles: int):
    # `key` stands in for the filtered frame when hashing the cache entry.
    return an.top_people(_fdf, role, n=15, sort=sort, min_titles=min_titles)


@st.cache_data(show_spinner=False, max_entries=64)
def _search(text: str):
    return an.search_people(text)


def render(cat, fdf, f):
    ui.page_head("People & credits", ui.scope_text(f, len(fdf)))
    if not cat.has.get("credits"):
        st.info("title.principals.tsv and title.crew.tsv were not found, so credits "
                "are unavailable.")
        return
    st.caption("Directors and writers come from title.crew (complete lists). Cast and "
               "other crew come from title.principals, which only holds the top-billed "
               "people for each title, so smaller roles are missing.")

    c1, c2, c3, c4 = st.columns([1.6, 1.8, 2.4, 1.4], vertical_alignment="bottom")
    role = c1.selectbox("Role", list(an.ROLE_LABELS), format_func=an.ROLE_LABELS.get,
                        key="pp_role")
    sort = c2.segmented_control("Rank by", ["Titles", "Mean rating"], default="Titles",
                                key="pp_sort", required=True)
    floor = c3.select_slider("Count titles with", [0, 100, 1_000, 10_000], value=1_000,
                             key="pp_floor", format_func=lambda v: "any votes" if v == 0
                             else f"{ui.fmt_compact(v)}+ votes",
                             help="Without a floor, the list is dominated by prolific "
                                  "makers of titles very few people have rated.")
    min_titles = c4.number_input("Min. rated titles", 2, 50, 5, key="pp_min",
                                 disabled=sort == "Titles",
                                 help="Only used when ranking by mean rating.")

    if fdf.empty:
        ui.empty_state()
    else:
        sort_key = "titles" if sort == "Titles" else "rating"
        pool = fdf[fdf["votes"] >= floor] if floor else fdf
        top = _top_people(pool, (f, floor, len(pool)), role, sort_key, int(min_titles))
        if top.empty:
            st.caption("Nobody in this role meets the threshold for the current selection.")
        else:
            event = ui.chart(viz.people_bars(top, sort_key, an.ROLE_LABELS[role]),
                             key="pp_bars", select=True)
            points = event.selection.get("points", []) if event and event.selection else []
            if points:
                # Bars are drawn bottom-up, so point 0 is the last row of `top`.
                nid = int(top["nid"].iloc[len(top) - 1 - points[0]["point_index"]])
                if st.session_state.get("pp_nid") != nid:
                    st.session_state["pp_nid"] = nid
                    st.session_state["pp_query"] = top.loc[top["nid"] == nid, "name"].iloc[0]

    ui.section("Look up a person")
    query = st.text_input("Name", key="pp_query", placeholder="e.g. Satyajit Ray",
                          label_visibility="collapsed")
    matches = _search(query) if query.strip() else None
    if matches is not None and matches.empty:
        st.caption("No one by that name has credits in this catalogue.")
        return
    if matches is None:
        return

    def describe(i):
        r = matches.iloc[i]
        years = ""
        if not pd.isna(r["birth_year"]):
            years = f" ({int(r['birth_year'])}–{'' if pd.isna(r['death_year']) else int(r['death_year'])})"
        prof = (r["professions"] or "").replace("_", " ").replace(",", ", ")
        return f"{r['name']}{years} · {prof} · {int(r['n_titles']):,} titles"

    wanted = st.session_state.get("pp_nid")
    index = int((matches["nid"] == wanted).idxmax()) if wanted in set(matches["nid"]) else 0
    choice = st.selectbox("Matches", range(len(matches)), index=index, format_func=describe,
                          key=f"pp_pick_{query}", label_visibility="collapsed")
    person = matches.iloc[choice]
    st.session_state["pp_nid"] = int(person["nid"])
    _profile(cat, person)


def _profile(cat, person):
    credits = an.person_credits(int(person["nid"]), cat.titles)
    if credits.empty:
        st.caption("This person's credits are all on titles outside the dashboard "
                   "(TV episodes, video games or adult titles).")
        return
    rated = credits[credits["rating"].notna()]
    years = credits["year"].dropna()
    span = f"{int(years.min())}–{int(years.max())}" if len(years) else "—"
    weighted = ((rated["rating"] * rated["votes"]).sum() / rated["votes"].sum()
                if len(rated) else None)
    st.markdown(f'<div class="detail-title" style="margin-top:10px">{html.escape(person["name"])}</div>'
                f'<div class="detail-meta"><a href="{ui.person_url(int(person["nid"]))}" '
                f'target="_blank" style="color:#666666">IMDb profile ↗</a></div>',
                unsafe_allow_html=True)
    ui.kpi_strip([
        ("Credited titles", ui.fmt_int(len(credits)), "in this dashboard's catalogue", ""),
        ("Active", span, "by release year", ""),
        ("Mean rating", "—" if rated.empty else f"{rated['rating'].mean():.2f}",
         f"over {len(rated):,} rated titles", "accent"),
        ("Vote-weighted", "—" if weighted is None else f"{weighted:.2f}",
         "each title weighted by its votes", ""),
    ])
    st.caption("Credits here ignore the sidebar filters so the full career is shown.")
    left, right = st.columns([3, 2], gap="large")
    with left:
        ui.chart(viz.career_scatter(credits, person["name"]))
    with right:
        table = credits.sort_values("year", ascending=False, na_position="last")
        st.dataframe(
            table.assign(role=table["role"].str.replace("_", " "))[
                ["title", "year", "role", "rating", "votes"]],
            hide_index=True, height=360,
            column_config={"title": st.column_config.TextColumn("Title", width="medium"),
                           "year": st.column_config.NumberColumn("Year", format="%d"),
                           "role": "Credit",
                           "rating": st.column_config.NumberColumn("Rating", format="%.1f"),
                           "votes": st.column_config.NumberColumn("Votes", format="compact")})
