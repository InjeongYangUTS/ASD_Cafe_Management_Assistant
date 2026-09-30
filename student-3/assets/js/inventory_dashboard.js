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

                    item.textContent = source;

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