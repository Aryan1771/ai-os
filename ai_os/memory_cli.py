"""Explicit local memory controls; values use stdin to avoid shell history."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ai_os.config import AI_OS_HOME
from ai_os.conversation_memory import ConversationMemory


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", type=Path, default=AI_OS_HOME)
    parser.add_argument("--session", default="default")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("inspect")
    commands.add_parser("sessions")
    remember = commands.add_parser("remember", help="Read preference value from stdin")
    remember.add_argument("key")
    note = commands.add_parser("note", help="Read long-term note body from stdin")
    note.add_argument("title")
    commands.add_parser(
        "forget", help="Read literal text from stdin; removes matching active records"
    )
    clear = commands.add_parser("clear-session")
    clear.add_argument("--confirm", action="store_true", required=True)
    clear_all = commands.add_parser("clear-all")
    clear_all.add_argument("--confirm", action="store_true", required=True)
    args = parser.parse_args()
    memory = ConversationMemory(args.home)
    if args.command == "inspect":
        result = {
            "history": memory.history(args.session),
            "notes": memory.notes(),
            "preferences": memory.preferences(),
        }
    elif args.command == "sessions":
        result = memory.sessions()
    elif args.command in {"remember", "note", "forget"}:
        value = sys.stdin.read(8194).strip()
        if args.command == "remember":
            memory.remember(args.key, value)
            result = {"saved": True}
        elif args.command == "note":
            result = {"note_id": memory.put(args.title, value)}
        else:
            result = {"removed_records": memory.forget(value)}
    elif args.command == "clear-session":
        memory.clear_history(args.session)
        result = {"cleared": True}
    else:
        memory.clear_all()
        result = {"cleared": True}
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
