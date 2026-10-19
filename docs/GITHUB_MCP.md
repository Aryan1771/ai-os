# GitHub access

REgenOS uses the official `github/github-mcp-server` as a bounded local stdio
process. The initial integration provides **read-only** branches, commits, open
issues, open pull requests and repository files. It does not create issues,
comment, change files, push, merge, trigger workflows or approve actions.
GitHub access is an online feature; offline runtime remains separate.

The current Codex session already exposes the connected GitHub MCP tools. No
duplicate Codex server or token-bearing configuration was added. Future Codex
sessions can check their connected tools; GitHub CLI authentication alone does
not automatically register an MCP server in a different client. See the
[official OpenAI MCP documentation](https://developers.openai.com/codex/mcp/).

## Local setup and boundaries

`ai_os.github_mcp.github_read` uses an explicit repository allowlist from the
private `~/.ai_os/github-mcp.json`. The model cannot choose an arbitrary server,
executable, host, credential, tool name or write operation. A trusted local setup
handler calls `configure_github(enabled, repositories, human_confirmed=True)`;
never register that setup function as a model tool. Disabling access is immediate
for subsequent requests. Existing requests are bounded to 25 seconds.

The native **Settings → Permissions → GitHub account reading** section has
**Choose repositories…** and **Disable GitHub access**. Scope approval defaults
to No and preserves unrelated unsaved preferences. Following the user's explicit
request, this host enables only `Aryan1771/ai-os`. A live branch read and a local
model routing that request through `github_read` passed; the latter took 2.00s
with temporary history and no private conversations. Try: “Read the branches of
Aryan1771/ai-os on GitHub.” These results do not enable commits or account writes.

The child obtains the existing github.com credential using `gh auth token`
internally. It passes the token only in the server's environment, never argv,
preferences or logs. Never run that auth command manually with its output visible
or put its output into Git. The underlying gh login can have broader privileges
than this reader; the MCP filter does not reduce the credential's own scopes.
A separately scoped credential is preferable for deployment.

Every invocation verifies the reviewed binary SHA256 and launches with
`--read-only`, an empty toolset and five fixed individual tools. The client also
checks the requested tool's `readOnlyHint` before calling it. Inherited GitHub
server overrides, proxies and logging options are excluded. Protocol data has a
1 MiB budget. Returned text has a 24,000-character limit, with common credential
formats withheld. These heuristics cannot guarantee that arbitrary source text
contains no secrets; known secret-file paths are refused. No raw server errors or
stderr are exposed. The child is stopped and reaped after every request.

Account content is untrusted reference data. It must not approve or trigger
computer actions, be forwarded to remote providers or be saved automatically as
personal memory. The reader requires a loopback Ollama endpoint. Native model
integration preserves this boundary: a GitHub result terminates the action loop
and is shown as bounded plaintext in the current native chat window. It is not
appended to persistent conversation databases, reinforcement or a later model
request. Even a manually constructed GitHub tool trace is rejected before
inference. Speech acknowledges readiness in English/Hindi without automatically
reading account file contents aloud. Native and resident voice callers use that
same speech boundary. Copying displayed material into a new user message is an
explicit new input, separate from automatic context collection.
Read-only access is not a complete OS sandbox or an account-wide security policy.

## Provisioned release on this Arch host

After the user's explicit request to download GitHub MCP tooling, fetched the
official Linux x86_64 release **v2.0.2**, built from
`eb47a99ddb866ca2b8a162920e6bda9521f33ebb`. The 9,209,049-byte archive digest
matched both the GitHub release API asset digest and the published checksums file.
Only the regular binary and LICENSE entries were extracted, not arbitrary archive
paths. Files live outside Git at:

```text
~/.ai_os/tools/github-mcp-server/v2.0.2/github-mcp-server
~/.ai_os/tools/github-mcp-server/v2.0.2/LICENSE
~/.ai_os/tools/github-mcp-server/v2.0.2/manifest.json
~/.ai_os/tools/github-mcp-server/v2.0.2/download/
```

Archive SHA256:
`815e27d931c796af0c97f24fd211e14f8a4607d4528377719a5ad2352086b0b0`

Extracted binary SHA256:
`721ffbb573397d8e95b847f7a1908359fd2973784ca8a8d5d3182db6f9fcb5b6`

The adapter pins this version and binary digest. Updating requires a reviewed
source change and validation, rather than silently downloading “latest.” The
currently pinned digest supports this Linux x86_64 release only. Other platforms
remain pending. No privileged package, Docker daemon, service or system setting
was changed. No GitHub account write was performed.

Exact download/version commands used:

```bash
mkdir -p ~/.ai_os/tools/github-mcp-server/v2.0.2/download
gh release download v2.0.2 --repo github/github-mcp-server \
  --pattern github-mcp-server_Linux_x86_64.tar.gz \
  --pattern github-mcp-server_2.0.2_checksums.txt \
  --dir ~/.ai_os/tools/github-mcp-server/v2.0.2/download
~/.ai_os/tools/github-mcp-server/v2.0.2/github-mcp-server --version
~/.ai_os/venv/bin/python -m ai_os.github_mcp --status
```

Before extracting a replacement archive, check its SHA256 against the exact
reviewed digest above and the published checksums. Extract only the regular
`github-mcp-server`/`LICENSE` members, reject links and existing output paths,
and set the binary to mode 0700. A normal `tar -x` over an existing directory is
not the reviewed extraction procedure. The private manifest records both hashes.

## Validation

```bash
~/.ai_os/venv/bin/python -m pytest -q tests/test_github_mcp.py
~/.ai_os/venv/bin/python -m pytest -q tests/test_github_mcp_integration.py \
  tests/test_interaction_harness.py
~/.ai_os/venv/bin/python -m ruff check --select E4,E7,E9,F \
  ai_os/github_mcp.py ai_os/ai_os_core.py ai_os/tool_protocol.py \
  tests/test_github_mcp.py tests/test_github_mcp_integration.py
```

The focused suite covers native-only setup, private preferences, checksum
tampering, write-tool rejection, secret/traversal paths, remote-provider refusal,
credential handling, real child timeout/output-budget cleanup, annotations and
embedded file text. Live stdio negotiation found exactly the five expected
read-only tools; branch and README reads succeeded without printing their content.
This is read-access evidence, not write capability or UI acceptance.

Integration tests also cover hostile tool-shaped repository text, persistent
memory isolation, public progress isolation, remote/local inference rejection,
later-turn context isolation and deterministic bounded display/speech. Partial
constructor failure and native SystemExit cancellation stop and reap the child.
The server remains in its request process group, so the resident voice worker's
group cancellation also reaches it; it cannot outlive that group by creating a
separate session. No model-selected commands run inside this fixed server.

Official references:

- [GitHub MCP server source and releases](https://github.com/github/github-mcp-server)
- [Read-only mode and tool selection](https://github.com/github/github-mcp-server/blob/main/docs/server-configuration.md)
- [GitHub's Codex client setup](https://github.com/github/github-mcp-server/blob/main/docs/installation-guides/install-codex.md)
- [OpenAI MCP configuration](https://developers.openai.com/codex/mcp/)
