from flask import Flask, jsonify
from config import RAG_HOST, RAG_PORT
from flask import Flask, jsonify, request
from config import RAG_HOST, RAG_PORT
from retriever import retrieve, classify_confidence
from llm import generate_response, is_grounded

app = Flask(__name__)


@app.get("/health")
def health():
    return jsonify({
        "status": "ok",
        "service": "shared-rag"
    }), 200

@app.post("/retrieve")
def retrieve_context():
    data = request.get_json(silent=True) or {}
    question = data.get("question")

    if not isinstance(question, str) or not question.strip():
        return jsonify({
            "error": "A non-empty question is required."
        }), 400

    results = retrieve(question.strip())

    return jsonify({
        "question": question.strip(),
        "results": results
    }), 200

@app.post("/query")
def query():
    data = request.get_json(silent=True) or {}
    question = data.get("question")

    if not isinstance(question, str) or not question.strip():
        return jsonify({
            "error": "A non-empty question is required."
        }), 400

    question = question.strip()
    results = retrieve(question)
    confidence = classify_confidence(results)

    # Do not generate an answer without retrieved context.
    if confidence == "insufficient":
        return jsonify({
            "question": question,
            "answer": None,
            "sources": [],
            "confidence": "insufficient",
            "status": "insufficient_context"
        }), 200

    # Include source identifiers so the LLM can reference them.
    context = "\n\n".join(
        f"[{index}] Source: {result['source']}\n"
        f"{result['content']}"
        for index, result in enumerate(results, start=1)
    )

    prompt = f"""
You are a Cafe Management Assistant.

Answer the question using only the supplied context.
Do not use outside knowledge or invent information.

If the context does not contain enough information
to answer the question, reply exactly:
Insufficient context.

Context:
{context}

Question:
{question}

Answer:
"""

    try:
        answer = generate_response(prompt)

    except RuntimeError as error:
        return jsonify({
            "error": str(error)
        }), 503

    if answer.strip().lower().rstrip(".") == "insufficient context":
        return jsonify({
            "question": question,
            "answer": None,
            "sources": [],
            "confidence": "insufficient",
            "status": "insufficient_context"
        }), 200

    # Reject generated answers that cannot be verified
    # against the retrieved source text.
    if not is_grounded(answer, results):
        answer = results[0]["content"]

    sources = [
        {
            "id": index,
            "document": result["source"],
            "excerpt": result["content"],
            "coverage": result["coverage"]
        }
        for index, result in enumerate(results, start=1)
    ]

    return jsonify({
        "question": question,
        "answer": answer,
        "sources": sources,
        "confidence": confidence,
        "status": "success"
    }), 200

if __name__ == "__main__":
    app.run(
        host=RAG_HOST,
        port=RAG_PORT,
        debug=True
    )