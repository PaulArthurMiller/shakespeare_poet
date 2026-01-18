"""Tier-1 feature extraction tests."""

from shpoet.features.tier1_raw import extract_tier1_features


def test_extract_tier1_features_basic_fields() -> None:
    """Ensure Tier-1 features include expected keys."""

    text = "To be, or not to be: that is the question."
    features = extract_tier1_features(text)

    assert features["token_count"] == 10
    assert features["char_count"] == len(text)
    assert features["first_token"] == "to"
    assert features["last_token"] == "question"
    assert features["punctuation"]["comma"] == 1
    assert features["punctuation"]["colon"] == 1
    assert features["punctuation"]["period"] == 1
    assert features["syllable_estimate"] > 0
    assert isinstance(features["starts_with_function_word"], bool)
    assert isinstance(features["ends_with_function_word"], bool)
