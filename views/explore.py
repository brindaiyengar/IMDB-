import html

import pandas as pd
import streamlit as st

import analytics as an
import components as ui

SORTS = {
    "Votes": "votes", "Rating": "rating", "Release year": "year",
    "Runtime": "runtime", "Title": "title",
}
PAGE_SIZES = [25, 50, 100]


@st.cache_data(show_spinner=False, max_entries=64)
def _credits(tid: int) -> pd.DataFrame:
    return an.title_credits(tid)


def _search(fdf: pd.DataFrame, text: str) -> pd.DataFrame:
    text = text.strip()
    if not text:
        return fdf
    hit = (fdf["title"].str.contains(text, case=False, regex=False, na=False)
           | fdf["original_title"].str.contains(text, case=False, regex=False, na=False))
    return fdf[hit]


def render(cat, fdf, f):
    ui.page_head("Explore titles", ui.scope_text(f, len(fdf)))

    c1, c2, c3, c4 = st.columns([4, 2, 1.4, 1.2], vertical_alignment="bottom")
    query = c1.text_input("Search titles", key="ex_query",
                          placeholder="Title or original title, e.g. Pather Panchali")
    sort_label = c2.selectbox("Sort by", list(SORTS), key="ex_sort")
    direction = c3.selectbox("Order", ["High → low", "Low → high"], key="ex_dir")
    page_size = c4.selectbox("Rows", PAGE_SIZES, key="ex_size")

    results = _search(fdf, query)
    if results.empty:
        ui.empty_state("No titles match this search and these filters.")
        return

    col = SORTS[sort_label]
    ascending = direction == "Low → high"
    if col == "title":
        ascending = not ascending  # A→Z reads as "low → high"
    # Secondary key keeps ties stable; missing values always go last.
    results = results.sort_values([col, "votes"], ascending=[ascending, False],
                                  na_position="last")

    pages = max(1, -(-len(results) // page_size))
    # Start from page 1 whenever the result set or ordering changes.
    signature = (query, sort_label, direction, page_size, f)
    if st.session_state.get("ex_sig") != signature:
        st.session_state["ex_sig"] = signature
        st.session_state["ex_page"] = 1
    st.session_state["ex_page"] = min(st.session_state.get("ex_page", 1), pages)

    page = st.session_state["ex_page"]
    start = (page - 1) * page_size
    view = results.iloc[start:start + page_size]

    table = pd.DataFrame({
        "Title": view["title"].values,
        "Year": view["year"].values,
        "Type": [ui.type_label(t) for t in view["title_type"]],
        "Genres": view["genres"].fillna("").str.replace(",", ", ").values,
        "Runtime": view["runtime"].values,
        "Rating": view["rating"].values,
        "Votes": view["votes"].values,
    })
    event = st.dataframe(
        table, hide_index=True, on_select="rerun", selection_mode="single-row",
        key=f"ex_table_{hash(signature)}_{page}",
        height=min(36 * len(table) + 40, 640),
        column_config={
            "Title": st.column_config.TextColumn(width="large"),
            "Year": st.column_config.NumberColumn(format="%d", width="small"),
            "Runtime": st.column_config.NumberColumn(format="%d min", width="small"),
            "Rating": st.column_config.NumberColumn(format="%.1f", width="small"),
            "Votes": st.column_config.NumberColumn(format="localized", width="small"),
        })

    nav = st.columns([5, 1, 1.2, 1], vertical_alignment="center")
    nav[0].caption(f"{start + 1:,}–{start + len(view):,} of {len(results):,} titles · "
                   "select a row for details")
    nav[1].button("‹ Prev", disabled=page <= 1, width="stretch",
                  on_click=lambda: st.session_state.update(ex_page=page - 1))
    nav[2].number_input("Page", 1, pages, key="ex_page", label_visibility="collapsed")
    nav[3].button("Next ›", disabled=page >= pages, width="stretch",
                  on_click=lambda: st.session_state.update(ex_page=page + 1))

    rows = event.selection.rows if event else []
    if rows:
        st.session_state["ex_selected"] = int(view["tid"].iloc[rows[0]])
    tid = st.session_state.get("ex_selected")
    if tid is not None and tid in cat.titles.index:
        detail(cat, tid)


def detail(cat, tid: int):
    row = cat.titles.loc[tid]
    st.divider()
    left, right = st.columns([3, 2], gap="large")

    with left:
        year = "" if pd.isna(row["year"]) else str(int(row["year"]))
        if not pd.isna(row["end_year"]):
            year += f"–{int(row['end_year'])}"
        meta = [ui.type_label(row["title_type"]), year]
        if not pd.isna(row["runtime"]):
            meta.append(f"{int(row['runtime'])} min")
        if not pd.isna(row["seasons"]) and row["seasons"] > 0:
            meta.append(f"{int(row['seasons'])} seasons · {int(row['episodes']):,} episodes")
        elif not pd.isna(row["episodes"]):
            meta.append(f"{int(row['episodes']):,} episodes")
        original = ("" if row["original_title"] == row["title"] or pd.isna(row["original_title"])
                    else f'<div class="detail-meta">Original title: {html.escape(row["original_title"])}</div>')
        tags = "".join(f'<span class="tag">{html.escape(g)}</span>'
                       for g in (row["genres"] or "").split(",") if g)
        st.markdown(
            f'<div class="detail-title">{html.escape(row["title"])}</div>{original}'
            f'<div class="detail-meta">{" · ".join(html.escape(m) for m in meta if m)}</div>'
            f'<div>{tags}</div>', unsafe_allow_html=True)
        st.link_button("View on IMDb", ui.imdb_url(tid), type="secondary")

    with right:
        if pd.isna(row["rating"]):
            st.markdown('<div class="detail-meta">Not rated yet (fewer than 5 votes)</div>',
                        unsafe_allow_html=True)
        else:
            st.markdown(
                f'<div class="detail-rating">{row["rating"]:.1f}<span> / 10</span></div>'
                f'<div class="detail-meta">{int(row["votes"]):,} votes</div>',
                unsafe_allow_html=True)
            context = an.rank_context(cat.titles, row)
            if context:
                st.caption(context)

    if not cat.has.get("credits"):
        return
    credits = _credits(tid)
    if credits.empty:
        st.caption("No credits listed for this title.")
        return
    groups = [("Director", credits[credits["role"] == "director"]),
              ("Writer", credits[credits["role"] == "writer"]),
              ("Cast", credits[credits["role"].isin(["actor", "actress"])]),
              ("Music", credits[credits["role"] == "composer"]),
              ("Cinematography", credits[credits["role"] == "cinematographer"]),
              ("Editing", credits[credits["role"] == "editor"]),
              ("Producer", credits[credits["role"] == "producer"])]
    rows = []
    for label, part in groups:
        if part.empty:
            continue
        people = []
        for _, p in part.drop_duplicates("nid").iterrows():
            name = html.escape(p["name"])
            if label == "Cast" and isinstance(p["characters"], str):
                name += f' <i>as {html.escape(p["characters"])}</i>'
            people.append(name)
        rows.append(f'<div class="credit-row"><div class="k">{label}</div>'
                    f'<div class="val">{", ".join(people)}</div></div>')
    st.markdown("".join(rows), unsafe_allow_html=True)
    st.caption("Cast and crew come from IMDb's principal credits, which list the "
               "top-billed people only, not the full credits.")
