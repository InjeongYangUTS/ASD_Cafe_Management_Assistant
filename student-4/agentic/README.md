# Agentic AI review loop — Student 4

**Plan → Act → Observe → Adapt** over my slice of Release 0.

```
python agentic/loop.py                    # all three services must be running
python agentic/loop.py --max-iterations 3
python agentic/loop.py --model qwen2.5
```

## What it reviews

The brief asks the loop to review *the database, the implementation, the
microservices architecture and the DevOps pipeline*. Sixteen probes, tagged by
area:

| Area | Probes |
| --- | --- |
| **database** | all three tables declared · 10+ seeded orders · delete cascades to items and history · order totals agree with their line items |
| **implementation** | full create/read/update/delete round trip · empty basket, unknown menu id and zero quantity all rejected · illegal status jump refused with 409 |
| **architecture** | backend never imports `sqlite3` · frontend holds no data layer · Students 2 and 3 reached only through their HTTP APIs · the menu still serves 15 items during a peer outage |
| **devops** | a Dockerfile per service · a HEALTHCHECK per Dockerfile · `student-4.yml` builds *and* validates · the shared compose wires my services plus Ollama · all three containers answer their health endpoint |

## How each step works

**PLAN** — iteration 1 runs every probe to get a baseline. Later iterations
run the probes of the focus area chosen by ADAPT, plus every probe that failed
last time, and print the reason for that selection.

**ACT** — runs the probes. Each one returns `(passed, evidence)`; an exception
inside a probe is caught and recorded as a failure rather than killing the run.

**OBSERVE** — aggregates pass/fail per area and collects the evidence strings.

**ADAPT** — sends the observation to Ollama (asset
[`prompts/03-agentic-adapt.md`](../prompts/03-agentic-adapt.md)) and asks it to
name the next focus area from a closed vocabulary. If Ollama is unreachable the
loop picks the area with the worst pass ratio and logs
`source: "rule (Ollama unavailable)"` — so a demo never depends on the model
being up. When every probe passes, ADAPT returns no focus and the loop stops.

## Logs

Each run writes two files to `logs/`:

- `loop-<timestamp>.md` — a readable report, one section per iteration
- `loop-<timestamp>.jsonl` — one JSON object per iteration for the report appendix

Two runs are kept in the repository as evidence:

| Run | Result |
| --- | --- |
| `loop-20260901-114456` | 15/16 — found the cancelled-order total defect, iterated twice on the database area |
| `loop-20260901-114556` | 16/16 — converged in one iteration after the fix |

The defect, the decision and the three-file fix are written up in
[`prompts/03-agentic-adapt.md`](../prompts/03-agentic-adapt.md).

## Exit code

`0` when every probe passes, `1` otherwise — so the loop is a gate in
`student-4.yml`, not just a report.
