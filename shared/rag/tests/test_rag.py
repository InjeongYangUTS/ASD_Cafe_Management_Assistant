import sys
from pathlib import Path
from unittest.mock import patch, Mock

import pytest

RAG_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAG_DIR))

from app import app
from retriever import load_documents, split_documents, retrieve
from llm import generate_response


@pytest.fixture
def client():
    app.config["TESTING"] = True

    with app.test_client() as client:
        yield client


def test_health(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.get_json()["status"] == "ok"


def test_load_documents():
    documents = load_documents()

    assert len(documents) > 0
    assert any(
        doc["source"] == "cafe_overview.txt"
        for doc in documents
    )


def test_split_documents():
    documents = [{
        "source": "test.txt",
        "content": "First paragraph.\n\nSecond paragraph."
    }]

    chunks = split_documents(documents)

    assert len(chunks) == 2
    assert chunks[0]["source"] == "test.txt"


def test_retrieve_relevant_context():
    results = retrieve(
        "What does the Menu and Recipe feature manage?"
    )

    assert len(results) > 0
    assert any(
        "ingredients" in result["content"].lower()
        for result in results
    )


def test_retrieve_unrelated_question():
    results = retrieve(
        "What is the capital of France?"
    )

    assert results == []


def test_retrieve_endpoint(client):
    response = client.post(
        "/retrieve",
        json={
            "question": "What does the Inventory feature manage?"
        }
    )

    assert response.status_code == 200
    assert len(response.get_json()["results"]) > 0


def test_retrieve_missing_question(client):
    response = client.post(
        "/retrieve",
        json={}
    )

    assert response.status_code == 400

def test_generate_response():
    mock_response = Mock()
    mock_response.json.return_value = {
        "response": "Ollama connection successful"
    }

    with patch("llm.requests.post", return_value=mock_response):
        result = generate_response("Test prompt")

    assert result == "Ollama connection successful"


def test_generate_response_empty_prompt():
    with pytest.raises(ValueError):
        generate_response("   ")


def test_generate_response_empty_answer():
    mock_response = Mock()
    mock_response.json.return_value = {
        "response": ""
    }

    with patch("llm.requests.post", return_value=mock_response):
        with pytest.raises(RuntimeError):
            generate_response("Test prompt")


def test_generate_response_connection_error():
    import requests

    with patch(
        "llm.requests.post",
        side_effect=requests.ConnectionError("Connection refused")
    ):
        with pytest.raises(RuntimeError):
            generate_response("Test prompt")