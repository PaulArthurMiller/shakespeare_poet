"""Integration tests for Tier-2 feature extraction pipeline."""

import json

import pytest

from shpoet.features.tier2_derived import (
    apply_tier2_features,
    extract_tier2_features,
    get_tier2_metadata_keys,
)


class TestExtractTier2Features:
    """Tests for single-chunk feature extraction."""

    def test_basic_extraction(self) -> None:
        """Test that all feature categories are extracted."""
        text = "To be or not to be that is the question"
        tokens = ["To", "be", "or", "not", "to", "be", "that", "is", "the", "question"]

        features = extract_tier2_features(text, tokens)

        # Phonetic features
        assert "phonemes" in features
        assert "stress_pattern" in features
        assert "rhyme_class" in features
        assert "alliteration_sound" in features

        # Meter features
        assert "syllable_count" in features
        assert "is_iambic" in features
        assert "iambic_score" in features

        # Syntax features
        assert "pos_tags" in features
        assert "pos_first" in features
        assert "pos_last" in features
        assert "grammatical_role" in features
        assert "has_verb" in features
        assert "has_noun" in features
        assert "clause_type" in features

        # Semantic features
        assert "emotion_valence" in features
        assert "emotion_intensity" in features
        assert "rhetoric_label" in features
        assert "topic_cluster" in features

    def test_feature_types(self) -> None:
        """Test that features have correct types."""
        text = "Sweet love of youth"
        tokens = ["Sweet", "love", "of", "youth"]

        features = extract_tier2_features(text, tokens)

        # Check types
        assert isinstance(features["phonemes"], str)  # JSON string
        assert isinstance(features["stress_pattern"], str)
        assert isinstance(features["syllable_count"], int)
        assert isinstance(features["is_iambic"], bool)
        assert isinstance(features["iambic_score"], float)
        assert isinstance(features["pos_tags"], str)  # JSON string
        assert isinstance(features["emotion_valence"], float)

    def test_phonemes_parseable(self) -> None:
        """Test that phonemes JSON is valid."""
        text = "Hello world"
        tokens = ["Hello", "world"]

        features = extract_tier2_features(text, tokens)

        # Should be valid JSON
        phonemes = json.loads(features["phonemes"])
        assert isinstance(phonemes, list)

    def test_pos_tags_parseable(self) -> None:
        """Test that POS tags JSON is valid."""
        text = "The quick fox"
        tokens = ["The", "quick", "fox"]

        features = extract_tier2_features(text, tokens)

        # Should be valid JSON
        pos_tags = json.loads(features["pos_tags"])
        assert isinstance(pos_tags, list)


class TestApplyTier2Features:
    """Tests for batch feature application."""

    def test_batch_processing(self) -> None:
        """Test batch processing of multiple chunks."""
        chunks = [
            {"text": "To be or not to be", "tokens": ["To", "be", "or", "not", "to", "be"]},
            {"text": "That is the question", "tokens": ["That", "is", "the", "question"]},
            {"text": "Sweet sorrow", "tokens": ["Sweet", "sorrow"]},
        ]

        enriched = apply_tier2_features(chunks)

        assert len(enriched) == 3
        for chunk in enriched:
            # Original fields preserved
            assert "text" in chunk
            assert "tokens" in chunk
            # New fields added
            assert "syllable_count" in chunk
            assert "is_iambic" in chunk

    def test_empty_chunks(self) -> None:
        """Test handling of empty chunk list."""
        enriched = apply_tier2_features([])
        assert enriched == []

    def test_preserves_original_fields(self) -> None:
        """Test that original chunk fields are preserved."""
        chunks = [
            {
                "chunk_id": "test_001",
                "text": "Hello world",
                "tokens": ["Hello", "world"],
                "source": "test",
            }
        ]

        enriched = apply_tier2_features(chunks)

        assert enriched[0]["chunk_id"] == "test_001"
        assert enriched[0]["source"] == "test"


class TestMetadataKeys:
    """Tests for metadata key listing."""

    def test_returns_all_keys(self) -> None:
        """Test that all expected keys are returned."""
        keys = get_tier2_metadata_keys()

        assert "phonemes" in keys
        assert "stress_pattern" in keys
        assert "syllable_count" in keys
        assert "is_iambic" in keys
        assert "pos_tags" in keys
        assert "emotion_valence" in keys
        assert "topic_cluster" in keys

    def test_matches_extracted_features(self) -> None:
        """Test that keys match what extract_tier2_features produces."""
        keys = set(get_tier2_metadata_keys())
        features = extract_tier2_features("Test text", ["Test", "text"])

        # All documented keys should be in features
        for key in keys:
            assert key in features, f"Key {key} not in extracted features"


class TestShakespeareanText:
    """Test pipeline with actual Shakespearean text."""

    def test_hamlet_line(self) -> None:
        """Test Hamlet's famous soliloquy line."""
        text = "To be or not to be that is the question"
        tokens = text.split()

        features = extract_tier2_features(text, tokens)

        # Should be roughly iambic pentameter
        assert 9 <= features["syllable_count"] <= 11
        # Contains "not" so may be detected as negation, or as statement
        assert features["rhetoric_label"] in ("question", "statement", "negation")

    def test_love_sonnet_line(self) -> None:
        """Test a line with love theme."""
        text = "Sweet love renews his force"
        tokens = ["Sweet", "love", "renews", "his", "force"]

        features = extract_tier2_features(text, tokens)

        # Should detect love topic
        assert features["topic_cluster"] == "love"
        # Should have positive valence
        assert features["emotion_valence"] > 0

    def test_death_theme(self) -> None:
        """Test a line with death theme."""
        text = "Death and sorrow fill the grave"
        tokens = ["Death", "and", "sorrow", "fill", "the", "grave"]

        features = extract_tier2_features(text, tokens)

        # Should detect death topic
        assert features["topic_cluster"] == "death"
        # Should have negative valence
        assert features["emotion_valence"] < 0

    def test_exclamation(self) -> None:
        """Test exclamatory text."""
        text = "O Romeo wherefore art thou Romeo!"
        tokens = ["O", "Romeo", "wherefore", "art", "thou", "Romeo"]

        features = extract_tier2_features(text, tokens)

        # Should be detected as exclamation or question
        assert features["rhetoric_label"] in ("exclamation", "question")
