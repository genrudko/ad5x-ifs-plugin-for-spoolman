#!/usr/bin/env python3
import ast
from pathlib import Path
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "plugin" / "ifs_spoolman.py"
WANTED = {
    "normalize_spool_id",
    "empty_assignment_map",
    "normalize_assignment_map",
    "extract_lane_assignments",
    "lane_record_with_assignment",
    "plan_lane_assignment_sync",
}

tree = ast.parse(SOURCE.read_text(encoding="utf-8"), filename=str(SOURCE))
nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in WANTED]
module = ast.Module(body=nodes, type_ignores=[])
ast.fix_missing_locations(module)
ns = {"SLOT_COUNT": 4}
exec(compile(module, str(SOURCE), "exec"), ns)

normalize_assignment_map = ns["normalize_assignment_map"]
extract_lane_assignments = ns["extract_lane_assignments"]
lane_record_with_assignment = ns["lane_record_with_assignment"]
plan = ns["plan_lane_assignment_sync"]


def amap(*values):
    return {str(index + 1): value for index, value in enumerate(values)}


def present(*values):
    return {str(index + 1): value for index, value in enumerate(values)}


class LaneDataSyncTests(unittest.TestCase):
    def test_first_start_remote_positive_wins(self):
        target, writes, sources = plan(
            amap(11, None, None, None),
            amap(22, None, None, None),
            present(True, False, False, False),
            None,
        )
        self.assertEqual(target["1"], 22)
        self.assertEqual(writes, {})
        self.assertEqual(sources["1"], "lane_data")

    def test_first_start_local_seeds_missing_lane(self):
        target, writes, _ = plan(
            amap(11, 22, None, None),
            amap(None, None, None, None),
            present(False, True, False, False),
            None,
        )
        self.assertEqual(target, amap(11, 22, None, None))
        self.assertEqual(writes, {"1": 11, "2": 22})

    def test_established_helix_change_is_imported(self):
        target, writes, sources = plan(
            amap(11, 22, None, None),
            amap(11, 33, None, None),
            present(True, True, False, False),
            amap(11, 22, None, None),
        )
        self.assertEqual(target["2"], 33)
        self.assertEqual(writes, {})
        self.assertEqual(sources["2"], "lane_data")

    def test_established_helix_clear_is_imported_when_lane_exists(self):
        target, writes, _ = plan(
            amap(11, 22, None, None),
            amap(11, None, None, None),
            present(True, True, False, False),
            amap(11, 22, None, None),
        )
        self.assertIsNone(target["2"])
        self.assertEqual(writes, {})

    def test_established_plugin_change_is_exported(self):
        target, writes, sources = plan(
            amap(11, 44, None, None),
            amap(11, 22, None, None),
            present(True, True, False, False),
            amap(11, 22, None, None),
        )
        self.assertEqual(target["2"], 44)
        self.assertEqual(writes, {"2": 44})
        self.assertEqual(sources["2"], "plugin")

    def test_simultaneous_conflict_prefers_shared_lane_data(self):
        target, writes, sources = plan(
            amap(11, 44, None, None),
            amap(11, 55, None, None),
            present(True, True, False, False),
            amap(11, 22, None, None),
        )
        self.assertEqual(target["2"], 55)
        self.assertEqual(writes, {})
        self.assertEqual(sources["2"], "lane_data_conflict")

    def test_missing_remote_record_is_not_interpreted_as_clear(self):
        target, writes, _ = plan(
            amap(11, 22, None, None),
            amap(None, None, None, None),
            present(False, False, False, False),
            amap(11, 22, None, None),
        )
        self.assertEqual(target, amap(11, 22, None, None))
        self.assertEqual(writes, {})

    def test_duplicate_result_is_rejected(self):
        with self.assertRaises(ValueError):
            plan(
                amap(11, 22, None, None),
                amap(22, None, None, None),
                present(True, False, False, False),
                None,
            )

    def test_lane_record_update_preserves_helix_metadata(self):
        doc = {
            "lane2": {
                "lane": "1",
                "spool_id": 22,
                "material": "PETG",
                "vendor_name": "Geek Fil/lament",
                "helix_locked_material": True,
            }
        }
        key, record, changed = lane_record_with_assignment(doc, 2, 44)
        self.assertTrue(changed)
        self.assertEqual(key, "lane2")
        self.assertEqual(record["spool_id"], 44)
        self.assertEqual(record["material"], "PETG")
        self.assertEqual(record["vendor_name"], "Geek Fil/lament")
        self.assertTrue(record["helix_locked_material"])

        _, cleared, changed = lane_record_with_assignment({key: record}, 2, None)
        self.assertTrue(changed)
        self.assertNotIn("spool_id", cleared)
        self.assertEqual(cleared["material"], "PETG")

    def test_extract_uses_ad5x_lane_style_and_inner_lane_guard(self):
        values, seen = extract_lane_assignments(
            {
                "lane1": {"lane": "0", "spool_id": 11},
                "lane2": {"lane": "99", "spool_id": 22},
                "T2": {"lane": "2", "spool_id": 33},
                "lane4": {"lane": "3", "spool_id": 44},
            }
        )
        self.assertEqual(values, amap(11, None, None, 44))
        self.assertEqual(seen, present(True, False, False, True))


if __name__ == "__main__":
    unittest.main()
