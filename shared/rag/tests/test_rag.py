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

def test_query_success(client):
    with patch(
        "app.generate_response",
        return_value="It manages menus, recipes and ingredients."
    ) as mock_generate:

        response = client.post(
            "/query",
            json={
                "question": "What does the Menu and Recipe feature manage?"
            }
        )

    data = response.get_json()

    assert response.status_code == 200
    assert data["status"] == "success"
    assert "menus" in data["answer"]
    assert any(source["document"] == "cafe_overview.txt" for source in data["sources"])
    assert data["confidence"] == "high"
    assert len(data["sources"]) == 1
    assert data["sources"][0]["id"] == 1
    assert data["sources"][0]["coverage"] == 0.75
    assert "ingredients" in data["sources"][0]["excerpt"]
    mock_generate.assert_called_once()


def test_query_insufficient_context(client):
    with patch("app.generate_response") as mock_generate:

        response = client.post(
            "/query",
            json={
                "question": "What is the capital of France?"
            }
        )

    data = response.get_json()

    assert response.status_code == 200
    assert data["status"] == "insufficient_context"
    assert data["answer"] is None
    assert data["sources"] == []

    # Ollama should not be called when retrieval finds nothing.
    mock_generate.assert_not_called()


def test_query_missing_question(client):
    response = client.post(
        "/query",
        json={}
    )

    assert response.status_code == 400
    assert "error" in response.get_json()

def test_query_llm_insufficient_context(client):
    with patch(
        "app.generate_response",
        return_value="Insufficient context."
    ):
        response = client.post(
            "/query",
            json={
                "question": "What does the Menu and Recipe feature manage?"
            }
        )

    data = response.get_json()

    assert response.status_code == 200
    assert data["status"] == "insufficient_context"
    assert data["answer"] is None
    assert data["sources"] == []
    assert data["confidence"] == "insufficient"


def test_query_ollama_error(client):
    with patch(
        "app.generate_response",
        side_effect=RuntimeError("Ollama unavailable")
    ):
        response = client.post(
            "/query",
            json={
                "question": "What does the Menu and Recipe feature manage?"
            }
        )

    assert response.status_code == 503
    assert "error" in response.get_json()


def test_confidence_categories():
    from retriever import classify_confidence

    assert classify_confidence([]) == "insufficient"
    assert classify_confidence([{"coverage": 0.8}]) == "high"
    assert classify_confidence([{"coverage": 0.6}]) == "medium"
    assert classify_confidence([{"coverage": 0.3}]) == "low"

def test_load_nested_documents(tmp_path, monkeypatch):
    import retriever

    student_dir = tmp_path / "student-2"
    student_dir.mkdir()

    document = student_dir / "menu_recipes.txt"
    document.write_text(
        "The Menu and Recipe feature manages cafe menus.",
        encoding="utf-8"
    )

    monkeypatch.setattr(retriever, "KNOWLEDGE_DIR", tmp_path)

    documents = retriever.load_documents()

    assert len(documents) == 1
    assert documents[0]["source"] == "student-2/menu_recipes.txt"
    assert "cafe menus" in documents[0]["content"]