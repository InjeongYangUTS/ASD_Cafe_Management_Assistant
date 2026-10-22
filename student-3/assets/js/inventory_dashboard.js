document.addEventListener("DOMContentLoaded", () => {
    const button = document.getElementById("mcp-check-button");
    const status = document.getElementById("mcp-status");
    const tableBody = document.getElementById("mcp-stock-items");

    function showMessage(message) {
        const row = document.createElement("tr");
        const cell = document.createElement("td");

        cell.colSpan = 5;
        cell.className = "empty-message";
        cell.textContent = message;

        row.appendChild(cell);
        tableBody.replaceChildren(row);
    }

    button.addEventListener("click", async () => {
        button.disabled = true;
        status.textContent = "Checking stock...";
        showMessage("Loading...");

        try {
            const response = await fetch(button.dataset.url, {
                headers: {
                    "Accept": "application/json"
                }
            });

            const data = await response.json();

            if (!response.ok || data.success === false) {
                throw new Error(data.error || "Stock check failed.");
            }

            if (!Array.isArray(data.items)) {
                throw new Error("Unexpected stock check result.");
            }

            status.textContent =
                `Stock check complete: ${data.items.length} items found.`;

            if (data.items.length === 0) {
                showMessage("No low-stock or out-of-stock items.");
                return;
            }

            tableBody.replaceChildren();

            data.items.forEach((item) => {
                const row = document.createElement("tr");

                const values = [
                    item.id,
                    item.name,
                    `${item.quantity} ${item.unit}`,
                    `${item.minimum_stock} ${item.unit}`,
                    item.status
                ];

                values.forEach((value) => {
                    const cell = document.createElement("td");
                    cell.textContent = value;
                    row.appendChild(cell);
                });

                tableBody.appendChild(row);
            });

        } catch (error) {
            status.textContent = `Error: ${error.message}`;
            showMessage("Unable to retrieve stock.");

        } finally {
            button.disabled = false;
        }
    });

    // RAG QUERY
    const ragButton = document.getElementById("rag-query-button");
    const ragQuestion = document.getElementById("rag-question");
    const ragStatus = document.getElementById("rag-status");

    const ragResult = document.getElementById("rag-result");
    const ragAnswer = document.getElementById("rag-answer");
    const ragConfidence = document.getElementById("rag-confidence");
    const ragSources = document.getElementById("rag-sources");


    ragButton.addEventListener("click", async () => {

        const question = ragQuestion.value.trim();

        if (!question) {
            ragStatus.textContent = "Please enter a question.";
            return;
        }


        ragButton.disabled = true;

        ragStatus.textContent = "Searching RAG context...";

        ragResult.style.display = "none";


        try {

            const response = await fetch(
                ragButton.dataset.url,
                {
                    method: "POST",

                    headers: {
                        "Content-Type": "application/json",
                        "Accept": "application/json"
                    },

                    body: JSON.stringify({
                        question: question
                    })
                }
            );


            const data = await response.json();


            if (!response.ok || data.success === false) {

                throw new Error(
                    data.error || "RAG request failed."
                );

            }


            if (data.insufficient_context) {

                ragAnswer.textContent =
                    "Insufficient context was found to answer this question.";

            } else {

                ragAnswer.textContent =
                    data.answer || "No answer returned.";

            }


            ragConfidence.textContent =
                data.confidence || "UNKNOWN";


            ragSources.replaceChildren();


            if (
                Array.isArray(data.sources) &&
                data.sources.length > 0
            ) {

                data.sources.forEach((source) => {

                    const item =
                        document.createElement("li");

                    if (source && typeof source === "object") {
                        item.textContent = source.document || "Unknown source";

                        if (source.excerpt) {
                            item.title = source.excerpt;
                        }
                    } else {
                        item.textContent = String(source);
                    }

                    ragSources.appendChild(item);

                });

            } else {

                const item =
                    document.createElement("li");

                item.textContent =
                    "No sources returned.";

                ragSources.appendChild(item);

            }


            ragResult.style.display = "block";

            ragStatus.textContent =
                "RAG response received.";


        } catch (error) {

            ragStatus.textContent =
                `Error: ${error.message}`;

            ragResult.style.display = "none";

        } finally {

            ragButton.disabled = false;

        }

    });

});

// Release 2: Multi-Agent workflow and human-in-the-loop controls.
document.addEventListener("DOMContentLoaded", () => {
    const panel = document.getElementById("multi-agent-panel");
    if (!panel) return;

    const $ = (id) => document.getElementById(id);
    const run = $("ma-run");
    const refresh = $("ma-refresh");
    const submit = $("ma-submit");
    const status = $("ma-status");
    let currentId = null;
    let busy = false;

    const endpoint = (suffix = "") => `${panel.dataset.workflowsUrl}/${encodeURIComponent(currentId)}${suffix}`;

    async function jsonRequest(url, options = {}) {
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), 125000);
        try {
            const response = await fetch(url, {
                ...options, signal: controller.signal,
                headers: { "Accept": "application/json", "Content-Type": "application/json", ...options.headers }
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || `Request failed (${response.status}).`);
            return data;
        } catch (error) {
            if (error.name === "AbortError") throw new Error("Request took too long. Check server logs before retrying.");
            throw error;
        } finally { clearTimeout(timer); }
    }

    function format(value) {
        if (value == null) return "Not available";
        if (typeof value === "string") {
            try { return JSON.stringify(JSON.parse(value), null, 2); } catch { return value; }
        }
        return JSON.stringify(value, null, 2);
    }

    function display(data) {
        currentId = data.workflow_id || currentId;
        $("ma-results").hidden = false;
        refresh.hidden = !currentId;
        $("ma-id").textContent = currentId || "Unknown";
        $("ma-workflow-status").textContent = data.status || "Unknown";
        $("ma-plan").textContent = format(data.plan);
        $("ma-worker").textContent = format(data.worker_output);
        $("ma-review").textContent = format(data.review);
        const history = $("ma-history");
        history.replaceChildren();
        (data.history || []).forEach((entry) => {
            const li = document.createElement("li");
            li.textContent = `${entry.event || "event"} — ${entry.timestamp || ""}`;
            history.appendChild(li);
        });
        $("ma-human-review").hidden = data.status !== "awaiting_human_review";
        $("ma-human-status").textContent = data.human_review
            ? `Last human decision: ${data.human_review.decision}` : "";
    }

    function setBusy(value) {
        busy = value;
        run.disabled = value;
        refresh.disabled = value;
        submit.disabled = value;
    }

    run.addEventListener("click", async () => {
        if (busy) return;
        const task = $("ma-task").value.trim();
        if (!task) { status.textContent = "Enter a review task."; return; }
        if (task.length > 1000) { status.textContent = "Task is too long."; return; }
        setBusy(true);
        status.textContent = "Running Planner, Worker, and Reviewer. Please avoid submitting twice...";
        try {
            const data = await jsonRequest(panel.dataset.startUrl, {
                method: "POST", body: JSON.stringify({ task })
            });
            display(data);
            status.textContent = "Workflow response received. Verify AI claims before reviewing.";
        } catch (error) { status.textContent = `Error: ${error.message}`; }
        finally { setBusy(false); }
    });

    refresh.addEventListener("click", async () => {
        if (busy || !currentId) return;
        setBusy(true);
        try { display(await jsonRequest(endpoint())); status.textContent = "Workflow refreshed."; }
        catch (error) { status.textContent = `Error: ${error.message}`; }
        finally { setBusy(false); }
    });

    submit.addEventListener("click", async () => {
        if (busy || !currentId) return;
        const decision = $("ma-decision").value;
        const comments = $("ma-comments").value.trim();
        if (decision === "correct" && !comments) {
            $("ma-human-status").textContent = "Enter a correction first."; return;
        }
        setBusy(true);
        $("ma-human-status").textContent = "Submitting human decision...";
        try {
            display(await jsonRequest(endpoint("/human-review"), {
                method: "POST", body: JSON.stringify({ decision, comments })
            }));
            status.textContent = "Human review recorded. Check the revised output and audit history.";
        } catch (error) { $("ma-human-status").textContent = `Error: ${error.message}`; }
        finally { setBusy(false); }
    });
});
