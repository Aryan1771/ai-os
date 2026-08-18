from __future__ import annotations

import sys
from dataclasses import dataclass
from enum import Enum


class ConsentDecision(str, Enum):
    APPROVED = "approved"
    DENIED = "denied"


@dataclass(frozen=True)
class ConsentRequest:
    action: str
    risk: str
    reason: str
    command: list[str] | None = None


def request_cli_consent(request: ConsentRequest) -> ConsentDecision:
    print("\n[AI-OS CONSENT REQUIRED]", file=sys.stderr)
    print(f"Action: {request.action}", file=sys.stderr)
    print(f"Risk: {request.risk}", file=sys.stderr)
    print(f"Reason: {request.reason}", file=sys.stderr)
    if request.command:
        print(f"Command: {' '.join(request.command)}", file=sys.stderr)

    while True:
        answer = input("[Approve/Deny] ").strip().lower()
        if answer in {"approve", "a", "yes", "y"}:
            return ConsentDecision.APPROVED
        if answer in {"deny", "d", "no", "n"}:
            return ConsentDecision.DENIED
        print("Please type Approve or Deny.", file=sys.stderr)

