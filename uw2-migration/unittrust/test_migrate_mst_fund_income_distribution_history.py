import importlib.util
import unittest
from pathlib import Path
from unittest.mock import MagicMock


SCRIPT_PATH = Path(__file__).with_name("migrate_mst_fund_income_distribution_history.py")


def load_migration_module():
    if not SCRIPT_PATH.exists():
        raise AssertionError(f"migration script is missing: {SCRIPT_PATH}")

    spec = importlib.util.spec_from_file_location("income_distribution_migration", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class MigrateFundIncomeDistributionHistoryTest(unittest.TestCase):
    def test_source_sql_selects_the_legacy_columns_in_target_order(self):
        migration = load_migration_module()

        self.assertEqual(
            "SELECT [fund_id], [distribution_type], [excluding_date], "
            "[reinvestment_date], [gross_income_dis_rate], [net_income_dis_rate], "
            "[created_by], [created_at], [created_ip], [updated_by], [updated_at], "
            "[updated_ip] FROM dbo.MstFundIncomeDistributionHistory",
            migration.source_sql(),
        )

    def test_upsert_sql_replays_the_source_composite_key(self):
        migration = load_migration_module()

        sql = migration.upsert_sql(2)

        self.assertEqual(24, sql.count("%s"))
        self.assertIn(
            "ON CONFLICT (fund_id, distribution_type, excluding_date) DO UPDATE SET",
            sql,
        )
        self.assertIn("reinvestment_date = EXCLUDED.reinvestment_date", sql)
        self.assertNotIn("fund_id = EXCLUDED.fund_id", sql)
        self.assertNotIn("distribution_type = EXCLUDED.distribution_type", sql)
        self.assertNotIn("excluding_date = EXCLUDED.excluding_date", sql)

    def test_transfer_streams_batches_and_commits_each_successful_batch(self):
        migration = load_migration_module()
        source_cursor = MagicMock()
        source_cursor.fetchmany.side_effect = [
            [("F001", "CASH", "2025-01-01")],
            [("F002", "REINVEST", "2025-02-01")],
            [],
        ]
        source_connection = MagicMock()
        source_connection.cursor.return_value = source_cursor
        target_cursor = MagicMock()
        target_connection = MagicMock()
        target_connection.cursor.return_value = target_cursor

        migrated = migration.transfer(source_connection, target_connection, batch_size=1)

        self.assertEqual(2, migrated)
        self.assertEqual(1, source_cursor.execute.call_count)
        self.assertEqual(3, source_cursor.fetchmany.call_count)
        self.assertEqual(2, target_cursor.execute.call_count)
        self.assertEqual(2, target_connection.commit.call_count)
        self.assertEqual(
            ["F001", "CASH", "2025-01-01"],
            target_cursor.execute.call_args_list[0].args[1],
        )

    def test_verify_target_table_rejects_an_absent_table_before_migration(self):
        migration = load_migration_module()
        connection = MagicMock()
        cursor = MagicMock()
        cursor.fetchone.return_value = None
        connection.cursor.return_value = cursor

        with self.assertRaisesRegex(RuntimeError, "V1.51"):
            migration.verify_target_table(connection)


if __name__ == "__main__":
    unittest.main()
