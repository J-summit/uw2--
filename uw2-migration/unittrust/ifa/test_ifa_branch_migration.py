import unittest
from io import StringIO
from unittest.mock import patch

from ifa_branch_migration import build_export_payload, main


class IfaBranchMigrationTests(unittest.TestCase):
    def test_build_export_payload_maps_ifa_and_branch_records(self):
        payload = build_export_payload(
            ifas=[
                {
                    "ifa_code": " UOBKH ",
                    "ifa_name": "UOB KAY HIAN (M) SDN. BHD.",
                    "company_no": "194990-K",
                    "addr1": "Level 1",
                    "postcode": "50000",
                    "state": "KUL",
                    "country": "MYS",
                    "tel": "0312345678",
                    "email": "ops@example.com",
                    "logo_path": "/logo.png",
                    "website": "https://example.com",
                    "created_by": "SYSTEM",
                    "created_at": "2024-01-02T03:04:05.000",
                    "created_ip": "127.0.0.1",
                    "updated_by": None,
                    "updated_at": None,
                    "updated_ip": None,
                    "is_backoffice": 1,
                }
            ],
            branches=[
                {
                    "Code": "001",
                    "ifa_code": "UOBKH",
                    "Name": "UOB KAY HIAN-JB",
                    "OldName": "OLD JB",
                    "Addr1": "Branch Addr",
                    "PostCode": "81200",
                    "Territory": "JHR",
                    "Country": "MYS",
                    "Tel1": "071234567",
                    "Tel2": None,
                    "Fax": None,
                    "Email": "jb@example.com",
                    "Virtual": 0,
                    "VirCode": "   ",
                    "created_by": "SYSTEM",
                    "created_at": "2024-01-03T03:04:05.000",
                    "created_ip": "127.0.0.1",
                    "updated_by": None,
                    "updated_at": None,
                    "updated_ip": None,
                }
            ],
            batch_id="ifa_test",
        )

        self.assertEqual(payload["manifest"]["source_ifas"], 1)
        self.assertEqual(payload["manifest"]["valid_branches"], 1)
        self.assertEqual(payload["manifest"]["rejected_branches"], 0)

        self.assertEqual(
            payload["ifa_organizations"][0],
            {
                "code": "UOBKH",
                "name": "UOB KAY HIAN (M) SDN. BHD.",
                "type": "IFA",
                "company_no": "194990-K",
                "addr1": "Level 1",
                "addr2": None,
                "addr3": None,
                "addr4": None,
                "addr5": None,
                "postcode": "50000",
                "state": "KUL",
                "country": "MYS",
                "tel": "0312345678",
                "email": "ops@example.com",
                "logo_path": "/logo.png",
                "website": "https://example.com",
                "is_backoffice": True,
                "source": "LEGACY_MSTIFA",
                "source_id": "MstIFA:UOBKH",
                "created_by": "SYSTEM",
                "created_at": "2024-01-02T03:04:05.000",
                "created_ip": "127.0.0.1",
                "updated_by": "SYSTEM",
                "updated_at": "2024-01-02T03:04:05.000",
                "updated_ip": "127.0.0.1",
            },
        )
        self.assertEqual(payload["branch_organizations"][0]["parent_code"], "UOBKH")
        self.assertEqual(payload["branch_organizations"][0]["source_id"], "MstBranch:001")
        self.assertEqual(payload["base_branches"][0]["code"], "001")
        self.assertEqual(payload["base_branches"][0]["post_code"], "81200")
        self.assertFalse(payload["base_branches"][0]["virtual"])
        self.assertIsNone(payload["base_branches"][0]["vir_code"])

    def test_build_export_payload_rejects_branch_without_matching_ifa(self):
        payload = build_export_payload(
            ifas=[{"ifa_code": "UOBKH", "ifa_name": "UOB"}],
            branches=[{"Code": "999", "ifa_code": "MISSING", "Name": "Missing IFA"}],
            batch_id="ifa_test",
        )

        self.assertEqual(payload["manifest"]["valid_branches"], 0)
        self.assertEqual(payload["manifest"]["rejected_branches"], 1)
        self.assertEqual(payload["rejects"][0]["reason"], "ifa_not_found")
        self.assertEqual(payload["rejects"][0]["branch_code"], "999")

    def test_main_without_arguments_enters_interactive_mode(self):
        with patch("builtins.input", return_value="q"), patch("sys.stdout", new_callable=StringIO) as stdout:
            result = main([])

        self.assertEqual(result, 0)
        self.assertIn("Choose command", stdout.getvalue())

    def test_interactive_import_prompts_for_input_dir_and_runs_import(self):
        answers = iter(["3", r"C:\tmp\ifa_batch", "y"])
        with patch("builtins.input", side_effect=lambda _: next(answers)), patch(
            "ifa_branch_migration.import_command"
        ) as import_command, patch("sys.stdout", new_callable=StringIO):
            result = main([])

        self.assertEqual(result, 0)
        self.assertEqual(import_command.call_count, 1)
        self.assertEqual(import_command.call_args.args[0].command, "import")
        self.assertEqual(import_command.call_args.args[0].input_dir, r"C:\tmp\ifa_batch")


if __name__ == "__main__":
    unittest.main()
