import json
import os
from datetime import datetime
from pathlib import Path

import requests


OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
MODEL_NAME = os.getenv("OLLAMA_MODEL", "qwen2.5:0.5b")
LOG_DIRECTORY = Path(os.getenv("LOG_DIRECTORY", Path(__file__).resolve().parent.parent / "logs"))


def format_inventory_context(items):
    lines = []
    for item in items:
        shortage = max(float(item["minimum_stock"]) - float(item["quantity"]), 0)
        lines.append(
            f"ID: {item['id']}, Name: {item['name']}, Current Quantity: {float(item['quantity']):g} {item['unit']}, Minimum Stock: {float(item['minimum_stock']):g} {item['unit']}, Shortage: {shortage:g} {item['unit']}, Status: {item['status']}"
        )
    return "\n".join(lines)


def ask_ollama(prompt):
    try:
        response = requests.post(
            OLLAMA_URL,
            json={"model": MODEL_NAME, "prompt": prompt, "stream": False},
            timeout=90,
        )
        response.raise_for_status()
        return response.json()["response"].strip()
    except (requests.RequestException, KeyError, ValueError) as exc:
        raise RuntimeError(f"AI service unavailable: {exc}") from exc


def plan(context, question):
    return ask_ollama(
        f"""You are an AI inventory management agent for a cafe.

CURRENT LOW OR OUT OF STOCK INVENTORY:
{context}

USER REQUEST:
{question}

The provided status is authoritative. LOW and OUT OF STOCK are different. Do not change statuses or invent data.

Create a concise plan that identifies critical stock problems, determines priority rules, and states what should be checked."""
    )


def act(context, question, plan_result):
    return ask_ollama(
        f"""You are an AI inventory management agent for a cafe.

CURRENT INVENTORY DATA:
{context}

PLAN:
{plan_result}

USER REQUEST:
{question}

Follow the plan. Separate OUT OF STOCK from LOW items and calculate how far each item is below minimum stock. Use only the supplied data and keep the analysis concise."""
    )


def observe(context, question, act_result):
    return ask_ollama(
        f"""Review the inventory analysis against the original data.

ORIGINAL INVENTORY DATA:
{context}

USER REQUEST:
{question}

ANALYSIS:
{act_result}

Identify incorrect statuses, quantities, missing critical items, or unsupported recommendations. Do not introduce new information. Keep the observation concise."""
    )


def adapt(context, question, plan_result, act_result, observe_result):
    return ask_ollama(
        f"""Produce the final corrected cafe inventory recommendation.

ORIGINAL INVENTORY DATA:
{context}

USER REQUEST:
{question}

PLAN:
{plan_result}

ACT RESULT:
{act_result}

OBSERVATION:
{observe_result}

Prioritise OUT OF STOCK items before LOW items. Use only the original data. Return a concise numbered priority list."""
    )


def run_agentic_loop(items, question="Which items should be restocked first?", save_log=True):
    context = format_inventory_context(items)
    plan_result = plan(context, question)
    act_result = act(context, question, plan_result)
    observe_result = observe(context, question, act_result)
    adapt_result = adapt(context, question, plan_result, act_result, observe_result)
    result = {
        "timestamp": datetime.now().isoformat(),
        "question": question,
        "inventory_context": context,
        "plan": plan_result,
        "act": act_result,
        "observe": observe_result,
        "adapt": adapt_result,
    }
    if save_log:
        LOG_DIRECTORY.mkdir(parents=True, exist_ok=True)
        path = LOG_DIRECTORY / f"inventory_agent_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        path.write_text(json.dumps(result, ensure_ascii=False, indent=4), encoding="utf-8")
    return result


if __name__ == "__main__":
    backend_url = os.getenv("BACKEND_URL", "http://localhost:8300").rstrip("/")
    response = requests.get(backend_url + "/api/dashboard", timeout=10)
    response.raise_for_status()
    workflow = run_agentic_loop(response.json()["low_stock_items"])
    print(json.dumps(workflow, ensure_ascii=False, indent=2))
