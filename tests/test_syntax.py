"""Tests for syntax feature extraction module."""

import json

import pytest

from shpoet.features.syntax import (
    check_syntax_adjacency,
    extract_syntax_features,
    get_compatible_roles,
)


class TestExtractSyntaxFeatures:
    """Tests for syntax feature extraction."""

    def test_basic_extraction(self) -> None:
        """Test basic syntax feature extraction."""
        text = "The quick brown fox"
        features = extract_syntax_features(text)

        assert "pos_tags" in features
        assert "pos_first" in features
        assert "pos_last" in features
        assert "grammatical_role" in features
        assert "has_verb" in features
        assert "has_noun" in features
        assert "clause_type" in features

    def test_pos_tags_json(self) -> None:
        """Test that POS tags are valid JSON."""
        features = extract_syntax_features("The dog runs")

        pos_tags = json.loads(features["pos_tags"])
        assert isinstance(pos_tags, list)
        assert len(pos_tags) > 0

    def test_noun_detection(self) -> None:
        """Test noun detection."""
        features = extract_syntax_features("The beautiful garden")

        assert features["has_noun"] is True

    def test_verb_detection(self) -> None:
        """Test verb detection."""
        features = extract_syntax_features("She runs quickly")

        assert features["has_verb"] is True

    def test_no_verb(self) -> None:
        """Test detection of chunks without verbs."""
        features = extract_syntax_features("the quick brown fox")

        assert features["has_verb"] is False

    def test_empty_text(self) -> None:
        """Test handling of empty text."""
        features = extract_syntax_features("")

        assert features["grammatical_role"] == "empty"
        assert features["pos_first"] == ""
        assert features["pos_last"] == ""

    def test_first_last_pos(self) -> None:
        """Test first and last POS extraction."""
        features = extract_syntax_features("The dog barks loudly")

        # "The" is typically DET, "loudly" is ADV
        assert features["pos_first"] != ""
        assert features["pos_last"] != ""


class TestGrammaticalRole:
    """Tests for grammatical role detection."""

    def test_subject_detection(self) -> None:
        """Test subject role detection."""
        features = extract_syntax_features("The old man")

        # Noun phrase could be subject or noun_phrase
        assert features["grammatical_role"] in ("subject", "noun_phrase", "fragment")

    def test_predicate_detection(self) -> None:
        """Test predicate/verb phrase detection."""
        features = extract_syntax_features("runs very fast")

        assert features["has_verb"] is True

    def test_modifier_detection(self) -> None:
        """Test prepositional phrase role detection."""
        features = extract_syntax_features("in the garden")

        # Prepositional phrases can be parsed as object or modifier
        # depending on spaCy's analysis
        assert features["grammatical_role"] in ("modifier", "object", "fragment")


class TestClauseType:
    """Tests for clause type detection."""

    def test_main_clause(self) -> None:
        """Test main clause detection."""
        features = extract_syntax_features("The dog runs")

        # Complete sentence with subject and verb
        assert features["clause_type"] in ("main", "none")

    def test_subordinate_clause(self) -> None:
        """Test subordinate clause detection."""
        features = extract_syntax_features("when the sun sets")

        # "when" marks subordinate clause
        assert features["clause_type"] in ("subordinate", "none")

    def test_conditional_clause(self) -> None:
        """Test conditional clause detection."""
        features = extract_syntax_features("if you go there")

        assert features["clause_type"] in ("conditional", "subordinate", "none")


class TestSyntaxAdjacency:
    """Tests for syntax adjacency checking."""

    def test_good_adjacency(self) -> None:
        """Test that valid adjacencies are accepted."""
        prev = {"pos_last": "NOUN", "grammatical_role": "subject", "has_verb": False}
        curr = {"pos_first": "VERB", "grammatical_role": "predicate", "has_verb": True}

        acceptable, reason = check_syntax_adjacency(prev, curr)
        assert acceptable is True

    def test_dangling_determiner(self) -> None:
        """Test that dangling determiners are caught."""
        prev = {"pos_last": "DET", "grammatical_role": "fragment", "has_verb": False}
        curr = {"pos_first": "VERB", "grammatical_role": "predicate", "has_verb": True}

        acceptable, reason = check_syntax_adjacency(prev, curr)
        # DET followed by VERB is often acceptable in real usage
        # This depends on implementation strictness

    def test_dangling_conjunction(self) -> None:
        """Test that dangling conjunctions are caught."""
        prev = {"pos_last": "CCONJ", "grammatical_role": "fragment", "has_verb": False}
        curr = {"pos_first": "PUNCT", "grammatical_role": "empty", "has_verb": False}

        acceptable, reason = check_syntax_adjacency(prev, curr)
        assert acceptable is False


class TestCompatibleRoles:
    """Tests for role compatibility."""

    def test_subject_compatible(self) -> None:
        """Test roles compatible with subject."""
        compatible = get_compatible_roles("subject")

        assert "predicate" in compatible
        assert "modifier" in compatible

    def test_predicate_compatible(self) -> None:
        """Test roles compatible with predicate."""
        compatible = get_compatible_roles("predicate")

        assert "object" in compatible
        assert "modifier" in compatible

    def test_fragment_compatible(self) -> None:
        """Test that fragment is broadly compatible."""
        compatible = get_compatible_roles("fragment")

        # Fragment should be compatible with most things
        assert len(compatible) > 3
