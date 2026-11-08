"""
Lambda — invocation, concurrency and cold starts. Starter template.

DESIGN DECISION — how to model a "container"?
  You could invoke the handler directly and call it done.
  CHOSEN: model the execution ENVIRONMENT explicitly, with a lifetime and
  reusable state. That is what makes cold starts, warm state and the
  "why is my global variable still there" question demonstrable — and global
  state surviving between invocations is the single most common Lambda bug.

DESIGN DECISION — one concurrency number, or reserved plus unreserved?
  CHOSEN: both. Reserved concurrency is a floor AND a ceiling: it guarantees a
  function that much capacity and forbids it more. Setting it on one function
  silently reduces what every other function can use, which is a failure mode
  worth feeling once.

DESIGN DECISION — how do sync and async invocations differ?
  CHOSEN: model both. Synchronous throttling returns a 429 to the caller;
  asynchronous throttling is retried internally, and only after the retries
  are exhausted does the event go to a dead-letter destination. Same function,
  completely different failure behaviour.
"""

import time
from typing import Any, Callable, Dict, List, Optional, Tuple


class Throttled(Exception):
    """TooManyRequestsException — 429."""


class ExecutionEnvironment:
    """One "container": has an init cost, then survives to be reused."""

    def __init__(self, env_id: int, init_ms: float, now: float):
        self.env_id = env_id
        self.init_ms = init_ms
        self.created_at = now
        self.last_used = now
        self.invocations = 0
        self.state: Dict[str, Any] = {}     # survives between invocations

    def __repr__(self) -> str:
        return f"<Env {self.env_id} invocations={self.invocations}>"


class Invocation:
    def __init__(self, request_id: str, cold: bool, duration_ms: float,
                 billed_ms: float, result: Any, error: Optional[str] = None,
                 env_id: int = 0, attempt: int = 1):
        self.request_id = request_id
        self.cold = cold
        self.duration_ms = duration_ms
        self.billed_ms = billed_ms
        self.result = result
        self.error = error
        self.env_id = env_id
        self.attempt = attempt

    def __repr__(self) -> str:
        state = f"error={self.error}" if self.error else f"result={self.result!r}"
        return (f"<{'COLD' if self.cold else 'warm'} {self.billed_ms:.0f}ms "
                f"env={self.env_id} {state}>")


class Function:
    def __init__(self, name: str, handler: Callable[[Any, Any], Any],
                 memory_mb: int = 128, timeout_s: float = 3.0,
                 init_ms: float = 800.0, env_ttl_s: float = 300.0,
                 reserved_concurrency: Optional[int] = None,
                 dead_letter: Optional[List[Any]] = None):
        self.name = name
        self.handler = handler
        self.memory_mb = memory_mb
        self.timeout_s = timeout_s
        self.init_ms = init_ms
        self.env_ttl_s = env_ttl_s
        self.reserved_concurrency = reserved_concurrency
        self.dead_letter = dead_letter if dead_letter is not None else []
        self.environments: List[ExecutionEnvironment] = []
        self.busy = 0
        self._next_env = 1
        self.stats = {"invocations": 0, "cold_starts": 0, "throttles": 0,
                      "errors": 0, "async_retries": 0, "dead_lettered": 0,
                      "billed_ms": 0.0}


class LambdaService:
    """The control plane: owns the account-wide concurrency pool."""

    ACCOUNT_CONCURRENCY = 10       # tiny, so the limit is reachable in a demo

    def __init__(self, account_concurrency: Optional[int] = None):
        self.account_concurrency = account_concurrency or self.ACCOUNT_CONCURRENCY
        self.functions: Dict[str, Function] = {}

    def register(self, function: Function) -> Function:
        self.functions[function.name] = function
        return function
    # -- concurrency accounting ---------------------------------------------

    def unreserved_capacity(self) -> int:
        """What is left for functions WITHOUT reserved concurrency.

        Reserved concurrency is carved out of the account pool whether it is
        being used or not. Reserving 5 of 10 for one function means every other
        function in the account now shares 5 — which is why a single reservation
        can throttle an unrelated service.
        """
        raise NotImplementedError

    def available_for(self, function: Function) -> int:
        raise NotImplementedError
    # -- invocation ---------------------------------------------------------

    def invoke(self, name: str, event: Any, now: Optional[float] = None,
               duration_ms: float = 50.0) -> Invocation:
        """Synchronous invoke. Throttling raises — the caller sees a 429."""
        raise NotImplementedError

    def invoke_async(self, name: str, event: Any, now: Optional[float] = None,
                     duration_ms: float = 50.0,
                     max_attempts: int = 3) -> List[Invocation]:
        """Asynchronous invoke: retried internally, then dead-lettered.

        This is the difference that matters operationally. A synchronous caller
        sees the failure immediately and decides what to do. An asynchronous
        event is retried by Lambda itself — twice by default — and only then
        goes to the destination. A handler that is not idempotent will run
        three times.
        """
        raise NotImplementedError

    def _acquire_environment(self, function: Function,
                             now: float) -> Tuple[ExecutionEnvironment, bool]:
        """Reuse a warm environment if one is free; otherwise pay the init cost."""
        raise NotImplementedError

    def concurrent_invoke(self, name: str, events: List[Any],
                          now: Optional[float] = None,
                          duration_ms: float = 50.0) -> Tuple[int, int]:
        """Fire N events at once. Returns (succeeded, throttled)."""
        raise NotImplementedError


def _demo() -> None:
    """Once the checks pass, write a demo that PRINTS the behaviour.

    The solution's demo is the reference — but write yours first and predict
    the numbers before running it. A result that surprises you is a gap in your
    model that passing tests did not reveal.
    """
    raise NotImplementedError


if __name__ == "__main__":
    _demo()
