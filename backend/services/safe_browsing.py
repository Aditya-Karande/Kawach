# Talks to Google's Safe Browsing API to check if a URL is known to be malicious (phishing, malware, scam sites, etc).

import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("GOOGLE_SAFE_BROWSING_KEY")
SAFE_BROWSING_URL = "https://safebrowsing.googleapis.com/v4/threatMatches:find"

# function -> url is safe or not
def check_url_safety(url:str) -> bool:
    """
    Returns True if the URL is safe (or unknown), False if Google's
    Safe Browsing API flags it as malicious.
    """
    if not API_KEY:
        print("Warning: GOOGLE_SAFE_BROWSING_KEY not set in .env — skipping check")
        return True

    payload = {
        "client":{
            "clientId":"kawach-hackathon",
            "clientVersion":"1.0.0",
        },
        "threatInfo":{
            "threatTypes":[
                "MALWARE",
                "SOCIAL_ENGINEERING",  # phishing/scam sites
                "UNWANTED_SOFTWARE",
                "POTENTIALLY_HARMFUL_APPLICATION",
            ],
            "platformTypes":["ANY_PLATFORM"],
            "threatEntryTypes":["URL"],
            "threatEntries":[{"url":url}],
        },
    }

    try:
        response = requests.post(
            SAFE_BROWSING_URL,
            params={"key":API_KEY},
            json=payload,
            timeout=5
        )
        response.raise_for_status()
        result = response.json()

        # If Google found any matches, "matches" key will be present and non-empty.
        # If the URL is safe/unknown, the response body is just {}
        is_unsafe = "matches" in result and len(result["matches"]) > 0

        return not is_unsafe

    except requests.exceptions.RequestException as e:
        # Network error, timeout, bad API key, etc.
        # We fail "safe" (don't block) but log it so we notice during testing.
        print(f"WARNING: Safe Browsing API call failed: {e}")
        return True

# testing..
if __name__ == "__main__":
    test_urls = [
        "http://example.com",
        "http://testsafebrowsing.appspot.com/s/malware.html",  # Google's official test URL
    ]

    for url in test_urls:
        result = check_url_safety(url)
        print(f"{url} -> safe: {result}")
