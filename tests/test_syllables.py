"""Tests for syllable counting module."""

import pytest

from shpoet.features.syllables import (
    SyllableCounter,
    count_syllables,
    count_text_syllables,
    get_syllable_counter,
)


class TestSyllableCounter:
    """Tests for the SyllableCounter class."""

    def test_singleton_instance(self) -> None:
        """Ensure get_syllable_counter returns the same instance."""
        counter1 = get_syllable_counter()
        counter2 = get_syllable_counter()
        assert counter1 is counter2

    def test_single_syllable_words(self) -> None:
        """Test counting syllables in single-syllable words."""
        counter = SyllableCounter()
        assert counter.count_syllables("cat") == 1
        assert counter.count_syllables("dog") == 1
        assert counter.count_syllables("man") == 1
        assert counter.count_syllables("word") == 1
        assert counter.count_syllables("speak") == 1

    def test_multi_syllable_words(self) -> None:
        """Test counting syllables in multi-syllable words."""
        counter = SyllableCounter()
        assert counter.count_syllables("question") == 2
        assert counter.count_syllables("beautiful") == 3
        # imagination can be 4 or 5 depending on dialect/speed
        assert counter.count_syllables("imagination") in (4, 5)
        assert counter.count_syllables("poetry") == 3

    def test_archaic_words(self) -> None:
        """Test counting syllables in Shakespearean archaic words."""
        counter = SyllableCounter()
        # These should come from archaic_pronunciations.json
        assert counter.count_syllables("thou") == 1
        assert counter.count_syllables("thee") == 1
        assert counter.count_syllables("hath") == 1
        assert counter.count_syllables("doth") == 1
        assert counter.count_syllables("'tis") == 1
        # o'er has 2 phonetic syllables (OW + ER) even though metrically 1
        assert counter.count_syllables("o'er") in (1, 2)
        assert counter.count_syllables("methinks") == 2
        assert counter.count_syllables("wherefore") == 2

    def test_contracted_words(self) -> None:
        """Test syllables in contracted/elided forms."""
        counter = SyllableCounter()
        # Contracted past tenses
        assert counter.count_syllables("return'd") == 2
        assert counter.count_syllables("call'd") == 1
        # Contracted syllables
        assert counter.count_syllables("heav'n") == 1
        assert counter.count_syllables("e'en") == 1

    def test_empty_and_edge_cases(self) -> None:
        """Test edge cases and empty input."""
        counter = SyllableCounter()
        assert counter.count_syllables("") == 1  # minimum is 1
        assert counter.count_syllables("a") == 1
        assert counter.count_syllables("I") == 1
        assert counter.count_syllables("...") == 1

    def test_punctuation_handling(self) -> None:
        """Test that punctuation is properly stripped."""
        counter = SyllableCounter()
        assert counter.count_syllables("word.") == counter.count_syllables("word")
        assert counter.count_syllables("'word'") == counter.count_syllables("word")
        assert counter.count_syllables("(hello)") == counter.count_syllables("hello")

    def test_syllable_breakdown(self) -> None:
        """Test getting syllable breakdown."""
        counter = SyllableCounter()
        breakdown = counter.get_syllable_breakdown("beautiful")
        assert len(breakdown) >= 2  # At least 2 parts

    def test_text_syllable_count(self) -> None:
        """Test counting syllables in a full text."""
        counter = SyllableCounter()
        # "To be or not to be" - each word is 1 syllable = 6 total
        count = counter.count_text_syllables("To be or not to be")
        assert count == 6

    def test_tokens_syllable_count(self) -> None:
        """Test counting syllables from token list."""
        counter = SyllableCounter()
        tokens = ["To", "be", "or", "not", "to", "be"]
        count = counter.count_tokens_syllables(tokens)
        assert count == 6


class TestConvenienceFunctions:
    """Tests for module-level convenience functions."""

    def test_count_syllables_function(self) -> None:
        """Test the count_syllables convenience function."""
        assert count_syllables("question") == 2
        assert count_syllables("the") == 1

    def test_count_text_syllables_function(self) -> None:
        """Test the count_text_syllables convenience function."""
        # Famous line should be ~10 syllables (iambic pentameter)
        text = "To be or not to be that is the question"
        count = count_text_syllables(text)
        # Allow +/- 1 for pronunciation variations
        assert 9 <= count <= 11


class TestShakespeareLines:
    """Test syllable counting on actual Shakespeare lines."""

    def test_hamlet_soliloquy_opening(self) -> None:
        """Test 'To be or not to be' line."""
        # Iambic pentameter = 10 syllables, allow +/-1 for variations
        count = count_text_syllables("To be or not to be that is the question")
        assert 9 <= count <= 11

    def test_romeo_and_juliet(self) -> None:
        """Test lines from Romeo and Juliet."""
        # "But soft what light through yonder window breaks" = ~10 syllables
        count = count_text_syllables("But soft what light through yonder window breaks")
        assert 9 <= count <= 11

    def test_macbeth_line(self) -> None:
        """Test line from Macbeth."""
        # "Tomorrow and tomorrow and tomorrow" = ~10 syllables
        count = count_text_syllables("Tomorrow and tomorrow and tomorrow")
        assert 9 <= count <= 11
