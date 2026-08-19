import importlib.util
import unittest
from pathlib import Path
from unittest.mock import MagicMock


SCRIPT_PATH = Path(__file__).with_name("migrate_mst_fund_bond.py")


def load_migration_module():
    if not SCRIPT_PATH.exists():
        raise AssertionError(f"migration script is missing: {SCRIPT_PATH}")

    spec = importlib.util.spec_from_file_location("fund_bond_migration", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class MigrateFundBondTest(unittest.TestCase):
    def test_source_sql_selects_columns_in_target_order(self):
        migration = load_migration_module()

        self.assertEqual(
            "SELECT [fund_id], [fund_name], [fund_currency], [active_status], "
            "[created_by], [created_at], [created_ip], [updated_by], [updated_at], "
            "[updated_ip] FROM dbo.MstFundBond",
            migration.source_sql(),
        )

    def test_upsert_uses_legacy_fund_id_as_the_conflict_key(self):
        migration = load_migration_module()

        sql = migration.upsert_sql(2)

        self.assertEqual(20, sql.count("%s"))
        self.assertIn("INSERT INTO fund_upstream.mst_fund_bond", sql)
        self.assertIn("ON CONFLICT (fund_id) DO UPDATE SET", sql)
        self.assertIn("fund_name = EXCLUDED.fund_name", sql)
        self.assertNotIn("fund_id = EXCLUDED.fund_id", sql)

    def test_transfer_streams_batches_and_commits_each_batch(self):
        migration = load_migration_module()
        source_cursor = MagicMock()
        source_cursor.fetchmany.side_effect = [
            [("BOND001", "Bond One", "MYR", "Y")],
            [("BOND002", "Bond Two", "USD", "N")],
            [],
        ]
        source_connection = MagicMock()
        source_connection.cursor.return_value = source_cursor
        target_cursor = MagicMock()
        target_connection = MagicMock()
        target_connection.cursor.return_value = target_cursor

        migrated = migration.transfer(
            source_connection, target_connection, batch_size=1
        )

        self.assertEqual(2, migrated)
        self.assertEqual(3, source_cursor.fetchmany.call_count)
        self.assertEqual(2, target_cursor.execute.call_count)
        self.assertEqual(2, target_connection.commit.call_count)
        self.assertEqual(
            ["BOND001", "Bond One", "MYR", "Y"],
            target_cursor.execute.call_args_list[0].args[1],
        )

    def test_verify_target_table_rejects_missing_columns(self):
        migration = load_migration_module()
        cursor = MagicMock()
        cursor.fetchone.return_value = ("fund_upstream.mst_fund_bond",)
        cursor.fetchall.return_value = [("fund_id",)]
        connection = MagicMock()
        connection.cursor.return_value = cursor

        with self.assertRaisesRegex(RuntimeError, "missing columns: fund_name"):
            migration.verify_target_table(connection)


if __name__ == "__main__":
    unittest.main()
