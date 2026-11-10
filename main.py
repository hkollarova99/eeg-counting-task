"""Entry point: start-up dialog -> instructions -> trials -> results saved.

Run with:  .venv\\Scripts\\python.exe main.py
Defaults come from config.py; the dialog lets you override the common ones.
"""

from __future__ import annotations

import dataclasses
import random
import sys

from psychopy import core, gui

from config import CONFIG, DatabaseConfig, ExperimentConfig, FIRST_STRATEGIES, ORDER_MODES
import design
from storage import ResultStore
from triggers import TriggerPort

# dialog label -> (config field, type)
FIELDS: dict[str, tuple[str, type]] = {
    "Order mode": ("order_mode", str),
    "First strategy (alternate/blocked)": ("first_strategy", str),
    "Head trials": ("head_trials", int),
    "Hands trials": ("hands_trials", int),
    "Total trials (random mode)": ("total_trials", int),
    "P(hands) (random mode)": ("hands_probability", float),
    "Numbers to add per trial": ("step_count", int),
    "Fixation duration (s)": ("fixation_seconds", float),
    "Number duration (s)": ("number_display_seconds", float),
    "Show feedback": ("show_feedback", bool),
    "Send EEG triggers": ("send_triggers", bool),
    "Fullscreen": ("fullscreen", bool),
    "Screen (0 = primary)": ("screen", int),
    "Seed (blank = random)": ("seed", int),
}


def _choices(current: str, options) -> list[str]:
    # DlgFromDict uses the first list item as the pre-selected value.
    return [current] + [o for o in options if o != current]


def message(title: str, text: str) -> bool:
    """Show a message; returns True for OK, False for Cancel."""
    dlg = gui.Dlg(title=title)
    dlg.addText(text)
    dlg.show()
    return bool(dlg.OK)


def ask_settings(cfg: ExperimentConfig) -> tuple[str, ExperimentConfig, bool]:
    info: dict = {"Subject ID": ""}
    for label, (name, _) in FIELDS.items():
        value = getattr(cfg, name)
        if name == "order_mode":
            value = _choices(value, ORDER_MODES)
        elif name == "first_strategy":
            value = _choices(value, FIRST_STRATEGIES)
        elif value is None:
            value = ""
        info[label] = value
    info["Save to PostgreSQL"] = True

    while True:
        dlg = gui.DlgFromDict(info, title="Counting task - session setup",
                              order=list(info), sortKeys=False)
        if not dlg.OK:
            core.quit()
        subject = str(info["Subject ID"]).strip()
        try:
            if not subject:
                raise ValueError("Please enter a subject ID.")
            overrides = {}
            for label, (name, typ) in FIELDS.items():
                raw = info[label]
                if typ is bool:
                    overrides[name] = bool(raw)
                elif name == "seed" and str(raw).strip() == "":
                    overrides[name] = None
                else:
                    try:
                        overrides[name] = typ(str(raw).strip())
                    except ValueError:
                        raise ValueError(f"'{label}' must be a {typ.__name__}, got '{raw}'.")
            new_cfg = dataclasses.replace(cfg, **overrides)
            problems = design.validate(new_cfg)
            if problems:
                raise ValueError("\n".join(problems))
        except ValueError as exc:
            message("Invalid settings", str(exc))
            # Keep what the user typed, but restore choice lists for the next dialog.
            info["Order mode"] = _choices(str(info["Order mode"]), ORDER_MODES)
            info["First strategy (alternate/blocked)"] = _choices(
                str(info["First strategy (alternate/blocked)"]), FIRST_STRATEGIES)
            continue
        return subject, new_cfg, bool(info["Save to PostgreSQL"])


def open_store(subject: str, cfg: ExperimentConfig, seed: int, use_db: bool) -> ResultStore:
    if use_db:
        db = DatabaseConfig()
        try:
            return ResultStore(subject, cfg, seed, db)
        except Exception as exc:  # connection / auth / permission problems
            if not message(
                "Database unavailable",
                f"Could not connect to PostgreSQL at {db.host}:{db.port}/{db.dbname}:\n\n"
                f"{exc}\n\nPress OK to continue saving to a local CSV file only, "
                f"or Cancel to quit.",
            ):
                core.quit()
    return ResultStore(subject, cfg, seed, db=None)


def main() -> None:
    subject, cfg, use_db = ask_settings(CONFIG)
    seed = cfg.seed if cfg.seed is not None else random.SystemRandom().randrange(2**31)
    trials = design.build_session(cfg, seed)
    store = open_store(subject, cfg, seed, use_db)
    port = TriggerPort(cfg.trigger_port_address, enabled=cfg.send_triggers)

    from experiment import CountingTask, QuitExperiment  # opens no window until here

    task = CountingTask(cfg, store, port)
    status = "aborted"
    try:
        task.run(trials)
        status = "completed"
    except QuitExperiment:
        pass
    finally:
        store.close(status)
        port.close()
        task.close()
    print(f"Session {status}. Data: {store.csv_path}"
          + (f" (database session_id={store.session_id})" if store.uses_database else ""))
    core.quit()


if __name__ == "__main__":
    sys.exit(main())
