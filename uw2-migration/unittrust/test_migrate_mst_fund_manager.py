import importlib.util
import unittest
from pathlib import Path
from unittest.mock import MagicMock


SCRIPT_PATH = Path(__file__).with_name("migrate_mst_fund_manager.py")


def load_migration_module():
    if not SCRIPT_PATH.exists():
        raise AssertionError(f"migration script is missing: {SCRIPT_PATH}")

    spec = importlib.util.spec_from_file_location("fund_manager_migration", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class MigrateFundManagerTest(unittest.TestCase):
    def test_source_sql_preserves_the_mssql_manager_and_relation_columns(self):
        migration = load_migration_module()

        self.assertEqual(
            "SELECT [datafeed_manager_id], [fund_manager_id], [fund_manager_name], "
            "[fund_manager_biography], [created_by], [created_at], [created_ip], "
            "[updated_by], [updated_at], [updated_ip] FROM dbo.MstFundManager",
            migration.source_sql(migration.MANAGER_SOURCE_TABLE, migration.MANAGER_COLUMNS),
        )
        self.assertEqual(
            "SELECT [fund_id], [fund_manager_id], [fund_manager_start_date], "
            "[fund_manager_tenure], [created_by], [created_at], [created_ip], "
            "[updated_by], [updated_at], [updated_ip] FROM dbo.MstFundManagerDetails",
            migration.source_sql(migration.DETAILS_SOURCE_TABLE, migration.DETAILS_COLUMNS),
        )

    def test_manager_upsert_keeps_the_legacy_manager_id_as_the_key(self):
        migration = load_migration_module()

        sql = migration.manager_upsert_sql(2)

        self.assertEqual(20, sql.count("%s"))
        self.assertIn(
            "ON CONFLICT (fund_manager_id) DO UPDATE SET",
            sql,
        )
        self.assertIn("fund_manager_biography = EXCLUDED.fund_manager_biography", sql)
        self.assertNotIn("fund_manager_id = EXCLUDED.fund_manager_id", sql)

    def test_details_refresh_replaces_the_current_snapshot_in_one_transaction(self):
        migration = load_migration_module()
        rows = [
            (
                "FN00000191",
                "FM00000243",
                "2018-08-01",
                7.67,
                "AUTOSP",
                "2026-08-05",
                "127.0.0.1",
                None,
                None,
                None,
            )
        ]
        source_connection = MagicMock()
        source_cursor = MagicMock()
        source_cursor.fetchall.return_value = rows
        source_connection.cursor.return_value = source_cursor
        target_connection = MagicMock()
        target_cursor = MagicMock()
        target_connection.cursor.return_value = target_cursor

        migrated = migration.refresh_details(source_connection, target_connection, batch_size=500)

        self.assertEqual(1, migrated)
        self.assertEqual(1, target_connection.commit.call_count)
        self.assertEqual(
            "DELETE FROM fund_upstream.mst_fund_manager_details",
            target_cursor.execute.call_args_list[0].args[0],
        )
        self.assertIn(
            "INSERT INTO fund_upstream.mst_fund_manager_details",
            target_cursor.execute.call_args_list[1].args[0],
        )
        self.assertEqual(list(rows[0]), target_cursor.execute.call_args_list[1].args[1])


if __name__ == "__main__":
    unittest.main()
