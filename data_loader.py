"""Locate the IMDb TSV dumps, convert them once into compact Parquet files, and
load those files for the app.

The raw dumps are ~10 GB and are never modified. On first run DuckDB streams
them into `.imdb_cache/` (a few hundred MB). Every later run reads only the
Parquet files, and Streamlit caches the parsed result in memory.

Scope decisions made at build time:
  * TV episodes are left out of the title table (they are ~10M of the ~13M rows
    and are not standalone titles); they are summarised per series instead.
  * Adult titles, video games and the single `tvPilot` row are excluded.
  * `tconst` / `nconst` are stored as integers (tt0111161 -> 111161) to keep the
    joins cheap; `imdb_id()` turns them back into IMDb identifiers.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path

import duckdb
import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq
import streamlit as st

DATA_DIR = Path(os.environ.get("IMDB_DATA_DIR", Path(__file__).parent))
CACHE_DIR = Path(__file__).parent / ".imdb_cache"
CACHE_VERSION = 1

DATASETS = {
    "basics": "title.basics",
    "ratings": "title.ratings",
    "crew": "title.crew",
    "principals": "title.principals",
    "names": "name.basics",
    "episodes": "title.episode",
    "akas": "title.akas",
}

TITLE_TYPES = [
    "movie", "tvMovie", "short", "video",
    "tvSeries", "tvMiniSeries", "tvSpecial", "tvShort",
]
TITLE_TYPE_LABELS = {
    "movie": "Movie", "tvMovie": "TV movie", "short": "Short", "video": "Video",
    "tvSeries": "TV series", "tvMiniSeries": "Mini-series",
    "tvSpecial": "TV special", "tvShort": "TV short",
}
# Credits we keep from title.principals. Directors and writers come from
# title.crew when it exists, because crew lists every director/writer while
# principals only lists the top-billed few.
CAST_AND_CREW_ROLES = [
    "actor", "actress", "producer", "composer", "cinematographer",
    "editor", "production_designer", "casting_director",
]

COLUMNS = {
    "basics": {"tconst": "VARCHAR", "titleType": "VARCHAR", "primaryTitle": "VARCHAR",
               "originalTitle": "VARCHAR", "isAdult": "VARCHAR", "startYear": "VARCHAR",
               "endYear": "VARCHAR", "runtimeMinutes": "VARCHAR", "genres": "VARCHAR"},
    "ratings": {"tconst": "VARCHAR", "averageRating": "DOUBLE", "numVotes": "BIGINT"},
    "crew": {"tconst": "VARCHAR", "directors": "VARCHAR", "writers": "VARCHAR"},
    "principals": {"tconst": "VARCHAR", "ordering": "INTEGER", "nconst": "VARCHAR",
                   "category": "VARCHAR", "job": "VARCHAR", "characters": "VARCHAR"},
    "names": {"nconst": "VARCHAR", "primaryName": "VARCHAR", "birthYear": "VARCHAR",
              "deathYear": "VARCHAR", "primaryProfession": "VARCHAR",
              "knownForTitles": "VARCHAR"},
    "episodes": {"tconst": "VARCHAR", "parentTconst": "VARCHAR",
                 "seasonNumber": "VARCHAR", "episodeNumber": "VARCHAR"},
}


def imdb_id(num: int, prefix: str = "tt") -> str:
    """111161 -> 'tt0111161' (IMDb pads ids to at least 7 digits)."""
    return f"{prefix}{int(num):07d}"


def find_sources() -> dict[str, Path]:
    """Return the dataset files that exist, preferring .tsv over .tsv.gz."""
    found = {}
    for key, stem in DATASETS.items():
        for suffix in (".tsv", ".tsv.gz"):
            path = DATA_DIR / f"{stem}{suffix}"
            if path.exists():
                found[key] = path
                break
    return found


def _reader(path: Path, key: str) -> str:
    # IMDb files are tab-separated with no quoting at all: titles can contain
    # stray quote characters, so quoting/escaping must be switched off.
    # DuckDB decompresses .gz transparently.
    cols = "{" + ", ".join(f"'{c}': '{t}'" for c, t in COLUMNS[key].items()) + "}"
    p = str(path).replace("'", "''")
    return (f"read_csv('{p}', delim='\\t', header=true, quote='', escape='', "
            f"nullstr='\\N', columns={cols}, ignore_errors=true)")


def _fingerprint(sources: dict[str, Path]) -> dict:
    return {
        "version": CACHE_VERSION,
        "sources": {k: [p.name, p.stat().st_size, int(p.stat().st_mtime)]
                    for k, p in sorted(sources.items()) if k != "akas"},
    }


def cache_is_current(sources: dict[str, Path]) -> bool:
    meta = CACHE_DIR / "meta.json"
    if not meta.exists():
        return False
    try:
        stored = json.loads(meta.read_text())
    except json.JSONDecodeError:
        return False
    return stored.get("fingerprint") == _fingerprint(sources)


def build_cache(sources: dict[str, Path], log=print) -> dict:
    """Convert the raw dumps into Parquet. Takes a few minutes for the full set."""
    if "basics" not in sources:
        raise FileNotFoundError(
            f"title.basics.tsv(.gz) not found in {DATA_DIR}. It is required.")
    CACHE_DIR.mkdir(exist_ok=True)
    started = time.time()
    con = duckdb.connect()
    con.execute(f"SET temp_directory='{CACHE_DIR / 'tmp'}'")
    q = lambda key: _reader(sources[key], key)  # noqa: E731
    type_list = ", ".join(f"'{t}'" for t in TITLE_TYPES)

    log("Reading title.basics")
    con.execute(f"""
        CREATE TABLE basics AS
        SELECT CAST(substr(tconst, 3) AS INTEGER) AS tid,
               titleType AS title_type,
               primaryTitle AS title,
               originalTitle AS original_title,
               TRY_CAST(startYear AS SMALLINT) AS year,
               TRY_CAST(endYear AS SMALLINT) AS end_year,
               CASE WHEN TRY_CAST(runtimeMinutes AS INTEGER) > 0
                    THEN TRY_CAST(runtimeMinutes AS INTEGER) END AS runtime,
               genres
        FROM {q('basics')}
        WHERE titleType IN ({type_list})
          AND isAdult = '0'
          AND coalesce(genres, '') NOT LIKE '%Adult%'
          AND tconst LIKE 'tt%'
    """)
    genres = [r[0] for r in con.execute(
        "SELECT DISTINCT unnest(string_split(genres, ',')) g FROM basics ORDER BY g"
    ).fetchall()]
    # One bit per genre: multi-genre filtering becomes a single bitwise AND.
    mask_sql = " + ".join(
        f"(CASE WHEN list_contains(string_split(genres, ','), '{g}') THEN {1 << i} ELSE 0 END)"
        for i, g in enumerate(genres))

    if "ratings" in sources:
        log("Joining title.ratings")
        ratings_join = f"""LEFT JOIN (
            SELECT CAST(substr(tconst, 3) AS INTEGER) AS tid,
                   averageRating AS rating, numVotes AS votes
            FROM {q('ratings')}) r USING (tid)"""
        rating_cols = "r.rating, r.votes"
    else:
        ratings_join, rating_cols = "", "NULL::DOUBLE AS rating, NULL::BIGINT AS votes"

    if "episodes" in sources:
        log("Summarising title.episode per series")
        episode_join = f"""LEFT JOIN (
            SELECT CAST(substr(parentTconst, 3) AS INTEGER) AS tid,
                   count(*) AS episodes,
                   count(DISTINCT TRY_CAST(seasonNumber AS INTEGER)) AS seasons
            FROM {q('episodes')} GROUP BY 1) e USING (tid)"""
        episode_cols = "e.episodes, e.seasons"
    else:
        episode_join, episode_cols = "", "NULL::BIGINT AS episodes, NULL::BIGINT AS seasons"

    log("Writing titles.parquet")
    con.execute(f"""
        CREATE TABLE titles AS
        SELECT b.*, CAST(coalesce({mask_sql}, 0) AS INTEGER) AS genre_mask,
               {rating_cols}, {episode_cols}
        FROM basics b {ratings_join} {episode_join}
    """)
    con.execute(f"COPY titles TO '{CACHE_DIR / 'titles.parquet'}' (FORMAT parquet)")
    n_titles = con.execute("SELECT count(*) FROM titles").fetchone()[0]
    con.execute("DROP TABLE basics")

    have_credits = "principals" in sources or "crew" in sources
    n_credits = n_people = 0
    if have_credits:
        parts = []
        if "principals" in sources:
            log("Reading title.principals (largest file, takes a while)")
            roles = list(CAST_AND_CREW_ROLES)
            if "crew" not in sources:
                roles += ["director", "writer"]
            role_list = ", ".join(f"'{r}'" for r in roles)
            # characters looks like ["Name"] or ["A","B"]; flatten it to "A / B".
            parts.append(f"""
                SELECT CAST(substr(tconst, 3) AS INTEGER) AS tid,
                       CAST(substr(nconst, 3) AS INTEGER) AS nid,
                       category AS role,
                       CAST(ordering AS SMALLINT) AS billing,
                       nullif(replace(trim(characters, '[]"'), '","', ' / '), '') AS characters
                FROM {q('principals')}
                WHERE category IN ({role_list})""")
        if "crew" in sources:
            log("Reading title.crew")
            for col, role in (("directors", "director"), ("writers", "writer")):
                parts.append(f"""
                    SELECT CAST(substr(tconst, 3) AS INTEGER) AS tid,
                           CAST(substr(n, 3) AS INTEGER) AS nid,
                           '{role}' AS role,
                           CAST(NULL AS SMALLINT) AS billing,
                           CAST(NULL AS VARCHAR) AS characters
                    FROM (SELECT tconst, unnest(string_split({col}, ',')) AS n
                          FROM {q('crew')} WHERE {col} IS NOT NULL)
                    WHERE n LIKE 'nm%'""")
        log("Writing credits.parquet")
        con.execute(f"""
            CREATE TABLE credits AS
            SELECT DISTINCT c.* FROM ({' UNION ALL '.join(parts)}) c
            SEMI JOIN titles t USING (tid)
        """)
        con.execute(f"""COPY (SELECT * FROM credits ORDER BY nid, tid)
                        TO '{CACHE_DIR / 'credits.parquet'}' (FORMAT parquet)""")
        n_credits = con.execute("SELECT count(*) FROM credits").fetchone()[0]

        if "names" in sources:
            log("Writing people.parquet")
            con.execute(f"""
                COPY (
                    SELECT n.nid, n.name, n.birth_year, n.death_year, n.professions,
                           c.n_titles
                    FROM (SELECT CAST(substr(nconst, 3) AS INTEGER) AS nid,
                                 primaryName AS name,
                                 TRY_CAST(birthYear AS SMALLINT) AS birth_year,
                                 TRY_CAST(deathYear AS SMALLINT) AS death_year,
                                 primaryProfession AS professions
                          FROM {q('names')} WHERE nconst LIKE 'nm%') n
                    JOIN (SELECT nid, count(DISTINCT tid) AS n_titles
                          FROM credits GROUP BY nid) c USING (nid)
                ) TO '{CACHE_DIR / 'people.parquet'}' (FORMAT parquet)
            """)
            n_people = con.execute(
                f"SELECT count(*) FROM '{CACHE_DIR / 'people.parquet'}'").fetchone()[0]
    con.close()

    meta = {
        "fingerprint": _fingerprint(sources),
        "genres": genres,
        "rows": {"titles": n_titles, "credits": n_credits, "people": n_people},
        "has": {
            "ratings": "ratings" in sources,
            "episodes": "episodes" in sources,
            "credits": have_credits,
            "people": have_credits and "names" in sources,
            "crew": "crew" in sources,
        },
        "snapshot": time.strftime(
            "%d %b %Y", time.localtime(sources["basics"].stat().st_mtime)),
        "built_in_seconds": round(time.time() - started, 1),
    }
    (CACHE_DIR / "meta.json").write_text(json.dumps(meta, indent=2))
    log(f"Done in {meta['built_in_seconds']} s")
    return meta


def setting(name: str) -> str | None:
    """Read a deployment setting from the environment or Streamlit secrets."""
    if os.environ.get(name):
        return os.environ[name]
    try:
        return st.secrets.get(name)
    except Exception:  # no secrets.toml configured
        return None


def download_cache(repo_id: str) -> None:
    """Fetch a prebuilt cache from a (private) Hugging Face dataset repo.
    Used on deployments, where the 10 GB of raw TSVs are not available."""
    from huggingface_hub import snapshot_download
    snapshot_download(repo_id, repo_type="dataset", local_dir=CACHE_DIR,
                      allow_patterns=["*.parquet", "meta.json"],
                      token=setting("HF_TOKEN"))


def ensure_cache() -> dict:
    """Build the Parquet cache if it is missing or stale; return its metadata."""
    sources = find_sources()
    meta_path = CACHE_DIR / "meta.json"
    if "basics" not in sources:
        # No raw files: use the prebuilt cache, downloading it if needed.
        repo = setting("IMDB_HF_DATASET")
        if not meta_path.exists() and repo:
            with st.spinner("Downloading prepared IMDb data..."):
                download_cache(repo)
        if meta_path.exists():
            return json.loads(meta_path.read_text())
        raise FileNotFoundError(
            f"title.basics.tsv(.gz) was not found in {DATA_DIR}.")
    if not cache_is_current(sources):
        with st.status("Preparing IMDb data (first run only, a few minutes)...",
                       expanded=True) as status:
            meta = build_cache(sources, log=status.write)
            status.update(label="IMDb data ready", state="complete", expanded=False)
        load_titles.clear()
        return meta
    return json.loads((CACHE_DIR / "meta.json").read_text())


@dataclass(frozen=True)
class Catalog:
    titles: pd.DataFrame
    genres: tuple[str, ...]
    has: dict
    snapshot: str


# cache_resource, not cache_data: one shared read-only frame instead of a
# pickled copy per rerun, which ran the 1 GB-class cloud hosts out of memory.
@st.cache_resource(show_spinner="Loading titles...")
def load_titles(fingerprint: str) -> pd.DataFrame:
    """Title table with compact dtypes. Numeric columns are float32 so that
    missing values are NaN and comparisons simply evaluate to False.
    Converted in Arrow to keep peak memory low; callers must not mutate it."""
    floats = ("year", "end_year", "runtime", "rating", "votes", "episodes", "seasons")
    t = pq.read_table(CACHE_DIR / "titles.parquet")
    t = t.cast(pa.schema([f.with_type(pa.float32()) if f.name in floats else f
                          for f in t.schema]))
    # Most original titles repeat the title; store those as missing.
    i = t.schema.get_field_index("original_title")
    t = t.set_column(i, "original_title", pc.if_else(
        pc.equal(t["original_title"], t["title"]), None, t["original_title"]))
    df = t.to_pandas(self_destruct=True, split_blocks=True)
    del t
    df["title_type"] = df["title_type"].astype(pd.CategoricalDtype(TITLE_TYPES))
    return df.set_index("tid", drop=False)


def get_catalog() -> Catalog:
    meta = ensure_cache()
    return Catalog(
        titles=load_titles(json.dumps(meta["fingerprint"], sort_keys=True)),
        genres=tuple(meta["genres"]),
        has=meta["has"],
        snapshot=meta["snapshot"],
    )


@st.cache_resource
def _duckdb() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    for name in ("credits", "people"):
        path = CACHE_DIR / f"{name}.parquet"
        if path.exists():
            con.execute(f"CREATE VIEW {name} AS SELECT * FROM '{path}'")
    return con


def query(sql: str, params: list | None = None, **frames) -> pd.DataFrame:
    """Run SQL against the credits/people Parquet files. Keyword DataFrames are
    registered as tables for the duration of the query (e.g. a filtered id list)."""
    cur = _duckdb().cursor()  # one cursor per call: connections aren't thread-safe
    try:
        for name, frame in frames.items():
            cur.register(name, frame)
        return cur.execute(sql, params or []).df()
    finally:
        cur.close()


if __name__ == "__main__":
    # Build (or rebuild) the cache from the command line: python data_loader.py
    srcs = find_sources()
    print("Found:", ", ".join(f"{k}={p.name}" for k, p in srcs.items()))
    build_cache(srcs)
