import unittest
from unittest.mock import patch

from app import app


class TestMultiAgentAPI(unittest.TestCase):

    def setUp(self):
        self.client = app.test_client()

    def test_health(self):
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["status"], "ok")

    def test_missing_task(self):
        response = self.client.post(
            "/workflows",
            json={"evidence": {}}
        )

        self.assertEqual(response.status_code, 400)

    def test_invalid_evidence(self):
        response = self.client.post(
            "/workflows",
            json={
                "task": "List ingredients",
                "evidence": []
            }
        )

        self.assertEqual(response.status_code, 400)

    def test_unknown_workflow(self):
        response = self.client.get(
            "/workflows/nonexistent-workflow"
        )

        self.assertEqual(response.status_code, 404)

    def test_invalid_human_review_decision(self):
        response = self.client.post(
            "/workflows/test-id/human-review",
            json={"decision": "invalid"}
        )

        self.assertEqual(response.status_code, 400)

    def test_agent_failure(self):
        with patch(
            "app.submit_human_review",
            side_effect=ValueError("Worker returned invalid JSON.")
        ):
            response = self.client.post(
                "/workflows/test-id/human-review",
                json={
                    "decision": "correct",
                    "comments": "Fix the answer"
                }
            )

        self.assertEqual(response.status_code, 500)

    def test_unexpected_failure(self):
        with patch(
            "app.submit_human_review",
            side_effect=RuntimeError("Unexpected failure")
        ):
            response = self.client.post(
                "/workflows/test-id/human-review",
                json={
                    "decision": "correct",
                    "comments": "Fix the answer"
                }
            )

        self.assertEqual(response.status_code, 500)


if __name__ == "__main__":
    unittest.main()
    