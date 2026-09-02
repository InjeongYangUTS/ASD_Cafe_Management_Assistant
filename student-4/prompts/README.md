# Prompt Engineering & Context Management — Student 4

**Stella Kwon · Order & Kitchen Management · 41026 ASD Release 0**

This folder is my prompt asset register. Every prompt that shaped my feature
is recorded here with the context it was given, what came back, whether I
adopted it, and what I changed on the next version.

| # | Asset | Used for | Runs where | Version |
| --- | --- | --- | --- | --- |
| 01 | [`01-kitchen-analysis.md`](01-kitchen-analysis.md) | AI-Mode: kitchen congestion & prep priority | **Production** — `backend/ai.py`, called on every AI request | v3 |
| 02 | [`02-order-service-scaffold.md`](02-order-service-scaffold.md) | Scaffolding the three microservices | Development only | v2 |
| 03 | [`03-agentic-adapt.md`](03-agentic-adapt.md) | ADAPT step of the review loop | **Production** — `agentic/loop.py` | v2 |
| 04 | [`04-data-design-review.md`](04-data-design-review.md) | Reviewing the ERD before writing `schema.sql` | Development only | v2 |

---

## Context management strategy

The limit that matters is not the model's context window, it is **how much of
the wrong context you can put in front of it before the answer degrades**.
Four rules I applied throughout:

**1. Summarise, never dump.**
The kitchen analysis prompt never receives raw database rows. `summarise_queue()`
in `backend/ai.py` first computes deterministic metrics — workload per station,
ticket ages, priority scores — and only that summary goes into the prompt.
A 40-row queue and a 4-row queue produce prompts of almost the same size.

**2. Strip anything the model does not need to answer.**
No `customer_id`, no `staff_id`, no primary keys, no SQL. The prompt carries
order numbers, times, item names and station names — the vocabulary a person
on the pass would use. `tests/test_ai_mode.py` asserts this
(`test_prompt_contains_the_queue_facts_and_no_raw_database_rows`), so a future
change that leaks identifiers into the prompt fails CI.

**3. Compute the facts, ask for the judgement.**
Numbers the model would get wrong — totals, minutes, ordering — are computed
in Python and given to it as fixed input. The model is asked only for the part
it is actually good at: reading the situation and phrasing an instruction.
This is also what makes the fallback possible: if Ollama is down, the metrics
are still there and `heuristic_analysis()` fills in the narrative.

**4. Constrain the output shape, then parse it.**
Every production prompt ends with the exact section labels required
(`CONGESTION / SEQUENCE / DELAY RISK / ACTION`). `parse_llm_reply()` splits on
those labels, and if the reply does not follow the format the code falls back
to the rule-based analysis and keeps the raw reply visible in the UI rather
than showing the user something broken.

## Where the prompts run

```
Frontend  ──POST /ui/ai/analyse──▶  Backend/API
                                        │
                                        │ 1. summarise_queue()  ← deterministic metrics
                                        │ 2. build_prompt()     ← asset 01
                                        ▼
                                     Ollama ──▶ Llama 3.2 / Qwen 2.5
                                        │
                                        ▼
                                  parse_llm_reply()  ← falls back if malformed
                                        │
                                        ▼
                          Rendered in the Kitchen Display AI panel,
                          with the exact prompt shown under
                          "Show the exact prompt sent to the model"
```

The demonstration screen deliberately exposes the prompt. Anyone marking the
feature can open that disclosure and see precisely what context the model
received — the evidence is in the running application, not only in this folder.
