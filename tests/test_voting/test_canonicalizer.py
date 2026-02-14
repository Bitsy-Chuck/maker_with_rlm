import pytest
from maker.voting.canonicalizer import Canonicalizer


class TestCanonicalize:
    def test_sorts_keys(self):
        canon = Canonicalizer()
        d1 = {"b": 1, "a": 2}
        d2 = {"a": 2, "b": 1}
        assert canon.canonicalize(d1) == canon.canonicalize(d2)

    def test_nested_keys_sorted(self):
        canon = Canonicalizer()
        d1 = {"outer": {"z": 1, "a": 2}}
        d2 = {"outer": {"a": 2, "z": 1}}
        assert canon.canonicalize(d1) == canon.canonicalize(d2)

    def test_deeply_nested_keys_sorted(self):
        canon = Canonicalizer()
        d1 = {"a": {"b": {"d": 1, "c": 2}}}
        d2 = {"a": {"b": {"c": 2, "d": 1}}}
        assert canon.canonicalize(d1) == canon.canonicalize(d2)

    def test_different_values_differ(self):
        canon = Canonicalizer()
        d1 = {"key": "value1"}
        d2 = {"key": "value2"}
        assert canon.canonicalize(d1) != canon.canonicalize(d2)

    def test_different_keys_differ(self):
        canon = Canonicalizer()
        d1 = {"a": 1}
        d2 = {"b": 1}
        assert canon.canonicalize(d1) != canon.canonicalize(d2)

    def test_extra_key_differs(self):
        canon = Canonicalizer()
        d1 = {"a": 1}
        d2 = {"a": 1, "b": 2}
        assert canon.canonicalize(d1) != canon.canonicalize(d2)

    def test_whitespace_in_strings_preserved(self):
        """String values with different whitespace should be different."""
        canon = Canonicalizer()
        d1 = {"text": "hello world"}
        d2 = {"text": "hello  world"}
        assert canon.canonicalize(d1) != canon.canonicalize(d2)

    def test_list_order_preserved(self):
        """Lists are NOT sorted — order matters."""
        canon = Canonicalizer()
        d1 = {"items": [1, 2, 3]}
        d2 = {"items": [3, 2, 1]}
        assert canon.canonicalize(d1) != canon.canonicalize(d2)

    def test_list_with_dicts_sorted_keys(self):
        canon = Canonicalizer()
        d1 = {"items": [{"b": 1, "a": 2}]}
        d2 = {"items": [{"a": 2, "b": 1}]}
        assert canon.canonicalize(d1) == canon.canonicalize(d2)

    def test_none_values(self):
        canon = Canonicalizer()
        d1 = {"key": None}
        d2 = {"key": None}
        assert canon.canonicalize(d1) == canon.canonicalize(d2)

    def test_boolean_values(self):
        canon = Canonicalizer()
        d1 = {"flag": True}
        d2 = {"flag": True}
        assert canon.canonicalize(d1) == canon.canonicalize(d2)
        assert canon.canonicalize(d1) != canon.canonicalize({"flag": False})

    def test_numeric_types(self):
        canon = Canonicalizer()
        d1 = {"count": 42}
        d2 = {"count": 42}
        assert canon.canonicalize(d1) == canon.canonicalize(d2)

    def test_empty_dict(self):
        canon = Canonicalizer()
        assert canon.canonicalize({}) == canon.canonicalize({})

    def test_returns_string(self):
        canon = Canonicalizer()
        result = canon.canonicalize({"key": "value"})
        assert isinstance(result, str)


class TestCanonicalHash:
    def test_same_content_same_hash(self):
        canon = Canonicalizer()
        d1 = {"b": 1, "a": 2}
        d2 = {"a": 2, "b": 1}
        assert canon.hash(d1) == canon.hash(d2)

    def test_different_content_different_hash(self):
        canon = Canonicalizer()
        assert canon.hash({"a": 1}) != canon.hash({"a": 2})

    def test_hash_is_string(self):
        canon = Canonicalizer()
        assert isinstance(canon.hash({"a": 1}), str)
