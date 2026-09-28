from pathlib import Path
import re

KNOWLEDGE_DIR = Path(__file__).resolve().parent / "knowledge"


def load_documents():
    """Load text documents from the knowledge directory."""
    documents = []

    for file_path in sorted(KNOWLEDGE_DIR.glob("*.txt")):
        content = file_path.read_text(encoding="utf-8").strip()

        if content:
            documents.append({
                "source": file_path.name,
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
    """Find chunks with words matching the question."""
    documents = load_documents()
    chunks = split_documents(documents)

    question_words = set(
        re.findall(r"\b\w+\b", question.lower())
    )

    # Exclude common words that are not useful for matching.
    stop_words = {
        "a", "an", "the", "is", "are", "what",
        "which", "who", "how", "does", "do",
        "of", "in", "on", "for", "to", "and"
    }

    question_words -= stop_words

    results = []

    for chunk in chunks:
        chunk_words = set(
            re.findall(r"\b\w+\b", chunk["content"].lower())
        )

        score = len(question_words & chunk_words)

        if score > 0:
            results.append({
                "source": chunk["source"],
                "content": chunk["content"],
                "score": score
            })

    results.sort(
        key=lambda item: item["score"],
        reverse=True
    )

    return results[:limit]