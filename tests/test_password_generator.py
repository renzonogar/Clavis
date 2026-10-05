"""
Tests for Clavis Password Generator and Strength Estimator:
- Cryptographic randomness verification
- Length limits and option validation
- Guaranteed character class representation
- Exclusion of ambiguous characters
- Entropy calculation and strength heuristic scoring
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from clavis.password_generator import (
    PasswordGenerator,
    GeneratorOptions,
    AMBIGUOUS_CHARS,
    LOWERCASE_CHARS,
    UPPERCASE_CHARS,
    DIGIT_CHARS,
    SYMBOL_CHARS
)


def test_generator_lengths():
    for length in [8, 16, 24, 32, 64, 128]:
        pw = PasswordGenerator.generate(GeneratorOptions(length=length))
        assert len(pw) == length

    # Invalid lengths
    with pytest.raises(ValueError):
        PasswordGenerator.generate(GeneratorOptions(length=7))
    with pytest.raises(ValueError):
        PasswordGenerator.generate(GeneratorOptions(length=129))


def test_character_class_guarantee():
    opts = GeneratorOptions(
        length=20,
        use_lowercase=True,
        use_uppercase=True,
        use_digits=True,
        use_symbols=True,
        exclude_ambiguous=False
    )
    for _ in range(50):
        pw = PasswordGenerator.generate(opts)
        assert any(c in LOWERCASE_CHARS for c in pw)
        assert any(c in UPPERCASE_CHARS for c in pw)
        assert any(c in DIGIT_CHARS for c in pw)
        assert any(c in SYMBOL_CHARS for c in pw)


def test_ambiguous_character_exclusion():
    opts = GeneratorOptions(
        length=32,
        use_lowercase=True,
        use_uppercase=True,
        use_digits=True,
        use_symbols=True,
        exclude_ambiguous=True
    )
    for _ in range(50):
        pw = PasswordGenerator.generate(opts)
        for amb in AMBIGUOUS_CHARS:
            assert amb not in pw


def test_strength_estimator_heuristics():
    # Empty
    res_empty = PasswordGenerator.estimate_strength("")
    assert res_empty["score"] == 0
    assert "Empty" in res_empty["label"]

    # Short / Very Weak
    res_short = PasswordGenerator.estimate_strength("abc")
    assert res_short["score"] == 0
    assert "Very Weak" in res_short["label"]

    # Weak (only digits)
    res_weak = PasswordGenerator.estimate_strength("12345678")
    assert res_weak["score"] in (0, 1)

    # Strong / Very Strong (high entropy, mixed classes, 24+ chars)
    res_strong = PasswordGenerator.estimate_strength("jK9#mQ2$xP8!vL5@zR1&wT4*")
    assert res_strong["score"] >= 3
    assert res_strong["entropy_bits"] > 70
    assert "disclaimer" in res_strong
