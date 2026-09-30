"""
Student 4 (Stella Kwon) - Shared Agentic Loop
Repository-reading helpers shared by the probe packs.

Both --mode mcp and --mode rag have to answer the same question: is this
service declared in docker-compose.yml? Release 1 requires the MCP
server, the RAG server and Ollama to run on the host, so a probe that
reads the compose file is the difference between a rule that is written
down and a rule that is enforced.

Parsing matters here. A first attempt matched any two-space-indented key
and reported the named volume `ollama-models` as if it were a service,
which is a false positive that would have sent somebody looking for a
container that was never there. compose_services() tracks the top-level
block it is inside and only returns names declared under `services:`.
"""

import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
STUDENT_DIR = os.path.dirname(HERE)
REPO_ROOT = os.path.dirname(STUDENT_DIR)

COMPOSE_PATH = os.path.join(REPO_ROOT, "docker-compose.yml")

TOP_LEVEL = re.compile(r"^([A-Za-z_][\w-]*):")
SERVICE_KEY = re.compile(r"^\s{2}([A-Za-z_][\w-]*):\s*(#.*)?$")


def compose_exists():
    return os.path.exists(COMPOSE_PATH)


def compose_services():
    """Return the service names declared under `services:`, in order.

    Only the services block is read. Keys under `volumes:`, `networks:`
    or any other top-level block are ignored, so a leftover named volume
    is never mistaken for a running container.
    """
    if not compose_exists():
        return None

    with open(COMPOSE_PATH, "r", encoding="utf-8") as handle:
        lines = handle.read().splitlines()

    services = []
    in_services = False

    for line in lines:
        if not line.strip() or line.lstrip().startswith("#"):
            continue

        top = TOP_LEVEL.match(line)
        if top:
            in_services = top.group(1) == "services"
            continue

        if in_services:
            match = SERVICE_KEY.match(line)
            if match:
                services.append(match.group(1))

    return services


def services_matching(*fragments):
    """Service names containing any of these fragments, case-insensitively."""
    services = compose_services()
    if services is None:
        return None
    lowered = [f.lower() for f in fragments]
    return [name for name in services
            if any(f in name.lower() for f in lowered)]


def must_not_be_containerised(label, *fragments, ok=None, fail=None):
    """Shared probe body: fail if any matching service is in compose."""
    found = services_matching(*fragments)

    if found is None:
        return fail("docker-compose.yml not found at the repository root")

    if found:
        return fail("%s is declared in docker-compose.yml as %s - Release 1 "
                    "requires it to run on the host, not in a container"
                    % (label, ", ".join(found)))

    return ok("%s is not a Compose service - it runs on the host as the "
              "brief requires" % label)
