"""Phase A: task-scoped code identity keeps caches valid across unrelated edits."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from research.contracts import (CODE_GROUPS, code_identity, same_code_identity,
                                task_code_groups)


class TaskCodeGroupsTests(unittest.TestCase):
    def test_every_mapped_task_uses_known_groups(self):
        for task in ("classical_ground_state", "spin_wave_spectrum",
                     "quantum_low_energy", "classical_monte_carlo",
                     "classical_finite_size", "fourier_exchange_spectrum",
                     "dipolar_ewald", "reduction_validation", "mechanism_test"):
            self.assertTrue(set(task_code_groups(task)).issubset(set(CODE_GROUPS)), task)

    def test_quantum_task_scope_excludes_lswt_and_cli(self):
        groups = task_code_groups("quantum_low_energy")
        self.assertNotIn("lswt", groups)
        self.assertNotIn("cli", groups)
        self.assertIn("three_dimensional", groups)

    def test_unmapped_task_falls_back_to_full_scope(self):
        self.assertEqual(tuple(task_code_groups("unknown_future_task")), CODE_GROUPS)

    def test_comparison_tasks_cover_all_groups(self):
        self.assertEqual(tuple(task_code_groups("reduction_validation")), CODE_GROUPS)
        self.assertEqual(tuple(task_code_groups("mechanism_test")), CODE_GROUPS)


class CodeIdentityTests(unittest.TestCase):
    def test_scoped_identity_records_groups(self):
        identity = code_identity(groups=("common", "research"))
        self.assertEqual(identity["groups"], ["common", "research"])
        self.assertEqual(set(identity["group_hashes"]), {"common", "research"})
        self.assertIn("runtime", identity)

    def test_full_identity_has_no_group_scope_for_legacy_shape(self):
        identity = code_identity()
        self.assertNotIn("groups", identity)
        self.assertEqual(set(identity["group_hashes"]), set(CODE_GROUPS))

    def test_scoped_identity_stable_across_calls(self):
        first = code_identity(groups=task_code_groups("quantum_low_energy"))
        second = code_identity(groups=task_code_groups("quantum_low_energy"))
        self.assertEqual(first, second)

    def test_different_scopes_differ(self):
        quantum = code_identity(groups=task_code_groups("quantum_low_energy"))
        lswt = code_identity(groups=task_code_groups("spin_wave_spectrum"))
        self.assertNotEqual(quantum["source_hash"], lswt["source_hash"])

    def test_unknown_group_rejected(self):
        with self.assertRaises(ValueError):
            code_identity(groups=("common", "does-not-exist"))

    def test_runtime_executable_is_canonical_absolute_path(self):
        import os
        from research.contracts import runtime_identity
        executable = runtime_identity()["executable"]
        self.assertTrue(os.path.isabs(executable), executable)
        # abspath, not realpath: a virtualenv's bin/python symlink must survive
        # so the worker keeps site-packages.
        self.assertEqual(executable, os.path.abspath(executable))


class SameCodeIdentityTests(unittest.TestCase):
    def test_scoped_record_matches_current_code(self):
        identity = code_identity(groups=("common",))
        self.assertTrue(same_code_identity(identity))

    def test_scoped_record_invalidates_when_scoped_file_changes(self):
        identity = code_identity(groups=("common",))
        fresh = {"groups": ["common"],
                 "group_hashes": {"common": "0" * 64},
                 "source_hash": "0" * 64,
                 "runtime": identity["runtime"]}
        self.assertFalse(same_code_identity(fresh))

    def test_runtime_change_invalidates(self):
        identity = code_identity(groups=("common",))
        tampered = {**identity, "runtime": {**identity["runtime"], "python": "0.0.0"}}
        self.assertFalse(same_code_identity(tampered))

    def test_legacy_full_record_compares_full_identity(self):
        self.assertTrue(same_code_identity(code_identity()))
        legacy = {**code_identity(), "source_hash": "f" * 64}
        self.assertFalse(same_code_identity(legacy))

    def test_malformed_records_rejected(self):
        self.assertFalse(same_code_identity(None))
        self.assertFalse(same_code_identity({}))
        self.assertFalse(same_code_identity({"source_hash": "x" * 64}))


if __name__ == "__main__":
    unittest.main()
