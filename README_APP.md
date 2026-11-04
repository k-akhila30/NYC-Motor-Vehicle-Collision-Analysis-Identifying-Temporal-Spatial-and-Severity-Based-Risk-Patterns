# VisionZeroMate — NYC collision assistant

A small Streamlit interface for exploring NYC Motor Vehicle Collision data with natural-language questions. The assistant uses Groq only to classify a question into a constrained intent; it runs predefined, parameterized SQLite queries locally. It does **not** let the model generate or execute SQL.

## Run locally

Requires Python 3.10+ and a Groq API key.

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python setup_db.py
```

Set the key and start the app:

```bash
export GROQ_API_KEY="your-key"  # Windows PowerShell: $env:GROQ_API_KEY="your-key"
streamlit run app.py
```

The app downloads the NYC Open Data Motor Vehicle Collisions dataset (dataset ID `h9gi-nx95`) into `data/nyc_crashes.sqlite`. The download can be large and may take a while. Set `NYC_CRASH_DB` to use a different local database path. Set `GROQ_MODEL` to override the default `llama-3.3-70b-versatile` model.

## What you can ask

- Collision counts by year, date, and borough
- Borough comparisons
- Intersections with the highest reported crash counts
- Crash counts by hour
- Injury and fatality totals for people, cyclists, pedestrians, or motorists

The answer panel explains how results were calculated. Collision counts are not exposure-adjusted risk estimates, and missing or incomplete fields in the source dataset can affect totals.

## Data and privacy

The collision database is local. Questions are sent to Groq for intent classification when you use the chat, so do not include personal or sensitive information. The original notebook-based analysis remains in `NYC_LLM.ipynb`; this app is a separate, reusable interface built around safe, predefined database queries.
