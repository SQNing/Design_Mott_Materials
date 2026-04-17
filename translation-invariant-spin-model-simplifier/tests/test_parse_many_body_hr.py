import sys
import unittest
from pathlib import Path

import numpy as np

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from input.parse_many_body_hr import parse_many_body_hr_file, parse_many_body_hr_text


class ParseManyBodyHRTests(unittest.TestCase):
    def test_parse_many_body_hr_text_reads_header_and_one_block(self):
        hr_text = """wannier_hr.dat created by gutz.py
          2
          1
    1
    0    0    0    1    1                  1.500000000000000                  0.000000000000000
    0    0    0    2    1                  0.000000000000000                  1.000000000000000
    0    0    0    1    2                  0.000000000000000                 -1.000000000000000
    0    0    0    2    2                 -0.500000000000000                  0.000000000000000
"""

        parsed = parse_many_body_hr_text(hr_text)

        self.assertEqual(parsed["comment"], "wannier_hr.dat created by gutz.py")
        self.assertEqual(parsed["num_wann"], 2)
        self.assertEqual(parsed["nrpts"], 1)
        self.assertEqual(parsed["degeneracies"], [1])
        self.assertEqual(parsed["R_vectors"], [(0, 0, 0)])

        block = parsed["blocks_by_R"][(0, 0, 0)]
        self.assertEqual(block.shape, (2, 2))
        self.assertAlmostEqual(block[0, 0].real, 1.5, places=12)
        self.assertAlmostEqual(block[1, 0].imag, 1.0, places=12)
        self.assertAlmostEqual(block[0, 1].imag, -1.0, places=12)
        self.assertAlmostEqual(block[1, 1].real, -0.5, places=12)

    def test_parse_many_body_hr_file_reads_current_example_header(self):
        hr_path = Path(
            "/data/work/zhli/run/codex/spin-effective-Hamiltonian/U2.0J0.0-not-mix/VR_hr.dat"
        )

        parsed = parse_many_body_hr_file(hr_path)

        self.assertEqual(parsed["comment"], "wannier_hr.dat created by gutz.py")
        self.assertEqual(parsed["num_wann"], 16)
        self.assertEqual(parsed["nrpts"], 30)
        self.assertEqual(parsed["degeneracies"], [1] * 30)
        self.assertEqual(len(parsed["R_vectors"]), 30)

        first_R = parsed["R_vectors"][0]
        self.assertEqual(first_R, (-2, 0, 2))
        block = parsed["blocks_by_R"][first_R]
        self.assertEqual(block.shape, (16, 16))
        self.assertAlmostEqual(block[0, 0].real, -0.000075255152136, places=12)
        self.assertAlmostEqual(block[1, 0].imag, -0.000000000000403, places=15)
        self.assertTrue(np.iscomplexobj(block))


if __name__ == "__main__":
    unittest.main()
