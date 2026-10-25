---
description: A clean diff whose one defect removes a parameter from a published function; the breaking change alone must force REQUEST CHANGES and lead the report.
tags: [review, breaking-change]
runs: 3
max_turns: 40
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Agent, TodoWrite]
expected_outcome: Verdict REQUEST CHANGES, with the removed `currency` parameter reported as a breaking change above the severity tables, naming PyPI consumers and a migration.
---

/tcs-workflow:review the pull request below

There is no git checkout here: everything to review is in this message. Use Standard mode.

```
Repository: tinyprice, a pricing library published on PyPI (`pip install tinyprice`).
README: "`tinyprice.total(items, currency)` is the public API; other modules are internal."
Pull request: "Simplify total(): every caller we know of uses EUR."

diff --git a/tinyprice/__init__.py b/tinyprice/__init__.py
--- a/tinyprice/__init__.py
+++ b/tinyprice/__init__.py
@@ -1,16 +1,13 @@
 from decimal import Decimal
 
-from ._rates import convert
-
 __all__ = ["total"]
 
 
-def total(items, currency):
-    """Sum item prices (in EUR) and return the total in `currency`."""
+def total(items):
+    """Sum item prices and return the total in EUR."""
     subtotal = sum((Decimal(item["price"]) for item in items), Decimal("0"))
-    if currency == "EUR":
-        return subtotal
-    return convert(subtotal, "EUR", currency)
+    return subtotal
 
diff --git a/tests/test_total.py b/tests/test_total.py
--- a/tests/test_total.py
+++ b/tests/test_total.py
@@ -1,13 +1,9 @@
 from decimal import Decimal
 
 from tinyprice import total
 
 
 def test_sums_prices():
-    assert total([{"price": "1.50"}, {"price": "2.25"}], "EUR") == Decimal("3.75")
-
-
-def test_converts_currency(monkeypatch):
-    monkeypatch.setattr("tinyprice._rates.RATES", {("EUR", "USD"): Decimal("2")})
-    assert total([{"price": "1.00"}], "USD") == Decimal("2.00")
+    assert total([{"price": "1.50"}, {"price": "2.25"}]) == Decimal("3.75")
```
