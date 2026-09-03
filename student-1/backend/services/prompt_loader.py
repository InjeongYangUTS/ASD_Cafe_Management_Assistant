"""
Student 1 (Hangyeol Yi) - Customer Feedback & Reviews
Prompt loader.

Prompts live in student-1/prompts/ as plain .txt files rather than as
strings inside the Python source. That is the course convention and it
earns its keep here:

  * the prompt is a reviewable artefact - it shows up in a diff when it
    changes, which is what the Prompt Engineering evidence needs;
  * the wording can be tuned without touching or redeploying code;
  * the same prompt text is used by the running service and by the
    agentic loop, so there is one version of it, not two that drift.

Placeholders are written {{LIKE_THIS}} and filled with render().
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# In the container the prompts are copied next to the backend; in a local
# checkout they sit one level up in student-1/prompts. Both are tried so
# the same code runs in either place.
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
    """
    Substitute {{PLACEHOLDER}} values into a prompt.

    A placeholder left unfilled would be sent to the model verbatim and
    read as an instruction, so anything still unresolved is an error
    rather than something to paper over.
    """
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
