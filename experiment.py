"""PsychoPy presentation of the counting task."""

from __future__ import annotations

from psychopy import core, event, sound, visual

from config import ExperimentConfig, Strategy
from design import TrialSpec
from storage import ResultStore
from triggers import (ADDITION_TRIGGERS, RESULT_TRIGGERS, START_NUMBER_TRIGGERS, Trigger,
                      TriggerPort, WROTE_NUMBER_TRIGGERS)

BASELINE_SECONDS = 60
PRACTICE_EXAMPLES: tuple[tuple[Strategy, int, tuple[int, ...]], ...] = (
    ("head", 4, (+2, -1, +3, -2)),
    ("hands", 3, (+2, +1, -2, +3)),
)
DIGIT_KEYS = {f"{d}": d for d in "0123456789"} | {f"num_{d}": d for d in "0123456789"}
ENTER_KEYS = {"return", "num_enter", "enter"}
MINUS = "−"  # typographic minus, same width as "+"

# (start, end) trigger of the counting period for each strategy.
STRATEGY_TRIGGERS: dict[Strategy, tuple[Trigger, Trigger]] = {
    "hands": (Trigger.STRATEGY_HANDS_START, Trigger.STRATEGY_HANDS_END),
    "head": (Trigger.STRATEGY_HEAD_START, Trigger.STRATEGY_HEAD_END),
}

STRATEGY_TEXT: dict[Strategy, tuple[str, str]] = {
    "head": (
        "Count IN YOUR HEAD",
        "Keep the running total in your mind only.\n"
        "Keep your hands relaxed and still on the table.",
    ),
    "hands": (
        "Count WITH YOUR HANDS",
        "Show the running total with your fingers (0 to 10).\n"
        "Update your fingers after every number, moving only your hands.",
    ),
}


class QuitExperiment(Exception):
    """Raised when the operator presses the quit key."""


def format_step(step: int) -> str:
    return f"+{step}" if step >= 0 else f"{MINUS}{abs(step)}"


class CountingTask:
    def __init__(self, cfg: ExperimentConfig, store: ResultStore, port: TriggerPort) -> None:
        self.cfg = cfg
        self.store = store
        self.port = port
        self.win = visual.Window(
            size=cfg.window_size, fullscr=cfg.fullscreen, screen=cfg.screen,
            color=cfg.background_color, units="height", allowGUI=not cfg.fullscreen,
        )
        self.win.mouseVisible = False
        self.aspect = self.win.size[0] / self.win.size[1]
        self.end_beep = sound.Sound(value=880, secs=0.5)
        self._build_stimuli()

    # ------------------------------------------------------------------ setup
    def _text(self, text: str = "", *, height: float | None = None, pos=(0, 0),
              color: str | None = None, bold: bool = False, wrap: float | None = None):
        return visual.TextStim(
            self.win, text=text, font=self.cfg.font, pos=pos, bold=bold,
            height=height or self.cfg.text_height, color=color or self.cfg.text_color,
            wrapWidth=wrap or min(1.2, self.aspect * 0.9), alignText="center",
        )

    def _build_stimuli(self) -> None:
        c = self.cfg
        arm, thick = c.fixation_size, c.fixation_size * 0.16
        self.fixation = [
            visual.Rect(self.win, width=arm, height=thick, fillColor=c.text_color, lineWidth=0),
            visual.Rect(self.win, width=thick, height=arm, fillColor=c.text_color, lineWidth=0),
        ]
        # Every number uses the same colour/size/position in both conditions so
        # the visual input is identical and does not confound the EEG contrast.
        self.number = self._text(height=c.number_height, bold=True)
        self.footer = self._text(pos=(0, -0.42), color=c.muted_color, height=c.text_height * 0.85)

    # ---------------------------------------------------------------- helpers
    def _check_quit(self, keys=None) -> None:
        keys = keys if keys is not None else event.getKeys([self.cfg.quit_key])
        if self.cfg.quit_key in keys:
            raise QuitExperiment

    def _present(self, stims, seconds: float) -> None:
        """Draw ``stims`` for ``seconds``, timed from the first screen flip."""
        for s in stims:
            s.draw()
        onset = self.win.flip()
        # Stop half a frame early so the next stimulus lands on the right frame.
        frame = self.win.monitorFramePeriod or 1 / 60
        while core.getTime() - onset < seconds - frame / 2:
            for s in stims:
                s.draw()
            self.win.flip()
            self._check_quit()

    def _wait_for_continue(self, stims) -> None:
        event.clearEvents()
        while True:
            for s in stims:
                s.draw()
            self.win.flip()
            keys = event.getKeys([self.cfg.continue_key, self.cfg.quit_key])
            self._check_quit(keys)
            if self.cfg.continue_key in keys:
                return

    def _continue_hint(self, verb: str = "continue") -> visual.TextStim:
        self.footer.text = f"Press {self.cfg.continue_key.upper()} to {verb}"
        return self.footer

    def resting_state_baseline(self) -> None:
        self._wait_for_continue([
            self._text(
                "Eyes open\n\n"
                "Keep your eyes on the fixation cross, blink as little as possible, "
                "and remain as still as possible.",
                pos=(0, 0.08),
            ),
            self._continue_hint("begin"),
        ])
        self.port.send_on_flip(self.win, Trigger.EYES_OPEN_START)
        self._present(self.fixation, BASELINE_SECONDS)

        self.port.send_on_flip(self.win, Trigger.EYES_OPEN_END)
        self._wait_for_continue([
            self._text("Eyes-open section complete.", pos=(0, 0.08)),
            self._continue_hint(),
        ])

        self._wait_for_continue([
            self._text(
                "Eyes closed\n\n"
                "Close your eyes and remain as still as possible. "
                "A beep will signal the end of this section.",
                pos=(0, 0.08),
            ),
            self._continue_hint("begin"),
        ])
        self.port.send_on_flip(self.win, Trigger.EYES_CLOSED_START)
        self._present([], BASELINE_SECONDS)
        self.port.send_on_flip(self.win, Trigger.EYES_CLOSED_END)
        self.win.callOnFlip(self.end_beep.play)
        self._wait_for_continue([
            self._text(
                "Eyes-closed section complete. You may open your eyes.",
                pos=(0, 0.08),
            ),
            self._continue_hint(),
        ])

    # ---------------------------------------------------------------- screens
    def instructions(self) -> None:
        c = self.cfg
        title = self._text("Counting task", height=0.06, pos=(0, 0.38), bold=True)
        intro = self._text(
            f"Each trial starts with a cross in the middle of the screen. Keep your eyes on it "
            f"and try not to blink or move your eyes while the numbers appear.\n\n"
            f"You will first see a starting number, followed by {c.step_count} numbers to add "
            f"or subtract (for example +3 or {MINUS}2). The running total always stays between "
            f"{c.value_min} and {c.value_max}. At the end, type the final total and press ENTER.\n\n"
            f"Before each trial you will be told which of two strategies to use:",
            pos=(0, 0.19), wrap=min(1.3, self.aspect * 0.85),
        )
        stims = [title, intro]
        panel_w = min(0.62, self.aspect * 0.42)
        x = panel_w / 2 + 0.03
        for sign, strategy, color in ((-1, "head", c.head_color), (1, "hands", c.hands_color)):
            heading, body = STRATEGY_TEXT[strategy]
            stims += [
                visual.Rect(self.win, width=panel_w, height=0.3, pos=(sign * x, -0.15),
                            fillColor=c.panel_color, lineColor=color, lineWidth=3),
                self._text(heading, pos=(sign * x, -0.05), color=color, bold=True,
                           height=c.text_height * 1.15),
                self._text(body, pos=(sign * x, -0.18), wrap=panel_w * 0.88,
                           height=c.text_height * 0.9),
            ]
        stims.append(self._continue_hint("begin"))
        self.port.send_on_flip(self.win, Trigger.EXPERIMENT_START)
        self._wait_for_continue(stims)

    def practice(self) -> None:
        """Explain and check both strategies before the first baseline."""
        self.port.send_on_flip(self.win, Trigger.PRACTICE_START)
        self._wait_for_continue([
            self._text("Practice first", height=0.07, pos=(0, 0.18), bold=True),
            self._text(
                "You will try both strategies. Each example has one starting number "
                "and only four numbers to add or subtract.\n\n"
                "A + sign means add; a minus sign means subtract. Keep the running "
                "total between steps. At the end, type the final number and press ENTER.",
                pos=(0, -0.02),
            ),
            self._continue_hint("begin practice"),
        ])
        results: dict[Strategy, bool] = {}
        for strategy, start, steps in PRACTICE_EXAMPLES:
            heading, body = STRATEGY_TEXT[strategy]
            color = self.cfg.head_color if strategy == "head" else self.cfg.hands_color
            self._wait_for_continue([
                self._text(heading, height=0.07, pos=(0, 0.19), color=color, bold=True),
                self._text(
                    f"{body}\n\nA cross appears before the starting number "
                    "and between each step. Start with the first number. Add when "
                    "you see + and subtract when you see a minus sign. Update your "
                    "running total after every step. The screens advance on their "
                    "own; type your final total when the answer box appears.",
                    pos=(0, -0.02),
                ),
                self._continue_hint("start the example"),
            ])
            self._present(self.fixation, self.cfg.fixation_seconds)
            self.number.text = str(start)
            self._present([self.number], self.cfg.number_display_seconds)
            for step in steps:
                self._present(self.fixation, self.cfg.fixation_seconds)
                self.number.text = format_step(step)
                self._present([self.number], self.cfg.number_display_seconds)
            self._present(self.fixation, self.cfg.fixation_seconds)
            response, _ = self.collect_response(emit_triggers=False)
            answer = start + sum(steps)
            correct = response == answer
            results[strategy] = correct
            working = "  →  ".join(
                [str(start)] + [str(start + sum(steps[:index])) for index in range(1, 5)]
            )
            self._present([
                self._text(
                    "Correct!" if correct else f"The correct answer is {answer}.",
                    height=0.06, pos=(0, 0.1),
                    color=self.cfg.correct_color if correct else self.cfg.incorrect_color,
                    bold=True,
                ),
                self._text(
                    f"The running total was: {working}", pos=(0, -0.05),
                ),
            ], max(4.0, self.cfg.feedback_seconds))
        self.port.send_on_flip(self.win, Trigger.PRACTICE_END)
        self._wait_for_continue([
            self._text("Practice complete", height=0.07, pos=(0, 0.15), bold=True),
            self._text(
                f"In your head: {'correct' if results['head'] else 'incorrect'}; "
                f"with your hands: {'correct' if results['hands'] else 'incorrect'}.\n\n"
                "Ask the experimenter if any instruction is unclear. "
                "The experiment begins with eyes-open and eyes-closed resting periods.",
                pos=(0, -0.03),
            ),
            self._continue_hint("begin the resting periods"),
        ])

    def strategy_cue(self, trial: TrialSpec, n_trials: int) -> None:
        c = self.cfg
        color = c.head_color if trial.strategy == "head" else c.hands_color
        heading, body = STRATEGY_TEXT[trial.strategy]
        self.port.send_on_flip(self.win, Trigger.TRIAL_START)
        self._wait_for_continue([
            self._text(f"Trial {trial.index} of {n_trials}", pos=(0, 0.2), color=c.muted_color),
            self._text(heading, height=0.07, pos=(0, 0.07), color=color, bold=True),
            self._text(body, pos=(0, -0.08)),
            self._continue_hint("start the trial"),
        ])

    def collect_response(self, *, emit_triggers: bool = True) -> tuple[int | None, float | None]:
        c = self.cfg
        prompt = self._text("What is the final number?", pos=(0, 0.14), height=0.045)
        box = visual.Rect(self.win, width=0.22, height=0.14, fillColor=c.panel_color,
                          lineColor=c.muted_color, lineWidth=2)
        typed = self._text(height=0.09, bold=True)
        hint = self._text("Type the number, then press ENTER  (BACKSPACE to correct)",
                          pos=(0, -0.16), color=c.muted_color, height=c.text_height * 0.85)
        answer = ""
        event.clearEvents()
        clock = core.Clock()
        self.win.callOnFlip(clock.reset)  # RT measured from prompt onset
        # Writing is part of the strategy period; the strategy end trigger is
        # sent later, when the result is revealed (see run_trial / feedback).
        if emit_triggers:
            self.port.send_on_flip(self.win, Trigger.WRITING_SUM_START)
        while True:
            typed.text = answer
            for s in (prompt, box, typed, hint):
                s.draw()
            self.win.flip()
            if c.response_timeout_seconds is not None and clock.getTime() > c.response_timeout_seconds:
                if emit_triggers:
                    self.port.send(Trigger.WRITING_SUM_END)
                return None, None
            for key in event.getKeys():
                self._check_quit([key])
                if key in DIGIT_KEYS and len(answer) < c.max_response_digits:
                    answer += DIGIT_KEYS[key]
                elif key == "backspace":
                    answer = answer[:-1]
                elif key in ENTER_KEYS and answer:
                    rt = clock.getTime()
                    value = int(answer)
                    if emit_triggers:
                        self.port.send(Trigger.WRITING_SUM_END)
                    if emit_triggers and value in WROTE_NUMBER_TRIGGERS:  # no trigger exists for e.g. 11+
                        self.port.send(WROTE_NUMBER_TRIGGERS[value])
                    return value, rt

    def feedback(self, correct: bool, trial: TrialSpec, response: int | None) -> None:
        """Show correct/incorrect; the strategy period ends at this flip."""
        c = self.cfg
        if correct:
            stims = [self._text("Correct", height=0.06, color=c.correct_color, bold=True)]
        else:
            head = "Too slow" if response is None else "Incorrect"
            stims = [
                self._text(head, height=0.06, pos=(0, 0.04), color=c.incorrect_color, bold=True),
                self._text(f"The answer was {trial.correct_answer}", pos=(0, -0.06)),
            ]
        self.port.send_on_flip(self.win, STRATEGY_TRIGGERS[trial.strategy][1])
        self.port.send_on_flip(self.win, Trigger.RESULT_REVEALED)
        self.port.send_on_flip(self.win, RESULT_TRIGGERS[trial.correct_answer])
        self._present(stims, c.feedback_seconds)

    def take_break(self, done: int, n_trials: int) -> None:
        """Rest screen between blocks; ends when the participant presses ENTER."""
        self.port.send_on_flip(self.win, Trigger.BREAK_START)
        stims = [
            self._text("Break", height=0.07, pos=(0, 0.12), bold=True),
            self._text(f"You have completed {done} of {n_trials} trials.\n\n"
                       f"Take a short rest. Press ENTER when you are ready to continue.",
                       pos=(0, -0.03)),
        ]
        event.clearEvents()
        while True:
            for s in stims:
                s.draw()
            self.win.flip()
            keys = event.getKeys(list(ENTER_KEYS) + [self.cfg.quit_key])
            self._check_quit(keys)
            if ENTER_KEYS & set(keys):
                break
        self.port.send(Trigger.BREAK_END)

    # ------------------------------------------------------------------ trial
    def run_trial(self, trial: TrialSpec, n_trials: int) -> bool:
        c = self.cfg
        self.strategy_cue(trial, n_trials)
        # Each item: (text shown on screen, trigger sent when it appears),
        # e.g. ("+2", Trigger.ADDITION_PLUS_2 = 40).
        shown = [(str(trial.start_value), START_NUMBER_TRIGGERS[trial.start_value])]
        shown += [(format_step(s), ADDITION_TRIGGERS[s]) for s in trial.steps]
        # Counting period starts with the first fixation cross after the cue.
        self.port.send_on_flip(self.win, STRATEGY_TRIGGERS[trial.strategy][0])
        for text, code in shown:
            self._present(self.fixation, c.fixation_seconds)
            self.number.text = text
            self.port.send_on_flip(self.win, code)
            self._present([self.number], c.number_display_seconds)
        self._present(self.fixation, c.fixation_seconds)

        response, rt = self.collect_response()
        correct = self.store.save_trial(
            trial_index=trial.index, strategy=trial.strategy, start_value=trial.start_value,
            steps=trial.steps, correct_answer=trial.correct_answer, response=response,
            rt_seconds=rt, task_id=trial.task_id, round=trial.round,
        )
        # The strategy period (counting + writing the sum) ends when the
        # correct/incorrect feedback appears, or right after the answer if
        # feedback is disabled.
        if c.show_feedback:
            self.feedback(correct, trial, response)
        else:
            self.port.send(STRATEGY_TRIGGERS[trial.strategy][1])
        self.port.send(Trigger.TRIAL_END)
        return correct

    def run(self, trials: list[TrialSpec]) -> None:
        self.instructions()
        if self.cfg.enable_practice:
            self.practice()
        self.resting_state_baseline()
        n, every = len(trials), self.cfg.break_every
        n_correct = 0
        for done, trial in enumerate(trials, start=1):
            n_correct += self.run_trial(trial, n)
            if every and done % every == 0 and done < n:
                self.take_break(done, n)
        self.resting_state_baseline()
        self._wait_for_continue([
            self._text("Thank you!", height=0.07, pos=(0, 0.08), bold=True),
            self._text(f"You answered {n_correct} of {len(trials)} trials correctly.",
                       pos=(0, -0.03)),
            self._continue_hint("finish"),
        ])

    def close(self) -> None:
        self.win.close()
