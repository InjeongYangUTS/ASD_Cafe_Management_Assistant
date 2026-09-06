import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

CANDIDATE_DIRS = [
    Path(os.environ.get("PROMPT_DIR", "")) if os.environ.get("PROMPT_DIR") else None,
    BASE_DIR / "prompts",
    BASE_DIR.parent / "prompts",
]


class PromptNotFound(Exception):
    """Raised when a prompt file is missing - never silently ignored."""


def prompt_dir():
    for candidate in CANDIDATE_DIRS:
        if candidate and candidate.is_dir():
            return candidate
    raise PromptNotFound(
        "no prompts directory found (looked in: %s)"
        % ", ".join(str(c) for c in CANDIDATE_DIRS if c)
    )


def load_prompt(relative_path):
    """Read one prompt file, e.g. load_prompt('service/ask_system_prompt.txt')."""
    path = prompt_dir() / relative_path

    if not path.is_file():
        raise PromptNotFound("prompt file not found: %s" % path)

    return path.read_text(encoding="utf-8").strip()


def render(template, **values):
    """Substitute {{PLACEHOLDER}} values into a prompt; an unresolved placeholder is an error."""
    text = template

    for key, value in values.items():
        text = text.replace("{{%s}}" % key.upper(), str(value))

    if "{{" in text:
        leftover = text[text.index("{{"):].split("}}")[0] + "}}"
        raise PromptNotFound(
            "prompt still contains an unfilled placeholder: %s" % leftover
        )

    return text


def load_and_render(relative_path, **values):
    return render(load_prompt(relative_path), **values)
