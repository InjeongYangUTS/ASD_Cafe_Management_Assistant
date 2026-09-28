from flask import Flask, jsonify
from config import RAG_HOST, RAG_PORT
from flask import Flask, jsonify, request
from config import RAG_HOST, RAG_PORT
from retriever import retrieve
from llm import generate_response

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

    # Do not generate an answer without retrieved context.
    if not results:
        return jsonify({
            "question": question,
            "answer": None,
            "sources": [],
            "status": "insufficient_context"
        }), 200

    context = "\n\n".join(
        result["content"]
        for result in results
    )

    prompt = f"""
You are a Cafe Management Assistant.

Answer the user's question using only the context below.
Do not invent information or use outside knowledge.

If the context does not contain enough information,
reply exactly: Insufficient context.

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
            "status": "insufficient_context"
        }), 200

    sources = sorted({
        result["source"]
        for result in results
    })

    return jsonify({
        "question": question,
        "answer": answer,
        "sources": sources,
        "status": "success"
    }), 200

if __name__ == "__main__":
    app.run(
        host=RAG_HOST,
        port=RAG_PORT,
        debug=True
    )