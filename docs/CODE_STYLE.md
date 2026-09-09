# Code style and comment conventions

These rules govern every Python and TypeScript file in this repository.
They exist so that a reader can trust each comment: if a comment survives
review, it states something the code cannot say on its own.

## Language

Comments and docstrings are written in English. Italian appears only in
user-facing strings and in LLM prompt bodies, where the generation target
is Italian text.

## Docstrings (PEP 257)

- Every public module, class, and function starts with a one-line
  imperative summary ("Compute...", "Fetch...", not "This function
  computes...").
- `Args` / `Returns` / `Raises` sections appear only when the signature
  leaves a real question open: non-obvious types, side effects, units,
  or normalization scales. A three-line wrapper does not get a five-line
  docstring.
- A docstring never restates the function name and never describes an
  implementation the code no longer has. When behavior changes, the
  docstring changes in the same commit.

## Comments

A comment must state a constraint the code cannot express:

- empirical thresholds, with their provenance and date
  (`# floor 0.78 calibrated on the eval set, 2026-08, see
  build/calibrate_relevance_gate.py`);
- invariants (`# chunk.text is an exact substring of speech.text: a
  build-time guarantee, checked in validate_db check 8`);
- external-system quirks (`# s.date is a Neo4j Date: cast string bounds
  with date(), string-vs-Date comparison silently matches nothing`).

The following never pass review:

- comments that paraphrase the next line (`# Loop through results`);
- section labels over short blocks and decorative separator lines;
- changelog comments (`# Fix 4`, `# Updated`, `# NEW:`) — history lives
  in git;
- comments addressed to a reviewer instead of the next reader
  (`# CORRECT:`, `# This approach is right because...`);
- ALL-CAPS emphasis (`CRITICAL`, `IMPORTANT`) and emoji;
- commented-out code and `if __name__ == "__main__"` test blocks inside
  `backend/app/` modules;
- `TODO` without an issue reference.

## Dead code

Unused imports, unreferenced functions, and parameters never read in the
function body are removed, not kept "just in case". `ruff check` (rules
F401, F841) is the arbiter for the mechanical cases.

## Empirical values

Every magic number that came from an experiment carries its provenance.
If the calibration script or the observation date is unknown, say so in
the comment rather than presenting the value as self-evident.
