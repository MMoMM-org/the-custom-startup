# conftest.py — pytest collection configuration
#
# These template test files use a bespoke standalone-runner pattern with
# test_*(arg) positional-arg functions. Pytest tries to inject fixtures for
# those args and produces collection errors. Exclude them here; run directly
# with `python3 <file>` instead.

collect_ignore = [
    "plugins/tcs-helper/skills/rule-enforcer/templates/test_ci_template.py",
    "plugins/tcs-helper/templates/githooks/test_pre_push_template.py",
]

# tests/fixtures/patterns-detection/*/repo/ holds synthetic repository trees
# (spec-020 T2.1) that deliberately contain files named test_*.py / *.bats so
# the detector has real evidence to find. Pytest's own default discovery
# would otherwise collect those as real tests (one fixture's `tests/test_app.py`
# silently added a passing test to this repo's own suite before this was
# added) -- excluded wholesale, same as the two template files above.
collect_ignore_glob = [
    "tests/fixtures/patterns-detection/*/repo/**",
]
