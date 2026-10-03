import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "qlib-demos"))

from download_to_qlib import write_features


class QlibExpressionsRunTest(unittest.TestCase):
    def test_bundled_provider_reads_all_default_instruments(self) -> None:
        import qlib
        from qlib.data import D

        provider_dir = ROOT / "qlib-demos/qlib-data"
        instruments = [
            "sh510050",
            "sh510300",
            "sh510500",
            "sz159915",
            "sh588000",
        ]
        qlib.init(provider_uri=str(provider_dir), region="cn")

        features = D.features(
            instruments,
            ["$close"],
            start_time="2021-01-04",
            end_time="2021-01-08",
        )

        self.assertEqual(
            set(instruments),
            set(features.index.get_level_values("instrument")),
        )
        self.assertFalse(features.empty)
        self.assertFalse(features["$close"].isna().any())

    def test_run_script_prints_rows_from_bundled_provider(self) -> None:
        result = subprocess.run(
            ["bash", str(ROOT / "qlib-demos/script/run_03.sh")],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )

        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("rolling_mom20_rank", result.stdout)
        self.assertNotIn("Empty DataFrame", result.stdout)

    def test_config_driven_workflow_runs_with_installed_pandas(self) -> None:
        result = subprocess.run(
            [
                "bash",
                str(ROOT / "qlib-demos/script/run_10.sh"),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )

        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn('"quantile_return_mean"', result.stdout)

    def test_model_training_baseline_produces_predictions(self) -> None:
        with tempfile.TemporaryDirectory() as working_directory:
            environment = os.environ.copy()
            environment["QLIB_EXP_URI"] = (Path(working_directory) / "mlruns").as_uri()
            result = subprocess.run(
                ["bash", str(ROOT / "qlib-demos/script/run_07.sh")],
                cwd=ROOT,
                env=environment,
                capture_output=True,
                text=True,
            )

        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("prediction rows:", result.stdout)

    def test_feature_binary_starts_with_calendar_index(self) -> None:
        calendar = pd.date_range("2024-01-01", periods=3, freq="D")
        frame = pd.DataFrame(
            {"close": np.array([10.0, 11.0], dtype=np.float32)},
            index=calendar[1:],
        )

        with tempfile.TemporaryDirectory() as directory:
            write_features(frame, "test", calendar, Path(directory))
            values = np.fromfile(
                Path(directory) / "features/test/close.day.bin", dtype="<f4"
            )

        np.testing.assert_array_equal(
            np.array([1.0, 10.0, 11.0], dtype=np.float32), values
        )


if __name__ == "__main__":
    unittest.main()
