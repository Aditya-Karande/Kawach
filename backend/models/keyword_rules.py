"""
A simple, non-ML backup check. It looks for known red-flag phrases
directly in the text (case-insensitive matching).
"""

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
    "different app",
    "private chat",
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
]

def check_keywords(text:str) -> dict | None:
    """
    Checks text against known red-flag phrase lists.
    Returns {"label": ..., "matched_phrase": ...} if something matches,
    or None if nothing matches (meaning: rely on the ML classifier's result).
    """
    lower_text = text.lower()

    for phrase in GROOMING_PHRASES:
        if phrase in lower_text:
            return {"label":"grooming","matched_phrase":phrase}

    for phrase in CONCEALMENT_PHRASES:
        if phrase in lower_text:
            return{"label":"concealment","matched_phrase":phrase}

    return None
    
# testing
if __name__ == "__main__":
    test_sentences = [
        "lets keep this between us ok",
        "what is the capital of france",
        "make sure to clear your history after",
        "you have won a free prize",
        "whats the difference between us"
    ]          

    for sentence in test_sentences:
        result = check_keywords(sentence)
        print(f"{sentence!r} -> {result}")