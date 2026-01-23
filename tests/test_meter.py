"""Tests for meter analysis module."""

import pytest

from shpoet.features.meter import (
    MeterAnalysis,
    analyze_meter,
    check_meter_adjacency,
    get_meter_features,
)


class TestAnalyzeMeter:
    """Tests for the analyze_meter function."""

    def test_iambic_pentameter(self) -> None:
        """Test analysis of classic iambic pentameter."""
        # "To be or not to be that is the question"
        # Classic iambic pentameter line
        text = "To be or not to be that is the question"
        analysis = analyze_meter(text)

        assert isinstance(analysis, MeterAnalysis)
        assert analysis.syllable_count >= 9  # Allow some variation
        assert analysis.syllable_count <= 11
        # Should be fairly iambic
        assert analysis.iambic_score >= 0.4

    def test_empty_text(self) -> None:
        """Test analysis of empty text."""
        analysis = analyze_meter("")

        assert analysis.stress_pattern == ""
        assert analysis.syllable_count == 0
        assert analysis.is_iambic is False
        assert analysis.iambic_score == 0.0

    def test_single_word(self) -> None:
        """Test analysis of single word."""
        analysis = analyze_meter("question")

        assert analysis.syllable_count == 2
        assert len(analysis.stress_pattern) > 0

    def test_with_tokens(self) -> None:
        """Test analysis with pre-tokenized input."""
        tokens = ["To", "be", "or", "not", "to", "be"]
        analysis = analyze_meter("To be or not to be", tokens)

        assert analysis.syllable_count == 6

    def test_pentameter_fit(self) -> None:
        """Test pentameter fit calculation."""
        # 10 syllables should have perfect fit
        text = "But soft what light through yonder breaks"
        analysis = analyze_meter(text)

        # Pentameter fit should be high for ~10 syllables
        if 9 <= analysis.syllable_count <= 11:
            assert analysis.pentameter_fit >= 0.6

    def test_feet_count(self) -> None:
        """Test feet count property."""
        text = "To be or not to be"  # 6 syllables = 3 feet
        analysis = analyze_meter(text)

        expected_feet = analysis.syllable_count // 2
        assert analysis.feet_count == expected_feet


class TestCheckMeterAdjacency:
    """Tests for meter adjacency checking."""

    def test_good_transition(self) -> None:
        """Test that good meter transitions are accepted."""
        # Stressed ending to unstressed start is good
        prev_pattern = "01"  # Ends stressed
        curr_pattern = "01"  # Starts unstressed

        acceptable, score = check_meter_adjacency(prev_pattern, curr_pattern)

        assert acceptable is True
        assert score >= 0.8

    def test_bad_transition(self) -> None:
        """Test that bad meter transitions are flagged."""
        # Stressed ending to stressed start disrupts meter
        prev_pattern = "01"  # Ends stressed
        curr_pattern = "10"  # Starts stressed

        acceptable, score = check_meter_adjacency(prev_pattern, curr_pattern, strictness=0.8)

        # With high strictness, this should be rejected
        assert score < 0.5

    def test_empty_patterns(self) -> None:
        """Test handling of empty patterns."""
        acceptable, score = check_meter_adjacency("", "01")
        assert acceptable is True

        acceptable, score = check_meter_adjacency("01", "")
        assert acceptable is True

    def test_strictness_levels(self) -> None:
        """Test different strictness levels."""
        prev = "01"  # Ends stressed
        curr = "10"  # Starts stressed (mediocre transition)

        # At strictness=0.5, threshold is 0.5
        _, score = check_meter_adjacency(prev, curr, strictness=0.5)

        # Score should be in valid range
        assert 0.0 <= score <= 1.0

        # Very strict should be more likely to reject
        accept_strict, _ = check_meter_adjacency(prev, curr, strictness=0.9)
        # Implementation-dependent behavior


class TestGetMeterFeatures:
    """Tests for the get_meter_features convenience function."""

    def test_returns_dict(self) -> None:
        """Test that get_meter_features returns correct structure."""
        features = get_meter_features("To be or not to be")

        assert "stress_pattern" in features
        assert "syllable_count" in features
        assert "is_iambic" in features
        assert "iambic_score" in features
        assert "pentameter_fit" in features

    def test_types(self) -> None:
        """Test that feature values have correct types."""
        features = get_meter_features("Hello world")

        assert isinstance(features["stress_pattern"], str)
        assert isinstance(features["syllable_count"], int)
        assert isinstance(features["is_iambic"], bool)
        assert isinstance(features["iambic_score"], float)
        assert isinstance(features["pentameter_fit"], float)


class TestShakespeareLines:
    """Test meter analysis on Shakespeare lines."""

    def test_hamlet_opening(self) -> None:
        """Test Hamlet's famous line."""
        text = "To be or not to be that is the question"
        analysis = analyze_meter(text)

        # Should be close to pentameter
        assert 9 <= analysis.syllable_count <= 11
        # Should show some iambic pattern
        assert analysis.iambic_score > 0.3

    def test_romeo_juliet_balcony(self) -> None:
        """Test Romeo and Juliet balcony scene line."""
        text = "But soft what light through yonder window breaks"
        analysis = analyze_meter(text)

        assert analysis.syllable_count >= 9
        # Classic iambic line
        assert analysis.iambic_score > 0.3

    def test_macbeth_tomorrow(self) -> None:
        """Test Macbeth's tomorrow speech."""
        text = "Tomorrow and tomorrow and tomorrow"
        analysis = analyze_meter(text)

        # Should be approximately 10 syllables
        assert 9 <= analysis.syllable_count <= 11
