from flask import Flask, jsonify
from config import RAG_HOST, RAG_PORT

app = Flask(__name__)


@app.get("/health")
def health():
    return jsonify({
        "status": "ok",
        "service": "shared-rag"
    }), 200


if __name__ == "__main__":
    app.run(
        host=RAG_HOST,
        port=RAG_PORT,
        debug=True
    )