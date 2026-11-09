"""Pure trial-design logic (no PsychoPy, no database) so it can be unit tested.

* ``build_schedule`` decides which strategy each trial uses.
* ``generate_trial`` draws the start number and the steps so the running total
  never leaves ``[value_min, value_max]`` (i.e. it is always countable on hands).
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from config import ExperimentConfig, Strategy, STRATEGIES


@dataclass(frozen=True)
class TrialSpec:
    index: int  # 1-based position in the session
    strategy: Strategy
    start_value: int
    steps: tuple[int, ...]

    @property
    def running_totals(self) -> tuple[int, ...]:
        totals = [self.start_value]
        for step in self.steps:
            totals.append(totals[-1] + step)
        return tuple(totals)

    @property
    def correct_answer(self) -> int:
        return self.running_totals[-1]


def validate(cfg: ExperimentConfig) -> list[str]:
    """Return a list of human-readable problems; empty means the config is usable."""
    problems: list[str] = []
    if cfg.value_min >= cfg.value_max:
        problems.append("value_min must be smaller than value_max.")
    if cfg.step_min > cfg.step_max:
        problems.append("step_min must not be larger than step_max.")
    if cfg.step_min > -1 and cfg.step_max < 1:
        problems.append("The step range must contain at least one non-zero step.")
    if cfg.step_count < 1:
        problems.append("step_count must be at least 1.")
    if cfg.fixation_seconds < 0 or cfg.number_display_seconds <= 0:
        problems.append("Timings must be positive.")
    if cfg.order_mode == "random":
        if cfg.total_trials < 1:
            problems.append("total_trials must be at least 1 in 'random' mode.")
        if not 0.0 <= cfg.hands_probability <= 1.0:
            problems.append("hands_probability must be between 0 and 1.")
    else:
        if cfg.head_trials < 0 or cfg.hands_trials < 0:
            problems.append("Trial counts cannot be negative.")
        if cfg.head_trials + cfg.hands_trials < 1:
            problems.append("There must be at least one trial.")
    # The answer must fit in the response box.
    longest = max(len(str(cfg.value_min)), len(str(cfg.value_max)))
    if cfg.max_response_digits < longest:
        problems.append("max_response_digits is too small for the value range.")
    return problems


def _first(cfg: ExperimentConfig, rng: random.Random) -> Strategy:
    if cfg.first_strategy == "random":
        return rng.choice(STRATEGIES)
    return cfg.first_strategy


def _other(strategy: Strategy) -> Strategy:
    return "hands" if strategy == "head" else "head"


def build_schedule(cfg: ExperimentConfig, rng: random.Random) -> list[Strategy]:
    """Strategy for each trial, in presentation order."""
    if cfg.order_mode == "random":
        return [
            "hands" if rng.random() < cfg.hands_probability else "head"
            for _ in range(cfg.total_trials)
        ]

    remaining = {"head": cfg.head_trials, "hands": cfg.hands_trials}

    if cfg.order_mode == "shuffled":
        schedule: list[Strategy] = ["head"] * remaining["head"] + ["hands"] * remaining["hands"]
        rng.shuffle(schedule)
        return schedule

    first = _first(cfg, rng)
    if cfg.order_mode == "blocked":
        second = _other(first)
        return [first] * remaining[first] + [second] * remaining[second]

    # "alternate": switch every trial; once one strategy runs out the rest
    # of the other strategy follow.
    schedule = []
    current = first
    while remaining["head"] or remaining["hands"]:
        if remaining[current] == 0:
            current = _other(current)
        schedule.append(current)
        remaining[current] -= 1
        current = _other(current)
    return schedule


def generate_trial(
    cfg: ExperimentConfig, rng: random.Random, index: int, strategy: Strategy
) -> TrialSpec:
    """Draw a start value and steps; each step is uniform over the steps that
    keep the running total inside the allowed range."""
    total = rng.randint(cfg.value_min, cfg.value_max)
    start = total
    steps: list[int] = []
    for _ in range(cfg.step_count):
        options = [
            s
            for s in range(cfg.step_min, cfg.step_max + 1)
            if (cfg.allow_zero_step or s != 0)
            and cfg.value_min <= total + s <= cfg.value_max
        ]
        if not options:  # only possible with a very narrow, odd config
            raise ValueError("No valid step available; check the number ranges in config.py.")
        step = rng.choice(options)
        steps.append(step)
        total += step
    return TrialSpec(index=index, strategy=strategy, start_value=start, steps=tuple(steps))


def build_session(cfg: ExperimentConfig, seed: int) -> list[TrialSpec]:
    rng = random.Random(seed)
    schedule = build_schedule(cfg, rng)
    return [generate_trial(cfg, rng, i + 1, s) for i, s in enumerate(schedule)]
