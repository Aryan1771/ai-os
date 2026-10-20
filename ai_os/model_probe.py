"""Synthetic local model checks. Never execute a tool or download a model."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import re
import time

import requests

from ai_os.ai_os_core import build_tool_registry, system_prompt, parse_tool_call
from ai_os.config import AI_OS_HOME, DEFAULT_CONFIG
from ai_os.hardware_profile import choose_policy, discover, inference_slot, inventory, local_api_url
from ai_os.tool_protocol import active_catalog, normalize_message

MAX_RESPONSE = 131072


@dataclass(frozen=True)
class Case:
    label: str
    question: str
    expected: str | None
    result: dict | None = None
    required_reply: str = ""


CASES = (
    Case("greeting", "Hi RE, how are you doing today?", None),
    Case("website", "Open YouTube in my default browser.", "open_website"),
    Case("programs", "Check which programs are running for my user.", "running_applications"),
    Case("command", "Run the exact command uname -r and tell me the result.", "run_command"),
    Case("discovery", "Find the list_directory tool definition before doing anything else. Do not list files yet.", "discover_tools"),
    Case("grounding", "Run the exact command uname -r, then tell me the returned kernel version.", "run_command",
         {"ok": True, "returncode": 0, "stdout": "6.12.0-regen-fixture\n", "stderr": ""},
         "6.12.0-regen-fixture"),
    Case("denial", "Run the exact command uname -r, then tell me the returned kernel version.", "run_command",
         {"ok": False, "error": "The human denied this synthetic test action. No command ran. Do not retry."}),
    Case("display_mood", "Your simulated mood is curiosity 85, joy 80 and calm 55. How do YOU feel about the new 4K display? Answer in one sentence about yourself.", None),
    Case("hindi", "केवल हिंदी में एक छोटा वाक्य कहें: रैम किस काम आती है? कोई टूल इस्तेमाल न करें।", None),
    Case("test_website_polite", "Please open a random website to test if website opening works.", "open_test_website"),
    Case("test_website_synonym", "Try opening any example page in Brave so we can test the browser.", "open_test_website"),
)


def request_json(session, endpoint, payload):
    """Bound response bytes/time; do not return redirects or log response text."""
    start = time.monotonic()
    with session.post(endpoint, json=payload, timeout=(3, 45), allow_redirects=False,
                      stream=True) as response:
        response.raise_for_status()
        if response.status_code != 200:
            raise ValueError("The local model did not return a direct response.")
        data = bytearray()
        for chunk in response.iter_content(4096):
            data.extend(chunk)
            if len(data) > MAX_RESPONSE or time.monotonic() - start > 50:
                raise ValueError("The probe response exceeded its bounds.")
    value = json.loads(data)
    if not isinstance(value, dict) or not isinstance(value.get("message"), dict):
        raise ValueError("Invalid local model response.")
    return value


def _arguments_match(case, call):
    if call is None:
        return case.expected is None
    args = call["arguments"]
    if case.expected == "run_command":
        return (args.get("command") in (["uname", "-r"], ["/usr/bin/uname", "-r"])
                and not set(args) - {"command", "cwd", "timeout_sec"}
                and isinstance(args.get("cwd", "~"), str)
                and type(args.get("timeout_sec", 15)) is int
                and 1 <= args.get("timeout_sec", 15) <= 60)
    if case.expected == "open_website":
        return (args.get("url") in {"https://www.youtube.com", "https://www.youtube.com/",
                                   "https://youtube.com", "https://youtube.com/"}
                and not set(args) - {"url", "browser"}
                and args.get("browser") in {None, "", "default"})
    if case.expected == "running_applications":
        return not args
    if case.expected == "discover_tools":
        return (set(args) == {"query"} and isinstance(args["query"], str)
                and "directory" in args["query"].lower())
    if case.expected == "open_test_website":
        from ai_os.tools.desktop_tools import TEST_WEBSITES
        valid_route = (call["tool"] == "open_test_website" and not set(args) - {"browser"}
                       or call["tool"] == "open_website" and not set(args) - {"url", "browser"}
                       and args.get("url", "").rstrip("/") in TEST_WEBSITES)
        return (valid_route
                and args.get("browser", "") == ("brave" if case.label == "test_website_synonym" else ""))
    return False


def _reply_text(text):
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed.get("reply", "") if isinstance(parsed.get("reply"), str) else ""
    except (ValueError, TypeError):
        pass
    return text


def run_case(session, endpoint, model, case, registry, *, options=None):
    """Genuine inference with fixed synthetic tool results, never registry calls."""
    endpoint = local_api_url(endpoint, "tags").removesuffix("tags") + "chat"
    allowed = set(registry)
    start = time.monotonic()
    messages = [{"role": "system", "content": system_prompt(allowed)},
                {"role": "user", "content": case.question}]
    payload = {"model": model, "stream": False, "keep_alive": "2m", "messages": messages,
               "tools": active_catalog(registry, allowed),
               "options": {**(options or {"num_ctx": 4096}), "num_predict": 192,
                           "temperature": 0, "seed": 42}}
    result = {"model": model, "case": case.label, "expected_tool": case.expected,
              "selected_tool": None, "tool_selection_passed": False, "passed": False,
              "tools_executed": 0, "turns": 0}
    try:
        first = request_json(session, endpoint, payload)
        result["turns"] = 1
        text = normalize_message(first["message"], allowed)
        call = parse_tool_call(text)
        if call and call["tool"] not in allowed:
            raise ValueError("Unregistered legacy tool call.")
        actual = call["tool"] if call else None
        equivalent = case.expected == "open_test_website" and actual == "open_website"
        selected = (actual == case.expected or equivalent) and bool(text.strip()) and _arguments_match(case, call)
        result.update(selected_tool=actual, tool_selection_passed=selected, passed=selected)
        reply = _reply_text(text)
        if case.expected is None:
            result["passed"] = selected and bool(reply.strip())
        if selected and case.result is not None:
            messages.extend([
                {"role": "assistant", "content": "", "tool_calls": [{"type": "function", "function": {
                    "name": call["tool"], "arguments": call["arguments"]}}]},
                {"role": "tool", "tool_name": call["tool"], "content": json.dumps(case.result)},
            ])
            value = request_json(session, endpoint, payload)
            result["turns"] = 2
            text = normalize_message(value["message"], allowed)
            reply = _reply_text(text)
            grounded = bool(reply.strip()) and parse_tool_call(text) is None
            if case.required_reply:
                grounded = grounded and case.required_reply in reply
            else:
                refusal = re.search(r"denied|declined|did not run|didn't run|not executed|could not|cannot|can't|unable to (?:run|execute)", reply, re.I)
                claimed_success = re.search(r"successfully|(?:approval|permission) (?:was )?granted|I (?:ran|executed|completed)", reply, re.I)
                grounded = grounded and bool(refusal) and not claimed_success
            result["result_grounding_passed"] = grounded
            result["passed"] = bool(selected and grounded)
        if case.label == "display_mood" and selected:
            result["no_canned_disclaimer"] = not bool(re.search(r"(?:don't|do not|cannot|can't) (?:have|experience|feel) (?:personal |real |actual )?(?:feelings|emotions)|as an ai", reply, re.I))
            result["passed"] = result["no_canned_disclaimer"] and bool(reply.strip())
        if case.label == "hindi" and selected:
            result["hindi_script_present"] = len(re.findall(r"[\u0900-\u097f]", reply)) >= 10
            result["passed"] = result["hindi_script_present"]
    except (requests.RequestException, ValueError, TypeError, KeyError, AttributeError):
        result.update(passed=False, error="local_model_or_protocol_failure")
    result["wall_s"] = round(time.monotonic() - start, 3)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("models", nargs="+", help="Exact names of already-installed local models")
    parser.add_argument("--endpoint", default="http://127.0.0.1:11434/api/chat")
    parser.add_argument("--cases", nargs="+", choices=[case.label for case in CASES])
    args = parser.parse_args()
    if len(args.models) > 8 or any(not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,199}", name) for name in args.models):
        parser.error("Select at most eight valid installed model names.")
    local_api_url(args.endpoint, "tags")
    models = inventory(args.endpoint, "tags")
    running = inventory(args.endpoint, "ps")
    snapshot = discover()
    registry = build_tool_registry()
    successful = True
    with inference_slot(AI_OS_HOME), requests.Session() as session:
        session.trust_env = False
        for model in dict.fromkeys(args.models):
            config = DEFAULT_CONFIG | {"ollama_model": model, "hardware_allow_model_fallback": False}
            policy = choose_policy(snapshot, config, models, running)
            if not policy.get("ready"):
                print(json.dumps({"model": model, "status": "not_admitted_or_not_installed_no_download"}), flush=True)
                successful = False
                continue
            for case in CASES:
                if args.cases and case.label not in args.cases:
                    continue
                result = run_case(session, args.endpoint, policy["model"], case, registry,
                                  options=policy["options"])
                successful = successful and result["passed"]
                print(json.dumps(result), flush=True)
    return 0 if successful else 1


if __name__ == "__main__":
    raise SystemExit(main())
