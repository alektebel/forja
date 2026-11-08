"""
SNS + EventBridge — fanout and pattern matching. Starter template.

DESIGN DECISION — push or pull?
  SQS is pull: a consumer asks, and a message waits until someone does.
  SNS is push: the topic delivers to every subscriber, now, and if a subscriber
  is down the message is retried and then dropped.
  CHOSEN: model push, and model the consequence — the classic architecture is
  SNS *in front of* SQS precisely so that fanout gets push semantics while each
  consumer keeps a durable buffer it controls.

DESIGN DECISION — filter at the subscriber or at the topic?
  Filtering in the subscriber is simpler and costs you a delivery per message
  per subscriber, most of which get thrown away.
  CHOSEN: filter policies evaluated at the topic. It also forces the semantics
  into the open: attributes AND across keys, OR within a key's value list —
  the same rule as IAM conditions, and wrong-footed for the same reason.
"""

import fnmatch
from typing import Any, Callable, Dict, List, Optional, Sequence


class Subscription:
    def __init__(self, protocol: str, endpoint: Any, name: str = "",
                 filter_policy: Optional[Dict[str, Any]] = None,
                 raw_delivery: bool = False):
        self.protocol = protocol          # "sqs", "lambda", "http"
        self.endpoint = endpoint
        self.name = name or protocol
        self.filter_policy = filter_policy
        self.raw_delivery = raw_delivery
        self.delivered = 0
        self.filtered_out = 0
        self.failed = 0

    def __repr__(self) -> str:
        return f"<Sub {self.name} delivered={self.delivered} filtered={self.filtered_out}>"


def matches_filter(policy: Optional[Dict[str, Any]],
                   attributes: Dict[str, Any]) -> bool:
    """SNS filter-policy semantics.

    The rule, which trips people up in exactly the same way IAM conditions do:
      - every KEY in the policy must match (AND)
      - any VALUE in that key's list may match (OR)
      - a key absent from the message attributes does NOT match

    Supported value forms: a literal, {"prefix": ...}, {"anything-but": ...},
    {"numeric": ["<", 5]}, and {"exists": true/false}.
    """
    raise NotImplementedError


def _value_matches(rule: Any, value: Any) -> bool:
    raise NotImplementedError


class Topic:
    def __init__(self, name: str):
        self.name = name
        self.subscriptions: List[Subscription] = []
        self.stats = {"published": 0, "deliveries": 0, "filtered": 0, "failed": 0}

    def subscribe(self, protocol: str, endpoint: Any, name: str = "",
                  filter_policy: Optional[Dict[str, Any]] = None) -> Subscription:
        subscription = Subscription(protocol, endpoint, name, filter_policy)
        self.subscriptions.append(subscription)
        return subscription

    def publish(self, message: str,
                attributes: Optional[Dict[str, Any]] = None,
                now: Optional[float] = None) -> Dict[str, int]:
        """Deliver to every matching subscriber. One publish, N deliveries.

        `now` is threaded through to SQS subscribers so a simulated clock stays
        consistent end to end. Without it, a topic on wall-clock time enqueues
        messages "in the future" relative to a test running at t=0, and they
        silently never become visible.
        """
        raise NotImplementedError

    @staticmethod
    def _deliver(subscription: Subscription, message: str,
                 attributes: Dict[str, Any],
                 now: Optional[float] = None) -> None:
        raise NotImplementedError
# ---------------------------------------------------------------------------
# EventBridge: the same idea, with structural pattern matching
# ---------------------------------------------------------------------------

def matches_event_pattern(pattern: Dict[str, Any], event: Dict[str, Any]) -> bool:
    """EventBridge matches the SHAPE of the event, not flat attributes.

    The difference from SNS: patterns nest, and a list in a pattern means "any
    of these", while a nested dict means "descend and keep matching". Content
    filters ({"prefix": ...}, {"numeric": [...]}) work at any depth.
    """
    raise NotImplementedError


class EventBus:
    def __init__(self, name: str = "default"):
        self.name = name
        self.rules: List[Dict[str, Any]] = []
        self.stats = {"events": 0, "matched": 0}

    def add_rule(self, name: str, pattern: Dict[str, Any],
                 target: Callable[[Dict[str, Any]], None]) -> None:
        raise NotImplementedError

    def put_event(self, event: Dict[str, Any]) -> List[str]:
        """An event may match zero, one or many rules — all of them fire."""
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
