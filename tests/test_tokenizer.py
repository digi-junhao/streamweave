"""Tests for the StreamWeave regex tokeniser.

v1 is the classic Thompson core: literals, concatenation, `|`, `()`, `*`.
Assertions compare token kinds and integer values, never repr strings, so a
cosmetic change to `__repr__` cannot break the suite.
"""

import pytest

from streamweave.tokenizer import ParseError, Token, TokenKind, tokenize

K = TokenKind


def kinds(pattern: str) -> list[TokenKind]:
    """The token kinds for `pattern`, EOF included."""
    return [t.kind for t in tokenize(pattern)]


def values(pattern: str) -> list[int | None]:
    """The token values for `pattern`, EOF's trailing None dropped."""
    return [t.value for t in tokenize(pattern)[:-1]]


def only(pattern: str) -> Token:
    """The single token of a one-token pattern."""
    tokens = tokenize(pattern)
    assert len(tokens) == 2, f"{pattern!r} produced {len(tokens) - 1} tokens, wanted 1"
    return tokens[0]


# ------------------------------------------------------------------ the basics
def test_empty_pattern_is_just_eof():
    # Rejecting "" is the grammar's job, not the tokeniser's.
    assert kinds("") == [K.EOF]


def test_eof_is_appended_exactly_once():
    tokens = tokenize("a|b*")
    assert tokens[-1].kind is K.EOF
    assert [t.kind for t in tokens].count(K.EOF) == 1


def test_eof_position_is_end_of_pattern():
    assert tokenize("abc")[-1].position == 3


@pytest.mark.parametrize(
    "pattern,expected",
    [
        ("a", [K.CHAR]),
        ("ab", [K.CHAR, K.CHAR]),
        ("a|b", [K.CHAR, K.PIPE, K.CHAR]),
        ("a*", [K.CHAR, K.STAR]),
        ("(a)", [K.LPAREN, K.CHAR, K.RPAREN]),
        ("a**", [K.CHAR, K.STAR, K.STAR]),
        ("(a|b)*", [K.LPAREN, K.CHAR, K.PIPE, K.CHAR, K.RPAREN, K.STAR]),
    ],
)
def test_kinds(pattern, expected):
    assert kinds(pattern) == expected + [K.EOF]


def test_only_six_token_kinds_exist():
    # A regression guard: the v1 language is deliberately this small.
    assert {k.name for k in K} == {"CHAR", "PIPE", "STAR", "LPAREN", "RPAREN", "EOF"}


def test_char_values_are_byte_ints():
    assert values("abc") == [97, 98, 99]


def test_operators_carry_no_value():
    assert values("|*()") == [None, None, None, None]


def test_positions_are_source_indices():
    assert [t.position for t in tokenize("a(b|c)*")] == [0, 1, 2, 3, 4, 5, 6, 7]


def test_high_bytes_are_accepted():
    assert only("\xff").value == 255


def test_codepoint_above_255_is_rejected():
    with pytest.raises(ParseError) as exc:
        tokenize("a€b")
    assert exc.value.position == 1


# ------------------------------------------------------------------- escapes
@pytest.mark.parametrize(
    "pattern,code",
    [
        (r"\n", 10),
        (r"\t", 9),
        (r"\r", 13),
        (r"\f", 12),
        (r"\v", 11),
        (r"\0", 0),
        (r"\*", 42),
        (r"\|", 124),
        (r"\(", 40),
        (r"\)", 41),
        ("\\\\", 92),
        (r"\+", 43),
        (r"\?", 63),
        (r"\.", 46),
        (r"\[", 91),
        (r"\]", 93),
        (r"\{", 123),
        (r"\}", 125),
        (r"\^", 94),
        (r"\$", 36),
        (r"\-", 45),
        (r"\x41", 65),
        (r"\xff", 255),
    ],
)
def test_escapes_produce_one_char_token(pattern, code):
    token = only(pattern)
    assert token.kind is K.CHAR
    assert token.value == code


def test_escaped_operator_is_a_literal_not_an_operator():
    assert kinds(r"a\*b") == [K.CHAR, K.CHAR, K.CHAR, K.EOF]
    assert values(r"a\*b") == [97, 42, 98]


def test_every_unsupported_character_is_still_writable_escaped():
    # `+` is rejected bare, so `\+` is the only way to match a plus sign.
    # If that failed, some bytes would be unmatchable.
    for char in "+?.[{^$":
        assert only("\\" + char).value == ord(char)


def test_characters_that_are_no_longer_special_are_bare_literals():
    # `]`, `}` and `-` only mattered inside character classes, which are gone.
    assert values("]}-") == [93, 125, 45]


# -------------------------------------------------------- unsupported syntax
@pytest.mark.parametrize(
    "pattern,position,fragment",
    [
        ("a+", 1, "'+' operator"),
        ("a?", 1, "'?' operator"),
        ("a.b", 1, "wildcard '.'"),
        ("[a-z]", 0, "character classes"),
        ("a{2,3}", 1, "bounded repetition"),
        ("^a", 0, "anchor '^'"),
        ("a$", 1, "anchor '$'"),
        (r"\d", 0, r"shorthand class '\d'"),
        (r"a\W", 1, r"shorthand class '\W'"),
        (r"\s", 0, r"shorthand class '\s'"),
    ],
)
def test_unsupported_constructs_are_named(pattern, position, fragment):
    with pytest.raises(ParseError) as exc:
        tokenize(pattern)
    assert exc.value.position == position, str(exc.value)
    assert fragment in exc.value.message


def test_plus_error_suggests_the_rewrite():
    with pytest.raises(ParseError) as exc:
        tokenize("a+")
    assert "aa*" in exc.value.message


# -------------------------------------------------------------------- errors
@pytest.mark.parametrize(
    "pattern,position,fragment",
    [
        ("a\\", 1, "trailing"),
        ("\\", 0, "trailing"),
        (r"a\q", 1, "unknown escape"),
        (r"\x4", 0, "two hex digits"),
        (r"\xzz", 0, "two hex digits"),
    ],
)
def test_lexical_error_positions_and_messages(pattern, position, fragment):
    with pytest.raises(ParseError) as exc:
        tokenize(pattern)
    assert exc.value.position == position, str(exc.value)
    assert fragment in exc.value.message


def test_error_renders_a_caret_under_the_position():
    with pytest.raises(ParseError) as exc:
        tokenize("ab{2}")
    assert str(exc.value).splitlines() == [
        "bounded repetition '{n,m}' is not supported in v1 at position 2",
        "  ab{2}",
        "    ^",
    ]


# ------------------------------------------------- what the parser must catch
def test_unbalanced_parens_are_not_the_tokenisers_problem():
    # Shape is the parser's job; the tokeniser only reports lexical failures.
    assert kinds("(a") == [K.LPAREN, K.CHAR, K.EOF]
    assert kinds("a)") == [K.CHAR, K.RPAREN, K.EOF]


def test_star_with_no_operand_is_not_the_tokenisers_problem():
    assert kinds("*a") == [K.STAR, K.CHAR, K.EOF]


def test_empty_alternation_branch_is_not_the_tokenisers_problem():
    assert kinds("a|") == [K.CHAR, K.PIPE, K.EOF]


# ---------------------------------------------------------------- integration
def test_the_canonical_thompson_pattern():
    tokens = tokenize("(a|b)*abb")
    assert [(t.kind, t.position) for t in tokens] == [
        (K.LPAREN, 0), (K.CHAR, 1), (K.PIPE, 2), (K.CHAR, 3), (K.RPAREN, 4),
        (K.STAR, 5), (K.CHAR, 6), (K.CHAR, 7), (K.CHAR, 8), (K.EOF, 9),
    ]


def test_a_pattern_mixing_literals_an_operator_and_an_escape():
    pattern = r"ht*p\."
    assert kinds(pattern) == [K.CHAR, K.CHAR, K.STAR, K.CHAR, K.CHAR, K.EOF]
    literals = [t.value for t in tokenize(pattern) if t.kind is K.CHAR]
    assert literals == [104, 116, 112, 46]  # h, t, p, and a literal dot
