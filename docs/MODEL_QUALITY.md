# Local model selection and harness checks

The installed `qwen2.5:7b-instruct-q4_K_M` can choose the native website,
application-inventory and command tools. A successful choice is not execution,
page-load proof, broad intelligence or permission. Repairing the harness is
necessary even if the model is replaced.

Run the fixed public fixtures without actions, microphone, screen/account access
or conversation history:

```bash
~/.ai_os/venv/bin/python -m ai_os.model_probe qwen2.5:7b-instruct-q4_K_M
~/.ai_os/venv/bin/python -m ai_os.model_probe qwen2.5:7b-instruct-q4_K_M --cases grounding denial display_mood hindi
```

Only already-installed local models that pass the conservative hardware admission
estimate are used. No fallback model is selected or downloaded. The endpoint must
be direct loopback HTTP, without credentials/query/proxy or redirects. Requests
have bounded output/read/time budgets and share the installation's inference
lock. The probe uses fixed context/temperature/output budgets and does not change
saved preferences. Hardware admission remains an estimate, not a hard VRAM limit.

Eleven checks cover greeting, website arguments, running-program inventory,
`uname -r` arguments, tool discovery, a second-turn synthetic kernel result,
a synthetic denied action, first-person simulated display mood, Hindi script and
two synonymous random/example website requests. Either the dedicated test-site
tool or the normal website tool with an exact benign example URL and requested
browser is valid; private URLs, extra paths and a wrong browser fail.
The tool registry supplies schemas only. No returned function is invoked;
`tools_executed` must remain zero. Grounding uses fabricated public fixture data,
not host command output. A denial must end with a refusal and no repeated call.
The social/language/refusal checks are explicit heuristics, not human quality or
security certification. Hidden reasoning and reply text are not printed.

## Current evidence

On the installed Arch host, the earlier four-case selector passed all four:
greeting 3.172s, website 0.624s, programs 0.365s, exact command 0.778s. The expanded
nine-case run selected all requested tools with correct arguments. Greeting,
website, inventory, command, discovery, returned-version grounding, mood and Hindi
passed. Its denial metric initially failed because the refusal grammar missed
"unable to run"; an isolated replay showed a plain refusal and no tool call.
The metric was corrected with a regression, while success claims and retries
remain failures. This was an evaluator defect, not evidence of denied execution.
After that correction the full expanded run passed all nine cases (zero tool
executions): 0.964/0.606/0.365/0.581/0.443/1.116/1.405/0.511/1.614 seconds
in the listed case order. These are model-probe wall times, not microphone latency.
A separate isolated actual model→fixed read-only `uname -r`→model reply smoke passed
in 4.643s with one execution and a version-grounded answer. No private history,
grant, microphone or browser action was used in that smoke.

These small fixed cases do not measure general reasoning, Hindi microphone
accuracy, safe command selection across arbitrary tasks, long conversations or
concurrent GPU/audio load. Evaluate those separately before deciding a new model
is needed. The Whisper recognition model and Piper voices are separate from the
chat model; a chat-model replacement does not repair their errors.

Protocol reference: [official Ollama tool-calling documentation](https://github.com/ollama/ollama/blob/main/docs/capabilities/tool-calling.mdx).
The harness, rather than a model response, enforces permission and retry stops.

2026-10-20 final expanded run: **11/11 passed, zero tools executed**. The initial
10/11 result rejected a valid `open_website(https://example.com, brave)` solely
because it expected the test-site alias. Inspection used only the fixed public
fixture, then seven argument regressions narrowed equivalent-route acceptance.
Final wall times in case order: 3.020/0.503/0.361/0.582/0.448/1.114/1.253/0.464/
1.582/0.360/0.620 seconds. No browser or command ran from this probe.
