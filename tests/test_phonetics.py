"""Tests for phonetic analysis module."""

import pytest

from shpoet.features.phonetics import (
    compute_rhyme_class,
    extract_phonetic_features,
    get_alliteration_sound,
    get_phonemes,
    get_stress_pattern,
    words_alliterate,
    words_rhyme,
)


class TestGetPhonemes:
    """Tests for phoneme extraction."""

    def test_common_words(self) -> None:
        """Test phonemes for common English words."""
        phonemes = get_phonemes("hello")
        assert len(phonemes) > 0
        assert isinstance(phonemes[0], list)

    def test_archaic_words(self) -> None:
        """Test phonemes for archaic Shakespearean words."""
        # These should come from archaic_pronunciations.json
        phonemes = get_phonemes("thou")
        assert len(phonemes) > 0
        assert phonemes[0] == ["DH", "AW1"]

        phonemes = get_phonemes("hath")
        assert len(phonemes) > 0
        assert phonemes[0] == ["HH", "AE1", "TH"]

    def test_unknown_word(self) -> None:
        """Test behavior with unknown words."""
        phonemes = get_phonemes("xyzzy123")
        assert phonemes == []

    def test_empty_input(self) -> None:
        """Test behavior with empty input."""
        assert get_phonemes("") == []
        assert get_phonemes("...") == []


class TestStressPattern:
    """Tests for stress pattern extraction."""

    def test_basic_stress(self) -> None:
        """Test stress pattern extraction."""
        # "hello" has stress pattern 0-1 (second syllable stressed)
        phonemes = get_phonemes("hello")
        if phonemes:
            pattern = get_stress_pattern(phonemes[0])
            assert "1" in pattern  # Should have primary stress

    def test_monosyllable(self) -> None:
        """Test stress pattern for single-syllable word."""
        phonemes = get_phonemes("cat")
        if phonemes:
            pattern = get_stress_pattern(phonemes[0])
            assert len(pattern) == 1


class TestRhymeClass:
    """Tests for rhyme class computation."""

    def test_rhyme_class_basic(self) -> None:
        """Test basic rhyme class computation."""
        phonemes = get_phonemes("night")
        if phonemes:
            rc = compute_rhyme_class(phonemes[0])
            assert rc  # Should not be empty

    def test_rhyming_words_same_class(self) -> None:
        """Test that rhyming words have the same class."""
        night_phonemes = get_phonemes("night")
        light_phonemes = get_phonemes("light")

        if night_phonemes and light_phonemes:
            rc1 = compute_rhyme_class(night_phonemes[0])
            rc2 = compute_rhyme_class(light_phonemes[0])
            assert rc1 == rc2


class TestWordsRhyme:
    """Tests for rhyme detection."""

    def test_perfect_rhymes(self) -> None:
        """Test detection of perfect rhymes."""
        assert words_rhyme("night", "light") is True
        assert words_rhyme("love", "above") is True
        assert words_rhyme("day", "way") is True
        assert words_rhyme("time", "rhyme") is True

    def test_non_rhymes(self) -> None:
        """Test non-rhyming words."""
        assert words_rhyme("cat", "dog") is False
        assert words_rhyme("love", "move") is False  # Looks like rhyme but isn't


class TestAlliteration:
    """Tests for alliteration detection."""

    def test_alliteration_sound(self) -> None:
        """Test extraction of initial alliteration sound."""
        # Consonant-starting words
        assert get_alliteration_sound("beautiful") != ""
        assert get_alliteration_sound("cat") != ""

        # Vowel-starting words return empty
        assert get_alliteration_sound("apple") == ""
        assert get_alliteration_sound("elephant") == ""

    def test_words_alliterate(self) -> None:
        """Test alliteration detection between words."""
        assert words_alliterate("fair", "fortune") is True
        assert words_alliterate("sweet", "sorrow") is True
        assert words_alliterate("cat", "dog") is False

    def test_digraph_handling(self) -> None:
        """Test handling of digraphs like 'th', 'sh'."""
        # Words starting with 'th' should alliterate
        sound1 = get_alliteration_sound("think")
        sound2 = get_alliteration_sound("thought")
        assert sound1 == sound2


class TestExtractPhoneticFeatures:
    """Tests for the full feature extraction function."""

    def test_feature_extraction(self) -> None:
        """Test extracting all phonetic features."""
        text = "To be or not to be"
        tokens = ["To", "be", "or", "not", "to", "be"]

        features = extract_phonetic_features(text, tokens)

        assert "phonemes" in features
        assert "stress_pattern" in features
        assert "rhyme_class" in features
        assert "alliteration_sound" in features

    def test_empty_tokens(self) -> None:
        """Test feature extraction with empty tokens."""
        features = extract_phonetic_features("", [])

        assert features["phonemes"] == []
        assert features["stress_pattern"] == ""
        assert features["rhyme_class"] == ""
        assert features["alliteration_sound"] == ""

    def test_stress_pattern_combined(self) -> None:
        """Test that stress patterns are combined correctly."""
        text = "hello world"
        tokens = ["hello", "world"]

        features = extract_phonetic_features(text, tokens)

        # Should have stress markers from both words
        assert len(features["stress_pattern"]) >= 2


class TestShakespeareRhymes:
    """Test rhyme detection on Shakespearean word pairs."""

    def test_sonnet_rhymes(self) -> None:
        """Test common Shakespearean rhyme pairs."""
        # From Sonnet 18
        assert words_rhyme("day", "May") is True
        # Note: Some pairs may not rhyme in modern pronunciation
        # but would have in Elizabethan English

    def test_archaic_rhymes(self) -> None:
        """Test rhymes involving archaic words."""
        # "thee" and "be" should rhyme
        assert words_rhyme("thee", "be") is True
        # "thou" and "now" should rhyme
        assert words_rhyme("thou", "now") is True
