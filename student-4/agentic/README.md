# Shared agentic loop — Student 4 (Stella Kwon)

**Plan → Act → Observe → Adapt**, now over three probe packs.

Release 0 shipped this as a review of my own three microservices. Release 1
extends it into the team's **shared agentic loop**: the same engine, selected
with `--mode`, now also validates the two shared AI services.

```
python agentic/loop.py                                  # --mode review (default)
python agentic/loop.py --mode mcp
python agentic/loop.py --mode rag
python agentic/loop.py --mode all --max-iterations 2
```

| Mode | What it validates | Probes | Areas |
| --- | --- | --- | --- |
| `review` | my database, backend and frontend | 16 | database · implementation · architecture · devops |
| `mcp` | the shared MCP server | 12 | availability · protocol · invocation · resilience |
| `rag` | the shared RAG server | 15 | availability · retrieval · grounding · resilience |

## The engine does not know what MCP or RAG are

`plan()`, `act()`, `observe()` and `adapt()` were not changed to add the two
new modes. A mode contributes a list of `Probe` objects and the four area
names those probes are tagged with; the engine plans, runs, aggregates and
adapts over whatever it is handed. `build_mode()` is the only function that
knows the three modes exist.

```
agentic/
    loop.py           the engine + the review pack + the mode registry
    probes_mcp.py     the MCP pack        build_mcp_probes(...)
    probes_rag.py     the RAG pack        build_rag_probes(...)
    repo.py           repository helpers both packs share
    logs/             loop-<mode>-<timestamp>.md and .jsonl
```

`repo.py` exists because of a bug this work found in itself. The first
version of the compose check matched any two-space-indented key and
reported the named volume `ollama-models` as a service, which would have
sent somebody looking for a container that never existed.
`compose_services()` tracks which top-level block it is inside and only
returns names declared under `services:`.

Adding a fourth mode means writing a fourth `probes_*.py` and one line in
`build_mode()`.

## Everything here runs on the host

The MCP server, the RAG server and Ollama are **deliberately not
containerised** in Release 1, which is why the defaults are `localhost`
addresses rather than Docker service names:

| Service | Default | Override |
| --- | --- | --- |
| Shared MCP server | `http://localhost:5700` | `--mcp-url` / `MCP_URL` |
| Shared RAG server | `http://localhost:5600` | `--rag-url` / `RAG_URL` |
| Ollama | `http://localhost:11434` | `--ollama-url` / `OLLAMA_URL` |

Two probes enforce that rule rather than trusting it: `mcp_not_containerised`
and `rag_not_containerised` read `docker-compose.yml` and fail if either
server — or Ollama — reappears as a Compose service.

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

## Logs

Each run writes two files to `logs/`, named for its mode:

- `loop-<mode>-<timestamp>.md` — a readable report, one section per iteration
- `loop-<mode>-<timestamp>.jsonl` — one JSON object per iteration for the report appendix

## Exit code

`0` when every probe passes, `1` otherwise, so each mode is a gate rather
than a report. `--mode all` runs the three packs in turn, prints a summary
table, and exits non-zero if any of them failed.

## In CI

`student-4.yml` runs `--mode review` inside the `validate` job as before.

The `mcp` and `rag` modes are **retained in the workflow but disabled by
default**, because a GitHub-hosted runner has neither server nor Ollama, and
they are required to be non-containerised. They run as job 4 only when the
workflow is dispatched with `run_ai_modes = true`.

What CI still enforces without those servers, in the `unit-tests` job:

- both probe packs compile and pass pyflakes
- `loop.py` really registers the `mcp`, `rag` and `all` modes
- building a pack touches no network, and no probe is tagged with an unknown area
- `docker-compose.yml` declares no `mcp`, no `rag` and no `ollama` service
- my backend exposes `/api/ai/mcp` and `/api/ai/rag`
