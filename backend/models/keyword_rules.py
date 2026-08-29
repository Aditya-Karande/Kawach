"""
A simple, non-ML backup check. It looks for known red-flag phrases
directly in the text (case-insensitive matching).
"""

from core.scoring import get_weight

# General grooming phrases — still relevant across signal types, but no
# longer the only chat-specific category (see PERSONAL_INFO_PHRASES and
# PLATFORM_SWITCH_PHRASES below, which the spec calls out with their own
# weights for chat_text specifically).
GROOMING_PHRASES = [
    "our secret",
    "between us",
    "dont tell your parents",
    "don't tell your parents",
    "dont tell anyone",
    "don't tell anyone",
    "you're so mature",
    "youre so mature",
    "just the two of us",
    "trust me",
]

CONCEALMENT_PHRASES = [
    "clear your history",
    "clear browser history",
    "incognito mode",
    "delete this chat",
    "delete our messages",
    "delete the messages",
    "before your parents",
    "wont tell if you dont tell",
    "won't tell if you don't tell",
    "hide my browser history",
    "hide browser history",
]

# Chat-specific: a message asking the child for identifying/personal info.
PERSONAL_INFO_PHRASES = [
    "what's your real name",
    "whats your real name",
    "where do you go to school",
    "what school do you go to",
    "what's your address",
    "whats your address",
    "where do you live",
    "send me a picture of yourself",
    "send a pic of yourself",
    "how old are you really",
    "what's your phone number",
    "whats your phone number",
    "are your parents home",
]

# Chat-specific: a message asking to move the conversation to another app.
PLATFORM_SWITCH_PHRASES = [
    "different app",
    "another app",
    "private chat",
    "add me on snap",
    "add me on snapchat",
    "add me on instagram",
    "dm me on",
    "message me on whatsapp",
    "let's talk somewhere else",
    "lets talk somewhere else",
    "switch to discord",
    "switch to telegram",
]


def check_keywords(text: str, signal_type: str = "chat_text") -> dict | None:
    """
    Checks text against known red-flag phrase lists. For chat_text, the
    two chat-specific categories (personal info / platform switch) are
    checked FIRST per spec Section 4.1/5, since they carry the highest
    weight and are the most actionable signal in a chat message.

    Returns {"label": ..., "matched_phrase": ..., "weight": ...} if
    something matches, or None if nothing matches (meaning: rely on the
    ML classifier's result).
    """
    lower_text = text.lower()

    if signal_type == "chat_text":
        for phrase in PERSONAL_INFO_PHRASES:
            if phrase in lower_text:
                return _result("personal_info_request", phrase, signal_type)

        for phrase in PLATFORM_SWITCH_PHRASES:
            if phrase in lower_text:
                return _result("platform_switch_request", phrase, signal_type)

    for phrase in GROOMING_PHRASES:
        if phrase in lower_text:
            return _result("grooming", phrase, signal_type)

    for phrase in CONCEALMENT_PHRASES:
        if phrase in lower_text:
            return _result("concealment", phrase, signal_type)

    return None


def _result(label: str, matched_phrase: str, signal_type: str) -> dict:
    return {
        "label": label,
        "matched_phrase": matched_phrase,
        "weight": get_weight(signal_type, label),
    }


# --- URL risk heuristic (for url_visit signals) ---
#
# Safe Browsing only tells us whether a URL is a CONFIRMED match against
# Google's threat lists. Most scam/phishing sites a kid stumbles onto
# aren't confirmed anywhere — they're new, low-traffic, or just never
# got reported. Treating every non-confirmed URL as "unconfirmed" (+2)
# would score ordinary browsing (a homework help site, a news article)
# the same as a sketchy prize-claim page, which produces constant false
# positives. So url_visit gets its own lightweight pattern check instead
# of a blanket "not on the blocklist = risky" rule.

URL_SCAM_KEYWORDS = [
    "free-robux", "free-v-bucks", "freevbucks", "freerobux",
    "claim-your-prize", "claim-prize", "claimreward", "claim-reward",
    "verify-your-account", "verify-account", "account-suspended",
    "account-locked", "confirm-identity",
    "gift-card-generator", "giftcard-generator", "free-gift-card",
    "crypto-doubler", "double-your-btc", "double-your-crypto",
    "urgent-action-required", "you-have-won", "youve-won", "you-ve-won",
    "no-verification-required", "no-human-verification",
    "unlock-followers", "free-followers", "free-likes",
]

# Suspicious-looking TLDs are only treated as a signal in COMBINATION
# with a scam keyword above — a .xyz or .top domain on its own is not
# remotely enough evidence to flag on its own.
SUSPICIOUS_TLDS = (".xyz", ".top", ".club", ".gq", ".tk", ".cf", ".ml", ".buzz")


def check_url_risk(url: str) -> dict | None:
    """
    Returns {"label": "unconfirmed", "matched_phrase": ..., "weight": ...}
    if the URL matches a known scam/phishing pattern, or None if it
    doesn't look suspicious by this heuristic (meaning: treat it as
    ordinary browsing, don't score it at all).
    """
    if not url:
        return None

    lower_url = url.lower()

    for keyword in URL_SCAM_KEYWORDS:
        if keyword in lower_url:
            return _result("unconfirmed", keyword, "url_visit")

    # A scam-adjacent word (not from the specific-phrase list above)
    # combined with a throwaway-looking TLD is still worth a flag, e.g.
    # "totally-legit-giveaway.xyz".
    generic_scam_words = ["giveaway", "prize", "reward", "bonus", "jackpot", "airdrop"]
    if any(tld in lower_url for tld in SUSPICIOUS_TLDS) and any(w in lower_url for w in generic_scam_words):
        return _result("unconfirmed", "suspicious-tld+scam-word", "url_visit")

    return None


# testing
if __name__ == "__main__":
    test_sentences = [
        "lets keep this between us ok",
        "what is the capital of france",
        "make sure to clear your history after",
        "you have won a free prize",
        "whats the difference between us",
        "whats your real name and where do you go to school",
        "can we talk on a different app instead",
    ]

    for sentence in test_sentences:
        result = check_keywords(sentence, signal_type="chat_text")
        print(f"{sentence!r} -> {result}")
