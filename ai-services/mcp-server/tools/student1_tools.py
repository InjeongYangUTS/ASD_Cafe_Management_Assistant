from typing import Annotated, Literal

from pydantic import Field

from adapters.student1_adapter import (
    Student1AdapterError,
    get_reviews,
    get_summary,
)

Limit = Annotated[int, Field(ge=1, le=20, description="How many reviews to return (1-20).")]
TopN = Annotated[int, Field(ge=1, le=10, description="How many rows to return (1-10).")]


def _summary():
    try:
        return get_summary()
    except Student1AdapterError as exc:
        raise RuntimeError(str(exc)) from exc


def _menu_row(item, reasons):
    top = (item.get(reasons) or [{}])[0]
    quote = (item.get("quotes") or [{}])[0]
    return {
        "menu_item": item["menu_item"],
        "average_rating": item["average_rating"],
        "reviews": item["reviews"],
        "main_reason": top.get("label"),
        "example": quote.get("text"),
    }


def _review_row(review):
    return {
        "id": review["id"],
        "rating": review["rating"],
        "title": review.get("title"),
        "sentiment": review.get("sentiment"),
        "status": review.get("status"),
        "submitted_at": review.get("submitted_at"),
    }


def register_student1_tools(mcp):

    @mcp.tool()
    def get_menu_item_feedback(view: Literal["best", "worst"] = "worst",
                               limit: TopN = 5) -> list[dict]:
        """See which menu items customers love or complain about, and why."""
        reasons = "praise" if view == "best" else "complaints"
        items = _summary()["%s_menu_items" % view][:limit]
        return [_menu_row(item, reasons) for item in items]

    @mcp.tool()
    def get_top_issues(limit: TopN = 5) -> list[dict]:
        """See which complaints to fix first, based on how often and how serious they are."""
        return [{
            "issue": issue["label"],
            "mentions": issue["mentions"],
            "average_rating": issue["average_rating"],
            "priority_score": issue["priority_score"],
            "example_orders": ", ".join(issue.get("example_orders") or []),
        } for issue in _summary()["top_issues"][:limit]]

    @mcp.tool()
    def get_reviews_needing_reply(limit: Limit = 5) -> list[dict]:
        """See unhappy customers who haven't had a reply yet."""
        try:
            reviews = get_reviews(limit, sentiment="NEGATIVE", needs_reply=True)
            return [_review_row(review) for review in reviews]
        except Student1AdapterError as exc:
            raise RuntimeError(str(exc)) from exc
