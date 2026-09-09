import sqlite3
import unittest
from src.utils.table_query import parse_table_params, query_paginated_table


class TestTableQueryUtils(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.db.row_factory = sqlite3.Row
        self.db.execute("CREATE TABLE mock_logs (id INTEGER PRIMARY KEY, status_code INT, created_at TEXT)")
        for i in range(1, 105):
            self.db.execute(
                "INSERT INTO mock_logs (id, status_code, created_at) VALUES (?, ?, ?)",
                (i, 200 if i % 2 == 0 else 500, f"2026-09-09 10:00:{i:02d}"),
            )
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_parse_table_params_defaults(self):
        params = parse_table_params({})
        self.assertEqual(params["page"], 1)
        self.assertEqual(params["page_size"], 50)
        self.assertEqual(params["sort_by"], "id")
        self.assertEqual(params["order"], "desc")

    def test_parse_table_params_custom_page_size(self):
        params = parse_table_params({"page": "2", "page_size": "100", "sort_by": "status_code", "order": "asc"})
        self.assertEqual(params["page"], 2)
        self.assertEqual(params["page_size"], 100)
        self.assertEqual(params["sort_by"], "status_code")
        self.assertEqual(params["order"], "asc")

    def test_query_paginated_table(self):
        allowed_sorts = {"id": "id", "status_code": "status_code", "created_at": "created_at"}
        result = query_paginated_table(
            db=self.db,
            base_from_sql="mock_logs",
            select_fields="*",
            allowed_sorts=allowed_sorts,
            default_sort="id",
            request_args={"page": "1", "page_size": "20", "sort_by": "id", "order": "desc"},
        )
        self.assertEqual(len(result["items"]), 20)
        self.assertEqual(result["pagination"]["total_count"], 104)
        self.assertEqual(result["pagination"]["total_pages"], 6)
        self.assertEqual(result["items"][0]["id"], 104)
        self.assertEqual(result["items"][-1]["id"], 85)

    def test_query_paginated_table_with_where(self):
        allowed_sorts = {"id": "id"}
        result = query_paginated_table(
            db=self.db,
            base_from_sql="mock_logs",
            select_fields="*",
            allowed_sorts=allowed_sorts,
            where_clauses=["status_code = ?"],
            where_params=[200],
            request_args={"page": "1", "page_size": "20"},
        )
        # Even numbers are 200: 104 / 2 = 52
        self.assertEqual(result["pagination"]["total_count"], 52)
        self.assertEqual(len(result["items"]), 20)
        self.assertTrue(all(row["status_code"] == 200 for row in result["items"]))

    def test_query_paginated_table_with_group_by_defensive(self):
        # Test when base_from_sql contains "GROUP BY" and where_clauses are supplied
        allowed_sorts = {"status_code": "status_code"}
        result = query_paginated_table(
            db=self.db,
            base_from_sql="mock_logs GROUP BY status_code",
            select_fields="status_code, COUNT(*) as cnt",
            allowed_sorts=allowed_sorts,
            default_sort="status_code",
            where_clauses=["status_code = ?"],
            where_params=[200],
            request_args={"page": "1", "page_size": "20"},
        )
        self.assertEqual(result["pagination"]["total_count"], 1)
        self.assertEqual(len(result["items"]), 1)
        self.assertEqual(result["items"][0]["status_code"], 200)
        self.assertEqual(result["items"][0]["cnt"], 52)


if __name__ == "__main__":
    unittest.main()
