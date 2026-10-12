---
title: IMDb Movie Analytics
emoji: 🎬
colorFrom: yellow
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
short_description: Ratings, genres, careers and release history from IMDb data
---

# IMDb | Movie Analytics

Interactive Streamlit dashboard built on IMDb's non-commercial datasets
(https://developer.imdb.com/non-commercial-datasets/). Personal, non-commercial
portfolio project. Information courtesy of IMDb (https://www.imdb.com), used
with permission under the non-commercial licence.

The app loads a prepared Parquet copy of the data from a private dataset repo
(`IMDB_HF_DATASET` variable, `HF_TOKEN` secret).
