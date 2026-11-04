# Experiment fixtures are target material, not repo tests: several fail on
# purpose (e.g. T4 needs LEDGERLITE_HOME). Keep the repo's pytest run out.
collect_ignore_glob = ["*"]
