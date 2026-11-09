"""Pure trial-design logic (no PsychoPy, no database) so it can be unit tested.

* ``build_schedule`` decides which strategy each trial uses.
* ``generate_trials`` draws the start numbers and the steps so the running total
  never leaves ``[value_min, value_max]`` (i.e. it is always countable on hands),
  while every start value and every step value occurs equally often.
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


def step_values(cfg: ExperimentConfig) -> list[int]:
    return [s for s in range(cfg.step_min, cfg.step_max + 1) if cfg.allow_zero_step or s != 0]


def _balanced_deck(values: list[int], n: int, rng: random.Random, offset: int) -> list[int]:
    """``n`` values where every value appears ``n // len(values)`` times; the
    ``n % len(values)`` leftovers are taken cyclically from ``offset`` so that
    leftovers are spread evenly across several decks."""
    k = len(values)
    deck = values * (n // k) + [values[(offset + j) % k] for j in range(n % k)]
    rng.shuffle(deck)
    return deck


def _violation(cfg: ExperimentConfig, row: list[int]) -> int:
    """How far (in total) the running total of ``row`` = [start, *steps] leaves
    the allowed range; 0 means the trial is valid."""
    total, bad = 0, 0
    for x in row:
        total += x
        if total < cfg.value_min:
            bad += cfg.value_min - total
        elif total > cfg.value_max:
            bad += total - cfg.value_max
    return bad


def _balance_ends(
    cfg: ExperimentConfig, rows: list[list[int]], rng: random.Random, budget: int
) -> int:
    """Swap values within columns between valid trials so that every end value
    occurs ``n // k`` or ``n // k + 1`` times (k = number of possible values).
    Only swaps that keep both trials valid and do not worsen the end balance are
    kept. Modifies ``rows`` in place; returns the remaining imbalance (0 = done).
    Requires the sum of all rows to be achievable (see ``_draw_decks``)."""
    n, columns = len(rows), len(rows[0])
    values = range(cfg.value_min, cfg.value_max + 1)
    lo = n // len(values)
    hi = lo + (n % len(values) > 0)
    ends = [sum(r) for r in rows]
    counts = {v: 0 for v in values}
    for e in ends:
        counts[e] += 1

    def penalty(c: int) -> int:
        return max(0, c - hi) + max(0, lo - c)

    imbalance = sum(penalty(c) for c in counts.values())
    for _ in range(budget):
        if imbalance == 0:
            break
        i = rng.randrange(n)
        if counts[ends[i]] <= lo:  # only move trials whose end value is over-represented
            continue
        j = rng.randrange(n)
        c = rng.randrange(columns)
        a, b = rows[i][c], rows[j][c]
        if i == j or a == b:
            continue
        new_i, new_j = ends[i] - a + b, ends[j] - b + a
        if new_i not in counts or new_j not in counts:
            continue
        old = {ends[i], ends[j], new_i, new_j}
        before = sum(penalty(counts[v]) for v in old)
        for v, d in ((ends[i], -1), (ends[j], -1), (new_i, 1), (new_j, 1)):
            counts[v] += d
        delta = sum(penalty(counts[v]) for v in old) - before
        rows[i][c], rows[j][c] = b, a
        if delta <= 0 and not _violation(cfg, rows[i]) and not _violation(cfg, rows[j]):
            ends[i], ends[j] = new_i, new_j
            imbalance += delta
        else:  # undo
            rows[i][c], rows[j][c] = a, b
            for v, d in ((ends[i], 1), (ends[j], 1), (new_i, -1), (new_j, -1)):
                counts[v] += d
    return imbalance


def _end_total_range(cfg: ExperimentConfig, count: int) -> tuple[int, int]:
    """Smallest and largest possible sum of all end values when every end value
    occurs ``count // k`` or ``count // k + 1`` times."""
    values = list(range(cfg.value_min, cfg.value_max + 1))
    base = (count // len(values)) * sum(values)
    extra = count % len(values)
    return base + sum(values[:extra]), base + sum(values[len(values) - extra:])


def _draw_decks(
    cfg: ExperimentConfig, rng: random.Random, count: int, starts: list[int], steps: list[int]
) -> list[list[int]]:
    """One balanced deck for the start column and one per step position.

    Swaps between trials never change the sum of all end values (it equals the
    sum of all deck values). With ``balance_end``, decks are therefore redrawn
    until that sum is one a balanced set of end values can actually have."""
    lo, hi = _end_total_range(cfg, count)
    for _ in range(1000):
        start_order, step_order = starts[:], steps[:]
        rng.shuffle(start_order)
        rng.shuffle(step_order)
        decks = [_balanced_deck(start_order, count, rng, 0)]
        decks += [
            _balanced_deck(step_order, count, rng, c * (count % len(steps)))
            for c in range(cfg.step_count)
        ]
        if not cfg.balance_end or lo <= sum(map(sum, decks)) <= hi:
            break
    return decks


def generate_trials(
    cfg: ExperimentConfig, rng: random.Random, count: int,
    max_attempts: int = 1000, swaps_per_trial: int = 2000,
) -> list[tuple[int, tuple[int, ...]]]:
    """Return ``count`` (start, steps) pairs whose running totals stay inside
    ``[value_min, value_max]``.

    Balancing: for the start value and for every step position, the values
    across the ``count`` trials are drawn from a balanced deck, so each value
    occurs equally often (up to the remainder when ``count`` is not a
    multiple of the number of values). Pooled over all positions the step
    values are balanced as well. Invalid trials are then repaired by swapping
    values *within the same column* between trials, which keeps all counts
    exactly balanced. If ``cfg.balance_end`` is set, further swaps then
    even out the end values (the correct answers) as far as possible.
    """
    if count == 0:
        return []
    starts = list(range(cfg.value_min, cfg.value_max + 1))
    steps = step_values(cfg)
    columns = cfg.step_count + 1
    for _ in range(max_attempts):
        decks = _draw_decks(cfg, rng, count, starts, steps)
        rows = [[decks[c][i] for c in range(columns)] for i in range(count)]
        cost = [_violation(cfg, r) for r in rows]
        bad = {i for i, v in enumerate(cost) if v}
        for _ in range(swaps_per_trial * count):
            if not bad:
                if cfg.balance_end:
                    _balance_ends(cfg, rows, rng, swaps_per_trial * count)
                return [(r[0], tuple(r[1:])) for r in rows]
            i = rng.choice(tuple(bad))
            j = rng.randrange(count)
            c = rng.randrange(columns)
            if i == j or rows[i][c] == rows[j][c]:
                continue
            rows[i][c], rows[j][c] = rows[j][c], rows[i][c]
            new_i, new_j = _violation(cfg, rows[i]), _violation(cfg, rows[j])
            if new_i + new_j <= cost[i] + cost[j]:
                cost[i], cost[j] = new_i, new_j
                for k in (i, j):
                    (bad.add if cost[k] else bad.discard)(k)
            else:  # undo
                rows[i][c], rows[j][c] = rows[j][c], rows[i][c]
    raise ValueError("Could not build valid balanced trials; check the number ranges in config.py.")


def build_session(cfg: ExperimentConfig, seed: int) -> list[TrialSpec]:
    """Each strategy's trials are balanced separately, so head and hands trials
    see the same distribution of start values and steps."""
    rng = random.Random(seed)
    schedule = build_schedule(cfg, rng)
    drawn = {s: generate_trials(cfg, rng, schedule.count(s)) for s in STRATEGIES}
    trials = []
    for i, strategy in enumerate(schedule):
        start, steps = drawn[strategy].pop()
        trials.append(TrialSpec(index=i + 1, strategy=strategy, start_value=start, steps=steps))
    return trials
