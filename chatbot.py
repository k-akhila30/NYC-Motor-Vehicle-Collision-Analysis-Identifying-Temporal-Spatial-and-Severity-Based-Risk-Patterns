"""Safe, database-grounded query layer for VisionZeroMate.

The language model extracts a small JSON intent. All SQL is authored here and
uses bound parameters; model output is never executed as SQL.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
from pathlib import Path
from typing import Any

DB_CANDIDATES = [
    Path(os.getenv("NYC_CRASH_DB", "data/nyc_crashes.sqlite")),
    Path("/content/nyc_crashes.sqlite"),
]
MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
BOROUGHS = {"BRONX", "BROOKLYN", "MANHATTAN", "QUEENS", "STATEN ISLAND"}


class AssistantError(RuntimeError):
    """An expected configuration or unsupported-question error for the UI."""


def _database_path() -> Path | None:
    return next((path for path in DB_CANDIDATES if path.is_file()), None)


def database_status() -> dict[str, Any]:
    path = _database_path()
    if path is None:
        return {
            "ready": False,
            "message": "No local SQLite snapshot found. Run `python setup_db.py` to prepare the collision data.",
        }
    try:
        with sqlite3.connect(path) as connection:
            row = connection.execute("SELECT COUNT(*) FROM crashes").fetchone()
        return {"ready": True, "message": f"{row[0]:,} collision records · {path}"}
    except sqlite3.Error as exc:
        return {"ready": False, "message": f"Database found but not ready: {exc}"}


def _connection() -> sqlite3.Connection:
    path = _database_path()
    if path is None:
        raise AssistantError("The collision database isn’t set up yet. Run `python setup_db.py`, then restart the app.")
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection


def _route(question: str) -> dict[str, Any]:
    """Ask Groq for a constrained intent; never ask it to write SQL."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise AssistantError("Add your Groq API key as `GROQ_API_KEY` in your environment or Streamlit secrets to enable chat.")
    try:
        from groq import Groq

        response = Groq(api_key=api_key).chat.completions.create(
            model=MODEL,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Classify this NYC motor-vehicle collision question. Return JSON only with keys intent and entities. "
                        "intent must be one of count, boroughs, hotspots, hours, severity, help. "
                        "entities may contain borough (one of Bronx, Brooklyn, Manhattan, Queens, Staten Island), "
                        "year (integer), date (YYYY-MM-DD), mode (cyclist, pedestrian, motorist, persons), "
                        "limit (integer from 3 to 10). Never return SQL. If the question is not supported, choose help."
                    ),
                },
                {"role": "user", "content": question},
            ],
        )
        result = json.loads(response.choices[0].message.content or "{}")
        if result.get("intent") not in {"count", "boroughs", "hotspots", "hours", "severity", "help"}:
            return {"intent": "help", "entities": {}}
        return {"intent": result["intent"], "entities": result.get("entities") or {}}
    except AssistantError:
        raise
    except Exception as exc:
        raise AssistantError(f"Couldn’t reach the Groq model. Check `GROQ_API_KEY` and network access. ({exc})") from exc


def _metric(mode: str | None) -> tuple[str, str, str]:
    mode = (mode or "persons").lower()
    if "cycl" in mode or "bike" in mode:
        return "number_of_cyclist_injured", "number_of_cyclist_killed", "cyclists"
    if "ped" in mode:
        return "number_of_pedestrians_injured", "number_of_pedestrians_killed", "pedestrians"
    if "motor" in mode:
        return "number_of_motorist_injured", "number_of_motorist_killed", "motorists"
    return "number_of_persons_injured", "number_of_persons_killed", "people"


def _run(sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    try:
        with _connection() as connection:
            return [dict(row) for row in connection.execute(sql, params).fetchall()]
    except sqlite3.Error as exc:
        raise AssistantError(f"Couldn’t query the collision database: {exc}. Check that it was created with `python setup_db.py`.") from exc


def _answer(question: str, intent: str, entities: dict[str, Any]) -> dict[str, Any]:
    borough = str(entities.get("borough", "")).strip().upper()
    if borough and borough not in BOROUGHS:
        borough = ""
    year = entities.get("year")
    if not isinstance(year, int) or not 2012 <= year <= 2035:
        year = None
    date_value = entities.get("date")
    if not isinstance(date_value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date_value):
        date_match = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", question)
        date_value = date_match.group(1) if date_match else None
    try:
        limit = int(entities.get("limit", 5))
    except (TypeError, ValueError):
        limit = 5
    limit = min(10, max(3, limit))
    mode = entities.get("mode")
    injured, killed, mode_label = _metric(mode)
    borough_clause = " AND borough = ?" if borough else ""
    params: list[Any] = []
    if intent == "help":
        return {
            "answer": "I can explore collision counts, compare boroughs, find hotspot intersections, analyze risky hours, and summarize injuries or fatalities. Try asking about a year, borough, or road-user group.",
            "details": "This assistant answers questions using aggregated queries against the NYC collision SQLite dataset.",
        }
    if intent == "count":
        where = []
        if date_value:
            where.append("crash_date = ?")
            params.append(date_value)
        if year:
            where.append("crash_year = ?")
            params.append(year)
        if borough:
            where.append("borough = ?")
            params.append(borough)
        sql = "SELECT COUNT(*) AS crashes FROM crashes" + (" WHERE " + " AND ".join(where) if where else "")
        row = _run(sql, tuple(params))[0]
        qualifiers = [part for part in [date_value, str(year) if year else None, borough.title() if borough else None] if part]
        suffix = f" in {', '.join(qualifiers)}" if qualifiers else " in the available dataset"
        return {"answer": f"I found **{row['crashes']:,} crashes**{suffix}.", "details": "Counted crash records from the `crashes` table, filtered using the requested date, year, and/or borough."}
    if intent == "boroughs":
        sql = "SELECT COALESCE(NULLIF(TRIM(borough), ''), 'Unknown') AS borough, COUNT(*) AS crashes FROM crashes GROUP BY borough ORDER BY crashes DESC"
        rows = _run(sql)
        return {"answer": "Here’s how reported crash records are distributed across boroughs.", "details": "Grouped the collision records by borough and counted rows. Records with a missing borough are shown as Unknown.", "table": rows}
    if intent == "hotspots":
        where = "WHERE intersection IS NOT NULL AND TRIM(intersection) != ''"
        if borough:
            where += " AND borough = ?"
            params.append(borough)
        if year:
            where += " AND crash_year = ?"
            params.append(year)
        sql = f"SELECT intersection, COUNT(*) AS crashes FROM crashes {where} GROUP BY intersection ORDER BY crashes DESC LIMIT ?"
        rows = _run(sql, tuple(params + [limit]))
        return {"answer": f"These are the top {len(rows)} intersections by reported crash count.", "details": "Grouped rows by the normalized intersection field, ordered by crash count, and limited the results. This is a count, not a severity-adjusted risk rate.", "table": rows}
    if intent == "hours":
        where = "WHERE crash_hour IS NOT NULL"
        if borough:
            where += " AND borough = ?"
            params.append(borough)
        if year:
            where += " AND crash_year = ?"
            params.append(year)
        sql = f"SELECT crash_hour AS hour_24, COUNT(*) AS crashes FROM crashes {where} GROUP BY crash_hour ORDER BY crashes DESC LIMIT 10"
        rows = _run(sql, tuple(params))
        if rows:
            peak = rows[0]
            return {"answer": f"The busiest recorded hour is **{peak['hour_24']:02d}:00–{(peak['hour_24'] + 1) % 24:02d}:00**, with **{peak['crashes']:,} crashes** in the selected data.", "details": "Grouped crash records by the hour component of crash time and ranked hours by record count. Counts are not adjusted for traffic volume.", "table": rows}
        return {"answer": "I couldn’t find records with a valid crash hour for those filters.", "details": "Grouped records with a non-null `crash_hour` value."}
    if intent == "severity":
        where = ""
        if borough:
            where += " WHERE borough = ?"
            params.append(borough)
        if year:
            where += (" AND " if where else " WHERE ") + "crash_year = ?"
            params.append(year)
        sql = f"SELECT COALESCE(SUM({injured}), 0) AS injured, COALESCE(SUM({killed}), 0) AS killed FROM crashes{where}"
        row = _run(sql, tuple(params))[0]
        qualifiers = [str(year) if year else None, borough.title() if borough else None]
        suffix = f" ({', '.join(x for x in qualifiers if x)})" if any(qualifiers) else " in the available dataset"
        return {"answer": f"The records show **{row['injured']:,} {mode_label} injured** and **{row['killed']:,} killed**{suffix}.", "details": f"Summed `{injured}` and `{killed}` across crash records, with any requested year or borough filter. These are reported totals in the dataset."}
    return _answer(question, "help", {})


def answer_question(question: str) -> dict[str, Any]:
    question = question.strip()
    if not question:
        raise AssistantError("Please enter a question about NYC collision patterns.")
    routed = _route(question)
    return _answer(question, routed["intent"], routed["entities"])
