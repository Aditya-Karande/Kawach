import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "openai/gpt-oss-20b"

def analyze_and_explain(risky_events:list) -> dict:
    # simple, readable of what was flagged, to feed the LLM.
    events_summary = "\n".join(
        f"- [{e.risk_label}] \"{e.content}\"" for e in risky_events
    )

    prompt = f"""You are a child-safety analyst reviewing flagged messages/URLs from a child's browser activity monitoring system.
 
Here are the flagged events:
{events_summary}
 
Your job:
1. Judge whether this is a GENUINE safety concern, based on real context and intent — not just because keywords matched. For example, "our secret" in the context of a treehouse club is NOT concerning, but "our secret, don't tell your parents" IS concerning. Consider the full picture of all events together.
2. If genuinely concerning, write a short, calm, plain-English explanation for a PARENT (2-3 sentences, no jargon, no alarmist language, just clear facts).
3. Assign a risk_level: "low", "medium", or "high".
 
Respond with ONLY valid JSON in this exact format, nothing else:
{{"is_genuine_concern": true or false, "explanation": "...", "risk_level": "low/medium/high"}}
"""
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
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": 0.3,
                "response_format": {"type": "json_object"}
            },
            timeout=10
        )

        response.raise_for_status()

        result_text = response.json()["choices"][0]["message"]["content"]

        parsed = json.loads(result_text)

        return {
            "is_genuine_concern": bool(parsed.get("is_genuine_concern", True)),
            "explanation": parsed.get(
                "explanation",
                "Concerning pattern detected — please review."
            ),
            "risk_level": parsed.get("risk_level", "medium"),
        }

    except Exception as e:
        print(f"WARNING: LLM call failed ({e}) — using fallback explanation")
        print(f"ERROR: {e}")
        print(response.text)
        return _fallback_result(risky_events)
    
def _fallback_result(risky_events:list) -> dict:
    """
    Simple non-LLM fallback, used if the API call fails.
    Fails SAFE: always treats it as a genuine concern, so technical
    issues never hide a real risk from a parent.
    """
    label_counts = {}

    for e in risky_events:
        label_counts[e.risk_label] = label_counts.get(e.risk_label,0)+1
    summary = ", ".join(f"{count} '{label}' events" for label, count in label_counts.items())

    return {
        "is_genuine_concern":True,
        "explanation":f"{len(risky_events)} concerning signals detected: {summary}. (Automated explanation — AI analysis unavailable.)",
        "risk_level":"medium"
    }

# test
if __name__ == "__main__":
    class FakeEvent:
        def __init__(self, risk_label, content):
            self.risk_label = risk_label
            self.content = content
 
    test_events = [
        FakeEvent("grooming", "this is our secret, don't tell your parents"),
        FakeEvent("concealment", "make sure to clear your history after"),
    ]
    result = analyze_and_explain(test_events)
    print(json.dumps(result, indent=2))