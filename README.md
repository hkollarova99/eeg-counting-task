# EEG counting task

Participants see a fixation cross, a start number, and then a series of steps (−10 … +10).
At the end they type the final total. Two strategies are compared: counting **in the
head** vs. **with the hands**. The running total always stays within 0–10, so it can be
shown on fingers.

The flow is: setup dialog (subject ID and parameters) → instructions → for each trial,
a strategy cue, then `+` → start → `+` → step … → `+` → response → (feedback) → end screen.

## Setup

```powershell
py -3.11 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe main.py
```

Press **Escape** at any time to abort. Completed trials are already saved.

## Parameters

All defaults are in `config.py`. The most common ones can also be changed in the setup dialog.

| Parameter | Default | Meaning |
|---|---|---|
| `step_count` | 7 | numbers added after the start number |
| `value_min/max`, `step_min/max` | 0/10, −4/4 | range of the running total and of each step |
| `fixation_seconds` | 2.0 | fixation cross before, between, and after the numbers |
| `number_display_seconds` | 1.0 | how long each number is shown |
| `order_mode` | `alternate` | `alternate` (switch every trial), `blocked`, `shuffled` (fixed counts, random order), `random` (each trial drawn with `hands_probability`) |
| `head_trials`, `hands_trials` | 1, 1 | trial counts for alternate/blocked/shuffled |
| `total_trials`, `hands_probability` | 2, 0.5 | used by `random` mode |
| `first_strategy` | `random` | which strategy starts in alternate/blocked |
| `screen` | 0 | monitor that shows the experiment window (0 = primary) |
| `seed` | random | the seed that was used is saved, so every session can be reproduced |

## Number balancing

Within each session, and separately for each strategy, every start value (0–10) and every
step value (±1…±4) occurs equally often, both at each of the 7 step positions and pooled
(see `design.generate_trials`). With `balance_end = True` (default) the end numbers
(correct answers) are balanced the same way.
Check the distributions with:

```powershell
.venv\Scripts\python.exe stats.py --sessions 1000 --plot stats.png   # simulated
.venv\Scripts\python.exe stats.py --csv "data/*.csv" --by-strategy   # recorded data
```

## Data

* **PostgreSQL**: connection settings come from the env vars `COUNTING_DB_HOST`, `_PORT`, `_NAME`,
  `_USER`, `_PASSWORD` (defaults are `localhost:5432`, `counting_task`, `postgres`/`postgres`).
  The database and tables (`sessions`, `trials`) are created automatically.
  If the database is unreachable, you can continue in CSV-only mode.
* **CSV backup**: `data/<subject>_<timestamp>.csv` (one row per trial), with a `.json` file
  next to it that holds the config and seed.

Example query:

```sql
SELECT s.subject_id, t.strategy, avg(t.is_correct::int) AS accuracy, avg(t.rt_seconds) AS rt
FROM trials t JOIN sessions s USING (session_id)
GROUP BY 1, 2 ORDER BY 1, 2;
```

## Tests

```powershell
.venv\Scripts\python.exe -m pytest
```
