import json
import unittest
from unittest.mock import patch

from workflow import start_workflow, submit_human_review


class TestWorkflow(unittest.TestCase):

    def setUp(self):
        self.evidence = {
            "recipe": "Cappuccino",
            "ingredients": ["Espresso", "Milk"]
        }

        self.plan = json.dumps({
            "available_information": ["Espresso", "Milk"],
            "information_to_check": [],
            "worker_steps": ["List ingredients"]
        })

        self.output = json.dumps({
            "result": "Espresso, Milk",
            "missing_information": [],
            "evidence_used": ["ingredients"]
        })

        self.review = json.dumps({
            "assessment": "Correct answer.",
            "issues": [],
            "recommendation": "approve",
            "reason": "Matches the evidence."
        })

    def create_test_workflow(self):
        with (
            patch(
                "workflow.create_plan",
                return_value={"plan": self.plan}
            ),
            patch(
                "workflow.execute_task",
                return_value={"output": self.output}
            ),
            patch(
                "workflow.review_task",
                return_value={"review": self.review}
            )
        ):
            return start_workflow(
                "List the ingredients for a cappuccino.",
                self.evidence
            )

    def test_workflow_creation(self):
        workflow = self.create_test_workflow()

        self.assertEqual(
            workflow["status"],
            "awaiting_human_review"
        )

        events = [item["event"] for item in workflow["history"]]

        self.assertEqual(
            events,
            [
                "workflow_started",
                "planner_completed",
                "worker_completed",
                "reviewer_completed"
            ]
        )

    def test_human_review_decisions(self):
        for decision in ("approve", "reject", "partial_accept"):
            with self.subTest(decision=decision):
                workflow = self.create_test_workflow()

                result = submit_human_review(
                    workflow["workflow_id"],
                    decision
                )

                self.assertEqual(result["status"], "completed")
                self.assertEqual(
                    result["human_review"]["decision"],
                    decision
                )

    def test_correction(self):
        workflow = self.create_test_workflow()

        revised_output = json.dumps({
            "result": "The ingredients are Espresso and Milk.",
            "missing_information": [],
            "evidence_used": ["ingredients"]
        })

        with (
            patch(
                "workflow.revise_task",
                return_value={"output": revised_output}
            ),
            patch(
                "workflow.review_task",
                return_value={"review": self.review}
            )
        ):
            result = submit_human_review(
                workflow["workflow_id"],
                "correct",
                "Make the answer a complete sentence."
            )

        self.assertEqual(
            result["status"],
            "awaiting_human_review"
        )
        self.assertEqual(result["worker_output"], revised_output)

        events = [item["event"] for item in result["history"]]

        self.assertIn("worker_revised", events)
        self.assertIn("reviewer_revised", events)

    def test_invalid_decision(self):
        workflow = self.create_test_workflow()

        with self.assertRaises(ValueError):
            submit_human_review(
                workflow["workflow_id"],
                "invalid"
            )


if __name__ == "__main__":
    unittest.main()