"""Plotly figures. Each function takes an aggregated frame and returns a figure
styled by the shared `imdb` template, so pages never set colours themselves."""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio

YELLOW = "#F5C518"
INK = "#222222"
MUTED = "#666666"
FAINT = "#A3A3A0"
GRID = "#EDEDEB"
SURFACE = "#FFFFFF"
CONTEXT = "#D3D3D0"   # de-emphasised marks (e.g. "all titles" behind "rated")
# Categorical order, validated for colour-vision deficiency.
# Yellow is the brand accent and always slot 1; colours follow the entity.
SERIES = [YELLOW, "#3987E5", "#D95926", "#199E70", "#9085E9", "#E66767"]
# Single-hue sequential ramp (page background -> brand yellow) for heatmaps.
SEQUENTIAL = [[0, "#F4F3EF"], [0.25, "#F3E2A0"], [0.5, "#F4D366"],
              [0.75, "#F5CA35"], [1, YELLOW]]

PLOTLY_CONFIG = {
    "displaylogo": False,
    "modeBarButtonsToRemove": ["lasso2d", "autoScale2d", "toggleSpikelines",
                               "hoverClosestCartesian", "hoverCompareCartesian"],
}

pio.templates["imdb"] = go.layout.Template(layout=go.Layout(
    font=dict(family="Inter, system-ui, sans-serif", size=12, color=MUTED),
    title=dict(font=dict(size=15, color=INK), x=0, xanchor="left", y=0.97,
               yanchor="top", pad=dict(l=2)),
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    colorway=SERIES,
    margin=dict(l=8, r=12, t=78, b=8),
    xaxis=dict(gridcolor=GRID, linecolor="#D6D6D4", zeroline=False, ticks="",
               title=dict(font=dict(size=12, color=MUTED)), automargin=True),
    yaxis=dict(gridcolor=GRID, linecolor="rgba(0,0,0,0)", zeroline=False, ticks="",
               title=dict(font=dict(size=12, color=MUTED)), automargin=True),
    hoverlabel=dict(bgcolor="#FFFFFF", bordercolor="#E2E2E0",
                    font=dict(family="Inter, system-ui, sans-serif", size=12, color=INK)),
    legend=dict(orientation="h", x=1, xanchor="right", y=1.0, yanchor="bottom",
                bgcolor="rgba(0,0,0,0)", font=dict(color=MUTED)),
    bargap=0.18,
    barcornerradius=3,
))
pio.templates.default = "imdb"


def _titled(fig: go.Figure, title: str, subtitle: str | None = None,
            height: int = 340) -> go.Figure:
    t = dict(text=title)
    if subtitle:
        t["subtitle"] = dict(text=subtitle, font=dict(size=12, color=MUTED))
    fig.update_layout(title=t, height=height)
    return fig


def _label(row) -> str:
    year = "" if pd.isna(row["year"]) else f" ({int(row['year'])})"
    title = row["title"] if len(row["title"]) <= 42 else row["title"][:40] + "…"
    return f"{title}{year}"


def empty_figure(message: str, height: int = 300) -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(text=message, showarrow=False, font=dict(color=MUTED, size=13),
                       x=0.5, y=0.5, xref="paper", yref="paper")
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    fig.update_layout(height=height)
    return fig


# ----------------------------------------------------------------- overview

def titles_per_year(df: pd.DataFrame, partial_year: int | None = None,
                    rangeslider: bool = False, height: int = 320) -> go.Figure:
    fig = go.Figure()
    fig.add_bar(x=df["year"], y=df["titles"], name="Released", marker_color=YELLOW,
                customdata=df[["rated"]],
                hovertemplate="<b>%{x}</b><br>%{y:,} titles released"
                              "<br>%{customdata[0]:,} with a rating<extra></extra>")
    fig.update_layout(bargap=0.08, barcornerradius=1, showlegend=False)
    fig.update_yaxes(title_text="Titles", tickformat="~s")
    fig.update_xaxes(title_text=None)
    if partial_year is not None and partial_year in set(df["year"]):
        fig.add_vrect(x0=partial_year - 0.5, x1=partial_year + 0.5,
                      fillcolor="#000000", opacity=0.04, line_width=0,
                      annotation_text="partial year", annotation_position="top left",
                      annotation_font=dict(size=11, color=MUTED))
    if rangeslider:
        fig.update_xaxes(rangeslider=dict(visible=True, thickness=0.07,
                                          bgcolor="#FAFAFA", bordercolor=GRID))
    return _titled(fig, "Titles released per year",
                   "Bars count every title in the selection, rated or not", height)


def rating_histogram(df: pd.DataFrame, avg: float | None) -> go.Figure:
    fig = go.Figure()
    fig.add_bar(x=df["rating"], y=df["titles"], marker_color=YELLOW,
                hovertemplate="Rating %{x:.1f}<br>%{y:,} titles<extra></extra>")
    fig.update_layout(bargap=0.15, barcornerradius=1, showlegend=False)
    if avg is not None:
        fig.add_vline(x=avg, line=dict(color=INK, width=1, dash="dot"),
                      annotation_text=f"mean {avg:.2f}", annotation_position="top",
                      annotation_font=dict(size=11, color=INK))
    fig.update_xaxes(title_text="IMDb rating", range=[0.8, 10.2], dtick=1)
    fig.update_yaxes(title_text="Titles", tickformat="~s")
    return _titled(fig, "How ratings are distributed",
                   "Rated titles only, in IMDb's 0.1 steps")


def genre_bars(df: pd.DataFrame, value: str = "titles", top: int = 12,
               title: str = "Most common genres", subtitle: str | None = None,
               highlight: str | None = None, height: int | None = None) -> go.Figure:
    d = df.nlargest(top, value).iloc[::-1]
    colors = [YELLOW if (highlight is None or g == highlight) else CONTEXT
              for g in d["genre"]]
    fig = go.Figure(go.Bar(
        x=d[value], y=d["genre"], orientation="h", marker_color=colors,
        customdata=np.stack([d["share"] * 100, d["rated"], d["avg_rating"]], axis=-1),
        hovertemplate="<b>%{y}</b><br>%{x:,} titles (%{customdata[0]:.1f}% of selection)"
                      "<br>%{customdata[1]:,} rated · mean %{customdata[2]:.2f}<extra></extra>"))
    fig.update_xaxes(title_text="Titles", tickformat="~s")
    fig.update_yaxes(title_text=None)
    return _titled(fig, title, subtitle or "A title counts once in each of its genres",
                   height or max(300, 26 * len(d) + 90))


def runtime_histogram(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure(go.Bar(x=df["runtime"], y=df["titles"], customdata=df[["label"]],
                           marker_color=YELLOW,
                           hovertemplate="%{customdata[0]}<br>%{y:,} titles<extra></extra>"))
    fig.update_layout(bargap=0.12, barcornerradius=1)
    fig.update_xaxes(title_text="Runtime (minutes, last bar = 240+)", dtick=30)
    fig.update_yaxes(title_text="Titles", tickformat="~s")
    return _titled(fig, "Runtime", "Titles with a listed runtime, 5-minute bins")


def rating_vote_heatmap(df: pd.DataFrame) -> go.Figure:
    if df.empty:
        return empty_figure("No rated titles in this selection")
    pivot = df.pivot_table(index="rating_bin", columns="votes_bin", values="titles",
                           aggfunc="sum").sort_index()
    votes_lo = [int(round(10 ** v)) for v in pivot.columns]
    fig = go.Figure(go.Heatmap(
        z=np.log10(pivot.values), x=pivot.columns, y=pivot.index,
        customdata=np.dstack([pivot.values, np.broadcast_to(votes_lo, pivot.shape),
                              np.broadcast_to((pivot.index.values + 0.4)[:, None], pivot.shape)]),
        colorscale=SEQUENTIAL, showscale=False, xgap=1, ygap=1,
        hovertemplate="Rating %{y:.1f}–%{customdata[2]:.1f}<br>Votes from %{customdata[1]:,}"
                      "<br><b>%{customdata[0]:,} titles</b><extra></extra>"))
    ticks = [v for v in range(0, 8) if pivot.columns.min() - 0.25 <= v <= pivot.columns.max() + 0.25]
    fig.update_xaxes(title_text="Votes (log scale)", tickvals=ticks,
                     ticktext=[f"{10 ** v:,.0f}" for v in ticks], showgrid=False)
    fig.update_yaxes(title_text="IMDb rating", dtick=1, showgrid=False)
    return _titled(fig, "Rating against number of votes",
                   "Brighter cells hold more titles (log colour scale)")


# ----------------------------------------------------------------- rankings

def ranked_bars(df: pd.DataFrame, value: str, title: str, subtitle: str,
                color: str = YELLOW, fmt: str = ".2f") -> go.Figure:
    d = df.iloc[::-1]
    labels = [_label(r) for _, r in d.iterrows()]
    custom = np.stack([d["rating"], d["votes"], d["tid"]], axis=-1)
    fig = go.Figure(go.Bar(
        x=d[value], y=labels, orientation="h", marker_color=color, customdata=custom,
        text=[f"{v:{fmt}}" if fmt != "votes" else f"{v / 1e6:.2f}M" if v >= 1e6 else f"{v / 1e3:.0f}K"
              for v in d[value]],
        textposition="outside", textfont=dict(color=MUTED, size=11), cliponaxis=False,
        hovertemplate="<b>%{y}</b><br>Rating %{customdata[0]:.1f} · "
                      "%{customdata[1]:,} votes<extra></extra>"))
    if value in ("rating", "score"):
        lo = max(0, float(d[value].min()) - 0.4)
        fig.update_xaxes(range=[lo, 10.15], title_text="Rating" if value == "rating" else "Weighted rating")
    else:
        fig.update_xaxes(title_text="Votes", tickformat="~s",
                         range=[0, float(d[value].max()) * 1.2])
    fig.update_yaxes(title_text=None, tickfont=dict(color=INK))
    return _titled(fig, title, subtitle, height=max(320, 24 * len(d) + 100))


def rating_vote_scatter(eligible: pd.DataFrame, top_ids: set, voted_ids: set,
                        max_points: int = 12_000) -> tuple[go.Figure, bool]:
    """Scatter of eligible titles. Background points are sampled above
    `max_points`; highlighted titles are always drawn. Returns (fig, sampled)."""
    group = np.where(eligible["tid"].isin(top_ids & voted_ids), "Both lists",
                     np.where(eligible["tid"].isin(top_ids), "Top rated",
                              np.where(eligible["tid"].isin(voted_ids), "Most voted", "Other")))
    d = eligible.assign(group=group)
    other = d[d["group"] == "Other"]
    sampled = len(other) > max_points
    if sampled:
        other = other.sample(max_points, random_state=7)
    styles = {"Other": (CONTEXT, 5, 0.55), "Most voted": (SERIES[1], 9, 1),
              "Top rated": (YELLOW, 9, 1), "Both lists": (SERIES[3], 10, 1)}
    fig = go.Figure()
    for name in ["Other", "Most voted", "Top rated", "Both lists"]:
        part = other if name == "Other" else d[d["group"] == name]
        if part.empty:
            continue
        color, size, opacity = styles[name]
        fig.add_scattergl(
            x=part["votes"], y=part["rating"], mode="markers", name=name,
            marker=dict(color=color, size=size, opacity=opacity,
                        line=dict(color=SURFACE, width=1 if size > 5 else 0)),
            customdata=np.stack([part["title"], part["year"].fillna(0).astype(int),
                                 part["tid"]], axis=-1),
            hovertemplate="<b>%{customdata[0]}</b> (%{customdata[1]})<br>"
                          "Rating %{y:.1f} · %{x:,} votes<extra></extra>")
    fig.update_xaxes(type="log", title_text="Votes (log scale)")
    fig.update_yaxes(title_text="IMDb rating", range=[max(0.8, d["rating"].min() - 0.3), 10.1])
    fig.update_layout(dragmode="select", legend=dict(y=1.0, yanchor="bottom"))
    return _titled(fig, "Rating against popularity",
                   "Drag a box over points to list those titles", height=440), sampled


# ----------------------------------------------------------------- genres

def genre_rating_dots(df: pd.DataFrame, overall: float | None, min_rated: int) -> go.Figure:
    d = df[df["rated"] >= min_rated].sort_values("avg_rating")
    if d.empty:
        return empty_figure("Not enough rated titles per genre")
    fig = go.Figure()
    fig.add_scatter(
        x=d["avg_rating"], y=d["genre"], mode="markers",
        marker=dict(color=YELLOW, size=10, line=dict(color=SURFACE, width=2)),
        customdata=d[["rated"]],
        hovertemplate="<b>%{y}</b><br>Mean rating %{x:.2f}<br>"
                      "from %{customdata[0]:,} rated titles<extra></extra>")
    if overall is not None:
        fig.add_vline(x=overall, line=dict(color=MUTED, width=1, dash="dot"),
                      annotation_text=f"all genres {overall:.2f}",
                      annotation_font=dict(size=11, color=MUTED), annotation_position="top")
    fig.update_xaxes(title_text="Mean IMDb rating")
    fig.update_yaxes(title_text=None, tickfont=dict(color=INK), showgrid=True)
    fig.update_layout(showlegend=False)
    return _titled(fig, "Average rating by genre",
                   f"Genres with at least {min_rated:,} rated titles",
                   height=max(300, 24 * len(d) + 100))


def genre_heatmap(df: pd.DataFrame, metric: str, period: int) -> go.Figure:
    if df.empty:
        return empty_figure("No titles in this selection")
    labels = {"share": "Share of the period's titles", "titles": "Titles",
              "avg_rating": "Mean rating"}
    pivot = df.pivot_table(index="genre", columns="period", values=metric, aggfunc="first")
    order = df.groupby("genre")["titles"].sum().sort_values().index
    pivot = pivot.reindex(order)
    counts = df.pivot_table(index="genre", columns="period", values="titles",
                            aggfunc="first").reindex(index=pivot.index, columns=pivot.columns)
    z = pivot.values
    zfmt = {"share": ".1%", "titles": ",.0f", "avg_rating": ".2f"}[metric]
    fig = go.Figure(go.Heatmap(
        z=z, x=[f"{p}s" if period == 10 else str(p) for p in pivot.columns], y=pivot.index,
        customdata=counts.fillna(0).values, colorscale=SEQUENTIAL, xgap=2, ygap=2,
        zmin=None if metric != "avg_rating" else np.nanmin(z),
        colorbar=dict(thickness=10, outlinewidth=0, tickfont=dict(color=MUTED),
                      tickformat=".0%" if metric == "share" else "~s" if metric == "titles" else ".1f"),
        hovertemplate="<b>%{y}</b>, %{x}<br>" + labels[metric] + ": %{z:" + zfmt + "}"
                      "<br>%{customdata:,} titles<extra></extra>"))
    fig.update_xaxes(showgrid=False, title_text=None, side="bottom")
    fig.update_yaxes(showgrid=False, title_text=None, tickfont=dict(color=INK))
    sub = {"share": "Share of each decade's titles that carry the genre",
           "titles": "Number of titles per genre and decade",
           "avg_rating": "Mean rating; blank where fewer than 20 titles are rated"}[metric]
    return _titled(fig, "Genres across the decades", sub,
                   height=max(360, 22 * len(pivot) + 120))


# ----------------------------------------------------------------- trends

def released_vs_rated(df: pd.DataFrame, partial_year: int | None) -> go.Figure:
    fig = go.Figure()
    fig.add_scatter(x=df["year"], y=df["titles"], name="Released", mode="lines",
                    line=dict(color=YELLOW, width=2),
                    hovertemplate="%{y:,} released<extra></extra>")
    fig.add_scatter(x=df["year"], y=df["rated"], name="Rated on IMDb", mode="lines",
                    line=dict(color=SERIES[1], width=2),
                    hovertemplate="%{y:,} rated<extra></extra>")
    fig.update_layout(hovermode="x unified")
    fig.update_yaxes(title_text="Titles", tickformat="~s")
    fig.update_xaxes(title_text=None, rangeslider=dict(visible=True, thickness=0.07,
                                                       bgcolor="#FAFAFA", bordercolor=GRID))
    if partial_year is not None and partial_year in set(df["year"]):
        fig.add_vrect(x0=partial_year - 1, x1=partial_year, fillcolor="#000000",
                      opacity=0.04, line_width=0)
    return _titled(fig, "Released and rated titles per year",
                   "A title only gets a rating once it has 5 or more votes", height=380)


def band_line(df: pd.DataFrame, center: str, title: str, subtitle: str,
              y_title: str, value_fmt: str) -> go.Figure:
    fig = go.Figure()
    fig.add_scatter(x=df["year"], y=df["q3"], mode="lines", line=dict(width=0),
                    hoverinfo="skip", showlegend=False)
    fig.add_scatter(x=df["year"], y=df["q1"], mode="lines", line=dict(width=0),
                    fill="tonexty", fillcolor="rgba(245,197,24,0.14)",
                    name="Middle 50%", hoverinfo="skip")
    fig.add_scatter(x=df["year"], y=df[center], mode="lines", name=center.capitalize(),
                    line=dict(color=YELLOW, width=2),
                    customdata=np.stack([df["q1"], df["q3"], df["titles"]], axis=-1),
                    hovertemplate="<b>%{x}</b><br>" + center.capitalize() + " %{y:" + value_fmt +
                                  "}<br>Middle 50%: %{customdata[0]:" + value_fmt + "}–%{customdata[1]:"
                                  + value_fmt + "}<br>%{customdata[2]:,} titles<extra></extra>")
    fig.update_yaxes(title_text=y_title)
    fig.update_xaxes(title_text=None)
    fig.update_layout(showlegend=False)
    return _titled(fig, title, subtitle, height=340)


def genre_share_lines(df: pd.DataFrame, genres: list[str], all_genres) -> go.Figure:
    if df.empty:
        return empty_figure("No titles in this selection")
    fig = go.Figure()
    for i, g in enumerate(genres):
        part = df[df["genre"] == g]
        color = SERIES[i % len(SERIES)]
        fig.add_scatter(x=part["year"], y=part["share"], name=g, mode="lines",
                        line=dict(color=color, width=2), customdata=part[["titles"]],
                        hovertemplate=f"<b>{g}</b> %{{y:.1%}}"
                                      " (%{customdata[0]:,} titles)<extra></extra>")
        last = part.iloc[-1] if len(part) else None
        if last is not None and len(genres) <= 4:
            fig.add_annotation(x=last["year"], y=last["share"], text=g, showarrow=False,
                               xanchor="left", xshift=6, font=dict(color=INK, size=11))
    fig.update_layout(hovermode="x unified", margin=dict(r=90))
    fig.update_yaxes(title_text="Share of the year's titles", tickformat=".0%")
    fig.update_xaxes(title_text=None)
    return _titled(fig, "Genre share over time",
                   "Share of each year's titles carrying the genre", height=380)


# ----------------------------------------------------------------- people

def people_bars(df: pd.DataFrame, sort: str, role_label: str) -> go.Figure:
    d = df.iloc[::-1]
    value = "titles" if sort == "titles" else "avg_rating"
    fig = go.Figure(go.Bar(
        x=d[value], y=d["name"], orientation="h", marker_color=YELLOW,
        customdata=np.stack([d["titles"], d["rated"], d["avg_rating"].fillna(0), d["nid"]], axis=-1),
        text=[f"{v:,.0f}" if value == "titles" else f"{v:.2f}" for v in d[value]],
        textposition="outside", textfont=dict(color=MUTED, size=11), cliponaxis=False,
        hovertemplate="<b>%{y}</b><br>%{customdata[0]:,} titles in selection"
                      "<br>%{customdata[1]:,} rated · mean %{customdata[2]:.2f}<extra></extra>"))
    if value == "titles":
        fig.update_xaxes(title_text="Credited titles", range=[0, d[value].max() * 1.12])
        title = f"Most credited {role_label.lower()}"
    else:
        fig.update_xaxes(title_text="Mean rating of their titles",
                         range=[max(0, d[value].min() - 0.5), 10.1])
        title = f"Highest rated {role_label.lower()}"
    fig.update_yaxes(title_text=None, tickfont=dict(color=INK))
    return _titled(fig, title, "Click a bar to open that person's profile",
                   height=max(320, 24 * len(d) + 100))


def career_scatter(df: pd.DataFrame, name: str) -> go.Figure:
    d = df[df["rating"].notna() & df["year"].notna()]
    if d.empty:
        return empty_figure("None of these titles has a rating yet")
    size = np.clip(np.log10(d["votes"].clip(lower=1)) * 4, 6, 26)
    fig = go.Figure(go.Scatter(
        x=d["year"], y=d["rating"], mode="markers",
        marker=dict(color=YELLOW, size=size, opacity=0.85, line=dict(color=SURFACE, width=1)),
        customdata=np.stack([d["title"], d["votes"], d["role"]], axis=-1),
        hovertemplate="<b>%{customdata[0]}</b> (%{x})<br>Rating %{y:.1f} · "
                      "%{customdata[1]:,} votes<br>%{customdata[2]}<extra></extra>"))
    fig.update_xaxes(title_text=None)
    fig.update_yaxes(title_text="IMDb rating", range=[max(0.8, d["rating"].min() - 0.5), 10.1])
    return _titled(fig, f"{name}: rated titles over time", "Marker size grows with votes",
                   height=340)
