import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

from services.prompt_loader import load_prompt, load_and_render

ISSUE_RULES = [
    ("slow_service", 1.0,
     ["wait", "waited", "waiting", "slow", "queue", "line", "took ages",
      "took forever", "still waiting", "late", "delay"]),
    ("cold_food", 1.2,
     ["cold food", "lukewarm", "tepid", "not hot", "went cold",
      "eggs were cold", "food was cold"]),
    ("cold_drink", 1.1,
     ["cold coffee", "coffee was cold", "cold by the time", "drink was cold",
      "gone cold"]),
    ("order_accuracy", 1.3,
     ["wrong order", "wrong", "incorrect", "instead of", "mix-up", "mixup",
      "mistake", "not what i ordered", "missing item"]),
    ("cleanliness", 1.4,
     ["dirty", "unclean", "not wiped", "sticky", "messy", "filthy", "crumbs",
      "hygiene"]),
    ("staff_attitude", 1.3,
     ["rude", "ignored", "unfriendly", "dismissive", "attitude", "abrupt"]),
    ("communication", 0.9,
     ["no explanation", "nobody explained", "not told", "did not tell",
      "never informed", "without explanation", "no one said"]),
    ("price", 0.8,
     ["expensive", "pricey", "overpriced", "too much", "price", "prices",
      "cost more"]),
    ("noise", 0.6,
     ["loud", "noisy", "too noisy", "can't hear", "cannot hear"]),
    ("seating", 0.6,
     ["cramped", "tight", "no seats", "nowhere to sit", "crowded", "seating"]),
    ("allergen_handling", 1.6,
     ["lactose", "allergy", "allergic", "intolerant", "gluten", "dairy"]),
    ("food_quality", 1.1,
     ["bland", "stale", "burnt", "soggy", "dry", "undercooked", "overcooked"]),
]

PRAISE_RULES = [
    ("coffee_quality", ["best coffee", "great coffee", "well made",
                        "perfectly extracted", "flat white", "good coffee"]),
    ("food_quality", ["delicious", "excellent", "best i have had", "tasty",
                      "fresh", "still warm", "lovely"]),
    ("staff_friendliness", ["friendly", "kind", "remembered", "helpful",
                            "went out of their way", "never rush"]),
    ("atmosphere", ["nice spot", "good wifi", "comfortable", "cosy", "cozy"]),
    ("consistency", ["consistent", "never drops", "always", "regular"]),
]

POSITIVE_WORDS = [
    "great", "excellent", "best", "lovely", "delicious", "perfect", "friendly",
    "amazing", "good", "enjoyed", "recommend", "fresh", "helpful", "warm",
    "consistent", "quick", "fast", "well made",
]

NEGATIVE_WORDS = [
    "slow", "cold", "wrong", "rude", "dirty", "expensive", "bad", "worst",
    "terrible", "disappointing", "late", "mistake", "never again", "ignored",
    "poor", "unacceptable", "bland", "stale",
]

SENTIMENTS = ["POSITIVE", "NEUTRAL", "NEGATIVE"]

RULES_MODEL = "rules"

_PROMPT_CACHE = {}


def system_prompt(name):
    if name not in _PROMPT_CACHE:
        _PROMPT_CACHE[name] = load_prompt("service/%s" % name)
    return _PROMPT_CACHE[name]


def _parse_time(value):
    if not value:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(str(value)[:19], fmt)
        except ValueError:
            continue
    return None


def detect_issues(text):
    """Return the issue tags present in one review. Deterministic."""
    lowered = (text or "").lower()
    return [tag for tag, _weight, phrases in ISSUE_RULES
            if any(phrase in lowered for phrase in phrases)]


def detect_praise(text):
    """Return the praise tags present in one review. Deterministic."""
    lowered = (text or "").lower()
    return [tag for tag, phrases in PRAISE_RULES
            if any(phrase in lowered for phrase in phrases)]


def issue_weight(tag):
    for name, weight, _phrases in ISSUE_RULES:
        if name == tag:
            return weight
    return 1.0


def match_menu_items(text, vocabulary):
    """Return the menu items named in a review, matching longer aliases first."""
    if not vocabulary:
        return []

    working = " %s " % (text or "").lower()

    candidates = []
    for name, entry in vocabulary.items():
        for alias in entry.get("aliases", []):
            candidates.append((alias, name))

    candidates.sort(key=lambda pair: len(pair[0]), reverse=True)

    found = []
    for alias, name in candidates:
        if name in found or not alias:
            continue
        if alias in working:
            found.append(name)
            working = working.replace(alias, " " * len(alias))

    return found


ISSUE_CATEGORY = {
    "slow_service": "WAIT_TIME",
    "cold_food": "FOOD",
    "cold_drink": "DRINK",
    "food_quality": "FOOD",
    "order_accuracy": "SERVICE",
    "allergen_handling": "SERVICE",
    "staff_attitude": "SERVICE",
    "communication": "SERVICE",
    "cleanliness": "CLEANLINESS",
    "price": "PRICE",
    "noise": "GENERAL",
    "seating": "GENERAL",
}


def classify_category(text, vocabulary=None):
    """Derive the review category from its wording. Deterministic."""
    issues = detect_issues(text)

    for tag in issues:
        if tag in ISSUE_CATEGORY:
            return ISSUE_CATEGORY[tag]

    menu_hits = match_menu_items(text, vocabulary or {})
    if menu_hits:
        entry = (vocabulary or {}).get(menu_hits[0], {})
        return entry.get("category", "GENERAL")

    return "GENERAL"


def measure_review(review):
    """Rule-based sentiment for one review, anchored on the star rating and nudged by the wording."""
    rating = int(review.get("rating") or 3)
    text = "%s %s" % (review.get("title") or "", review.get("comment") or "")
    lowered = text.lower()

    score = (rating - 3) / 2.0

    positive_hits = [word for word in POSITIVE_WORDS if word in lowered]
    negative_hits = [word for word in NEGATIVE_WORDS if word in lowered]

    score += 0.08 * len(positive_hits)
    score -= 0.08 * len(negative_hits)
    score = max(-1.0, min(1.0, score))

    if score >= 0.25:
        sentiment = "POSITIVE"
    elif score <= -0.25:
        sentiment = "NEGATIVE"
    else:
        sentiment = "NEUTRAL"

    issues = detect_issues(text)
    praise = detect_praise(text)

    return {
        "sentiment": sentiment,
        "sentiment_score": round(score, 3),
        "issues": issues,
        "praise": praise,
        "positive_terms": positive_hits,
        "negative_terms": negative_hits,
    }


def build_review_prompt(review, measured):
    """Render prompts/service/sentiment_task_prompt.txt for one review."""
    return load_and_render(
        "service/sentiment_task_prompt.txt",
        rating=review.get("rating"),
        order_number=review.get("order_number") or "not linked to an order",
        title=review.get("title") or "(none)",
        comment=review.get("comment") or "",
        detected_issues=", ".join(measured["issues"]) or "none",
    )


def parse_review_reply(text):
    parsed = {"sentiment": "", "score": None, "issues": [], "summary": ""}

    for raw_line in (text or "").splitlines():
        line = raw_line.strip().lstrip("-*# ").strip()
        if not line or ":" not in line:
            continue

        label, _, value = line.partition(":")
        label = label.strip().upper()
        value = value.strip()

        if label.startswith("SENTIMENT"):
            found = value.upper()
            for candidate in SENTIMENTS:
                if candidate in found:
                    parsed["sentiment"] = candidate
                    break
        elif label.startswith("SCORE"):
            match = re.search(r"-?\d+(?:\.\d+)?", value)
            if match:
                try:
                    parsed["score"] = max(-1.0, min(1.0, float(match.group())))
                except ValueError:
                    pass
        elif label.startswith("ISSUE"):
            if value.lower() not in ("none", "n/a", "-", ""):
                parsed["issues"] = [
                    re.sub(r"[^a-z0-9_]+", "_", tag.strip().lower()).strip("_")
                    for tag in value.split(",") if tag.strip()
                ][:6]
        elif label.startswith("SUMMARY"):
            parsed["summary"] = value

    return parsed


def analyse_review(review, llm):
    """Full AI-Mode analysis of one review; 'mode' says whether the LLM or the rules produced it."""
    measured = measure_review(review)
    prompt = build_review_prompt(review, measured)

    result = {
        "feedback_id": review.get("id"),
        "mode": "heuristic",
        "model": llm.model,
        "prompt": prompt,
        "raw_response": None,
        "note": None,
        "corrections": [],
        "measured": measured,
        "sentiment": measured["sentiment"],
        "sentiment_score": measured["sentiment_score"],
        "ai_issues": measured["issues"],
        "ai_summary": None,
    }

    raw, call_error = llm.call_model(
        system_prompt("sentiment_system_prompt.txt"), prompt, max_tokens=200
    )

    if call_error:
        result["note"] = ("%s - stored the rule-based analysis instead."
                          % call_error)
        result["ai_summary"] = fallback_summary(review, measured)
        result["model"] = "heuristic"
        return result

    parsed = parse_review_reply(raw)
    result["raw_response"] = raw

    if not parsed["sentiment"]:
        result["note"] = ("Model reply did not follow the requested format - "
                          "stored the rule-based analysis, raw reply kept below.")
        result["ai_summary"] = fallback_summary(review, measured)
        result["model"] = "heuristic"
        return result

    corrections = []
    sentiment = parsed["sentiment"]
    score = parsed["score"]

    rating = int(review.get("rating") or 3)

    if rating <= 2 and sentiment == "POSITIVE":
        sentiment = measured["sentiment"]
        score = measured["sentiment_score"]
        corrections.append(
            "Sentiment replaced with the rule-based value: the model returned "
            "POSITIVE for a %d-star review." % rating
        )
    elif rating >= 5 and sentiment == "NEGATIVE":
        sentiment = measured["sentiment"]
        score = measured["sentiment_score"]
        corrections.append(
            "Sentiment replaced with the rule-based value: the model returned "
            "NEGATIVE for a %d-star review." % rating
        )

    if score is None:
        score = measured["sentiment_score"]
        corrections.append(
            "Model gave no usable SCORE - kept the rule-based score."
        )
    elif (score > 0) != (measured["sentiment_score"] > 0) and \
            abs(score - measured["sentiment_score"]) > 1.0:
        corrections.append(
            "Model score %.2f disagrees in sign with the rule-based score "
            "%.2f; kept the model value but flagged it for review."
            % (score, measured["sentiment_score"])
        )

    issues = list(dict.fromkeys(measured["issues"] + parsed["issues"]))

    result.update({
        "mode": "ollama",
        "sentiment": sentiment,
        "sentiment_score": round(float(score), 3),
        "ai_issues": issues,
        "ai_summary": parsed["summary"] or fallback_summary(review, measured),
        "corrections": corrections,
    })

    return result


def fallback_summary(review, measured):
    rating = review.get("rating")
    if measured["issues"]:
        return ("%s-star review reporting %s."
                % (rating, ", ".join(tag.replace("_", " ")
                                     for tag in measured["issues"][:3])))
    if measured["praise"]:
        return ("%s-star review praising %s."
                % (rating, ", ".join(tag.replace("_", " ")
                                     for tag in measured["praise"][:3])))
    return "%s-star review with no specific issue detected." % rating


def measure_store(reviews, now=None, recent_days=7,
                  menu_vocabulary=None, order_items=None):
    """Store-wide measured facts, used as the LLM context for the whole-store analysis."""
    now = now or datetime.now(timezone.utc).replace(tzinfo=None)
    cutoff = now - timedelta(days=recent_days)
    menu_vocabulary = menu_vocabulary or {}
    order_items = order_items or {}

    total = len(reviews)
    ratings = [int(review.get("rating") or 0) for review in reviews
               if review.get("rating")]
    average = round(sum(ratings) / len(ratings), 2) if ratings else 0.0

    distribution = {str(star): 0 for star in range(1, 6)}
    for rating in ratings:
        if 1 <= rating <= 5:
            distribution[str(rating)] += 1

    issue_counter = Counter()
    praise_counter = Counter()
    issue_ratings = defaultdict(list)
    issue_recent = Counter()
    issue_examples = defaultdict(list)

    category_ratings = defaultdict(list)
    sentiment_counter = Counter()
    unanalysed = 0
    negative_reviews = []

    menu_ratings = defaultdict(list)
    menu_issues = defaultdict(Counter)
    menu_praise = defaultdict(Counter)
    menu_quotes = defaultdict(list)
    menu_attribution = Counter()

    for review in reviews:
        text = "%s %s" % (review.get("title") or "", review.get("comment") or "")
        rating = int(review.get("rating") or 3)
        submitted = _parse_time(review.get("submitted_at"))
        is_recent = submitted is not None and submitted >= cutoff

        stored_issues = review.get("ai_issues") or []
        if isinstance(stored_issues, str):
            try:
                stored_issues = json.loads(stored_issues)
            except (TypeError, ValueError):
                stored_issues = []

        tags = list(dict.fromkeys(list(stored_issues) + detect_issues(text)))
        praise_tags = detect_praise(text)

        for tag in tags:
            issue_counter[tag] += 1
            issue_ratings[tag].append(rating)
            if is_recent:
                issue_recent[tag] += 1
            if len(issue_examples[tag]) < 3 and review.get("order_number"):
                issue_examples[tag].append(review["order_number"])

        for tag in praise_tags:
            praise_counter[tag] += 1

        category_ratings[review.get("category") or "GENERAL"].append(rating)

        named = match_menu_items(text, menu_vocabulary)

        if named:
            attributed = named
            menu_attribution["named_in_review"] += 1
        else:
            ordered = order_items.get(review.get("order_id")) or []
            if len(ordered) == 1:
                attributed = ordered
                menu_attribution["single_item_order"] += 1
            else:
                attributed = []
                menu_attribution["not_attributed"] += 1

        for name in attributed:
            menu_ratings[name].append(rating)
            for tag in tags:
                menu_issues[name][tag] += 1
            for tag in praise_tags:
                menu_praise[name][tag] += 1

            quote = (review.get("title") or review.get("comment") or "").strip()
            if quote and len(menu_quotes[name]) < 2:
                menu_quotes[name].append({
                    "feedback_id": review.get("id"),
                    "rating": rating,
                    "text": quote[:120],
                })

        if review.get("sentiment"):
            sentiment_counter[review["sentiment"]] += 1
        else:
            unanalysed += 1

        if rating <= 2:
            negative_reviews.append({
                "id": review.get("id"),
                "rating": rating,
                "category": review.get("category"),
                "order_number": review.get("order_number"),
                "title": review.get("title"),
                "issues": tags,
            })

    priorities = []
    for tag, count in issue_counter.items():
        tag_ratings = issue_ratings[tag]
        mean_rating = sum(tag_ratings) / len(tag_ratings)
        severity = 1.0 + (5 - mean_rating) / 4.0
        recency = 1.0 + 0.5 * (issue_recent[tag] / count)
        score = count * severity * issue_weight(tag) * recency

        priorities.append({
            "issue": tag,
            "label": tag.replace("_", " "),
            "mentions": count,
            "recent_mentions": issue_recent[tag],
            "average_rating": round(mean_rating, 2),
            "severity_weight": round(issue_weight(tag), 2),
            "priority_score": round(score, 2),
            "example_orders": issue_examples[tag],
        })

    priorities.sort(key=lambda row: row["priority_score"], reverse=True)

    category_summary = sorted(
        (
            {
                "category": category,
                "reviews": len(values),
                "average_rating": round(sum(values) / len(values), 2),
            }
            for category, values in category_ratings.items()
        ),
        key=lambda row: row["average_rating"],
    )

    negative_share = (
        round(100.0 * len([r for r in ratings if r <= 2]) / len(ratings), 1)
        if ratings else 0.0
    )

    menu_feedback = []
    for name, item_ratings in menu_ratings.items():
        mean_rating = sum(item_ratings) / len(item_ratings)
        complaints = menu_issues[name].most_common(3)
        praise = menu_praise[name].most_common(3)

        menu_feedback.append({
            "menu_item": name,
            "menu_id": menu_vocabulary.get(name, {}).get("menu_id"),
            "reviews": len(item_ratings),
            "average_rating": round(mean_rating, 2),
            "complaints": [{"issue": tag, "label": tag.replace("_", " "),
                            "mentions": count} for tag, count in complaints],
            "praise": [{"praise": tag, "label": tag.replace("_", " "),
                        "mentions": count} for tag, count in praise],
            "verdict": ("PRAISED" if mean_rating >= 4
                        else "COMPLAINED_ABOUT" if mean_rating <= 2.5
                        else "MIXED"),
            "confidence": "low" if len(item_ratings) < 2 else "normal",
            "quotes": menu_quotes[name],
        })

    menu_feedback.sort(key=lambda row: (row["average_rating"], -row["reviews"]))

    return {
        "generated_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        "review_count": total,
        "average_rating": average,
        "rating_distribution": distribution,
        "negative_share_percent": negative_share,
        "recent_window_days": recent_days,
        "sentiment_counts": dict(sentiment_counter),
        "unanalysed_count": unanalysed,
        "top_issues": priorities[:8],
        "top_praise": [{"praise": tag, "mentions": count}
                       for tag, count in praise_counter.most_common(5)],
        "weakest_categories": category_summary[:3],
        "negative_reviews": negative_reviews[:8],
        "menu_feedback": menu_feedback,
        "worst_menu_items": [row for row in menu_feedback
                             if row["verdict"] == "COMPLAINED_ABOUT"][:5],
        "best_menu_items": [row for row in reversed(menu_feedback)
                            if row["verdict"] == "PRAISED"][:5],
        "menu_attribution": dict(menu_attribution),
    }


def build_store_summary(metrics):
    lines = [
        "CUSTOMER REVIEW SUMMARY (%s)" % metrics["generated_at"],
        "",
        "Reviews analysed : %d" % metrics["review_count"],
        "Average rating   : %.2f out of 5" % metrics["average_rating"],
        "1-2 star share   : %.1f%%" % metrics["negative_share_percent"],
        "Rating spread    : %s" % ", ".join(
            "%s star %d" % (star, count)
            for star, count in sorted(metrics["rating_distribution"].items())
        ),
        "",
        "COMPLAINT THEMES (already ranked by our priority score)",
    ]

    if metrics["top_issues"]:
        for row in metrics["top_issues"][:6]:
            lines.append(
                "  %-20s %2d mentions (%d in the last %d days), "
                "average rating %.2f, priority %.2f"
                % (row["label"], row["mentions"], row["recent_mentions"],
                   metrics["recent_window_days"], row["average_rating"],
                   row["priority_score"])
            )
    else:
        lines.append("  none detected")

    lines += ["", "WHAT CUSTOMERS PRAISE"]
    if metrics["top_praise"]:
        for row in metrics["top_praise"]:
            lines.append("  %-20s %d mentions"
                         % (row["praise"].replace("_", " "), row["mentions"]))
    else:
        lines.append("  none detected")

    lines += ["", "MENU ITEMS CUSTOMERS COMPLAIN ABOUT (worst average first)"]
    if metrics["worst_menu_items"]:
        for row in metrics["worst_menu_items"]:
            lines.append(
                "  %-22s %.2f stars over %d review(s)%s - %s"
                % (row["menu_item"], row["average_rating"], row["reviews"],
                   " [only one review]" if row["confidence"] == "low" else "",
                   ", ".join("%s x%d" % (c["label"], c["mentions"])
                             for c in row["complaints"]) or "no specific issue")
            )
    else:
        lines.append("  none")

    lines += ["", "MENU ITEMS CUSTOMERS PRAISE (best average first)"]
    if metrics["best_menu_items"]:
        for row in metrics["best_menu_items"]:
            lines.append(
                "  %-22s %.2f stars over %d review(s)%s - %s"
                % (row["menu_item"], row["average_rating"], row["reviews"],
                   " [only one review]" if row["confidence"] == "low" else "",
                   ", ".join("%s x%d" % (p["label"], p["mentions"])
                             for p in row["praise"]) or "no specific praise")
            )
    else:
        lines.append("  none")

    lines += ["", "WEAKEST CATEGORIES BY AVERAGE RATING"]
    for row in metrics["weakest_categories"]:
        lines.append("  %-12s %.2f stars across %d reviews"
                     % (row["category"], row["average_rating"], row["reviews"]))

    return "\n".join(lines)


def _menu_sentence(metrics):
    """Plain-language version of the per-item breakdown."""
    worst = metrics.get("worst_menu_items") or []
    best = metrics.get("best_menu_items") or []

    if not worst and not best:
        return ("No review named a specific menu item often enough to draw a "
                "conclusion.")

    parts = []

    if worst:
        parts.append("Complaints centre on %s." % "; ".join(
            "%s (%.2f stars over %d review(s)%s)"
            % (row["menu_item"], row["average_rating"], row["reviews"],
               ", one review only" if row["confidence"] == "low" else "")
            for row in worst[:3]
        ))

    if best:
        parts.append("Praise centres on %s." % "; ".join(
            "%s (%.2f stars over %d review(s))"
            % (row["menu_item"], row["average_rating"], row["reviews"])
            for row in best[:3]
        ))

    return " ".join(parts)


MENU_WORDS = ["menu", "item", "dish", "drink", "coffee", "food", "beverage"]

PRAISE_WORDS = [
    "praise", "praised", "complimented", "compliment", "best", "like",
    "liked", "love", "loved", "positive", "favourite", "favorite", "happy",
    "good", "enjoy", "recommend", "strength",
]

COMPLAINT_WORDS = [
    "complain", "complaint", "problem", "issue", "worst", "bad", "negative",
    "unhappy", "wrong", "dislike", "weak", "poor",
]

PRIORITY_WORDS = [
    "first", "priority", "urgent", "fix", "improve", "focus", "action",
    "should we", "what to do",
]

RATING_WORDS = ["rating", "star", "average", "score", "how many"]

SUPERLATIVE_WORDS = ["most", "best", "worst", "top", "least", "highest",
                     "lowest", "number one"]


def question_focus(question):
    """Return (subject, polarity, superlative) describing what the question asks for."""
    lowered = (question or "").lower()

    subject = "menu" if any(word in lowered for word in MENU_WORDS) else "overall"

    if any(word in lowered for word in PRAISE_WORDS):
        polarity = "praise"
    elif any(word in lowered for word in COMPLAINT_WORDS):
        polarity = "complaint"
    elif any(word in lowered for word in PRIORITY_WORDS):
        polarity = "priority"
    elif any(word in lowered for word in RATING_WORDS):
        polarity = "rating"
    else:
        polarity = "summary"

    superlative = any(word in lowered for word in SUPERLATIVE_WORDS)

    return subject, polarity, superlative


def rank_menu_items(rows, best_first):
    """Order menu items by strength of evidence, so a single-review item does not outrank a well-reviewed one."""
    return sorted(
        rows,
        key=lambda row: (row["confidence"] == "low",
                         -row["average_rating"] if best_first
                         else row["average_rating"]),
    )


def name_menu_verdict(metrics, best_first, superlative):
    """Answer a question about which menu items are praised or complained about."""
    rows = [row for row in metrics.get("menu_feedback", [])
            if row["verdict"] == ("PRAISED" if best_first else "COMPLAINED_ABOUT")]

    if not rows:
        return ("No menu item has enough %s reviews to stand out."
                % ("positive" if best_first else "negative"))

    ranked = rank_menu_items(rows, best_first)
    top = ranked[0]

    tags = top["praise"] if best_first else top["complaints"]
    reason = (" for %s" % ", ".join(item["label"] for item in tags[:2])
              if tags else "")

    answer = ("%s is the most %s menu item: %.2f stars across %d review(s)%s."
              % (top["menu_item"],
                 "praised" if best_first else "complained about",
                 top["average_rating"], top["reviews"], reason))

    if top["confidence"] == "low":
        answer += (" That is a single review, so it is an anecdote rather "
                   "than a pattern.")

    others = ranked[1:3]
    if others and not superlative:
        answer += (" Also %s: %s."
                   % ("praised" if best_first else "criticised",
                      "; ".join("%s (%.2f stars over %d review(s))"
                                % (row["menu_item"], row["average_rating"],
                                   row["reviews"]) for row in others)))
    elif others and superlative:
        runner = others[0]
        answer += (" Next is %s at %.2f stars over %d review(s)."
                   % (runner["menu_item"], runner["average_rating"],
                      runner["reviews"]))

    return answer


def questioned_menu_items(question, metrics, vocabulary=None):
    """The menu items the question names, restricted to those we hold reviews for."""
    named = match_menu_items(question, vocabulary or {})
    if not named:
        return []

    by_name = {row["menu_item"]: row for row in metrics.get("menu_feedback", [])}
    return [by_name[name] for name in named if name in by_name]


def describe_menu_item(row):
    """One item, in one or two sentences, with its own numbers."""
    parts = [
        "Customers rate %s %.2f stars across %d review(s)."
        % (row["menu_item"], row["average_rating"], row["reviews"])
    ]

    if row["complaints"]:
        parts.append("Complaints: %s." % ", ".join(
            "%s (%d)" % (item["label"], item["mentions"])
            for item in row["complaints"]
        ))

    if row["praise"]:
        parts.append("Praise: %s." % ", ".join(
            "%s (%d)" % (item["label"], item["mentions"])
            for item in row["praise"]
        ))

    if not row["complaints"] and not row["praise"]:
        parts.append("No specific theme was detected in those reviews.")

    if row["confidence"] == "low":
        parts.append("That is one review only, so treat it as an anecdote "
                     "rather than a pattern.")

    return " ".join(parts)


def heuristic_answer(question, metrics, vocabulary=None):
    """Rule-based answer, used when Ollama is unreachable or the model's reply fails validation."""
    subject, polarity, superlative = question_focus(question)
    issues = metrics.get("top_issues") or []

    asked_about = questioned_menu_items(question, metrics, vocabulary)
    if asked_about:
        return " ".join(describe_menu_item(row) for row in asked_about[:2])

    reviewed = {row["menu_item"] for row in metrics.get("menu_feedback", [])}
    unreviewed = [name for name in match_menu_items(question, vocabulary or {})
                  if name not in reviewed]
    if unreviewed:
        return ("No review mentions %s yet, so there is nothing to report "
                "on it." % " or ".join(unreviewed[:2]))

    if subject == "menu":
        if polarity == "praise":
            return name_menu_verdict(metrics, True, superlative)
        if polarity == "complaint":
            return name_menu_verdict(metrics, False, superlative)
        if polarity == "priority":
            worst = metrics.get("worst_menu_items") or []
            if worst:
                return ("Fix %s first: it averages %.2f stars over %d "
                        "review(s)." % (worst[0]["menu_item"],
                                        worst[0]["average_rating"],
                                        worst[0]["reviews"]))
        return _menu_sentence(metrics)

    if polarity == "praise":
        praise = metrics.get("top_praise") or []
        if not praise:
            return "No recurring compliment has been detected."
        return "Customers most often praise %s." % "; ".join(
            "%s (%d mention(s))" % (row["praise"].replace("_", " "),
                                    row["mentions"])
            for row in praise[:3]
        )

    if polarity == "complaint":
        if not issues:
            return "No recurring complaint theme has been detected."
        return "The most common complaints are %s." % "; ".join(
            "%s (%d mention(s), averaging %.2f stars)"
            % (row["label"], row["mentions"], row["average_rating"])
            for row in issues[:3]
        )

    if polarity == "priority":
        if not issues:
            return "Nothing is currently flagged as urgent."
        top = issues[0]
        worst = metrics.get("worst_menu_items") or []
        detail = (" The worst-rated item is %s at %.2f stars."
                  % (worst[0]["menu_item"], worst[0]["average_rating"])
                  if worst else "")
        return ("Fix %s first: %d mention(s) averaging %.2f stars, priority "
                "score %.2f.%s"
                % (top["label"], top["mentions"], top["average_rating"],
                   top["priority_score"], detail))

    if polarity == "rating":
        return ("%d reviews, averaging %.2f stars. %.1f%% are one or two "
                "stars." % (metrics["review_count"], metrics["average_rating"],
                            metrics["negative_share_percent"]))

    return ("%d reviews averaging %.2f stars. %s"
            % (metrics["review_count"], metrics["average_rating"],
               ("Top issue: %s." % issues[0]["label"]) if issues
               else "No recurring complaint theme."))


def build_review_summary(question, metrics, vocabulary=None):
    """The factual context handed to the model, narrowed to one menu item when the question names one."""
    asked_about = questioned_menu_items(question, metrics, vocabulary)

    if not asked_about:
        subject, polarity, _superlative = question_focus(question)

        if subject == "menu" and polarity in ("praise", "complaint"):
            best = polarity == "praise"
            rows = rank_menu_items(
                [row for row in metrics["menu_feedback"]
                 if row["verdict"] == ("PRAISED" if best else "COMPLAINED_ABOUT")],
                best,
            )

            if rows:
                lines = ["MENU ITEMS CUSTOMERS %s"
                         % ("PRAISE" if best else "COMPLAIN ABOUT"), ""]
                for row in rows[:4]:
                    tags = row["praise"] if best else row["complaints"]
                    lines.append(
                        "  %-22s %.2f stars over %d review(s)%s - %s"
                        % (row["menu_item"], row["average_rating"],
                           row["reviews"],
                           " [one review only]" if row["confidence"] == "low"
                           else "",
                           ", ".join("%s x%d" % (item["label"], item["mentions"])
                                     for item in tags[:3]) or "no specific theme")
                    )
                lines += [
                    "",
                    "The list is already ordered by strength of evidence: an "
                    "item with several reviews outranks one with a single "
                    "review, whatever its average.",
                    "Answer about these items only. Do not mention any other "
                    "menu item.",
                ]
                return "\n".join(lines)

        return build_store_summary(metrics)

    lines = ["REVIEW DATA FOR THE MENU ITEM(S) ASKED ABOUT", ""]

    for row in asked_about[:2]:
        lines.append(row["menu_item"])
        lines.append("  Average rating : %.2f stars over %d review(s)"
                     % (row["average_rating"], row["reviews"]))
        lines.append("  Complaints     : %s" % (", ".join(
            "%s x%d" % (item["label"], item["mentions"])
            for item in row["complaints"]) or "none"))
        lines.append("  Praise         : %s" % (", ".join(
            "%s x%d" % (item["label"], item["mentions"])
            for item in row["praise"]) or "none"))

        for quote in row["quotes"]:
            lines.append('  Customer said  : "%s" (%d stars)'
                         % (quote["text"], quote["rating"]))

        lines.append("")

    lines.append(
        "Answer ONLY about the menu item(s) above. Do not mention any other "
        "menu item."
    )

    return "\n".join(lines)


def build_question_prompt(question, metrics, vocabulary=None):
    """Render prompts/service/ask_task_prompt.txt for one staff question."""
    return load_and_render(
        "service/ask_task_prompt.txt",
        review_summary=build_review_summary(question, metrics, vocabulary),
        staff_question=question.strip(),
    )


def answer_question(question, reviews, llm, now=None,
                    menu_vocabulary=None, order_items=None):
    """Answer one free-text staff question, falling back to the rules when Ollama is unreachable."""
    metrics = measure_store(reviews, now=now,
                            menu_vocabulary=menu_vocabulary,
                            order_items=order_items)
    prompt = build_question_prompt(question, metrics, menu_vocabulary)
    fallback = heuristic_answer(question, metrics, menu_vocabulary)

    result = {
        "question": question.strip(),
        "metrics": metrics,
        "prompt": prompt,
        "mode": "heuristic",
        "model": llm.model,
        "answer": fallback,
        "raw_response": None,
        "note": None,
    }

    if not reviews:
        result["answer"] = "There are no reviews to answer from yet."
        result["model"] = "heuristic"
        return result

    reviewed = {row["menu_item"] for row in metrics["menu_feedback"]}
    unreviewed = [name for name in match_menu_items(question, menu_vocabulary or {})
                  if name not in reviewed]

    if unreviewed and not questioned_menu_items(question, metrics, menu_vocabulary):
        result["answer"] = ("No review mentions %s yet, so there is nothing "
                            "to report on it." % " or ".join(unreviewed[:2]))
        result["model"] = "heuristic"
        result["note"] = "Answered without calling the model: no data exists."
        return result

    raw, call_error = llm.call_model(
        system_prompt("ask_system_prompt.txt"), prompt, max_tokens=220
    )

    if call_error:
        result["note"] = ("%s - answered from the measured data instead."
                          % call_error)
        result["model"] = "heuristic"
        return result

    cleaned = " ".join((raw or "").split())

    looks_like_a_list = (
        cleaned.count(" - ") >= 2
        or cleaned.lstrip().startswith("-")
        or re.search(r"x\d+\b.*x\d+", cleaned)
    )

    if looks_like_a_list:
        result["raw_response"] = raw
        result["note"] = ("The model read the summary back rather than "
                          "answering - answered from the measured data instead.")
        result["model"] = "heuristic"
        return result

    if len(cleaned) < 25:
        result["raw_response"] = raw
        result["note"] = ("The model did not return a usable answer - "
                          "answered from the measured data instead.")
        result["model"] = "heuristic"
        return result

    subject, polarity, superlative = question_focus(question)

    if superlative and subject == "menu" and polarity in ("praise", "complaint"):
        best = polarity == "praise"
        ranked = rank_menu_items(
            [row for row in metrics["menu_feedback"]
             if row["verdict"] == ("PRAISED" if best else "COMPLAINED_ABOUT")],
            best,
        )

        weak = [row for row in ranked if row["confidence"] == "low"]
        strong = [row for row in ranked if row["confidence"] != "low"]

        if weak and strong:
            crowned_weak = re.search(
                r"(?i)\b%s\b[^.]{0,80}\b(more|most|highest|best|worst|top)\b"
                % re.escape(weak[0]["menu_item"]), cleaned
            ) or re.search(
                r"(?i)\b(most|highest|best|worst|top)\b[^.]{0,80}\b%s\b"
                % re.escape(weak[0]["menu_item"]), cleaned
            )

            if crowned_weak:
                result["raw_response"] = raw
                result["note"] = (
                    "The model named %s, which has only %d review, as the "
                    "top item over %s, which has %d. One review is an "
                    "anecdote - answered from the measured ranking instead."
                    % (weak[0]["menu_item"], weak[0]["reviews"],
                       strong[0]["menu_item"], strong[0]["reviews"])
                )
                result["model"] = "heuristic"
                return result

    asked_about = questioned_menu_items(question, metrics, menu_vocabulary)

    if asked_about:
        allowed = {row["menu_item"].lower() for row in asked_about}
        strayed = sorted(
            name for name in (menu_vocabulary or {})
            if name.lower() not in allowed and name.lower() in cleaned.lower()
        )

        if strayed:
            result["raw_response"] = raw
            result["note"] = (
                "The model also answered about %s, which is not what was "
                "asked - answered from the measured data for %s instead."
                % (", ".join(strayed),
                   ", ".join(row["menu_item"] for row in asked_about))
            )
            result["model"] = "heuristic"
            return result

    result.update({
        "mode": "ollama",
        "answer": cleaned,
        "raw_response": raw,
    })

    return result
