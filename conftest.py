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
