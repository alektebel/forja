"""
VPC — CIDR, routing, and the difference that causes the most confusion:
security groups are STATEFUL, network ACLs are NOT. Starter template.

DESIGN DECISION — model packets, or model rules?
  Evaluating rules in isolation tells you what a rule says. It does not tell
  you whether a connection works, and "the rule looks right but it does not
  connect" is the entire genre of VPC bug.
  CHOSEN: model a CONNECTION — a request packet and its reply — and evaluate
  both directions. The stateful/stateless difference then appears as a
  behavioural result rather than a fact to memorise: the same ruleset that
  works for a security group silently drops the RETURN traffic on a NACL.

DESIGN DECISION — how much CIDR arithmetic to implement?
  Python has `ipaddress`. Using it would skip the part worth understanding:
  that a /24 inside a /16 is a containment test on the network address, and
  that subnets in one VPC must not overlap.
  CHOSEN: use `ipaddress` for parsing, but implement containment, overlap and
  the usable-host count by hand, since those are the numbers people get wrong.
"""

import ipaddress
from typing import Any, Dict, List, NamedTuple, Optional, Sequence, Tuple

# AWS reserves 5 addresses in every subnet: network, VPC router, DNS, future
# use, and broadcast. A /28 gives you 11 usable hosts, not 16 — which is how
# people run out of addresses in a subnet they sized "with room to spare".
AWS_RESERVED_PER_SUBNET = 5


class Cidr:
    def __init__(self, notation: str):
        self.network = ipaddress.ip_network(notation, strict=False)
        self.notation = notation

    def contains(self, other: "Cidr") -> bool:
        raise NotImplementedError

    def contains_ip(self, address: str) -> bool:
        raise NotImplementedError

    def overlaps(self, other: "Cidr") -> bool:
        raise NotImplementedError

    def usable_hosts(self) -> int:
        raise NotImplementedError

    def __repr__(self) -> str:
        return self.notation


class Rule(NamedTuple):
    number: int
    action: str                 # "allow" or "deny"
    protocol: str               # "tcp", "udp", "icmp", "-1"
    port_from: int
    port_to: int
    cidr: str

    def matches(self, protocol: str, port: int, address: str) -> bool:
        if self.protocol not in ("-1", protocol):
            return False
        if self.protocol != "-1" and not self.port_from <= port <= self.port_to:
            return False
        return Cidr(self.cidr).contains_ip(address)


class SecurityGroup:
    """STATEFUL. If a request is allowed out, the reply is allowed back in —
    regardless of the inbound rules. You never write a rule for return traffic.
    """

    def __init__(self, group_id: str, name: str = ""):
        self.group_id = group_id
        self.name = name or group_id
        self.inbound: List[Rule] = []
        self.outbound: List[Rule] = [
            Rule(1, "allow", "-1", 0, 65535, "0.0.0.0/0")]   # AWS default

    def allow_inbound(self, protocol: str, port_from: int, port_to: int,
                      cidr: str) -> None:
        self.inbound.append(Rule(len(self.inbound) + 1, "allow", protocol,
                                 port_from, port_to, cidr))

    def evaluate(self, direction: str, protocol: str, port: int,
                 address: str) -> bool:
        """Allow-only: there is no deny rule. Absence of an allow IS the deny."""
        rules = self.inbound if direction == "in" else self.outbound
        return any(rule.matches(protocol, port, address) for rule in rules)


class NetworkAcl:
    """STATELESS. Every packet is evaluated on its own, in rule-number order,
    first match wins. Return traffic needs its OWN rule — on ephemeral ports.
    """

    def __init__(self, acl_id: str):
        self.acl_id = acl_id
        self.inbound: List[Rule] = []
        self.outbound: List[Rule] = []

    def add(self, direction: str, number: int, action: str, protocol: str,
            port_from: int, port_to: int, cidr: str) -> None:
        rules = self.inbound if direction == "in" else self.outbound
        rules.append(Rule(number, action, protocol, port_from, port_to, cidr))

    def evaluate(self, direction: str, protocol: str, port: int,
                 address: str) -> Tuple[bool, str]:
        """Stage 58 replaces insertion order with lowest-rule-number priority."""
        rules = self.inbound if direction == "in" else self.outbound
        # Stage 58 will order these by rule number. For now use insertion order.
        for rule in rules:
            if rule.matches(protocol, port, address):
                return rule.action == "allow", f"rule {rule.number} ({rule.action})"
        return False, "no rule matched"


class Subnet:
    def __init__(self, subnet_id: str, cidr: str, public: bool = False,
                 acl: Optional[NetworkAcl] = None):
        self.subnet_id = subnet_id
        self.cidr = Cidr(cidr)
        self.public = public
        self.acl = acl
        self.route_table: List[Tuple[str, str]] = [("local", "local")]

    def add_route(self, destination: str, target: str) -> None:
        raise NotImplementedError

    def route_for(self, address: str) -> str:
        """Most specific match wins — the longest prefix, not the first entry."""
        raise NotImplementedError


class Vpc:
    def __init__(self, vpc_id: str, cidr: str):
        self.vpc_id = vpc_id
        self.cidr = Cidr(cidr)
        self.subnets: Dict[str, Subnet] = {}

    def add_subnet(self, subnet_id: str, cidr: str, public: bool = False,
                   acl: Optional[NetworkAcl] = None) -> Subnet:
        raise NotImplementedError


def test_connection(source_ip: str, dest_ip: str, port: int,
                    security_group: Optional[SecurityGroup] = None,
                    acl: Optional[NetworkAcl] = None,
                    protocol: str = "tcp",
                    ephemeral_port: int = 49152) -> Dict[str, Any]:
    """Evaluate a whole connection: the request AND its reply.

    This is the function that makes the stateful/stateless difference visible.
    A security group evaluates the request; the reply is implied. A NACL
    evaluates both packets independently, and the reply arrives on an EPHEMERAL
    port — which no one remembers to allow.

    TODO: evaluate BOTH directions and AND the results:
      1. NACL inbound on the request port.
      2. Security group inbound on the request port.
      3. The reply. A security group is STATEFUL — the reply needs no rule.
         A NACL is STATELESS — evaluate its OUTBOUND rules against the
         EPHEMERAL port the reply goes back to (49152-65535).

    Step 3 is the whole point. Evaluate only the request and a NACL will look
    identical to a security group, and the most common VPC bug becomes
    invisible.
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
