# Session Context

**Session ID:** f1492798-4a44-4e63-b5ca-b7d30d1ada3f

**Commit Message:** Fix #2 — Orphan step check doesn't handle conditional step branching

## Prompt

fix #2 — Orphan step check doesn't handle conditional step branching

## Summary

247/247 passing. Fixed: conditional steps (nsn == -2) now treat all higher-numbered steps as reachable branch targets, while orphans *before* a conditional are still caught. Want me to commit?

## Key Actions

- - **Edit**: /Users/air/Dropbox/air/projects/maker/src/maker/validator/deterministic.py
- - **Edit**: /Users/air/Dropbox/air/projects/maker/tests/test_validator/test_deterministic.py
- - **Bash**: Run deterministic validator tests
- - **Bash**: Full test suite
