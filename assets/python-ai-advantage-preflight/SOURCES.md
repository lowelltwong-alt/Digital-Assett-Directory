# Sources and evidence posture

## Confirmed sources

- Python lexical analysis docs: https://docs.python.org/3/reference/lexical_analysis.html
- Python built-in functions docs: https://docs.python.org/3/library/functions.html
- Python expression/operator docs: https://docs.python.org/3/reference/expressions.html
- Python data model / special methods docs: https://docs.python.org/3/reference/datamodel.html
- Python compound statements / match / with / except* docs: https://docs.python.org/3/reference/compound_stmts.html
- Python typing docs: https://docs.python.org/3/library/typing.html
- Python dataclasses docs: https://docs.python.org/3/library/dataclasses.html
- Python enum docs: https://docs.python.org/3/library/enum.html
- Python contextlib docs: https://docs.python.org/3/library/contextlib.html
- Python functools docs: https://docs.python.org/3/library/functools.html
- Python pathlib docs: https://docs.python.org/3/library/pathlib.html
- Python collections docs: https://docs.python.org/3/library/collections.html
- Python itertools docs: https://docs.python.org/3/library/itertools.html

## Inference note

The underused-pattern ranking is a practical heuristic, not a measured GitHub-wide frequency analysis. Use it as a teaching and preflight layer, then verify with tests, type checks, and repo-local conventions.

## AI-code-corpus note

Public source-code corpora are important in training and evaluating code models, but no current proprietary AI coding model should be assumed to be trained only on GitHub or to reflect a transparent frequency distribution. The reliable principle is weaker and safer: common public code patterns can influence model defaults, so repo-local instructions should explicitly teach safer, more structured patterns.
