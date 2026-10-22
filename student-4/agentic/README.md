# Shared agentic loop — Student 4 (Stella Kwon)

**Plan → Act → Observe → Adapt**, now over six probe packs.

Release 0 shipped this as a review of my own three microservices. Release 1
extended it into the team's **shared agentic loop**: the same engine,
selected with `--mode`, validating the two shared AI services. Release 2
adds three more modes, and they review something different in kind — not a
running service, but the **evidence the rest of the team produces**.

```
python agentic/loop.py                        # --mode review (default)
python agentic/loop.py --mode mcp
python agentic/loop.py --mode rag
python agentic/loop.py --mode all             # the three Release 1 modes

python agentic/loop.py --mode multi-agent     # Release 2
python agentic/loop.py --mode testing
python agentic/loop.py --mode cloud
python agentic/loop.py --mode release2        # the three Release 2 modes
```

| Mode | What it validates | Probes | Areas |
| --- | --- | --- | --- |
| `review` | my database, backend and frontend | 16 | database · implementation · architecture · devops |
| `mcp` | the shared MCP server | 12 | availability · protocol · invocation · resilience |
| `rag` | the shared RAG server | 15 | availability · retrieval · grounding · resilience |
| `multi-agent` | the shared Multi-Agent server and its workflow records | 19 | availability · workflow · chain-of-custody · human-review |
| `testing` | pre-commit security scanning and post-commit endpoint testing | 17 | configuration · security-scan · endpoint-tests · reporting |
| `cloud` | the cloud deployment, its AI baseline and the release decision | 17 | artefacts · deployment · baseline · release-decision |

## The engine does not know what any of the six modes are

`plan()`, `act()`, `observe()` and `adapt()` have not been changed once
across five new modes. A mode contributes a list of `Probe` objects and the
four area names those probes are tagged with; the engine plans, runs,
aggregates and adapts over whatever it is handed. `build_mode()` is still
the only function that knows the modes exist.

```
agentic/
    loop.py                 the engine + the review pack + the mode registry
    probes_mcp.py           the MCP pack            build_mcp_probes(...)
    probes_rag.py           the RAG pack            build_rag_probes(...)
    probes_multiagent.py    the Multi-Agent pack    build_multiagent_probes(...)
    probes_testing.py       the testing pack        build_testing_probes(...)
    probes_cloud.py         the cloud pack          build_cloud_probes(...)
    repo.py                 repository helpers the packs share
    evidence.py             evidence helpers the Release 2 packs share
    capture_multiagent.py   records my own workflow run as evidence
    logs/                   loop-<mode>-<timestamp>.md and .jsonl
```

`repo.py` exists because of a bug this work found in itself. The first
version of the compose check matched any two-space-indented key and
reported the named volume `ollama-models` as a service, which would have
sent somebody looking for a container that never existed.
`compose_services()` tracks which top-level block it is inside and only
returns names declared under `services:`.

Adding another mode means writing another `probes_*.py` and one line in
`build_mode()`. That is how the three Release 2 modes were added.

## Everything here runs on the host

The MCP server, the RAG server and Ollama are **deliberately not
containerised** in Release 1, which is why the defaults are `localhost`
addresses rather than Docker service names:

| Service | Default | Override |
| --- | --- | --- |
| Shared MCP server | `http://localhost:5700` | `--mcp-url` / `MCP_URL` |
| Shared RAG server | `http://localhost:5600` | `--rag-url` / `RAG_URL` |
| Shared Multi-Agent server | `http://localhost:5800` | `--multiagent-url` / `MULTI_AGENT_URL` |
| Ollama | `http://localhost:11434` | `--ollama-url` / `OLLAMA_URL` |

Three probes enforce that rule rather than trusting it:
`mcp_not_containerised`, `rag_not_containerised` and
`ma_not_containerised` read `docker-compose.yml` and fail if any of the
three servers — or Ollama — reappears as a Compose service.

## `--mode mcp`

The MCP server was still being written when this pack was, so it does not
assume a transport. On the first call it tries, in order, JSON-RPC 2.0 at
`POST /mcp`, JSON-RPC at `POST /`, then REST at `GET /tools` with
`POST /invoke` or `POST /tools/<name>`. Whichever answers first is remembered
and **named in the evidence**, so the log records the contract the server
actually implements rather than the one I hoped for. Both transports were
tested against stub servers before this was committed.

| Area | Probes |
| --- | --- |
| **availability** | the server answers and its transport is known · it is not a Compose service |
| **protocol** | a tool list is discoverable, named and free of duplicates · every tool carries a description *and* an input schema, because a model cannot choose a tool it cannot read · an Order & Kitchen tool is exposed |
| **invocation** | a tool call returns structured data rather than prose · **the tool agrees with the owning service** · a call finishes inside 15 s |
| **resilience** | an unknown tool name is refused, not a 500 · bad arguments are refused, not a 500 · no MCP source file opens a database directly · a missing order is reported rather than invented |

`mcp_agrees_with_owner` is the probe that earns its place. It calls the MCP
tool and my own `student-4-backend` for the same data and compares the order
ids. A tool that is up, well-formed and *wrong* is the failure nothing else
catches, because every other check would pass.

## `--mode rag`

Validated against the contract in `shared/rag/`: `GET /health`,
`POST /retrieve` and `POST /query`, a 0.5 keyword-coverage floor, at most
three chunks, confidence `high ≥ 0.75 / medium ≥ 0.5 / low`, and
`insufficient_context` returned without invoking the model at all.

| Area | Probes |
| --- | --- |
| **availability** | `/health` answers · the RAG server is not a Compose service · Ollama is not a Compose service |
| **retrieval** | `/retrieve` returns the documented shape · missing, empty, whitespace and wrong-typed questions are all refused with 400 · every chunk clears the 0.5 floor · at most three chunks, ordered best first · Order & Kitchen is in the knowledge base |
| **grounding** | `/query` answers an in-corpus question · every source names a document and quotes the excerpt it came from · **the answer stays inside its sources** · the reported confidence matches the measured coverage |
| **resilience** | an unanswerable question is refused with `answer: null` and no sources · the refusal short-circuits *before* the model · a model outage degrades to a 503 with a message |

`rag_stays_grounded` is the one that matters. It takes the content words of
the answer, takes the content words of the excerpts that were actually cited,
and measures how much of the answer is traceable to them. This is the same
pattern my Release 0 AI-Mode used on its own narrative — compute the facts,
then validate the model's prose against them — applied to somebody else's
service.

It was tested by pointing the real RAG server at a deliberately hallucinating
model. Fourteen of the fifteen probes still passed; that one failed with
*"94% of the answer's content words appear in none of the cited excerpts"*.
Citations alone would not have caught it, because the citations were correct
— it was the answer that had left them.

`rag_refusal_is_cheap` is a timing probe: a real model takes seconds, the
retrieval path takes milliseconds, so a refusal returned in under three
seconds proves the model was never invoked.

## Release 2 — reviewing evidence rather than services

The three Release 1 modes all probe something that is running. The three
Release 2 modes mostly do not: a cloud deployment, a CI security scan and a
multi-agent workflow all happen and then leave **evidence** behind, and the
review is of that evidence. `evidence.py` exists for one reason — to tell
the two cases apart honestly:

> is this missing because nobody has produced it yet, or present and wrong?

Those are different findings belonging to different people, so the probes
report them differently. A mode that said "FAIL" for both would be useless
to the person reading it.

`evidence.py` also carries a scar. Its path walker is called `dig()`, not
`get()`. An earlier version was called `get()`, and three cloud probes wrote
`ev.get("status", "")` out of habit — which parsed as the nested path
`data["status"][""]`, resolved to `None`, stringified to `"none"`, and
compared against the wrong value *while passing their own tests*. Renaming
the method is the fix, because the `dict.get` shape is now impossible to
write by accident.

### `--mode multi-agent`

Reviews the shared Planner → Worker → Reviewer → Human Review server and the
workflow records it leaves in `evidence/release2/multi-agent/`.

| Area | Probes |
| --- | --- |
| **availability** | the server answers `/health` · it is not a Compose service · the workflow route is live and 404s an unknown id rather than faulting · **it is reachable from my own feature**, through `student-4-backend`'s health report |
| **workflow** | a record exists and parses · all three agents produced output · that output is structured, not prose · the coordination log covers every stage · the log is in chronological order |
| **chain-of-custody** | the Planner set out steps · the plan separates what it read from what it could not · **the Worker used the plan** · the Worker cited the supplied evidence · **the Reviewer judged the actual work** · the review gives a recommendation *and* a reason |
| **human-review** | a human made one of the four valid decisions · the decision is timestamped after the run · a non-approval carries comments · the run reached `completed` |

The chain-of-custody probes are the ones that earn their place. Three agents
in sequence can each produce a plausible document while nobody reads anybody
else's — the Worker answering the task directly and ignoring the plan, the
Reviewer judging the task rather than the work. Nothing in the output looks
wrong when that happens. So these probes measure **vocabulary overlap
between stages**: how much of the plan's language appears in the work, and
how much of the work's appears in the review. A stage that did not read its
input is the failure the pipeline cannot see from the inside.

`capture_multiagent.py` records my own run as evidence, deliberately
**through `student-4-backend`** rather than against `:5800` directly —
calling the shared server myself would prove only that somebody else's
server works.

### `--mode testing`

Reviews the team's pre-commit security scanning and post-commit endpoint
testing: `.pre-commit-config.yaml`, the Ruff `S` rules, the detect-secrets
baseline, `tests/release2/post_commit/` and the reports in
`reports/release2/`.

| Area | Probes |
| --- | --- |
| **configuration** | all three scanners are named · Ruff's security rules are selected · every suppression carries a written reason · a detect-secrets baseline is committed · the dependency audit script exists |
| **security-scan** | every hook entry resolves · the excludes do not skip application source · Ruff runs against the shared config |
| **endpoint-tests** | every service has an endpoint test file · two endpoint functions tested each · every test asserts something · the workflows actually invoke them · **the pytest output shows passes and no failures** · the output came from a CI runner, not a laptop |
| **reporting** | every student filed an audit row · **the audit rows agree with the pytest output** · the rows are timestamped |

`audit_rows_agree_with_the_pytest_output` is the one that matters. An audit
row saying `PASS` next to a captured pytest log showing failures is a
reporting failure, not a test failure, and it is the only kind that survives
a green pipeline.

`suppressions_carry_a_reason` had to be rewritten once. The first version
looked three lines back for a comment and false-positived on ten
well-documented entries, because one comment introduces a *group* of
per-file ignores. It is now a state machine: a comment opens a justified
block, a blank line closes it. Both directions were re-tested.

### `--mode cloud`

Reviews the cloud deployment artefacts, the AI baseline and the human
release decision.

| Area | Probes |
| --- | --- |
| **artefacts** | `cloud-deployment.yml` exists and names a platform · deployment is gated on validation · the deployment scripts are parameterised rather than hard-coded · the scripts exit on the first failure · no literal credentials anywhere in them · a smoke test exists and actually runs |
| **deployment** | the deployment report exists and parses · the deployment succeeded and links its run · the deployed frontend was reached · all four CRUD operations were verified in the cloud |
| **baseline** | **every AI service has an enable/disable flag** · no AI service is enabled by default · the report agrees with the configuration · bonus work is a separate profile |
| **release-decision** | a human made the decision · the decision cites this review · a no-go names its blockers |

This mode ends with a **release recommendation** — GO, GO WITH
RESERVATIONS, or NO-GO — written at the top of the log, with the blocking
findings separated from the merely untidy ones. It is a recommendation and
says so: the decision itself is a person's, recorded in
`evidence/release2/cloud/release-decision.json`.

It found something real on its first run: the brief requires AI-Mode to be
**disabled by default** in the cloud, and the cloud configuration has
`MCP_ENABLED`, `RAG_ENABLED` and `MULTI_AGENT_ENABLED` but nothing at all
for AI-Mode itself. A baseline cannot be asserted for a service that nothing
switches.

## Logs

Each run writes two files to `logs/`, named for its mode:

- `loop-<mode>-<timestamp>.md` — a readable report, one section per iteration
- `loop-<mode>-<timestamp>.jsonl` — one JSON object per iteration for the report appendix

## Exit code

`0` when every probe passes, `1` otherwise, so each mode is a gate rather
than a report. `--mode all` runs the three Release 1 packs in turn and
`--mode release2` the three Release 2 packs; both print a summary table and
exit non-zero if any pack failed.

The final tally counts **every probe at its latest outcome**, not the last
iteration's. A later iteration re-runs only what failed, so reading the
headline off the last iteration would have reported "0/10 passing" for a
suite standing at 7/17 — flattering in neither direction, just wrong.

## In CI

`student-4.yml` runs `--mode review` inside the `validate` job as before.

The `mcp`, `rag` and `multi-agent` modes are **retained in the workflow but
disabled by default**, because a GitHub-hosted runner has none of the three
servers and no Ollama, and all of them are required to be non-containerised.
They run as job 4 only when the workflow is dispatched with
`run_ai_modes = true`.

The `testing` and `cloud` modes review committed evidence rather than
running services, so they need nothing a GitHub runner lacks and run on
**every build**, as job 5. `cloud` is marked `continue-on-error` for now,
with the reason written beside it: its NO-GO is correct but it is reporting
on deliverables that are not mine, and failing every Student 4 build on
somebody else's pending work would bury my own failures. That one line comes
out the day the deployment evidence lands.

What CI enforces without any of the servers, in the `unit-tests` job:

- every probe pack compiles and passes pyflakes
- `loop.py` really registers all six modes plus `all` and `release2`
- building a pack touches no network, and no probe is tagged with an unknown area
- `docker-compose.yml` declares no `mcp`, no `rag` and no `ollama` service
- my backend exposes `/api/ai/mcp`, `/api/ai/rag` and the three
  `/api/ai/multi-agent/...` routes
