# IMDb | Movie Analytics

An interactive Streamlit dashboard for exploring IMDb's official datasets: 2.7 million titles,
23 million credits and 5.3 million people.

## Pages

- **Overview** – summary numbers, titles released per year, rating and runtime distributions,
  rating against votes.
- **Explore titles** – search, sort and page through titles; select one for ratings, rank among
  its peers, and credits.
- **Ratings & rankings** – highest rated vs most voted, optional weighted (Bayesian) rating,
  box-select on a rating-vs-popularity scatter plot.
- **Genre analysis** – titles and average rating per genre, genre-by-decade heatmap, drill-down.
- **Trends over time** – released vs rated titles, rating and runtime by year, genre share.
- **People & credits** – most credited people by role, person search and career profiles.

Sidebar filters (title type, year, genre, votes, rating, runtime) apply to every page.

## Run locally

1. Download the TSV files from https://datasets.imdbws.com (`.tsv` or `.tsv.gz`) into the project
   folder, or point `IMDB_DATA_DIR` at the folder that holds them. Only `title.basics` is
   required; pages that need other files are hidden when those files are missing.
2. Install and run:

   ```bash
   python -m venv .venv
   .venv/bin/pip install -r requirements.txt
   .venv/bin/streamlit run app.py
   ```

The first run converts the TSVs (about 10 GB) into compact Parquet files in `.imdb_cache/`
(about 440 MB) with DuckDB. Later runs read only the Parquet files.

## How it works

| File | Role |
|---|---|
| `data_loader.py` | Finds the dumps, builds the Parquet cache with DuckDB, loads it with caching |
| `analytics.py` | Filters and aggregations (pure pandas/DuckDB, testable without Streamlit) |
| `visualizations.py` | Plotly figures and the dark IMDb-style theme |
| `components.py` | Header, sidebar filters, KPI strip, styling |
| `views/` | One module per page |
| `test_analytics.py` | Cross-checks the analytics against independent DuckDB queries |

Data handling notes:

- IMDb's `\N` is read as missing. Averages use rated titles only.
- TV episodes, adult titles and video games are excluded.
- A title with several genres counts once in each genre.
- Cast credits come from `title.principals`, which lists top-billed people only. Directors and
  writers come from `title.crew`.

## Data licence

Information courtesy of IMDb (https://www.imdb.com). Used with permission under the
[IMDb non-commercial datasets licence](https://developer.imdb.com/non-commercial-datasets/).
This project is for personal, non-commercial use. The data files are not included in this
repository.
