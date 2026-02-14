import json
import hashlib


class Canonicalizer:
    def canonicalize(self, data: dict) -> str:
        """Convert dict to canonical JSON string with sorted keys."""
        normalized = self._sort_keys_recursive(data)
        return json.dumps(normalized, sort_keys=True, ensure_ascii=True, separators=(",", ":"))

    def hash(self, data: dict) -> str:
        """Return a hash of the canonical representation."""
        canonical = self.canonicalize(data)
        return hashlib.sha256(canonical.encode()).hexdigest()[:16]

    def _sort_keys_recursive(self, obj):
        """Recursively sort dict keys. Lists maintain order but dicts inside them are sorted."""
        if isinstance(obj, dict):
            return {k: self._sort_keys_recursive(v) for k, v in sorted(obj.items())}
        elif isinstance(obj, list):
            return [self._sort_keys_recursive(item) for item in obj]
        return obj
