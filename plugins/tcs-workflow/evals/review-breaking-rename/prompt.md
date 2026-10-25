---
description: A behaviour-preserving rename of a published function. Nothing is wrong with the code; the breaking change alone must force REQUEST CHANGES.
tags: [review, breaking-change]
runs: 3
max_turns: 40
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Agent, TodoWrite]
expected_outcome: Verdict REQUEST CHANGES although no finding is a defect, with the rename reported as breaking above the severity tables.
---

/tcs-workflow:review the pull request below

There is no git checkout here: everything to review is in this message. Use Standard mode.

```
Repository: tinyprice, a pricing library published on PyPI (`pip install tinyprice`).
README (updated in this PR): "`tinyprice.order_total(items)` is the public API; other modules are internal."
Pull request: "Rename total() to order_total() for clarity."

diff --git a/tinyprice/__init__.py b/tinyprice/__init__.py
--- a/tinyprice/__init__.py
+++ b/tinyprice/__init__.py
@@ -1,9 +1,9 @@
 from decimal import Decimal
 
-__all__ = ["total"]
+__all__ = ["order_total"]
 
 
-def total(items):
+def order_total(items):
     """Sum item prices and return the total as a Decimal."""
     return sum((Decimal(item["price"]) for item in items), Decimal("0"))
 
diff --git a/README.md b/README.md
--- a/README.md
+++ b/README.md
@@ -3,3 +3,3 @@
-`tinyprice.total(items)` is the public API; other modules are internal.
+`tinyprice.order_total(items)` is the public API; other modules are internal.
diff --git a/tests/test_total.py b/tests/test_total.py
--- a/tests/test_total.py
+++ b/tests/test_total.py
@@ -1,7 +1,7 @@
 from decimal import Decimal
 
-from tinyprice import total
+from tinyprice import order_total
 
 
 def test_sums_prices():
-    assert total([{"price": "1.50"}, {"price": "2.25"}]) == Decimal("3.75")
+    assert order_total([{"price": "1.50"}, {"price": "2.25"}]) == Decimal("3.75")
```
