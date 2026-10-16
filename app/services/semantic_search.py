import hashlib
import math
import re

VECTOR_SIZE = 384
_STOP_WORDS = {
    "a", "an", "and", "are", "at", "for", "in", "is", "of", "on", "or",
    "the", "to", "with", "about", "that", "this", "show", "anime",
}
_CONCEPTS = {
    "cozy": {
        "calm", "comfort", "cozy", "gentle", "heartwarming", "peaceful",
        "relaxing", "soothing", "wholesome",
    },
    "slice_of_life": {
        "daily", "everyday", "iyashikei", "life", "routine", "slice",
        "slow", "slice-of-life", "slice_of_life",
    },
    "cooking": {
        "bake", "baking", "chef", "cook", "cooking", "culinary", "food",
        "kitchen", "meal", "recipe", "restaurant",
    },
    "romance": {"affection", "dating", "love", "romance", "romantic"},
    "adventure": {"adventure", "explore", "journey", "quest", "travel"},
    "comedy": {"comedic", "comedy", "funny", "humor", "humorous"},
    "fantasy": {"fantasy", "magic", "magical", "mythical", "supernatural"},
    "action": {"action", "battle", "combat", "fight", "fighting"},
}
_TOKEN_PATTERN = re.compile(r"[a-z0-9]+(?:[-_][a-z0-9]+)*")


def _features(text: str) -> list[str]:
    normalized = text.lower().replace("slice of life", "slice_of_life")
    tokens = [
        token.replace("-", "_")
        for token in _TOKEN_PATTERN.findall(normalized)
        if token not in _STOP_WORDS
    ]
    features = list(tokens)
    for token in tokens:
        for concept, terms in _CONCEPTS.items():
            if token in terms:
                features.append(f"concept:{concept}")
    return features


def embed_text(text: str) -> list[float]:
    vector = [0.0] * VECTOR_SIZE
    features = _features(text)
    for feature in features:
        digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
        index = int.from_bytes(digest[:4], "big") % VECTOR_SIZE
        sign = 1.0 if digest[4] & 1 else -1.0
        vector[index] += sign
    magnitude = math.sqrt(sum(value * value for value in vector))
    if magnitude:
        vector = [value / magnitude for value in vector]
    return vector


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != VECTOR_SIZE or len(right) != VECTOR_SIZE:
        return 0.0
    return sum(a * b for a, b in zip(left, right, strict=True))
