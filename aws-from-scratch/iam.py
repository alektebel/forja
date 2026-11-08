"""
IAM — policy evaluation. Starter template.

The most valuable service to implement, because the evaluation rule is short,
counter-intuitive, and everybody gets it wrong at least once:

    1. An explicit DENY anywhere always wins.
    2. Otherwise, an explicit ALLOW grants access.
    3. Otherwise, DENY (implicit).

That is it. Everything else — wildcards, conditions, NotAction, boundaries — is
detail hung off those three lines.

DESIGN DECISION — evaluate statements in order, or partition by effect?
  Reading statements top-to-bottom and letting the last one win is how firewall
  rules work, and it is what people expect.
  CHOSEN: partition by effect. Collect every matching Deny, then every matching
  Allow. Order is irrelevant. This is what AWS actually does, and it is why
  moving a statement in a policy document never changes the outcome — a
  property worth having, and worth proving to yourself.

DESIGN DECISION — how much of the condition language to support?
  The real one has dozens of operators, set semantics, policy variables.
  CHOSEN: StringEquals, StringLike, Bool, IpAddress, NumericLessThan and
  ArnLike. Enough to show that conditions AND across keys and OR within a key —
  the rule that surprises people — without drowning in operators.
"""

import fnmatch
import ipaddress
from typing import Any, Dict, List, Optional, Sequence, Tuple

ALLOW, DENY = "Allow", "Deny"


class Statement:
    """One statement of a policy document."""

    def __init__(self, effect: str, action, resource, condition=None,
                 not_action=None, sid: str = ""):
        if effect not in (ALLOW, DENY):
            raise ValueError(f"effect must be Allow or Deny, got {effect!r}")
        self.effect = effect
        self.action = _as_list(action)
        self.not_action = _as_list(not_action) if not_action else None
        self.resource = _as_list(resource)
        self.condition: Dict[str, Dict[str, Any]] = condition or {}
        self.sid = sid

    def __repr__(self) -> str:
        return f"<{self.effect} {self.action or 'NOT ' + str(self.not_action)}>"


def _as_list(value) -> List[str]:
    if value is None:
        return []
    return [value] if isinstance(value, str) else list(value)


class Policy:
    def __init__(self, statements: Sequence[Statement], name: str = ""):
        self.statements = list(statements)
        self.name = name

    def __repr__(self) -> str:
        return f"<Policy {self.name or '(unnamed)'} {len(self.statements)} stmts>"


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------

def matches_action(pattern: str, action: str) -> bool:
    """`s3:*` matches `s3:GetObject`. Case-insensitive, like the real thing."""
    return fnmatch.fnmatch(action.lower(), pattern.lower())


def matches_resource(pattern: str, resource: str) -> bool:
    """ARN matching with `*` and `?`.

    Note `*` crosses `:` and `/` here, which is also true in AWS — a common
    surprise, since `arn:aws:s3:::bucket/*` matches every key including ones
    with slashes in them.
    """
    return fnmatch.fnmatch(resource, pattern)


def evaluate_condition(condition: Dict[str, Dict[str, Any]],
                       context: Dict[str, Any]) -> bool:
    """All condition blocks must pass; within one key, any listed value passes.

    This is the rule people get wrong: conditions AND across keys and OR within
    a key's value list. Two separate StringEquals keys must BOTH hold; two
    values under one key means either will do.
    """
    raise NotImplementedError


def _condition_holds(operator: str, actual: Any, options: List[Any]) -> bool:
    if actual is None:
        return False
    if operator == "StringEquals":
        return any(str(actual) == str(option) for option in options)
    if operator == "StringNotEquals":
        return all(str(actual) != str(option) for option in options)
    if operator in ("StringLike", "ArnLike", "ArnEquals"):
        return any(fnmatch.fnmatch(str(actual), str(option)) for option in options)
    if operator == "Bool":
        return any(bool(actual) == (str(option).lower() == "true") for option in options)
    if operator == "NumericLessThan":
        return any(float(actual) < float(option) for option in options)
    if operator == "NumericGreaterThanEquals":
        return any(float(actual) >= float(option) for option in options)
    if operator == "IpAddress":
        address = ipaddress.ip_address(str(actual))
        return any(address in ipaddress.ip_network(str(option), strict=False)
                   for option in options)
    raise ValueError(f"unsupported condition operator {operator!r}")
# ---------------------------------------------------------------------------
# The evaluation rule
# ---------------------------------------------------------------------------

class Decision:
    def __init__(self, allowed: bool, reason: str, statement: Optional[Statement] = None):
        self.allowed = allowed
        self.reason = reason
        self.statement = statement

    def __bool__(self) -> bool:
        return self.allowed

    def __repr__(self) -> str:
        return f"{'ALLOW' if self.allowed else 'DENY '}  {self.reason}"


def statement_matches(statement: Statement, action: str, resource: str,
                      context: Dict[str, Any]) -> bool:
    if statement.not_action is not None:
        if any(matches_action(pattern, action) for pattern in statement.not_action):
            return False
    elif not any(matches_action(pattern, action) for pattern in statement.action):
        return False
    if not any(matches_resource(pattern, resource) for pattern in statement.resource):
        return False
    return not statement.condition or evaluate_condition(statement.condition, context)


def evaluate(policies: Sequence[Policy], action: str, resource: str,
             context: Optional[Dict[str, Any]] = None) -> Decision:
    """Explicit deny > explicit allow > implicit deny.

    Note that policies are evaluated as a SET. Statement order within a policy,
    and policy order within the list, cannot change the answer — which is worth
    verifying yourself, because it is the property that makes large policy sets
    tractable to reason about.

    Stage 1: replace the raise with an implicit-deny Decision when policies is
    empty. That is a one-line first green. Stage 2 adds a matching Allow;
    stage 3 gives matching Deny precedence regardless of order. Read only the
    guide for the stage you are on.
    """
    raise NotImplementedError


def evaluate_with_boundary(identity: Sequence[Policy], boundary: Optional[Policy],
                           action: str, resource: str,
                           context: Optional[Dict[str, Any]] = None) -> Decision:
    """A permissions boundary caps what identity policies can grant.

    The boundary never grants anything on its own: the request must be allowed
    by BOTH the identity policies and the boundary. This is how you delegate
    "you may create roles" without also delegating "you may create admin roles".
    """
    raise NotImplementedError
# ---------------------------------------------------------------------------
# STS: assuming a role
# ---------------------------------------------------------------------------

class Role:
    """A role is a permission set plus a trust policy saying who may assume it."""

    def __init__(self, arn: str, trust: Policy, permissions: Sequence[Policy]):
        self.arn = arn
        self.trust = trust
        self.permissions = list(permissions)


class Credentials:
    def __init__(self, principal: str, policies: Sequence[Policy],
                 session_name: str = "", expires_at: float = 0.0):
        self.principal = principal
        self.policies = list(policies)
        self.session_name = session_name
        self.expires_at = expires_at

    def __repr__(self) -> str:
        return f"<Credentials {self.principal} session={self.session_name!r}>"


def assume_role(caller: Credentials, role: Role, session_name: str,
                context: Optional[Dict[str, Any]] = None) -> Credentials:
    """Two checks, and forgetting either one is a real security bug.

    1. The role's TRUST policy must allow this caller to assume it.
    2. The caller's own policies must allow sts:AssumeRole on the role ARN.

    Both directions matter: the role decides who may wear it, and the caller's
    administrator decides which roles their people may wear.
    """
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
