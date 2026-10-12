"""Cross-checks the pandas analytics against independent DuckDB queries on the
cached Parquet files. Run: python test_analytics.py (needs the cache built)."""
import json

import duckdb
import numpy as np
import pandas as pd

import analytics as an
import data_loader as dl

meta = json.loads((dl.CACHE_DIR / "meta.json").read_text())
GENRES = meta["genres"]
titles = dl.load_titles(json.dumps(meta["fingerprint"], sort_keys=True))
db = duckdb.connect()
T = f"'{dl.CACHE_DIR / 'titles.parquet'}'"


def sql(q):
    return db.execute(q.replace("TITLES", T)).fetchone()


def test_default_filter_counts():
    f = an.Filters()
    fdf = an.apply_filters(titles, f, GENRES)
    n, avg = sql(f"SELECT count(*), avg(rating) FROM TITLES WHERE title_type='movie' "
                 f"AND year BETWEEN {an.FIRST_YEAR} AND {an.CURRENT_YEAR}")
    assert len(fdf) == n, (len(fdf), n)
    k = an.kpis(fdf)
    assert abs(k["avg_rating"] - avg) < 1e-4, (k["avg_rating"], avg)   # NaN ratings ignored
    assert k["rated"] < k["titles"]                                      # unrated titles kept


def test_genre_any_all():
    f = an.Filters(genres=("Crime", "Drama"), genre_match="Any", types=())
    n_any = len(an.apply_filters(titles, f, GENRES))
    n_all = len(an.apply_filters(titles, an.Filters(genres=("Crime", "Drama"),
                                                     genre_match="All", types=()), GENRES))
    y = f"year BETWEEN {an.FIRST_YEAR} AND {an.CURRENT_YEAR}"
    has = lambda g: f"list_contains(string_split(genres, ','), '{g}')"  # noqa: E731
    assert n_any == sql(f"SELECT count(*) FROM TITLES WHERE {y} AND ({has('Crime')} OR {has('Drama')})")[0]
    assert n_all == sql(f"SELECT count(*) FROM TITLES WHERE {y} AND {has('Crime')} AND {has('Drama')}")[0]


def test_genre_summary_multi_count():
    fdf = an.apply_filters(titles, an.Filters(), GENRES)
    s = an.genre_summary(fdf, GENRES).set_index("genre")
    drama = sql(f"SELECT count(*), avg(rating) FROM TITLES WHERE title_type='movie' AND year "
                f"BETWEEN {an.FIRST_YEAR} AND {an.CURRENT_YEAR} AND genres LIKE '%Drama%'")
    assert s.loc["Drama", "titles"] == drama[0]
    assert abs(s.loc["Drama", "avg_rating"] - drama[1]) < 1e-4
    assert s["titles"].sum() > fdf["genres"].notna().sum()               # multi-genre counted per genre


def test_missing_value_rules():
    base = an.apply_filters(titles, an.Filters(), GENRES)
    rated_only = an.apply_filters(titles, an.Filters(rating=(1.0, 9.9)), GENRES)
    assert rated_only["rating"].notna().all() and len(rated_only) < len(base)
    long = an.apply_filters(titles, an.Filters(runtime=(200, an.RUNTIME_CAP)), GENRES)
    assert long["runtime"].min() >= 200 and long["runtime"].max() > an.RUNTIME_CAP  # open-ended top
    voted = an.apply_filters(titles, an.Filters(min_votes=1000), GENRES)
    assert voted["votes"].min() >= 1000


def test_weighted_rating():
    df = pd.DataFrame({"votes": [100.0, 1e6], "rating": [9.9, 9.0]})
    wr = an.weighted_rating(df, m=25_000, c=7.0)
    assert np.isclose(wr[0], 100 / 25_100 * 9.9 + 25_000 / 25_100 * 7.0)
    assert wr[1] > wr[0]                                                 # few votes pulled to mean


def test_known_title_and_credits():
    row = titles.loc[111161]
    assert row["title"] == "The Shawshank Redemption" and row["year"] == 1994
    credits = an.title_credits(111161)
    assert "Frank Darabont" in set(credits.loc[credits["role"] == "director", "name"])
    assert "Morgan Freeman" in set(credits["name"])


def test_top_people_counts():
    fdf = an.apply_filters(titles, an.Filters(min_votes=1000), GENRES)
    top = an.top_people(fdf, "director", n=5)
    nid = int(top.iloc[0]["nid"])
    ids = set(fdf["tid"])
    c = dl.query("SELECT DISTINCT tid FROM credits WHERE nid = ? AND role = 'director'", [nid])
    assert int(top.iloc[0]["titles"]) == len(set(c["tid"]) & ids)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
