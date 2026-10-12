"""IMDb | Movie Analytics — entry point.

Run with:  streamlit run app.py
"""
import streamlit as st

import analytics as an
import components as ui
import data_loader
from views import explore, genres, overview, people, rankings, trends

st.set_page_config(page_title="IMDb | Movie Analytics", page_icon="assets/imdb_logo.svg",
                   layout="wide", initial_sidebar_state="expanded")
ui.inject_css()

try:
    catalog = data_loader.get_catalog()
except FileNotFoundError as err:
    ui.header("—")
    st.error(f"{err} Put the IMDb .tsv or .tsv.gz files next to app.py, or set "
             "IMDB_DATA_DIR to the folder that holds them.")
    st.stop()

# Pages are closures so they share the catalogue and the filtered frame that is
# computed once per run below.
state = {}


def page(module):
    def run():
        module.render(catalog, state["fdf"], state["filters"])
    # Streamlit identifies callable pages by name, so each needs its own.
    run.__name__ = run.__qualname__ = module.__name__.rsplit(".", 1)[-1]
    return run


pages = [
    st.Page(page(overview), title="Overview", url_path="overview", default=True),
    st.Page(page(explore), title="Explore titles", url_path="explore"),
    st.Page(page(rankings), title="Ratings & rankings", url_path="rankings"),
    st.Page(page(genres), title="Genre analysis", url_path="genres"),
    st.Page(page(trends), title="Trends over time", url_path="trends"),
]
if catalog.has.get("credits"):
    pages.append(st.Page(page(people), title="People & credits", url_path="people"))

nav = st.navigation(pages, position="sidebar")
state["filters"] = ui.sidebar_filters(catalog.genres, catalog.has.get("ratings", False))
state["fdf"] = an.apply_filters(catalog.titles, state["filters"], catalog.genres)

ui.header(catalog.snapshot)
nav.run()
