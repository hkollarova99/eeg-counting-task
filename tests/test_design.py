import dataclasses
import random
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import CONFIG  # noqa: E402
import design  # noqa: E402


@pytest.mark.parametrize("seed", range(500))
def test_running_total_stays_in_range(seed):
    trial = design.generate_trial(CONFIG, random.Random(seed), 1, "hands")
    assert len(trial.steps) == CONFIG.step_count
    assert all(CONFIG.value_min <= t <= CONFIG.value_max for t in trial.running_totals)
    assert all(CONFIG.step_min <= s <= CONFIG.step_max and s != 0 for s in trial.steps)


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
