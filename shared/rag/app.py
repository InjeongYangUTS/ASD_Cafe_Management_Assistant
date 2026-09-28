from flask import Flask, jsonify
from config import RAG_HOST, RAG_PORT
from flask import Flask, jsonify, request
from config import RAG_HOST, RAG_PORT
from retriever import retrieve

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

if __name__ == "__main__":
    app.run(
        host=RAG_HOST,
        port=RAG_PORT,
        debug=True
    )