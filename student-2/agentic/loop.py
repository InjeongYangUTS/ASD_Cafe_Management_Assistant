import json
import socket
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path


# ---------------------------------------------------------
# Student 2 - Menu & Recipe Management
# Agentic AI Loop: Plan -> Act -> Observe -> Adapt
# ---------------------------------------------------------

BACKEND_URL = "http://localhost:5201"
DATABASE_HOST = "localhost"
DATABASE_PORT = 5202
OLLAMA_URL = "http://localhost:11434"

OLLAMA_MODEL = "qwen2.5:0.5b"

MAX_ITERATIONS = 3

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent.parent
LOG_DIR = BASE_DIR / "logs"

LOG_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------
# Helper functions
# ---------------------------------------------------------

def http_get(url, timeout=10):
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json"}
    )

    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read().decode("utf-8")

        if not body:
            return None

        return json.loads(body)


def check_port(host, port, timeout=3):
    with socket.create_connection((host, port), timeout=timeout):
        return True


def make_result(name, area, passed, evidence):
    return {
        "name": name,
        "area": area,
        "passed": passed,
        "evidence": evidence
    }


# ---------------------------------------------------------
# ACT - Individual checks
# ---------------------------------------------------------

def check_project_structure():
    required_paths = [
        PROJECT_ROOT / "student-2" / "frontend",
        PROJECT_ROOT / "student-2" / "backend",
        PROJECT_ROOT / "student-2" / "database",
        PROJECT_ROOT / "student-2" / "tests",
        PROJECT_ROOT / "student-2" / "agentic",
    ]

    missing = []

    for path in required_paths:
        if not path.exists():
            missing.append(str(path.relative_to(PROJECT_ROOT)))

    if missing:
        return make_result(
            "Student 2 project structure",
            "implementation",
            False,
            f"Missing: {', '.join(missing)}"
        )

    return make_result(
        "Student 2 project structure",
        "implementation",
        True,
        "Frontend, backend, database, tests and agentic folders exist."
    )


def check_ci_workflow():
    workflow = PROJECT_ROOT / ".github" / "workflows" / "student-2.yml"

    if workflow.exists():
        return make_result(
            "Student 2 CI workflow",
            "devops",
            True,
            ".github/workflows/student-2.yml exists."
        )

    return make_result(
        "Student 2 CI workflow",
        "devops",
        False,
        "student-2.yml could not be found."
    )


def check_docker_compose():
    compose_file = PROJECT_ROOT / "docker-compose.yml"

    if not compose_file.exists():
        return make_result(
            "Docker Compose configuration",
            "architecture",
            False,
            "docker-compose.yml could not be found."
        )

    content = compose_file.read_text(encoding="utf-8")

    required_services = [
        "student2-frontend",
        "student2-backend",
        "student2-database"
    ]

    missing = [
        service for service in required_services
        if service not in content
    ]

    if missing:
        return make_result(
            "Docker Compose configuration",
            "architecture",
            False,
            f"Missing Student 2 services: {', '.join(missing)}"
        )

    return make_result(
        "Docker Compose configuration",
        "architecture",
        True,
        "Student 2 frontend, backend and database services are defined."
    )


def check_database_service():
    try:
        check_port(DATABASE_HOST, DATABASE_PORT)

        return make_result(
            "Database microservice",
            "database",
            True,
            f"Database service is reachable on port {DATABASE_PORT}."
        )

    except OSError as error:
        return make_result(
            "Database microservice",
            "database",
            False,
            f"Database service is not reachable: {error}"
        )


def check_menu_api():
    try:
        data = http_get(f"{BACKEND_URL}/api/menus")

        if isinstance(data, list):
            return make_result(
                "Menu API",
                "api",
                True,
                f"Menu API returned {len(data)} menu item(s)."
            )

        return make_result(
            "Menu API",
            "api",
            False,
            "Menu API returned an unexpected response."
        )

    except Exception as error:
        return make_result(
            "Menu API",
            "api",
            False,
            str(error)
        )


def check_recipe_api():
    try:
        data = http_get(f"{BACKEND_URL}/api/recipes")

        if isinstance(data, list):
            return make_result(
                "Recipe API",
                "api",
                True,
                f"Recipe API returned {len(data)} recipe(s)."
            )

        return make_result(
            "Recipe API",
            "api",
            False,
            "Recipe API returned an unexpected response."
        )

    except Exception as error:
        return make_result(
            "Recipe API",
            "api",
            False,
            str(error)
        )


def check_ingredient_api():
    try:
        data = http_get(f"{BACKEND_URL}/api/ingredients")

        if isinstance(data, list):
            return make_result(
                "Ingredient API",
                "api",
                True,
                f"Ingredient API returned {len(data)} ingredient(s)."
            )

        return make_result(
            "Ingredient API",
            "api",
            False,
            "Ingredient API returned an unexpected response."
        )

    except Exception as error:
        return make_result(
            "Ingredient API",
            "api",
            False,
            str(error)
        )


def check_ollama():
    try:
        data = http_get(f"{OLLAMA_URL}/api/tags")

        if isinstance(data, dict):
            models = data.get("models", [])

            return make_result(
                "Ollama service",
                "ai",
                True,
                f"Ollama is reachable with {len(models)} model(s) available."
            )

        return make_result(
            "Ollama service",
            "ai",
            False,
            "Ollama returned an unexpected response."
        )

    except Exception as error:
        return make_result(
            "Ollama service",
            "ai",
            False,
            str(error)
        )


def check_ai_price_recommendation():
    try:
        menus = http_get(f"{BACKEND_URL}/api/menus")

        if not isinstance(menus, list) or len(menus) == 0:
            return make_result(
                "AI price recommendation",
                "ai",
                False,
                "No menu items were available for AI testing."
            )

        first_menu = menus[0]

        menu_id = (
            first_menu.get("menu_id")
            or first_menu.get("id")
        )

        if menu_id is None:
            return make_result(
                "AI price recommendation",
                "ai",
                False,
                "Could not determine a menu ID."
            )

        data = http_get(
            f"{BACKEND_URL}/api/ai/price-recommendation/{menu_id}",
            timeout=60
        )

        if isinstance(data, dict):
            return make_result(
                "AI price recommendation",
                "ai",
                True,
                f"AI recommendation successfully returned for menu ID {menu_id}."
            )

        return make_result(
            "AI price recommendation",
            "ai",
            False,
            "AI recommendation returned an unexpected response."
        )

    except Exception as error:
        return make_result(
            "AI price recommendation",
            "ai",
            False,
            str(error)
        )


# ---------------------------------------------------------
# All available probes
# ---------------------------------------------------------

PROBES = [
    check_project_structure,
    check_ci_workflow,
    check_docker_compose,
    check_database_service,
    check_menu_api,
    check_recipe_api,
    check_ingredient_api,
    check_ollama,
    check_ai_price_recommendation,
]


# ---------------------------------------------------------
# PLAN
# ---------------------------------------------------------

def plan(iteration, previous_results=None, focus_area=None):
    print("\n[PLAN]")

    if iteration == 1:
        print("Initial iteration - checking all Student 2 areas.")
        return PROBES

    failed_areas = set()

    if previous_results:
        for result in previous_results:
            if not result["passed"]:
                failed_areas.add(result["area"])

    selected = []

    for probe in PROBES:
        if focus_area is None:
            selected.append(probe)
            continue

        # Keep probes related to the selected focus.
        probe_name = probe.__name__

        area_mapping = {
            "database": ["database"],
            "api": ["menu", "recipe", "ingredient"],
            "ai": ["ollama", "ai_price"],
            "devops": ["ci"],
            "architecture": ["docker"],
            "implementation": ["project_structure"]
        }

        keywords = area_mapping.get(focus_area, [])

        if any(keyword in probe_name for keyword in keywords):
            selected.append(probe)

    # If nothing was selected, run all checks.
    if not selected:
        selected = PROBES

    print(f"Iteration {iteration} focus: {focus_area}")
    print(f"Selected {len(selected)} check(s).")

    return selected


# ---------------------------------------------------------
# ACT
# ---------------------------------------------------------

def act(selected_probes):
    print("\n[ACT]")

    results = []

    for probe in selected_probes:
        try:
            result = probe()

        except Exception as error:
            result = make_result(
                probe.__name__,
                "unknown",
                False,
                f"Unexpected error: {error}"
            )

        results.append(result)

        status = "PASS" if result["passed"] else "FAIL"

        print(
            f"{status} - {result['name']}: "
            f"{result['evidence']}"
        )

    return results


# ---------------------------------------------------------
# OBSERVE
# ---------------------------------------------------------

def observe(results):
    print("\n[OBSERVE]")

    passed = sum(
        1 for result in results
        if result["passed"]
    )

    failed = len(results) - passed

    failed_by_area = {}

    for result in results:
        if not result["passed"]:
            area = result["area"]

            failed_by_area[area] = (
                failed_by_area.get(area, 0) + 1
            )

    observation = {
        "total": len(results),
        "passed": passed,
        "failed": failed,
        "failed_by_area": failed_by_area
    }

    print(f"Checks completed: {len(results)}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")

    if failed_by_area:
        print("Areas requiring attention:")

        for area, count in failed_by_area.items():
            print(f"- {area}: {count} failure(s)")

    return observation


# ---------------------------------------------------------
# ADAPT
# ---------------------------------------------------------

def ask_ollama_for_focus(observation):
    areas = [
        "database",
        "api",
        "ai",
        "devops",
        "architecture",
        "implementation"
    ]

    prompt = f"""
You are reviewing the Student 2 Menu & Recipe Management microservice.

The latest system checks produced this result:

{json.dumps(observation, indent=2)}

Choose the ONE area that should be checked next.

Allowed answers:
database
api
ai
devops
architecture
implementation

Return only one word.
"""

    payload = json.dumps({
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False
    }).encode("utf-8")

    request = urllib.request.Request(
        f"{OLLAMA_URL}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    with urllib.request.urlopen(
        request,
        timeout=60
    ) as response:

        data = json.loads(
            response.read().decode("utf-8")
        )

    answer = data.get(
        "response",
        ""
    ).strip().lower()

    for area in areas:
        if area in answer:
            return area

    return None


def adapt(observation):
    print("\n[ADAPT]")

    if observation["failed"] == 0:
        print("All selected checks passed.")
        print("No further iteration is required.")
        return None

    try:
        focus = ask_ollama_for_focus(observation)

        if focus:
            print(
                f"Ollama recommends focusing on: {focus}"
            )

            return focus

    except Exception as error:
        print(
            f"Ollama could not select the next focus: {error}"
        )

    # Fallback if Ollama is unavailable.
    failed_by_area = observation["failed_by_area"]

    if failed_by_area:
        focus = max(
            failed_by_area,
            key=failed_by_area.get
        )

        print(
            f"Using rule-based fallback. "
            f"Next focus: {focus}"
        )

        return focus

    return None


# ---------------------------------------------------------
# Logging
# ---------------------------------------------------------

def save_logs(run_data):
    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    json_path = LOG_DIR / f"agentic_run_{timestamp}.json"

    markdown_path = (
        LOG_DIR /
        f"agentic_run_{timestamp}.md"
    )

    with open(
        json_path,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            run_data,
            file,
            indent=2
        )

    with open(
        markdown_path,
        "w",
        encoding="utf-8"
    ) as file:

        file.write(
            "# Student 2 Agentic AI Loop\n\n"
        )

        file.write(
            "Plan → Act → Observe → Adapt\n\n"
        )

        for iteration in run_data["iterations"]:
            file.write(
                f"## Iteration "
                f"{iteration['iteration']}\n\n"
            )

            file.write(
                f"**Focus:** "
                f"{iteration['focus'] or 'All areas'}\n\n"
            )

            file.write("### Results\n\n")

            for result in iteration["results"]:
                status = (
                    "PASS"
                    if result["passed"]
                    else "FAIL"
                )

                file.write(
                    f"- **{status}** - "
                    f"{result['name']}: "
                    f"{result['evidence']}\n"
                )

            observation = iteration["observation"]

            file.write("\n### Observation\n\n")
            file.write(
                f"- Passed: "
                f"{observation['passed']}\n"
            )
            file.write(
                f"- Failed: "
                f"{observation['failed']}\n"
            )

            file.write("\n")

    print("\nLog files saved:")
    print(json_path)
    print(markdown_path)


# ---------------------------------------------------------
# Main agentic loop
# ---------------------------------------------------------

def main():
    print("=" * 55)
    print("STUDENT 2 - MENU & RECIPE MANAGEMENT")
    print("AGENTIC AI LOOP")
    print("PLAN -> ACT -> OBSERVE -> ADAPT")
    print("=" * 55)

    run_data = {
        "feature": "Menu & Recipe Management",
        "student": "Student 2",
        "started_at": datetime.now().isoformat(),
        "iterations": []
    }

    previous_results = None
    focus_area = None

    for iteration in range(
        1,
        MAX_ITERATIONS + 1
    ):

        print(
            f"\n{'=' * 20} "
            f"ITERATION {iteration} "
            f"{'=' * 20}"
        )

        selected_probes = plan(
            iteration,
            previous_results,
            focus_area
        )

        results = act(selected_probes)

        observation = observe(results)

        next_focus = adapt(observation)

        run_data["iterations"].append({
            "iteration": iteration,
            "focus": focus_area,
            "results": results,
            "observation": observation,
            "next_focus": next_focus
        })

        previous_results = results

        if observation["failed"] == 0:
            print(
                "\nAgentic loop completed successfully."
            )
            break

        focus_area = next_focus

        if iteration == MAX_ITERATIONS:
            print(
                "\nMaximum iteration limit reached."
            )

    run_data["completed_at"] = (
        datetime.now().isoformat()
    )

    save_logs(run_data)


if __name__ == "__main__":
    main()