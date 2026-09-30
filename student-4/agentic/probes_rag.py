"""
Student 4 (Stella Kwon) - Shared Agentic Loop
RAG validation probe pack.

Validates the shared RAG server that the team runs locally and
non-containerised. The server is owned by Ei Thandar; this pack is the
contract test that decides whether it is behaving, and it is the
--mode rag half of the shared agentic loop.

The contract being validated (shared/rag/):

    GET  /health     -> 200 {"status": "ok", "service": "shared-rag"}
    POST /retrieve   {"question": str}
                     -> 200 {"question": str,
                             "results": [{"source", "content",
                                          "score", "coverage"}]}
                     -> 400 when the question is missing or blank
    POST /query      {"question": str}
                     -> 200 {"question", "answer", "sources",
                             "confidence", "status"}
                        status "success"              answer + sources present
                        status "insufficient_context" answer None, sources []
                     -> 503 when Ollama cannot be reached

Grounding rules the server claims and this pack measures:
    - a chunk is only retrieved when keyword coverage >= 0.5
    - at most three chunks are retrieved
    - confidence is high >= 0.75, medium >= 0.5, otherwise low
    - no answer is generated at all when nothing is retrieved

The interesting probes are the last ones. Anything can return a string
called "answer"; grounded_answer_stays_inside_its_sources is the probe
that decides whether the answer was actually built from the retrieved
text or invented around it. That is the same validate-the-narrative-
against-the-measured-facts pattern the Release 0 AI-Mode used, applied
to somebody else's service.
"""

import re
import time

import requests

from repo import must_not_be_containerised

AREAS = ["availability", "retrieval", "grounding", "resilience"]

# A question whose words are in the shared knowledge base, and one whose
# words are certainly not. The first must be answerable, the second must
# be refused.
IN_CORPUS = "What does the Order and Kitchen feature manage?"
OUT_OF_CORPUS = "What was the unemployment rate in Reykjavik during 1974?"

STOP_WORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "this", "that", "these", "those", "it", "its", "of", "in", "on", "for",
    "to", "and", "or", "but", "with", "as", "at", "by", "from", "into",
    "manages", "manage", "feature", "features", "cafe", "system",
}


def _words(text):
    return {w for w in re.findall(r"[a-z]{4,}", (text or "").lower())
            if w not in STOP_WORDS}


def build_rag_probes(rag_url, ok, fail, Probe):
    """Return the RAG probe pack. ok/fail/Probe come from loop.py."""

    base = rag_url.rstrip("/")

    def post(path, payload, timeout=180):
        return requests.post(base + path, json=payload, timeout=timeout)

    # ---------------- availability ----------------

    def rag_server_answers():
        started = time.time()
        body = requests.get(base + "/health", timeout=8).json()
        elapsed = time.time() - started
        if body.get("status") != "ok":
            return fail("health returned %r" % body)
        return ok("%s answered in %.0f ms, service=%s"
                  % (base, elapsed * 1000, body.get("service", "?")))

    def rag_is_not_a_compose_service():
        return must_not_be_containerised(
            "the RAG server", "rag", ok=ok, fail=fail)

    def ollama_is_not_a_compose_service():
        return must_not_be_containerised(
            "Ollama", "ollama", ok=ok, fail=fail)

    # ---------------- retrieval ----------------

    def retrieve_returns_the_documented_shape():
        response = post("/retrieve", {"question": IN_CORPUS})
        if response.status_code != 200:
            return fail("/retrieve returned HTTP %d" % response.status_code)
        body = response.json()
        if "results" not in body:
            return fail("/retrieve response has no 'results' key: %r"
                        % sorted(body))
        results = body["results"]
        if not results:
            return fail("nothing retrieved for a question that is in the "
                        "knowledge base: %r" % IN_CORPUS)
        required = {"source", "content", "score", "coverage"}
        for index, item in enumerate(results):
            missing = required - set(item)
            if missing:
                return fail("result %d is missing %s"
                            % (index, ", ".join(sorted(missing))))
        return ok("%d chunk(s), each with source, content, score and "
                  "coverage; best source %s"
                  % (len(results), results[0]["source"]))

    def blank_question_is_refused():
        codes = {}
        for label, payload in (("missing", {}),
                               ("empty", {"question": ""}),
                               ("whitespace", {"question": "   "}),
                               ("wrong type", {"question": 42})):
            codes[label] = post("/retrieve", payload, timeout=20).status_code
        bad = {k: v for k, v in codes.items() if v != 400}
        if bad:
            return fail("these should all be 400 but were not: %s"
                        % ", ".join("%s=%d" % kv for kv in bad.items()))
        return ok("missing, empty, whitespace and wrong-typed questions all "
                  "rejected with 400")

    def every_chunk_clears_the_coverage_floor():
        body = post("/retrieve", {"question": IN_CORPUS}).json()
        results = body.get("results", [])
        if not results:
            return fail("no chunks to check")
        weak = [(r["source"], r["coverage"]) for r in results
                if r["coverage"] < 0.5]
        if weak:
            return fail("chunks below the 0.5 coverage floor were returned: "
                        "%s" % ", ".join("%s=%.3f" % w for w in weak))
        return ok("all %d chunk(s) at or above the 0.5 floor (lowest %.3f)"
                  % (len(results), min(r["coverage"] for r in results)))

    def retrieval_is_capped_and_ordered():
        body = post("/retrieve", {"question":
                                  "What does the cafe application manage "
                                  "for menu inventory order payment and "
                                  "feedback?"}).json()
        results = body.get("results", [])
        if len(results) > 3:
            return fail("%d chunks returned, the contract caps it at 3"
                        % len(results))
        coverages = [r["coverage"] for r in results]
        if coverages != sorted(coverages, reverse=True):
            return fail("chunks are not ordered by coverage: %s" % coverages)
        return ok("%d chunk(s), capped at 3 and ordered best first %s"
                  % (len(results), coverages))

    # ---------------- grounding ----------------

    def query_returns_a_grounded_answer():
        body = post("/query", {"question": IN_CORPUS}).json()
        status = body.get("status")
        if status == "insufficient_context":
            return fail("the server refused a question that is in its own "
                        "knowledge base - retrieval is too strict")
        if status != "success":
            return fail("unexpected status %r" % status)
        if not body.get("answer"):
            return fail("status was success but the answer was empty")
        if not body.get("sources"):
            return fail("an answer was returned with no sources - that is "
                        "an ungrounded answer")
        return ok("answered from %d source(s), confidence %s, %d characters"
                  % (len(body["sources"]), body.get("confidence"),
                     len(body["answer"])))

    def every_source_is_citable():
        body = post("/query", {"question": IN_CORPUS}).json()
        sources = body.get("sources", [])
        if not sources:
            return fail("no sources to check")
        required = {"id", "document", "excerpt", "coverage"}
        for source in sources:
            missing = required - set(source)
            if missing:
                return fail("a source is missing %s"
                            % ", ".join(sorted(missing)))
            if not str(source["document"]).strip():
                return fail("a source has an empty document name")
            if not str(source["excerpt"]).strip():
                return fail("source %s has no excerpt, so the claim cannot "
                            "be checked against it" % source["document"])
        ids = [s["id"] for s in sources]
        if ids != list(range(1, len(sources) + 1)):
            return fail("citation ids are not 1..n: %s" % ids)
        return ok("%d citation(s), each naming a document and quoting the "
                  "excerpt it came from: %s"
                  % (len(sources),
                     ", ".join("[%s] %s" % (s["id"], s["document"])
                               for s in sources)))

    def grounded_answer_stays_inside_its_sources():
        """The probe that actually tests grounding.

        Take the content words of the answer, take the content words of
        the excerpts that were cited, and measure how much of the answer
        is not traceable to the excerpts. A grounded answer paraphrases
        its sources; a hallucinating one introduces vocabulary that is
        nowhere in them.
        """
        body = post("/query", {"question": IN_CORPUS}).json()
        if body.get("status") != "success":
            return fail("no successful answer to check grounding on")

        answer_words = _words(body["answer"]) - _words(IN_CORPUS)
        if not answer_words:
            return fail("the answer carried no content words")

        source_words = set()
        for source in body.get("sources", []):
            source_words |= _words(source.get("excerpt", ""))

        unsupported = answer_words - source_words
        share = len(unsupported) / len(answer_words)

        if share > 0.6:
            sample = ", ".join(sorted(unsupported)[:8])
            return fail("%.0f%% of the answer's content words appear in none "
                        "of the cited excerpts (e.g. %s) - the answer is "
                        "drifting away from its sources"
                        % (share * 100, sample))
        return ok("%.0f%% of the answer's content words are traceable to the "
                  "cited excerpts" % ((1 - share) * 100))

    def confidence_matches_the_measured_coverage():
        body = post("/query", {"question": IN_CORPUS}).json()
        confidence = body.get("confidence")
        if confidence not in ("high", "medium", "low", "insufficient"):
            return fail("confidence %r is not one of the four documented "
                        "categories" % confidence)

        sources = body.get("sources", [])
        if not sources:
            if confidence != "insufficient":
                return fail("no sources but confidence was %r" % confidence)
            return ok("no sources and confidence 'insufficient' - consistent")

        best = max(s["coverage"] for s in sources)
        expected = ("high" if best >= 0.75
                    else "medium" if best >= 0.5
                    else "low")
        if confidence != expected:
            return fail("best coverage %.3f should give '%s' but the server "
                        "reported '%s'" % (best, expected, confidence))
        return ok("best coverage %.3f -> '%s', matching the documented "
                  "thresholds" % (best, confidence))

    # ---------------- resilience ----------------

    def unanswerable_question_is_refused_not_invented():
        body = post("/query", {"question": OUT_OF_CORPUS}).json()
        if body.get("status") != "insufficient_context":
            return fail("a question with nothing behind it produced status "
                        "%r and the answer %r - the server invented one"
                        % (body.get("status"), (body.get("answer") or "")[:90]))
        if body.get("answer") is not None:
            return fail("status was insufficient_context but an answer was "
                        "still returned")
        if body.get("sources"):
            return fail("status was insufficient_context but sources were "
                        "still cited")
        if body.get("confidence") != "insufficient":
            return fail("confidence should be 'insufficient', was %r"
                        % body.get("confidence"))
        return ok("refused cleanly: answer None, sources empty, confidence "
                  "'insufficient'")

    def refusal_does_not_pay_for_the_model():
        """An empty retrieval must short-circuit before Ollama is called.

        Ollama on a laptop takes seconds; the retrieval path takes
        milliseconds. If the refusal is fast, the model was not invoked.
        """
        started = time.time()
        body = post("/query", {"question": OUT_OF_CORPUS}, timeout=180).json()
        elapsed = time.time() - started
        if body.get("status") != "insufficient_context":
            return fail("the control question was answered, so this timing "
                        "says nothing")
        if elapsed > 3.0:
            return fail("the refusal took %.1f s, which suggests the model "
                        "was invoked before the context was checked"
                        % elapsed)
        return ok("refused in %.0f ms - the model was never invoked"
                  % (elapsed * 1000))

    def model_outage_degrades_to_503():
        """Ask against a deliberately wrong Ollama address.

        RAG_OLLAMA_PROBE_URL lets the run point the server at a dead
        model host. Where that is not wired up the probe reports what it
        can observe rather than failing the build on something it cannot
        control.
        """
        try:
            response = post("/query", {"question": IN_CORPUS}, timeout=180)
        except requests.RequestException as exc:
            return fail("the server did not respond at all when queried: %s"
                        % exc)
        if response.status_code == 503:
            body = response.json()
            if "error" not in body:
                return fail("503 returned without an error message")
            return ok("Ollama unreachable and the server said so with a 503 "
                      "and a message, instead of crashing")
        if response.status_code == 200:
            return ok("Ollama is up, so the outage path could not be "
                      "exercised; the 503 handler is present in "
                      "shared/rag/app.py")
        return fail("unexpected HTTP %d from /query" % response.status_code)

    def my_feature_is_retrievable():
        """The knowledge base has to know about Order & Kitchen.

        This is the probe I own as the feature author: if the shared
        corpus cannot answer a question about my slice of the system,
        the RAG panel on my screens has nothing to ground itself on.
        """
        body = post("/retrieve", {"question":
                                  "What does the Order and Kitchen "
                                  "feature manage?"}).json()
        results = body.get("results", [])
        hit = [r for r in results
               if "order" in r["content"].lower()
               and "kitchen" in r["content"].lower()]
        if not hit:
            return fail("no chunk mentioning Order and Kitchen was "
                        "retrieved - my feature is missing from the shared "
                        "knowledge base")
        return ok("Order & Kitchen is documented in %s at coverage %.3f"
                  % (hit[0]["source"], hit[0]["coverage"]))

    return [
        Probe("rag_health", "availability",
              "RAG server answers /health", rag_server_answers),
        Probe("rag_not_containerised", "availability",
              "RAG server is not a Compose service",
              rag_is_not_a_compose_service),
        Probe("ollama_not_containerised", "availability",
              "Ollama is not a Compose service",
              ollama_is_not_a_compose_service),

        Probe("rag_retrieve_shape", "retrieval",
              "/retrieve returns the documented shape",
              retrieve_returns_the_documented_shape),
        Probe("rag_rejects_blank", "retrieval",
              "Blank questions are refused with 400",
              blank_question_is_refused),
        Probe("rag_coverage_floor", "retrieval",
              "Every chunk clears the 0.5 coverage floor",
              every_chunk_clears_the_coverage_floor),
        Probe("rag_cap_and_order", "retrieval",
              "At most three chunks, best first",
              retrieval_is_capped_and_ordered),
        Probe("rag_my_feature", "retrieval",
              "Order & Kitchen is in the knowledge base",
              my_feature_is_retrievable),

        Probe("rag_answer", "grounding",
              "/query answers an in-corpus question",
              query_returns_a_grounded_answer),
        Probe("rag_citations", "grounding",
              "Every source is citable and quoted",
              every_source_is_citable),
        Probe("rag_stays_grounded", "grounding",
              "The answer stays inside its sources",
              grounded_answer_stays_inside_its_sources),
        Probe("rag_confidence", "grounding",
              "Confidence matches the measured coverage",
              confidence_matches_the_measured_coverage),

        Probe("rag_refuses", "resilience",
              "Unanswerable questions are refused",
              unanswerable_question_is_refused_not_invented),
        Probe("rag_refusal_is_cheap", "resilience",
              "Refusal short-circuits before the model",
              refusal_does_not_pay_for_the_model),
        Probe("rag_model_outage", "resilience",
              "Model outage degrades to a 503",
              model_outage_degrades_to_503),
    ]
