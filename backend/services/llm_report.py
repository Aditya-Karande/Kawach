import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "openai/gpt-oss-20b"

# This is ONLY called for tier-3 clusters (score 6+) — see
# core/correlation_engine.py. Tiers 1 and 2 are pure Python and never
# reach the LLM, both to keep cost down and because the spec only wants
# an AI explanation once something is actually being sent to a parent.

SYSTEM_PROMPT = """You are a child-safety analyst writing a short explanation for a PARENT about flagged activity from their child's browser/chat monitoring system.

Follow these rules exactly:
1. Judge whether this is a GENUINE safety concern based on real context and intent, not just because keywords matched. For example, "our secret" in the context of a treehouse club is NOT concerning, but "our secret, don't tell your parents" IS concerning. Consider the full picture of all events together.
2. If genuinely concerning, write the explanation in plain, everyday language a stressed parent can read in ten seconds. No jargon, no alarmist language.
3. Always structure the explanation in this order: what happened, then why it matters, then what to do. Never reorder this.
4. Calibrate tone to severity — don't make a medium-severity pattern sound like an emergency, and don't undersell a high-severity one.
5. NEVER use the words "danger", "predator", or "emergency".
6. NEVER diagnose intent. Say something "matches a common scam/grooming pattern" — never say "your child is being groomed" or state as fact what a stranger's intent is.
7. severity_label must be either "medium" or "high" (this function is only called for clusters serious enough to reach a parent at all).

Respond with ONLY valid JSON in this exact format, nothing else:
{"is_genuine_concern": true or false, "what_happened": "1-2 sentences", "why_it_matters": "1-2 sentences", "recommended_action": "1 concrete sentence", "severity_label": "medium or high"}
"""


def analyze_and_explain(risky_events: list) -> dict:
    # simple, readable summary of what was flagged, to feed the LLM.
    events_summary = "\n".join(
        f"- [{e.risk_label}] \"{e.content}\"" for e in risky_events
    )

    user_prompt = f"Here are the flagged events:\n{events_summary}"

    if not GROQ_API_KEY:
        print("WARNING: GROQ_API_KEY not set in .env — using fallback explanation")
        return _fallback_result(risky_events)

    try:
        response = requests.post(
            GROQ_URL,
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": GROQ_MODEL,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.3,
                "response_format": {"type": "json_object"}
            },
            timeout=10
        )

        response.raise_for_status()

        result_text = response.json()["choices"][0]["message"]["content"]
        parsed = json.loads(result_text)

        is_genuine_concern = bool(parsed.get("is_genuine_concern", True))

        return {
            "is_genuine_concern": is_genuine_concern,
            "ai_explanation": {
                "what_happened": parsed.get("what_happened", "Concerning activity was detected."),
                "why_it_matters": parsed.get("why_it_matters", "This matches a pattern worth reviewing."),
                "recommended_action": parsed.get("recommended_action", "Take a look at the activity in your dashboard."),
                "severity_label": parsed.get("severity_label", "medium"),
            },
        }

    except Exception as e:
        print(f"WARNING: LLM call failed ({e}) — using fallback explanation")
        return _fallback_result(risky_events)


def _fallback_result(risky_events: list) -> dict:
    """
    Simple non-LLM fallback, used if the API call fails. Fails SAFE:
    always treats it as a genuine concern, so a technical issue never
    hides a real risk from a parent — but still respects the copy-tone
    rules (plain language, no "danger"/"predator"/"emergency", no
    diagnosing intent).
    """
    label_counts = {}
    for e in risky_events:
        label_counts[e.risk_label] = label_counts.get(e.risk_label, 0) + 1
    summary = ", ".join(f"{count} '{label}' signal(s)" for label, count in label_counts.items())

    return {
        "is_genuine_concern": True,
        "ai_explanation": {
            "what_happened": f"We picked up {len(risky_events)} concerning signals: {summary}.",
            "why_it_matters": "Together, this matches a pattern that's worth a closer look.",
            "recommended_action": "Open the dashboard and review the flagged activity yourself.",
            "severity_label": "medium",
        },
    }


# test
if __name__ == "__main__":
    class FakeEvent:
        def __init__(self, risk_label, content):
            self.risk_label = risk_label
            self.content = content

    test_events = [
        FakeEvent("personal_info_request", "whats your real name and where do you go to school"),
        FakeEvent("platform_switch_request", "let's talk on a different app instead"),
    ]
    result = analyze_and_explain(test_events)
    print(json.dumps(result, indent=2))
