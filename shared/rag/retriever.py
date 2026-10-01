from pathlib import Path
import re

KNOWLEDGE_DIR = Path(__file__).resolve().parent / "knowledge"

STOP_WORDS = {
    "a", "an", "the", "is", "are", "what",
    "which", "who", "how", "does", "do",
    "of", "in", "on", "for", "to", "and",
    "it", "its", "can", "you", "me",
    "tell", "about", "please"
}

def tokenize(text):
    """Extract meaningful words from text."""
    words = set(re.findall(r"\b\w+\b", text.lower()))
    return words - STOP_WORDS

def load_documents():
    """Load text documents from all knowledge subdirectories."""
    documents = []

    for file_path in sorted(KNOWLEDGE_DIR.rglob("*.txt")):
        content = file_path.read_text(encoding="utf-8").strip()

        if content:
            documents.append({
                "source": file_path.relative_to(
                    KNOWLEDGE_DIR
                ).as_posix(),
                "content": content
            })

    return documents


def split_documents(documents):
    """Split documents into smaller searchable chunks."""
    chunks = []

    for document in documents:
        paragraphs = re.split(
            r"\n\s*\n",
            document["content"]
        )

        for paragraph in paragraphs:
            paragraph = paragraph.strip()

            if paragraph:
                chunks.append({
                    "source": document["source"],
                    "content": paragraph
                })

    return chunks


def retrieve(question, limit=3):
    """Retrieve relevant chunks and calculate keyword coverage."""
    documents = load_documents()
    chunks = split_documents(documents)

    question_words = tokenize(question)

    if not question_words:
        return []

    results = []

    for chunk in chunks:
        chunk_words = tokenize(chunk["content"])
        matching_words = question_words & chunk_words

        if not matching_words:
            continue

        score = len(matching_words)
        coverage = score / len(question_words)

        # Exclude chunks with low keyword coverage.
        if coverage < 0.5:
            continue

        results.append({
            "source": chunk["source"],
            "content": chunk["content"],
            "score": score,
            "coverage": round(coverage, 3)
        })

    results.sort(
        key=lambda item: (
            item["coverage"],
            item["score"]
        ),
        reverse=True
    )

    return results[:limit]

def classify_confidence(results):
    """Classify retrieval confidence using keyword coverage."""

    if not results:
        return "insufficient"

    best_coverage = results[0]["coverage"]

    if best_coverage >= 0.75:
        return "high"

    if best_coverage >= 0.5:
        return "medium"

    return "low"