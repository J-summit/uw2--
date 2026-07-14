import datetime as dt
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock

import migrate_eod_tables as migration


class MigrateEodTablesTest(unittest.TestCase):
    def test_default_start_date_is_2025_01_01(self):
        args = migration.parse_args([])

        self.assertEqual(dt.date(2025, 1, 1), args.from_date)
        self.assertIsNone(args.to_date)

    def test_default_config_file_is_unittrust_db_ini(self):
        expected = Path(migration.__file__).resolve().parent.parent / "db.ini"

        self.assertEqual(expected, Path(migration.DEFAULT_CONFIG_FILE))

    def test_source_sql_aliases_legacy_bfe_columns(self):
        sql = migration._source_sql(migration.HOLDING_EOD, None)

        self.assertIn("[BFECode] AS [bfe_code]", sql)
        self.assertIn("[BFESubCode] AS [bfe_sub_code]", sql)
        self.assertNotIn("ORDER BY", sql)

    def test_transfer_table_streams_batches_and_commits_each_batch(self):
        source_cursor = MagicMock()
        source_cursor.description = [("holding_no",), ("holding_date",), ("entitled_unit",)]
        source_cursor.fetchmany.side_effect = [
            [("H1", dt.datetime(2025, 1, 31), Decimal("10.00"))],
            [("H2", dt.datetime(2025, 2, 28), Decimal("20.00"))],
            [],
        ]
        source_connection = MagicMock()
        source_connection.cursor.return_value = source_cursor
        target_cursor = MagicMock()
        target_connection = MagicMock()
        target_connection.cursor.return_value = target_cursor
        table = migration.TableSpec(
            source_table="dbo.TrnClientHoldingEOD",
            target_table="eod_service.trn_client_holding_eod",
            date_column="holding_date",
            columns=("holding_no", "holding_date", "entitled_unit"),
            key_columns=("holding_no", "holding_date"),
        )

        migrated = migration.transfer_table(
            source_connection,
            target_connection,
            table,
            dt.date(2025, 1, 1),
            None,
            batch_size=1,
        )

        self.assertEqual(2, migrated)
        self.assertEqual(
            [dt.datetime(2025, 1, 1)],
            source_cursor.execute.call_args.args[1],
        )
        self.assertEqual(3, source_cursor.fetchmany.call_count)
        self.assertEqual(2, target_cursor.execute.call_count)
        self.assertEqual(2, target_connection.commit.call_count)
        first_sql = target_cursor.execute.call_args_list[0].args[0]
        self.assertIn("ON CONFLICT (holding_no, holding_date) DO UPDATE SET", first_sql)
        self.assertIn("entitled_unit = EXCLUDED.entitled_unit", first_sql)


if __name__ == "__main__":
    unittest.main()
