import sqlite3
import requests
import os


# =========================================================
# CONFIGURATION
# =========================================================

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(BACKEND_DIR)

DATABASE = os.path.join(
    BASE_DIR,
    "database",
    "inventory.db"
)

OLLAMA_URL = "http://localhost:11434/api/generate"

MODEL_NAME = "qwen2.5:0.5b"


# =========================================================
# DATABASE
# =========================================================

def get_inventory_context():

    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row

    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            id,
            name,
            quantity,
            unit,
            minimum_stock,
            status
        FROM inventory
        WHERE status IN ('LOW', 'OUT OF STOCK')
        ORDER BY
            CASE
                WHEN status = 'OUT OF STOCK' THEN 1
                WHEN status = 'LOW' THEN 2
                ELSE 3
            END,
            id ASC
    """)

    rows = cursor.fetchall()

    connection.close()

    inventory_context = ""

    for row in rows:

        inventory_context += (
            f"ID: {row['id']}, "
            f"Name: {row['name']}, "
            f"Current Quantity: {row['quantity']:g} {row['unit']}, "
            f"Minimum Stock: {row['minimum_stock']:g} {row['unit']}, "
            f"Status: {row['status']}\n"
        )

    return inventory_context

# =========================================================
# OLLAMA
# =========================================================

def ask_ollama(prompt):

    try:

        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL_NAME,
                "prompt": prompt,
                "stream": False
            },
            timeout=60
        )

        response.raise_for_status()

        result = response.json()

        return result["response"].strip()

    except requests.RequestException as error:

        return f"AI service unavailable: {error}"
    
    # =========================================================
# PLAN
# =========================================================

def plan(inventory_context):

    prompt = f"""
You are an AI inventory management agent for a cafe.

The following inventory items are currently LOW or OUT OF STOCK:

{inventory_context}

PLAN PHASE:

Create a short plan for analysing the current inventory problem.

Your plan should:
1. Identify the most critical stock problems.
2. Decide how restocking priority should be determined.
3. Explain what information should be checked before making a recommendation.

Do not invent any inventory data.

Keep the plan concise.
"""

    return ask_ollama(prompt)

# =========================================================
# ACT
# =========================================================

def act(inventory_context, plan_result):

    prompt = f"""
You are an AI inventory management agent for a cafe.

CURRENT INVENTORY DATA:

{inventory_context}

PLAN:

{plan_result}

ACT PHASE:

Follow the plan and analyse the inventory data.

Identify:
- OUT OF STOCK items
- LOW stock items
- The amount each item is below its minimum stock level

Do not invent any data.

Return a concise analysis.
"""

    return ask_ollama(prompt)

# =========================================================
# OBSERVE
# =========================================================

def observe(inventory_context, act_result):

    prompt = f"""
You are reviewing an inventory analysis.

ORIGINAL INVENTORY DATA:

{inventory_context}

ANALYSIS PRODUCED DURING ACT:

{act_result}

OBSERVE PHASE:

Check whether the analysis is consistent with the original inventory data.

Identify:
- Any incorrect stock status
- Any incorrect quantities
- Any missing critical items
- Any recommendation that is not supported by the data

If the analysis is correct, clearly say so.

Do not introduce new inventory information.

Keep the observation concise.
"""

    return ask_ollama(prompt)

# =========================================================
# ADAPT
# =========================================================

def adapt(
    inventory_context,
    plan_result,
    act_result,
    observe_result
):

    prompt = f"""
You are an AI inventory management agent for a cafe.

ORIGINAL INVENTORY DATA:

{inventory_context}

PLAN:

{plan_result}

ACT RESULT:

{act_result}

OBSERVATION:

{observe_result}

ADAPT PHASE:

Produce the final corrected inventory recommendation.

Rules:
- OUT OF STOCK items must have higher priority than LOW stock items.
- Use only the original inventory data.
- Correct any problems identified during the observation phase.
- Do not invent stock values.
- Make the final recommendation concise and practical.

Return a numbered priority list.
"""

    return ask_ollama(prompt)

# =========================================================
# AGENTIC LOOP
# =========================================================

def run_agentic_loop():

    print("\n========================================")
    print("INVENTORY AGENTIC AI WORKFLOW")
    print("Plan -> Act -> Observe -> Adapt")
    print("========================================\n")


    inventory_context = get_inventory_context()


    print("CURRENT INVENTORY CONTEXT")
    print("----------------------------------------")
    print(inventory_context)


    # PLAN

    print("\n========================================")
    print("PLAN")
    print("========================================")

    plan_result = plan(inventory_context)

    print(plan_result)


    # ACT

    print("\n========================================")
    print("ACT")
    print("========================================")

    act_result = act(
        inventory_context,
        plan_result
    )

    print(act_result)


    # OBSERVE

    print("\n========================================")
    print("OBSERVE")
    print("========================================")

    observe_result = observe(
        inventory_context,
        act_result
    )

    print(observe_result)


    # ADAPT

    print("\n========================================")
    print("ADAPT")
    print("========================================")

    adapt_result = adapt(
        inventory_context,
        plan_result,
        act_result,
        observe_result
    )

    print(adapt_result)


    print("\n========================================")
    print("AGENTIC LOOP COMPLETE")
    print("========================================\n")


if __name__ == "__main__":
    run_agentic_loop()