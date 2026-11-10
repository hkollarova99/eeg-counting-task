"""All experiment parameters live here for quick, auditable editing.

The most commonly changed values can also be overridden at runtime in the
start-up dialog (see ``main.py``); everything else is edited here.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Literal


Strategy = Literal["head", "hands"]
OrderMode = Literal["alternate", "shuffled", "blocked", "random"]
FirstStrategy = Literal["random", "head", "hands"]

STRATEGIES: tuple[Strategy, ...] = ("head", "hands")
ORDER_MODES: tuple[OrderMode, ...] = ("alternate", "shuffled", "blocked", "random")
FIRST_STRATEGIES: tuple[FirstStrategy, ...] = ("random", "head", "hands")


@dataclass(frozen=True)
class ExperimentConfig:
    # --- Numbers -----------------------------------------------------------
    # The running total must stay countable on two hands, so it never leaves
    # [value_min, value_max] at any point during a trial.
    value_min: int = 0
    value_max: int = 10
    step_min: int = -4
    step_max: int = 4
    # How many numbers are added after the initial one.
    step_count: int = 7
    # A "+0" step is usually pointless, so it is excluded by default.
    allow_zero_step: bool = False
    # Start values and step values are always balanced within a session.
    # If True, the end values (correct answers) are balanced as well.
    balance_end: bool = True

    # --- Timing (seconds) --------------------------------------------------
    # A fixation cross is shown before the first number, between every pair
    # of numbers, and after the last number before the response prompt.
    fixation_seconds: float = 2.0
    number_display_seconds: float = 1.0
    # None = wait indefinitely for the typed answer.
    response_timeout_seconds: float | None = None
    show_feedback: bool = True
    feedback_seconds: float = 1.5

    # --- Trial structure ---------------------------------------------------
    # Used by the "alternate", "shuffled" and "blocked" order modes:
    head_trials: int = 50
    hands_trials: int = 50
    #   alternate - strategies switch every trial (head, hands, head, ...)
    #   shuffled  - fixed counts above, in random order
    #   blocked   - all trials of one strategy, then all of the other
    #   random    - each trial's strategy drawn independently (see below)
    order_mode: OrderMode = "alternate"
    # Which strategy goes first in "alternate" / "blocked" modes.
    first_strategy: FirstStrategy = "random"
    # Used only by the "random" order mode:
    total_trials: int = 100
    hands_probability: float = 0.5
    # None = a fresh seed per session (the seed used is saved with the session).
    seed: int | None = None

    # --- Display -----------------------------------------------------------
    fullscreen: bool = True
    window_size: tuple[int, int] = (1280, 800)
    # Monitor index for the experiment window (0 = primary). Also in the setup dialog.
    screen: int = 0
    font: str = "Arial"
    background_color: str = "#1b1d23"
    text_color: str = "#eceff4"
    muted_color: str = "#9aa3b2"
    head_color: str = "#88c0d0"
    hands_color: str = "#ebcb8b"
    correct_color: str = "#a3be8c"
    incorrect_color: str = "#bf616a"
    panel_color: str = "#272a33"
    # Sizes are in "height" units (1.0 = full screen height).
    fixation_size: float = 0.05
    number_height: float = 0.14
    text_height: float = 0.032
    max_response_digits: int = 2

    # --- Keys --------------------------------------------------------------
    continue_key: str = "space"
    quit_key: str = "escape"


def _env(name: str, default: str) -> str:
    return os.getenv(name, default)


@dataclass(frozen=True)
class DatabaseConfig:
    """PostgreSQL connection settings, overridable via environment variables."""

    host: str = field(default_factory=lambda: _env("COUNTING_DB_HOST", "localhost"))
    port: int = field(default_factory=lambda: int(_env("COUNTING_DB_PORT", "5432")))
    dbname: str = field(default_factory=lambda: _env("COUNTING_DB_NAME", "counting_task"))
    user: str = field(default_factory=lambda: _env("COUNTING_DB_USER", "postgres"))
    password: str = field(default_factory=lambda: _env("COUNTING_DB_PASSWORD", "postgres"))
    connect_timeout: int = 5


CONFIG = ExperimentConfig()
