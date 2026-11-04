import unittest
from datetime import date

from tasklog.dates import days_between, is_overdue, parse_due
from tasklog.paging import page_count, paginate
from tasklog.store import TaskStore


class StoreTest(unittest.TestCase):
    def setUp(self):
        self.store = TaskStore()

    def tearDown(self):
        self.store.close()

    def test_add_and_get(self):
        tid = self.store.add("write report", date(2026, 1, 5))
        self.assertEqual(self.store.get(tid).title, "write report")

    def test_get_missing_is_none(self):
        self.assertIsNone(self.store.get(99))

    def test_mark_done(self):
        tid = self.store.add("x")
        self.assertTrue(self.store.mark_done(tid))
        self.assertTrue(self.store.get(tid).done)


class HelpersTest(unittest.TestCase):
    def test_paging(self):
        self.assertEqual(page_count(41, 20), 3)
        self.assertEqual(paginate(list(range(5)), 2, 2), [2, 3])

    def test_dates(self):
        self.assertEqual(parse_due("2026-02-01"), date(2026, 2, 1))
        self.assertEqual(days_between(date(2026, 1, 1), date(2026, 1, 3)), 2)

    def test_overdue(self):
        store = TaskStore()
        tid = store.add("y", date(2026, 1, 1))
        self.assertTrue(is_overdue(store.get(tid), date(2026, 1, 2)))
        store.close()


if __name__ == "__main__":
    unittest.main()
