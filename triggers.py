"""EEG trigger table and parallel-port sender.

Usage::

    from triggers import Trigger, TriggerPort

    port = TriggerPort()                       # opens LPT1 (0x0378)
    port.send(Trigger.EXPERIMENT_START)        # send immediately
    port.send_on_flip(win, Trigger.START_NUMBER_3)  # send exactly at next screen flip
"""

from __future__ import annotations

from enum import IntEnum

from psychopy import core

PORT_ADDRESS = 0x0378
PULSE_SECONDS = 0.001
# After every trigger the program freezes until GAP_SECONDS have passed since
# its onset, so two triggers can never be sent at the same time (e.g. when
# several belong to the same screen flip). Must be longer than PULSE_SECONDS.
GAP_SECONDS = 0.01


class Trigger(IntEnum):
    # --- Experiment / trial structure -------------------------------------
    EXPERIMENT_START = 1
    TRIAL_START = 2
    TRIAL_END = 3
    BREAK_START = 4
    BREAK_END = 5
    # --- Resting state ----------------------------------------------------
    EYES_OPEN_START = 6
    EYES_OPEN_END = 7
    EYES_CLOSED_START = 8
    EYES_CLOSED_END = 9
    # --- Counting strategy ------------------------------------------------
    STRATEGY_HANDS_START = 10
    STRATEGY_HANDS_END = 11
    STRATEGY_HEAD_START = 12
    STRATEGY_HEAD_END = 13
    # --- Response / feedback ----------------------------------------------
    WRITING_SUM_START = 14
    WRITING_SUM_END = 15
    RESULT_REVEALED = 16
    # --- Starting number shown (0-10) -------------------------------------
    START_NUMBER_0 = 24
    START_NUMBER_1 = 25
    START_NUMBER_2 = 26
    START_NUMBER_3 = 27
    START_NUMBER_4 = 28
    START_NUMBER_5 = 29
    START_NUMBER_6 = 30
    START_NUMBER_7 = 31
    START_NUMBER_8 = 32
    START_NUMBER_9 = 33
    START_NUMBER_10 = 34
    # --- Addition shown (-4..+4, no 0) ------------------------------------
    ADDITION_MINUS_4 = 35
    ADDITION_MINUS_3 = 36
    ADDITION_MINUS_2 = 37
    ADDITION_MINUS_1 = 38
    ADDITION_PLUS_1 = 39
    ADDITION_PLUS_2 = 40
    ADDITION_PLUS_3 = 41
    ADDITION_PLUS_4 = 42
    # --- Number the participant wrote (0-10) ------------------------------
    WROTE_NUMBER_0 = 43
    WROTE_NUMBER_1 = 44
    WROTE_NUMBER_2 = 45
    WROTE_NUMBER_3 = 46
    WROTE_NUMBER_4 = 47
    WROTE_NUMBER_5 = 48
    WROTE_NUMBER_6 = 49
    WROTE_NUMBER_7 = 50
    WROTE_NUMBER_8 = 51
    WROTE_NUMBER_9 = 52
    WROTE_NUMBER_10 = 53
    # --- Correct result (0-10) --------------------------------------------
    RESULT_WAS_0 = 54
    RESULT_WAS_1 = 55
    RESULT_WAS_2 = 56
    RESULT_WAS_3 = 57
    RESULT_WAS_4 = 58
    RESULT_WAS_5 = 59
    RESULT_WAS_6 = 60
    RESULT_WAS_7 = 61
    RESULT_WAS_8 = 62
    RESULT_WAS_9 = 63
    RESULT_WAS_10 = 64


DESCRIPTIONS: dict[int, str] = {
    1: "start of the experiment",
    2: "start of the trial",
    3: "end of the trial",
    4: "start of break",
    5: "end of break",
    6: "eyes open start",
    7: "eyes open end",
    8: "eyes closed start",
    9: "eyes closed end",
    10: "strategy hands start",
    11: "strategy hands end",
    12: "strategy head start",
    13: "strategy head end",
    14: "writing final sum start",
    15: "writing final sum end",
    16: "result revealed",
    **{24 + n: f"starting number {n}" for n in range(11)},
    **{35 + i: f"addition {s:+d}" for i, s in enumerate((-4, -3, -2, -1, 1, 2, 3, 4))},
    **{43 + n: f"wrote number {n}" for n in range(11)},
    **{54 + n: f"result was {n}" for n in range(11)},
}

# --------------------------------------------- shown/typed value -> trigger
# Starting number shown on screen -> trigger.
START_NUMBER_TRIGGERS: dict[int, Trigger] = {
    0: Trigger.START_NUMBER_0,
    1: Trigger.START_NUMBER_1,
    2: Trigger.START_NUMBER_2,
    3: Trigger.START_NUMBER_3,
    4: Trigger.START_NUMBER_4,
    5: Trigger.START_NUMBER_5,
    6: Trigger.START_NUMBER_6,
    7: Trigger.START_NUMBER_7,
    8: Trigger.START_NUMBER_8,
    9: Trigger.START_NUMBER_9,
    10: Trigger.START_NUMBER_10,
}

# Addition shown on screen (e.g. "+2") -> trigger.
ADDITION_TRIGGERS: dict[int, Trigger] = {
    -4: Trigger.ADDITION_MINUS_4,
    -3: Trigger.ADDITION_MINUS_3,
    -2: Trigger.ADDITION_MINUS_2,
    -1: Trigger.ADDITION_MINUS_1,
    +1: Trigger.ADDITION_PLUS_1,
    +2: Trigger.ADDITION_PLUS_2,
    +3: Trigger.ADDITION_PLUS_3,
    +4: Trigger.ADDITION_PLUS_4,
}

# Number the participant typed as the final sum -> trigger.
WROTE_NUMBER_TRIGGERS: dict[int, Trigger] = {
    0: Trigger.WROTE_NUMBER_0,
    1: Trigger.WROTE_NUMBER_1,
    2: Trigger.WROTE_NUMBER_2,
    3: Trigger.WROTE_NUMBER_3,
    4: Trigger.WROTE_NUMBER_4,
    5: Trigger.WROTE_NUMBER_5,
    6: Trigger.WROTE_NUMBER_6,
    7: Trigger.WROTE_NUMBER_7,
    8: Trigger.WROTE_NUMBER_8,
    9: Trigger.WROTE_NUMBER_9,
    10: Trigger.WROTE_NUMBER_10,
}

# Correct final sum (revealed in the feedback) -> trigger.
RESULT_TRIGGERS: dict[int, Trigger] = {
    0: Trigger.RESULT_WAS_0,
    1: Trigger.RESULT_WAS_1,
    2: Trigger.RESULT_WAS_2,
    3: Trigger.RESULT_WAS_3,
    4: Trigger.RESULT_WAS_4,
    5: Trigger.RESULT_WAS_5,
    6: Trigger.RESULT_WAS_6,
    7: Trigger.RESULT_WAS_7,
    8: Trigger.RESULT_WAS_8,
    9: Trigger.RESULT_WAS_9,
    10: Trigger.RESULT_WAS_10,
}


# --------------------------------------------------------------- sending
class TriggerPort:
    """Sends trigger codes to the EEG amplifier over the parallel port.

    With ``enabled=False`` nothing is sent (the port is never opened).

    Every ``send`` freezes the program for ``gap_seconds`` from the trigger
    onset (pulse included), so consecutive triggers are always at least
    ``gap_seconds`` apart.
    """

    def __init__(self, address: int = PORT_ADDRESS, *, enabled: bool = True,
                 pulse_seconds: float = PULSE_SECONDS, gap_seconds: float = GAP_SECONDS) -> None:
        self.pulse_seconds = pulse_seconds
        self.gap_seconds = gap_seconds
        self.port = None
        if enabled:
            from psychopy.parallel import ParallelPort
            self.port = ParallelPort(address=address)
            self.port.setData(0)

    def send(self, code: int) -> None:
        if self.port is None:
            return
        onset = core.getTime()
        self.port.setData(int(code))
        core.wait(self.pulse_seconds, hogCPUperiod=self.pulse_seconds)
        self.port.setData(0)
        # Freeze for the rest of the gap, so the next trigger cannot follow sooner.
        remaining = onset + self.gap_seconds - core.getTime()
        if remaining > 0:
            core.wait(remaining, hogCPUperiod=remaining)

    def send_on_flip(self, win, code: int) -> None:
        """Send ``code`` exactly when the next ``win.flip()`` shows the stimulus."""
        if self.port is not None:
            win.callOnFlip(self.send, code)

    def close(self) -> None:
        if self.port is not None:
            self.port.setData(0)


# Sanity check: every code has a description and codes are unique.
assert set(DESCRIPTIONS) == {t.value for t in Trigger}, "DESCRIPTIONS out of sync with Trigger"
