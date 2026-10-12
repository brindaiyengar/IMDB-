"""Filtering and aggregation. Everything here takes and returns DataFrames so it
can be tested without Streamlit. Charts receive aggregated frames only; raw
title rows never go to the browser except as a paginated table."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd

import data_loader

CURRENT_YEAR = date.today().year
FIRST_YEAR = 1874
RUNTIME_CAP = 240           # slider ceiling; the top value means "240 minutes or more"
VOTE_STEPS = [0, 10, 100, 1_000, 5_000, 10_000, 25_000, 50_000,
              100_000, 250_000, 500_000, 1_000_000]

ROLE_LABELS = {
    "director": "Directors", "writer": "Writers", "cast": "Cast",
    "producer": "Producers", "composer": "Composers",
    "cinematographer": "Cinematographers", "editor": "Editors",
}


@dataclass(frozen=True)
class Filters:
    years: tuple[int, int] = (FIRST_YEAR, CURRENT_YEAR)
    types: tuple[str, ...] = ("movie",)
    genres: tuple[str, ...] = ()
    genre_match: str = "Any"          # "Any" or "All" of the selected genres
    min_votes: int = 0
    rating: tuple[float, float] = (1.0, 10.0)
    runtime: tuple[int, int] = (0, RUNTIME_CAP)

    @property
    def rating_active(self) -> bool:
        return self.rating != (1.0, 10.0)

    @property
    def runtime_active(self) -> bool:
        return self.runtime != (0, RUNTIME_CAP)


def genre_bit(genre: str, all_genres) -> int:
    return 1 << list(all_genres).index(genre)


def apply_filters(df: pd.DataFrame, f: Filters, all_genres) -> pd.DataFrame:
    """Return the titles that pass every sidebar filter.

    Missing values are only excluded by a filter that actually needs the value:
    an untouched rating range keeps unrated titles, an untouched runtime range
    keeps titles without a runtime. Titles without a release year, and titles
    announced for future years, are always outside the year range.
    """
    keep = df["year"].between(f.years[0], f.years[1]).to_numpy()
    if f.types:
        keep = keep & df["title_type"].isin(f.types).to_numpy()
    if f.genres:
        bits = sum(genre_bit(g, all_genres) for g in f.genres)
        masked = df["genre_mask"].to_numpy() & bits
        keep = keep & ((masked == bits) if f.genre_match == "All" else (masked != 0))
    if f.min_votes > 0:
        keep = keep & (df["votes"] >= f.min_votes).to_numpy()
    if f.rating_active:
        keep = keep & df["rating"].between(*f.rating).to_numpy()
    if f.runtime_active:
        rt = df["runtime"]
        hi = np.inf if f.runtime[1] >= RUNTIME_CAP else f.runtime[1]
        keep = keep & ((rt >= f.runtime[0]) & (rt <= hi)).to_numpy()
    return df[keep]


# ----------------------------------------------------------------- overview

def kpis(fdf: pd.DataFrame, best_min_votes: int = 25_000) -> dict:
    rated = fdf[fdf["rating"].notna()]
    eligible = rated[rated["votes"] >= best_min_votes]
    best = (eligible.sort_values(["rating", "votes"], ascending=False).iloc[0]
            if len(eligible) else None)
    genre_present = int(np.bitwise_or.reduce(fdf["genre_mask"].to_numpy())) if len(fdf) else 0
    return {
        "titles": len(fdf),
        "movies": int((fdf["title_type"] == "movie").sum()),
        "rated": len(rated),
        "avg_rating": rated["rating"].mean() if len(rated) else None,
        "median_votes": rated["votes"].median() if len(rated) else None,
        "best": best,
        "best_min_votes": best_min_votes,
        "genres": bin(genre_present).count("1"),
    }


def titles_per_year(fdf: pd.DataFrame) -> pd.DataFrame:
    g = fdf.groupby("year", observed=True)
    out = pd.DataFrame({"titles": g.size(), "rated": g["rating"].count()})
    out.index = out.index.astype(int)
    return out.reset_index()


def rating_distribution(fdf: pd.DataFrame) -> pd.DataFrame:
    """Counts per 0.1 rating step (IMDb publishes ratings to one decimal)."""
    r = fdf["rating"].dropna().round(1)
    return r.value_counts().sort_index().rename_axis("rating").reset_index(name="titles")


def runtime_distribution(fdf: pd.DataFrame, step: int = 5) -> pd.DataFrame:
    rt = fdf["runtime"].dropna()
    binned = (np.minimum(rt, RUNTIME_CAP) // step * step).astype(int)
    out = binned.value_counts().sort_index().rename_axis("runtime").reset_index(name="titles")
    out["label"] = [f"{m}–{m + step - 1} min" if m < RUNTIME_CAP else f"{RUNTIME_CAP}+ min"
                    for m in out["runtime"]]
    return out


def rating_vote_density(fdf: pd.DataFrame) -> pd.DataFrame:
    """2-D counts: rating (0.5 bands) x votes (log10 bands). Aggregating keeps
    the chart exact for any number of titles."""
    rated = fdf[fdf["rating"].notna() & (fdf["votes"] > 0)]
    if rated.empty:
        return pd.DataFrame(columns=["rating_bin", "votes_bin", "titles"])
    rb = (np.floor(rated["rating"] * 2) / 2).clip(upper=9.5)
    vb = np.floor(np.log10(rated["votes"]) * 4) / 4
    return (pd.DataFrame({"rating_bin": rb, "votes_bin": vb})
            .value_counts().rename("titles").reset_index())


# ----------------------------------------------------------------- genres

def genre_flags(fdf: pd.DataFrame, all_genres) -> pd.DataFrame:
    """Boolean title x genre matrix from the bitmask (one column per genre)."""
    m = fdf["genre_mask"].to_numpy()
    return pd.DataFrame({g: (m & (1 << i)) != 0 for i, g in enumerate(all_genres)},
                        index=fdf.index)


def genre_summary(fdf: pd.DataFrame, all_genres) -> pd.DataFrame:
    """Per-genre counts and rating stats. A title is counted once in every one
    of its genres, so the genre totals add up to more than the title count."""
    flags = genre_flags(fdf, all_genres)
    rating, votes = fdf["rating"].to_numpy(), fdf["votes"].to_numpy()
    rows = []
    for g in all_genres:
        sel = flags[g].to_numpy()
        n = int(sel.sum())
        if not n:
            continue
        r = rating[sel]
        r = r[~np.isnan(r)]
        rows.append({
            "genre": g, "titles": n, "rated": len(r),
            "share": n / len(fdf),
            "avg_rating": float(r.mean()) if len(r) else np.nan,
            "median_votes": float(np.nanmedian(votes[sel])) if len(r) else np.nan,
        })
    return pd.DataFrame(rows).sort_values("titles", ascending=False, ignore_index=True)


def genre_by_period(fdf: pd.DataFrame, all_genres, period: int = 10,
                    min_rated: int = 20) -> pd.DataFrame:
    """Long frame genre x period with title count, share of the period's
    titles, and average rating (blank when fewer than `min_rated` ratings)."""
    flags = genre_flags(fdf, all_genres)
    bucket = (fdf["year"] // period * period).astype(int)
    totals = bucket.value_counts()
    rated = fdf["rating"].notna()
    out = []
    for g in all_genres:
        sel = flags[g]
        if not sel.any():
            continue
        grp = fdf[sel].groupby(bucket[sel])
        part = pd.DataFrame({
            "titles": grp.size(),
            "rated": grp["rating"].count(),
            "avg_rating": grp["rating"].mean(),
        })
        part["avg_rating"] = part["avg_rating"].where(part["rated"] >= min_rated)
        part["share"] = part["titles"] / totals.reindex(part.index)
        part["genre"] = g
        out.append(part.rename_axis("period").reset_index())
    if not out:
        return pd.DataFrame(columns=["period", "titles", "rated", "avg_rating", "share", "genre"])
    del rated
    return pd.concat(out, ignore_index=True)


# ----------------------------------------------------------------- rankings

def weighted_rating(df: pd.DataFrame, m: int, c: float) -> pd.Series:
    """Bayesian average used by IMDb's Top 250 formula:
    WR = v/(v+m)·R + m/(v+m)·C. Titles with few votes are pulled toward C."""
    v, r = df["votes"], df["rating"]
    return v / (v + m) * r + m / (v + m) * c


def eligible_titles(fdf: pd.DataFrame, min_votes: int) -> pd.DataFrame:
    return fdf[fdf["rating"].notna() & (fdf["votes"] >= max(min_votes, 1))]


def top_rated(elig: pd.DataFrame, n: int, measure: str, m: int) -> pd.DataFrame:
    if measure == "Weighted rating":
        c = elig["rating"].mean()
        elig = elig.assign(score=weighted_rating(elig, max(m, 1), c))
    else:
        elig = elig.assign(score=elig["rating"])
    return elig.sort_values(["score", "votes"], ascending=False).head(n)


def most_voted(elig: pd.DataFrame, n: int) -> pd.DataFrame:
    return elig.sort_values("votes", ascending=False).head(n)


def rank_context(df: pd.DataFrame, row: pd.Series, min_votes: int = 1_000) -> str | None:
    """'#3 of 412 rated movies from 1994 with 1,000+ votes' for the detail view."""
    if pd.isna(row["rating"]) or pd.isna(row["year"]) or row["votes"] < min_votes:
        return None
    peers = df[(df["year"] == row["year"]) & (df["title_type"] == row["title_type"])
               & (df["votes"] >= min_votes)]
    rank = int((peers["rating"] > row["rating"]).sum()) + 1
    kind = data_loader.TITLE_TYPE_LABELS[row["title_type"]].lower()
    return f"#{rank:,} of {len(peers):,} rated {kind}s from {int(row['year'])} with {min_votes:,}+ votes"


# ----------------------------------------------------------------- trends

def rating_by_year(fdf: pd.DataFrame, min_votes: int, min_titles: int = 20) -> pd.DataFrame:
    rated = fdf[fdf["rating"].notna() & (fdf["votes"] >= max(min_votes, 1))]
    g = rated.groupby("year")["rating"]
    out = pd.DataFrame({"titles": g.size(), "mean": g.mean(), "median": g.median(),
                        "q1": g.quantile(0.25), "q3": g.quantile(0.75)})
    out = out[out["titles"] >= min_titles]
    out.index = out.index.astype(int)
    return out.rename_axis("year").reset_index()


def runtime_by_year(fdf: pd.DataFrame, min_titles: int = 20) -> pd.DataFrame:
    rt = fdf[fdf["runtime"].notna()]
    g = rt.groupby("year")["runtime"]
    out = pd.DataFrame({"titles": g.size(), "median": g.median(),
                        "q1": g.quantile(0.25), "q3": g.quantile(0.75)})
    out = out[out["titles"] >= min_titles]
    out.index = out.index.astype(int)
    return out.rename_axis("year").reset_index()


def genre_share_by_year(fdf: pd.DataFrame, all_genres, genres) -> pd.DataFrame:
    flags = genre_flags(fdf, all_genres)
    year = fdf["year"].astype(int)
    totals = year.value_counts()
    frames = []
    for g in genres:
        counts = year[flags[g]].value_counts()
        frames.append(pd.DataFrame({
            "year": counts.index, "genre": g, "titles": counts.values,
            "share": counts.values / totals.reindex(counts.index).values}))
    if not frames:
        return pd.DataFrame(columns=["year", "genre", "titles", "share"])
    return pd.concat(frames).sort_values("year", ignore_index=True)


# ----------------------------------------------------------------- people

def _role_clause(role: str) -> str:
    return "role IN ('actor', 'actress')" if role == "cast" else "role = ?"


def top_people(fdf: pd.DataFrame, role: str, n: int = 15, sort: str = "titles",
               min_titles: int = 3) -> pd.DataFrame:
    """People with the most credits (in `role`) among the filtered titles."""
    ids = fdf[["tid", "rating", "votes"]].reset_index(drop=True)
    params = [] if role == "cast" else [role]
    order = "titles DESC, avg_rating DESC" if sort == "titles" else "avg_rating DESC, titles DESC"
    having = "" if sort == "titles" else f"HAVING count(i.rating) >= {int(min_titles)}"
    return data_loader.query(f"""
        WITH c AS (
            SELECT DISTINCT c.nid, c.tid FROM credits c
            JOIN ids USING (tid) WHERE {_role_clause(role)})
        SELECT c.nid, coalesce(p.name, 'nm' || lpad(c.nid::VARCHAR, 7, '0')) AS name,
               count(*) AS titles, count(i.rating) AS rated,
               avg(i.rating) AS avg_rating, sum(i.votes) AS total_votes
        FROM c JOIN ids i USING (tid)
        LEFT JOIN {'people' if _has_people() else '(SELECT NULL::INT nid, NULL name)'} p USING (nid)
        GROUP BY ALL {having}
        ORDER BY {order} LIMIT {int(n)}
    """, params, ids=ids)


def _has_people() -> bool:
    return (data_loader.CACHE_DIR / "people.parquet").exists()


def search_people(text: str, limit: int = 25) -> pd.DataFrame:
    if not text.strip() or not _has_people():
        return pd.DataFrame(columns=["nid", "name", "birth_year", "death_year",
                                     "professions", "n_titles"])
    return data_loader.query("""
        SELECT * FROM people WHERE name ILIKE ?
        ORDER BY (lower(name) = lower(?)) DESC, n_titles DESC LIMIT ?
    """, [f"%{text.strip()}%", text.strip(), limit])


def person_credits(nid: int, titles: pd.DataFrame) -> pd.DataFrame:
    c = data_loader.query(
        "SELECT tid, role, characters FROM credits WHERE nid = ?", [int(nid)])
    roles = (c.groupby("tid")
             .agg(role=("role", lambda s: ", ".join(sorted(set(s)))),
                  characters=("characters", lambda s: " / ".join(s.dropna().unique())))
             .reset_index())
    cols = ["tid", "title", "year", "title_type", "genres", "rating", "votes"]
    return titles.loc[titles.index.intersection(roles["tid"]), cols].reset_index(
        drop=True).merge(roles, on="tid")


def title_credits(tid: int) -> pd.DataFrame:
    people = "people" if _has_people() else "(SELECT NULL::INT nid, NULL name)"
    return data_loader.query(f"""
        SELECT c.nid, coalesce(p.name, 'nm' || lpad(c.nid::VARCHAR, 7, '0')) AS name,
               c.role, c.billing, c.characters
        FROM credits c LEFT JOIN {people} p USING (nid)
        WHERE c.tid = ? ORDER BY c.billing NULLS LAST, c.role
    """, [int(tid)])
