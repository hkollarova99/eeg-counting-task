import dataclasses
import random
from collections import Counter
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import CONFIG  # noqa: E402
import design  # noqa: E402


@pytest.mark.parametrize("seed", range(100))
def test_running_total_stays_in_range(seed):
    for trial in design.build_session(CONFIG, seed):
        assert len(trial.steps) == CONFIG.step_count
        assert all(CONFIG.value_min <= t <= CONFIG.value_max for t in trial.running_totals)
        assert all(CONFIG.step_min <= s <= CONFIG.step_max and s != 0 for s in trial.steps)


@pytest.mark.parametrize("count", [1, 2, 3, 5, 8, 13, 50, 100])
def test_small_and_odd_counts_are_valid(count):
    trials = design.generate_trials(CONFIG, random.Random(count), count)
    assert len(trials) == count
    for start, steps in trials:
        assert design._violation(CONFIG, [start, *steps]) == 0


def _spread(values, categories):
    counts = Counter(values)
    observed = [counts.get(c, 0) for c in categories]
    return max(observed) - min(observed)


@pytest.mark.parametrize("seed", range(20))
def test_starts_and_steps_are_balanced_per_strategy(seed):
    session = design.build_session(CONFIG, seed)
    steps = design.step_values(CONFIG)
    starts = range(CONFIG.value_min, CONFIG.value_max + 1)
    for strategy in ("head", "hands"):
        trials = [t for t in session if t.strategy == strategy]
        assert _spread([t.start_value for t in trials], starts) <= 1
        for pos in range(CONFIG.step_count):
            assert _spread([t.steps[pos] for t in trials], steps) <= 1
        assert _spread([s for t in trials for s in t.steps], steps) <= 1
        assert _spread([t.correct_answer for t in trials], starts) <= 1


@pytest.mark.parametrize("count", [5, 11, 22, 37, 50, 100])
def test_end_values_are_balanced(count):
    trials = design.generate_trials(CONFIG, random.Random(count), count)
    values = range(CONFIG.value_min, CONFIG.value_max + 1)
    assert _spread([start + sum(steps) for start, steps in trials], values) <= 1


def test_end_balancing_can_be_switched_off():
    cfg = dataclasses.replace(CONFIG, balance_end=False)
    for start, steps in design.generate_trials(cfg, random.Random(0), 50):
        assert design._violation(cfg, [start, *steps]) == 0


def test_alternate_switches_every_trial():
    cfg = dataclasses.replace(CONFIG, order_mode="alternate", head_trials=3,
                              hands_trials=3, first_strategy="hands")
    assert design.build_schedule(cfg, random.Random(0)) == ["hands", "head"] * 3


def test_alternate_with_unequal_counts_appends_remainder():
    cfg = dataclasses.replace(CONFIG, order_mode="alternate", head_trials=1,
                              hands_trials=3, first_strategy="head")
    assert design.build_schedule(cfg, random.Random(0)) == ["head", "hands", "hands", "hands"]


def test_blocked_and_shuffled_keep_counts():
    for mode in ("blocked", "shuffled"):
        cfg = dataclasses.replace(CONFIG, order_mode=mode, head_trials=4, hands_trials=2)
        schedule = design.build_schedule(cfg, random.Random(1))
        assert schedule.count("head") == 4 and schedule.count("hands") == 2
    cfg = dataclasses.replace(CONFIG, order_mode="blocked", head_trials=2,
                              hands_trials=2, first_strategy="head")
    assert design.build_schedule(cfg, random.Random(0)) == ["head", "head", "hands", "hands"]


def test_random_mode_uses_total_trials():
    cfg = dataclasses.replace(CONFIG, order_mode="random", total_trials=10, hands_probability=1.0)
    assert design.build_schedule(cfg, random.Random(0)) == ["hands"] * 10


def test_session_is_reproducible_from_seed():
    assert design.build_session(CONFIG, 42) == design.build_session(CONFIG, 42)


def test_default_config_is_valid_and_bad_config_is_rejected():
    assert design.validate(CONFIG) == []
    assert design.validate(dataclasses.replace(CONFIG, head_trials=0, hands_trials=0))
