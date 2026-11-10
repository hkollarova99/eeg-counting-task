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

## EEG triggers

Triggers are sent on the parallel port (`0x0378`) as a 1 ms pulse, then reset to 0.
Codes are defined in `triggers.py` (`Trigger` enum); keep this table in sync with it.
Codes 17-23 are unused (reserved).

| Code | Name | Meaning |
|-----:|------|---------|
| 1 | `EXPERIMENT_START` | start of the experiment |
| 2 | `TRIAL_START` | start of the trial |
| 3 | `TRIAL_END` | end of the trial |
| 4 | `BREAK_START` | start of break |
| 5 | `BREAK_END` | end of break |
| 6 | `EYES_OPEN_START` | eyes open start |
| 7 | `EYES_OPEN_END` | eyes open end |
| 8 | `EYES_CLOSED_START` | eyes closed start |
| 9 | `EYES_CLOSED_END` | eyes closed end |
| 10 | `STRATEGY_HANDS_START` | strategy hands start |
| 11 | `STRATEGY_HANDS_END` | strategy hands end |
| 12 | `STRATEGY_HEAD_START` | strategy head start |
| 13 | `STRATEGY_HEAD_END` | strategy head end |
| 14 | `WRITING_SUM_START` | writing final sum start |
| 15 | `WRITING_SUM_END` | writing final sum end |
| 16 | `RESULT_REVEALED` | result revealed |
| 24 | `START_NUMBER_0` | starting number 0 |
| 25 | `START_NUMBER_1` | starting number 1 |
| 26 | `START_NUMBER_2` | starting number 2 |
| 27 | `START_NUMBER_3` | starting number 3 |
| 28 | `START_NUMBER_4` | starting number 4 |
| 29 | `START_NUMBER_5` | starting number 5 |
| 30 | `START_NUMBER_6` | starting number 6 |
| 31 | `START_NUMBER_7` | starting number 7 |
| 32 | `START_NUMBER_8` | starting number 8 |
| 33 | `START_NUMBER_9` | starting number 9 |
| 34 | `START_NUMBER_10` | starting number 10 |
| 35 | `ADDITION_MINUS_4` | addition -4 |
| 36 | `ADDITION_MINUS_3` | addition -3 |
| 37 | `ADDITION_MINUS_2` | addition -2 |
| 38 | `ADDITION_MINUS_1` | addition -1 |
| 39 | `ADDITION_PLUS_1` | addition +1 |
| 40 | `ADDITION_PLUS_2` | addition +2 |
| 41 | `ADDITION_PLUS_3` | addition +3 |
| 42 | `ADDITION_PLUS_4` | addition +4 |
| 43 | `WROTE_NUMBER_0` | wrote number 0 |
| 44 | `WROTE_NUMBER_1` | wrote number 1 |
| 45 | `WROTE_NUMBER_2` | wrote number 2 |
| 46 | `WROTE_NUMBER_3` | wrote number 3 |
| 47 | `WROTE_NUMBER_4` | wrote number 4 |
| 48 | `WROTE_NUMBER_5` | wrote number 5 |
| 49 | `WROTE_NUMBER_6` | wrote number 6 |
| 50 | `WROTE_NUMBER_7` | wrote number 7 |
| 51 | `WROTE_NUMBER_8` | wrote number 8 |
| 52 | `WROTE_NUMBER_9` | wrote number 9 |
| 53 | `WROTE_NUMBER_10` | wrote number 10 |
| 54 | `RESULT_WAS_0` | result was 0 |
| 55 | `RESULT_WAS_1` | result was 1 |
| 56 | `RESULT_WAS_2` | result was 2 |
| 57 | `RESULT_WAS_3` | result was 3 |
| 58 | `RESULT_WAS_4` | result was 4 |
| 59 | `RESULT_WAS_5` | result was 5 |
| 60 | `RESULT_WAS_6` | result was 6 |
| 61 | `RESULT_WAS_7` | result was 7 |
| 62 | `RESULT_WAS_8` | result was 8 |
| 63 | `RESULT_WAS_9` | result was 9 |
| 64 | `RESULT_WAS_10` | result was 10 |
