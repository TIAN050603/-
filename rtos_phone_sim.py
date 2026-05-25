from __future__ import annotations

import argparse
from collections import deque
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Deque, Optional


BOARD_WIDTH = 12
BOARD_HEIGHT = 5


class RuntimeVersion(Enum):
    BUG_REPRODUCTION = "A"
    FIXED_RUNTIME = "B"


class AppId(Enum):
    SNAKE = "SnakeGame"
    PHONE = "PhoneCall"


class AppState(Enum):
    FOREGROUND = auto()
    BACKGROUND = auto()
    PAUSED = auto()
    TERMINATED = auto()


class EventType(Enum):
    TICK = auto()
    INPUT = auto()
    CALL_INCOMING = auto()
    CALL_END = auto()


class Direction(Enum):
    RIGHT = auto()
    DOWN = auto()
    LEFT = auto()
    UP = auto()


@dataclass(frozen=True)
class Event:
    event_type: EventType
    input_key: str = ""


class EventQueue:
    def __init__(self) -> None:
        self._events: Deque[Event] = deque()

    def push(self, event: Event) -> None:
        self._events.append(event)

    def pop(self) -> Optional[Event]:
        if not self._events:
            return None
        return self._events.popleft()

    def __bool__(self) -> bool:
        return bool(self._events)


@dataclass
class SnakeModel:
    x: int = 7
    y: int = 2
    direction: Direction = Direction.RIGHT
    score: int = 0
    alive: bool = True
    tick_count: int = 0

    def apply_input(self, key: str) -> None:
        mapping = {
            "w": Direction.UP,
            "a": Direction.LEFT,
            "s": Direction.DOWN,
            "d": Direction.RIGHT,
        }
        if key in mapping:
            self.direction = mapping[key]

    def tick(self) -> None:
        if not self.alive:
            return

        if self.direction is Direction.RIGHT:
            self.x += 1
        elif self.direction is Direction.DOWN:
            self.y += 1
        elif self.direction is Direction.LEFT:
            self.x -= 1
        elif self.direction is Direction.UP:
            self.y -= 1

        self.score += 1
        self.tick_count += 1

        if self.x < 0 or self.x >= BOARD_WIDTH or self.y < 0 or self.y >= BOARD_HEIGHT:
            self.alive = False


@dataclass
class Application:
    app_id: AppId
    state: AppState
    snake: SnakeModel = field(default_factory=SnakeModel)

    @property
    def name(self) -> str:
        return self.app_id.value

    def on_lifecycle(self, next_state: AppState) -> None:
        if self.state is not next_state:
            print(f"  lifecycle: {self.name} {self.state.name} -> {next_state.name}")
            self.state = next_state

    def on_event(self, event: Event) -> None:
        if self.app_id is AppId.SNAKE:
            self._snake_on_event(event)
        elif self.app_id is AppId.PHONE:
            self._phone_on_event(event)

    def render(self) -> None:
        if self.app_id is AppId.SNAKE:
            self._render_snake()
        elif self.app_id is AppId.PHONE:
            self._render_phone()

    def _snake_on_event(self, event: Event) -> None:
        if event.event_type is EventType.TICK:
            before = (self.snake.x, self.snake.y)
            self.snake.tick()
            after = (self.snake.x, self.snake.y)
            print(
                "  dispatch: SnakeGame consumed TICK "
                f"{before} -> {after}, score={self.snake.score}, alive={self.snake.alive}"
            )
        elif event.event_type is EventType.INPUT:
            self.snake.apply_input(event.input_key)
            print(f"  dispatch: SnakeGame consumed INPUT '{event.input_key}'")

    def _phone_on_event(self, event: Event) -> None:
        if event.event_type is EventType.TICK:
            print("  dispatch: PhoneCall consumed TICK for ringing UI")
        elif event.event_type is EventType.INPUT:
            print(f"  dispatch: PhoneCall consumed INPUT '{event.input_key}'")

    def _render_snake(self) -> None:
        print("  screen: SnakeGame")
        print("  +------------+")
        for y in range(BOARD_HEIGHT):
            row = []
            for x in range(BOARD_WIDTH):
                if self.snake.alive and self.snake.x == x and self.snake.y == y:
                    row.append("S")
                else:
                    row.append(".")
            print(f"  |{''.join(row)}|")
        print(
            "  +------------+ "
            f"score={self.snake.score} ticks={self.snake.tick_count} state={self.state.name}"
        )

    def _render_phone(self) -> None:
        print("  screen: PhoneCall")
        print("  +------------+")
        print("  | INCOMING   |")
        print("  |   CALL     |")
        print("  | accept/end |")
        print(f"  +------------+ state={self.state.name}")


@dataclass
class ResourceTable:
    screen_owner: Optional[AppId] = None
    input_owner: Optional[AppId] = None
    tick_owner: Optional[AppId] = None


class ApplicationManager:
    def __init__(self, version: RuntimeVersion) -> None:
        self.version = version
        self.apps = {
            AppId.SNAKE: Application(AppId.SNAKE, AppState.BACKGROUND),
            AppId.PHONE: Application(AppId.PHONE, AppState.TERMINATED),
        }
        self.resources = ResourceTable()
        self.previous_foreground: Optional[AppId] = None
        self.call_active = False
        self.step = 0
        self._grant_foreground(AppId.SNAKE)

    def process_event(self, event: Event) -> None:
        print(f"\n[step {self.step:02d}] event={event.event_type.name}")
        self.step += 1

        if event.event_type is EventType.CALL_INCOMING:
            self._handle_call_incoming()
        elif event.event_type is EventType.CALL_END:
            self._handle_call_end()
        elif event.event_type is EventType.TICK:
            self._dispatch_tick(event)
        elif event.event_type is EventType.INPUT:
            self._dispatch_input(event)

        self._print_resource_table()
        self._render_screen_owner()

    def _grant_foreground(self, app_id: AppId) -> None:
        self.resources.screen_owner = app_id
        self.resources.input_owner = app_id
        self.resources.tick_owner = app_id
        self.apps[app_id].on_lifecycle(AppState.FOREGROUND)

    def _handle_call_incoming(self) -> None:
        print("  manager: incoming call preempts foreground")
        self.call_active = True
        self.previous_foreground = self.resources.screen_owner

        if self.version is RuntimeVersion.BUG_REPRODUCTION:
            self.apps[AppId.PHONE].on_lifecycle(AppState.FOREGROUND)
            self.resources.screen_owner = AppId.PHONE
            self.resources.input_owner = AppId.PHONE
            print("  bug: timer/tick owner was not revoked from SnakeGame")
            return

        if self.previous_foreground is not None and self.previous_foreground is not AppId.PHONE:
            self.apps[self.previous_foreground].on_lifecycle(AppState.PAUSED)
        self._grant_foreground(AppId.PHONE)

    def _handle_call_end(self) -> None:
        print("  manager: call ended, restore previous foreground app")
        self.call_active = False
        self.apps[AppId.PHONE].on_lifecycle(AppState.TERMINATED)

        if self.previous_foreground is not None:
            self._grant_foreground(self.previous_foreground)
        else:
            self.resources = ResourceTable()

    def _dispatch_tick(self, event: Event) -> None:
        owner = self.resources.tick_owner
        if owner is None or self.apps[owner].state is AppState.TERMINATED:
            print("  dispatch: no active tick owner")
            return

        if (
            self.version is RuntimeVersion.FIXED_RUNTIME
            and self.apps[AppId.SNAKE].state is AppState.PAUSED
        ):
            print("  dispatch: SnakeGame tick suppressed by ApplicationManager")

        self.apps[owner].on_event(event)

    def _dispatch_input(self, event: Event) -> None:
        owner = self.resources.input_owner
        if owner is None or self.apps[owner].state is AppState.TERMINATED:
            print("  dispatch: no active input owner")
            return
        self.apps[owner].on_event(event)

    def _print_resource_table(self) -> None:
        def label(owner: Optional[AppId]) -> str:
            return owner.value if owner is not None else "None"

        print(
            "  resources: "
            f"screen={label(self.resources.screen_owner)} "
            f"input={label(self.resources.input_owner)} "
            f"tick={label(self.resources.tick_owner)}"
        )

    def _render_screen_owner(self) -> None:
        owner = self.resources.screen_owner
        if owner is None or self.apps[owner].state is AppState.TERMINATED:
            print("  screen: blank")
            return
        self.apps[owner].render()


def build_scenario(name: str) -> EventQueue:
    queue = EventQueue()

    if name == "normal":
        for _ in range(3):
            queue.push(Event(EventType.TICK))
    elif name == "call":
        queue.push(Event(EventType.TICK))
        queue.push(Event(EventType.CALL_INCOMING))
        for _ in range(5):
            queue.push(Event(EventType.TICK))
    elif name == "call_end":
        queue.push(Event(EventType.TICK))
        queue.push(Event(EventType.TICK))
        queue.push(Event(EventType.CALL_INCOMING))
        queue.push(Event(EventType.TICK))
        queue.push(Event(EventType.TICK))
        queue.push(Event(EventType.CALL_END))
        queue.push(Event(EventType.TICK))
        queue.push(Event(EventType.TICK))
    else:
        raise ValueError(f"unknown scenario: {name}")

    return queue


def run_simulation(version: RuntimeVersion, scenario: str) -> None:
    print("\n============================================================")
    title = "A BUG REPRODUCTION" if version is RuntimeVersion.BUG_REPRODUCTION else "B FIXED"
    print(f"Runtime {title} | scenario={scenario}")
    print("============================================================")

    manager = ApplicationManager(version)
    queue = build_scenario(scenario)
    manager._print_resource_table()

    while queue:
        event = queue.pop()
        if event is not None:
            manager.process_event(event)

    snake = manager.apps[AppId.SNAKE].snake
    snake_state = manager.apps[AppId.SNAKE].state
    print(
        "\nsummary: "
        f"snake=(x={snake.x}, y={snake.y}, score={snake.score}, "
        f"ticks={snake.tick_count}, alive={snake.alive}, state={snake_state.name})"
    )


def run_all_tests() -> None:
    run_simulation(RuntimeVersion.FIXED_RUNTIME, "normal")
    run_simulation(RuntimeVersion.BUG_REPRODUCTION, "call")
    run_simulation(RuntimeVersion.FIXED_RUNTIME, "call")
    run_simulation(RuntimeVersion.FIXED_RUNTIME, "call_end")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Feature-phone RTOS lifecycle/resource arbitration simulator"
    )
    parser.add_argument(
        "--version",
        choices=["A", "B"],
        default="B",
        help="A reproduces the bug, B uses the fixed runtime",
    )
    parser.add_argument(
        "--scenario",
        choices=["normal", "call", "call_end"],
        default="call_end",
        help="simulation scenario to run",
    )
    parser.add_argument("--test", action="store_true", help="run all required test scenarios")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.test:
        run_all_tests()
        return

    version = RuntimeVersion.BUG_REPRODUCTION if args.version == "A" else RuntimeVersion.FIXED_RUNTIME
    run_simulation(version, args.scenario)


if __name__ == "__main__":
    main()
