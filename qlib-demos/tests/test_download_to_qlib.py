import argparse
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "qlib-demos"))

import download_to_qlib
import qlib_demo_common


class BundledMultiEtfProviderTest(unittest.TestCase):
    provider_dir = ROOT / "qlib-demos/qlib-data"

    @property
    def expected_symbols(self) -> list[str]:
        return sorted(
            spec.qlib_symbol
            for spec in download_to_qlib.DEFAULT_INSTRUMENTS
        )

    def read_metadata(self) -> list[tuple[str, str, str]]:
        return [
            tuple(line.split("\t"))
            for line in (
                self.provider_dir / "instruments/all.txt"
            ).read_text().splitlines()
        ]

    def test_bundled_provider_contains_exactly_default_instruments(self) -> None:
        metadata_symbols = sorted(row[0] for row in self.read_metadata())
        feature_symbols = sorted(
            path.name
            for path in (self.provider_dir / "features").iterdir()
            if path.is_dir()
        )

        self.assertEqual(self.expected_symbols, metadata_symbols)
        self.assertEqual(self.expected_symbols, feature_symbols)

    def test_bundled_provider_starts_at_earliest_etf_listing(self) -> None:
        metadata = {
            symbol: (start, end)
            for symbol, start, end in self.read_metadata()
        }
        calendar = (
            self.provider_dir / "calendars/day.txt"
        ).read_text().splitlines()

        self.assertEqual("2005-02-23", metadata["sh510050"][0])
        self.assertEqual("2005-02-23", calendar[0])

    def test_bundled_provider_files_and_binary_contract_are_valid(self) -> None:
        calendar_path = self.provider_dir / "calendars/day.txt"
        calendar_lines = calendar_path.read_text().splitlines()
        calendar = pd.DatetimeIndex(pd.to_datetime(calendar_lines))
        self.assertTrue(calendar.is_monotonic_increasing)
        self.assertFalse(calendar.has_duplicates)

        required_feature_names = {
            f"{field}.day.bin"
            for field in download_to_qlib.REQUIRED_FIELDS
        }
        optional_feature_names = {
            f"{field}.day.bin"
            for field in download_to_qlib.OPTIONAL_FIELDS
        }
        reconstructed_frames: dict[str, pd.DataFrame] = {}
        for symbol, start_text, end_text in self.read_metadata():
            instrument_dir = self.provider_dir / "features" / symbol
            feature_names = {
                path.name for path in instrument_dir.iterdir()
            }
            self.assertEqual(
                {
                    f"{field}.day.bin"
                    for field in download_to_qlib.FEATURES
                },
                feature_names,
                (symbol, feature_names),
            )
            self.assertTrue(
                required_feature_names.issubset(feature_names),
                (symbol, feature_names),
            )
            self.assertFalse(
                feature_names - required_feature_names - optional_feature_names,
                (symbol, feature_names),
            )

            start = pd.Timestamp(start_text)
            end = pd.Timestamp(end_text)
            start_pos = int(calendar.searchsorted(start))
            end_pos = int(calendar.searchsorted(end))
            self.assertEqual(start, calendar[start_pos])
            self.assertEqual(end, calendar[end_pos])
            calendar_slice = calendar[start_pos : end_pos + 1]

            columns: dict[str, np.ndarray] = {}
            for field in download_to_qlib.FEATURES:
                feature_path = instrument_dir / f"{field}.day.bin"
                if not feature_path.is_file():
                    continue
                values = np.fromfile(feature_path, dtype="<f4")
                self.assertEqual(float(start_pos), values[0])
                self.assertEqual(len(calendar_slice) + 1, len(values))
                columns[field] = values[1:]
            reconstructed_frames[symbol] = pd.DataFrame(
                columns, index=calendar_slice
            )

        download_to_qlib.validate_provider(
            self.provider_dir, reconstructed_frames
        )

    def test_bundled_provider_satisfies_market_data_numeric_contract(self) -> None:
        calendar = pd.DatetimeIndex(
            pd.to_datetime(
                (
                    self.provider_dir / "calendars/day.txt"
                ).read_text().splitlines()
            )
        )
        specs = {
            spec.qlib_symbol: spec
            for spec in download_to_qlib.DEFAULT_INSTRUMENTS
        }

        for symbol, start_text, end_text in self.read_metadata():
            start_pos = int(calendar.searchsorted(pd.Timestamp(start_text)))
            end_pos = int(calendar.searchsorted(pd.Timestamp(end_text)))
            calendar_slice = calendar[start_pos : end_pos + 1]
            columns = {}
            for field in download_to_qlib.FEATURES:
                values = np.fromfile(
                    self.provider_dir
                    / "features"
                    / symbol
                    / f"{field}.day.bin",
                    dtype="<f4",
                )
                columns[field] = values[1:]
            frame = pd.DataFrame(columns, index=calendar_slice)
            observed = frame.dropna(how="all")

            self.assertFalse(
                observed.isna().any().any(),
                (symbol, observed[observed.isna().any(axis=1)]),
            )
            prices = observed[["open", "close", "high", "low"]]
            self.assertTrue(
                np.isfinite(prices.to_numpy()).all(), symbol
            )
            self.assertTrue((prices > 0).all().all(), symbol)
            self.assertTrue(
                (observed["volume"] >= 0).all()
                and np.isfinite(observed["volume"]).all(),
                symbol,
            )
            self.assertTrue(
                (observed["amount"] >= 0).all()
                and np.isfinite(observed["amount"]).all(),
                symbol,
            )
            self.assertTrue(
                (observed["factor"] > 0).all()
                and np.isfinite(observed["factor"]).all(),
                symbol,
            )
            tolerance = 1e-7 + 1e-6 * prices.abs().max(axis=1)
            self.assertTrue(
                (
                    observed["high"] + tolerance
                    >= observed[["open", "close", "low"]].max(axis=1)
                ).all(),
                symbol,
            )
            self.assertTrue(
                (
                    observed["low"]
                    <= observed[["open", "close"]].min(axis=1) + tolerance
                ).all(),
                symbol,
            )
            with self.subTest(symbol=symbol):
                download_to_qlib.validate_frame(observed, specs[symbol])


class SharedInstrumentEnvironmentTest(unittest.TestCase):
    env_script = ROOT / "qlib-demos/qlib_env.sh"

    def test_default_instrument_pool_matches_bundled_provider(self) -> None:
        self.assertTrue(hasattr(qlib_demo_common, "instrument_pool"))
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("QLIB_INSTRUMENT_POOL", None)
            self.assertEqual("all", qlib_demo_common.instrument_pool())

        self.assertFalse(hasattr(qlib_demo_common, "market"))

    def test_shared_environment_exports_default_instruments(self) -> None:
        result = subprocess.run(
            [
                "bash",
                "-c",
                'source "$1" && printf "%s" "$QLIB_INSTRUMENTS"',
                "bash",
                str(self.env_script),
            ],
            check=True,
            capture_output=True,
            text=True,
        )

        self.assertEqual(
            "sh510050,sh510300,sh510500,sz159915,sh588000",
            result.stdout,
        )

    def test_shared_environment_preserves_caller_override(self) -> None:
        result = subprocess.run(
            [
                "bash",
                "-c",
                'QLIB_INSTRUMENTS="custom"; source "$1" && '
                'printf "%s" "$QLIB_INSTRUMENTS"',
                "bash",
                str(self.env_script),
            ],
            check=True,
            capture_output=True,
            text=True,
        )

        self.assertEqual("custom", result.stdout)

    def test_shared_environment_preserves_empty_override(self) -> None:
        result = subprocess.run(
            [
                "bash",
                "-c",
                'set -u; QLIB_INSTRUMENTS=""; source "$1" && '
                'printf "%s" "$QLIB_INSTRUMENTS"',
                "bash",
                str(self.env_script),
            ],
            check=True,
            capture_output=True,
            text=True,
        )

        self.assertEqual("", result.stdout)

    def test_environment_demo_prints_actual_default_feature_instruments(self) -> None:
        environment = os.environ.copy()
        environment.pop("QLIB_INSTRUMENTS", None)

        result = subprocess.run(
            [
                "bash",
                str(
                    ROOT
                    / "qlib-demos/script/run_01.sh"
                ),
            ],
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
        )

        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn(
            "feature instruments: "
            "['sh510050', 'sh510300', 'sh510500', "
            "'sz159915', 'sh588000']",
            result.stdout,
        )

    def test_environment_demo_preserves_explicit_empty_override(self) -> None:
        environment = os.environ.copy()
        environment["QLIB_INSTRUMENTS"] = ""

        result = subprocess.run(
            [
                "bash",
                str(
                    ROOT
                    / "qlib-demos/script/run_01.sh"
                ),
            ],
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
        )

        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("instruments: all", result.stdout)
        self.assertIn(
            "feature instruments: instrument pool all "
            "(feature query skipped)",
            result.stdout,
        )

    def test_all_run_scripts_source_shared_environment(self) -> None:
        run_scripts = sorted((ROOT / "qlib-demos/script").glob("run_*.sh"))

        self.assertEqual(15, len(run_scripts))
        for run_script in run_scripts:
            with self.subTest(run_script=run_script):
                contents = run_script.read_text()
                self.assertIn(
                    'source "$SCRIPT_DIR/../qlib_env.sh"', contents
                )
                self.assertNotIn(
                    'export QLIB_INSTRUMENTS="sh510300"', contents
                )

    def test_dataset_demos_use_shared_instrument_selector(self) -> None:
        demos = [
            "04-data-handler-and-dataset/data_handler_and_dataset.py",
            "11-alpha158-alpha360-feature-sets/alpha_feature_sets.py",
            "12-native-backtest-architecture/native_backtest_architecture.py",
        ]

        for relative_path in demos:
            with self.subTest(demo=relative_path):
                contents = (ROOT / "qlib-demos" / relative_path).read_text()
                self.assertIn("instruments=instruments()", contents)
                self.assertNotIn("instruments=instrument_pool()", contents)

    def test_default_benchmark_is_available_in_bundled_provider(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("QLIB_BENCHMARK", None)
            self.assertEqual("sh510300", qlib_demo_common.benchmark())

        with mock.patch.dict(
            os.environ, {"QLIB_BENCHMARK": "sh510050"}
        ):
            self.assertEqual("sh510050", qlib_demo_common.benchmark())

    def test_native_backtest_enables_mlflow_file_store(self) -> None:
        run_script = (
            ROOT / "qlib-demos/script/run_12.sh"
        ).read_text()

        self.assertIn("export MLFLOW_ALLOW_FILE_STORE=true", run_script)

    def test_native_backtest_demo_runs_with_bundled_provider(self) -> None:
        environment = os.environ.copy()
        environment.pop("QLIB_BENCHMARK", None)
        environment.pop("QLIB_INSTRUMENTS", None)
        repository_mlruns_existed = (ROOT / "mlruns").exists()

        with tempfile.TemporaryDirectory() as working_directory:
            result = subprocess.run(
                [
                    "bash",
                    str(
                        ROOT
                        / "qlib-demos/script/run_12.sh"
                    ),
                ],
                cwd=working_directory,
                env=environment,
                capture_output=True,
                text=True,
                timeout=180,
            )

            output = result.stdout + result.stderr
            self.assertEqual(0, result.returncode, output)
            self.assertIn(
                "instruments: ['sh510050', 'sh510300', 'sh510500', "
                "'sz159915', 'sh588000']",
                output,
            )
            self.assertIn("benchmark: sh510300", output)
            self.assertIn("portfolio report tail:", output)
            self.assertIn("portfolio analysis:", output)
            self.assertTrue(
                (Path(working_directory) / "mlruns").is_dir(), output
            )

        self.assertEqual(
            repository_mlruns_existed, (ROOT / "mlruns").exists()
        )

    def test_data_handler_demo_runs_with_bundled_provider(self) -> None:
        result = subprocess.run(
            [
                "bash",
                str(
                    ROOT
                    / "qlib-demos/script/run_04.sh"
                ),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )

        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("train shape:", result.stdout)

    def test_alpha_feature_demo_runs_with_bundled_provider(self) -> None:
        result = subprocess.run(
            [
                "bash",
                str(
                    ROOT
                    / "qlib-demos/script/run_11.sh"
                ),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )

        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("Alpha158", result.stdout)
        self.assertIn("Alpha360", result.stdout)


class MultiEtfProviderModelTest(unittest.TestCase):
    def setUp(self) -> None:
        self.frames = {
            "sh588000": pd.DataFrame(
                {"close": np.array([20.0, 21.0], dtype=np.float32)},
                index=pd.to_datetime(["2024-01-02", "2024-01-03"]),
            ),
            "sh510050": pd.DataFrame(
                {"close": np.array([10.0, 11.0], dtype=np.float32)},
                index=pd.to_datetime(["2024-01-01", "2024-01-02"]),
            ),
        }

    def test_default_instruments_have_expected_values_in_order(self) -> None:
        self.assertEqual(
            [
                ("510050", "sh510050", "上证50 ETF"),
                ("510300", "sh510300", "沪深300 ETF"),
                ("510500", "sh510500", "中证500 ETF"),
                ("159915", "sz159915", "创业板 ETF"),
                ("588000", "sh588000", "科创50 ETF"),
            ],
            [
                (spec.source_symbol, spec.qlib_symbol, spec.name)
                for spec in download_to_qlib.DEFAULT_INSTRUMENTS
            ],
        )

    def test_build_calendar_returns_sorted_union(self) -> None:
        calendar = download_to_qlib.build_calendar(self.frames)

        pd.testing.assert_index_equal(
            pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"]),
            calendar,
        )

    def test_build_calendar_rejects_empty_mapping(self) -> None:
        with self.assertRaises(ValueError):
            download_to_qlib.build_calendar({})

    def test_build_calendar_sorts_and_removes_duplicates_within_frame(self) -> None:
        frame = pd.DataFrame(
            {"close": np.array([12.0, 10.0, 11.0], dtype=np.float32)},
            index=pd.to_datetime(
                ["2024-01-02", "2024-01-01", "2024-01-02"]
            ),
        )

        calendar = download_to_qlib.build_calendar({"sh510050": frame})

        pd.testing.assert_index_equal(
            pd.to_datetime(["2024-01-01", "2024-01-02"]), calendar
        )

    def test_build_calendar_normalizes_date_like_string_index(self) -> None:
        frame = pd.DataFrame(
            {"close": np.array([11.0, 10.0], dtype=np.float32)},
            index=["2024-01-02", "2024-01-01"],
        )

        calendar = download_to_qlib.build_calendar({"sh510050": frame})

        self.assertIsInstance(calendar, pd.DatetimeIndex)
        pd.testing.assert_index_equal(
            pd.to_datetime(["2024-01-01", "2024-01-02"]), calendar
        )

    def test_write_instruments_sorts_symbols_and_uses_frame_dates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            download_to_qlib.write_instruments(self.frames, Path(directory))
            contents = (
                Path(directory) / "instruments" / "all.txt"
            ).read_text()

        self.assertEqual(
            "sh510050\t2024-01-01\t2024-01-02\n"
            "sh588000\t2024-01-02\t2024-01-03\n",
            contents,
        )

    def test_write_features_keeps_union_calendar_start_index_header(self) -> None:
        calendar = pd.to_datetime(
            ["2024-01-01", "2024-01-02", "2024-01-03"]
        )

        with tempfile.TemporaryDirectory() as directory:
            download_to_qlib.write_features(
                self.frames["sh588000"],
                "sh588000",
                calendar,
                Path(directory),
            )
            values = np.fromfile(
                Path(directory) / "features/sh588000/close.day.bin",
                dtype="<f4",
            )

        np.testing.assert_array_equal(
            np.array([1.0, 20.0, 21.0], dtype=np.float32), values
        )


class EtfDownloadFallbackTest(unittest.TestCase):
    def setUp(self) -> None:
        self.spec = download_to_qlib.InstrumentSpec(
            "510050", "sh510050", "上证50 ETF"
        )

    @staticmethod
    def eastmoney_frame() -> pd.DataFrame:
        return pd.DataFrame(
            {
                "日期": ["2024-01-02", "2024-01-03"],
                "开盘": [10.0, 11.0],
                "收盘": [10.5, 11.5],
                "最高": [11.0, 12.0],
                "最低": [9.5, 10.5],
                "成交量": [100.0, 110.0],
                "成交额": [1000.0, 1200.0],
            }
        )

    @staticmethod
    def sina_frame() -> pd.DataFrame:
        return pd.DataFrame(
            {
                "date": ["2024-01-01", "2024-01-02", "2024-01-03"],
                "open": [9.0, 10.0, 11.0],
                "high": [10.0, 11.0, 12.0],
                "low": [8.5, 9.5, 10.5],
                "close": [9.5, 10.5, 11.5],
                "volume": [90.0, 100.0, 110.0],
            }
        )

    @staticmethod
    def akshare_mock() -> mock.Mock:
        return mock.Mock(name="akshare")

    def test_eastmoney_success_keeps_amount_and_does_not_call_sina(self) -> None:
        akshare = self.akshare_mock()
        akshare.fund_etf_hist_em.return_value = self.eastmoney_frame()

        with mock.patch.dict(sys.modules, {"akshare": akshare}):
            frame = download_to_qlib.download(
                self.spec, "20240101", "20240103", "qfq"
            )

        akshare.fund_etf_hist_em.assert_called_once_with(
            symbol="510050",
            period="daily",
            start_date="20240101",
            end_date="20240103",
            adjust="qfq",
        )
        akshare.fund_etf_hist_sina.assert_not_called()
        self.assertEqual(list(download_to_qlib.FEATURES), list(frame.columns))
        self.assertEqual(np.dtype("float32"), frame["amount"].dtype)

    def test_eastmoney_failure_uses_exact_sina_symbol_without_amount(self) -> None:
        akshare = self.akshare_mock()
        akshare.fund_etf_hist_em.side_effect = OSError("EastMoney offline")
        akshare.fund_etf_hist_sina.return_value = self.sina_frame()

        with mock.patch.dict(sys.modules, {"akshare": akshare}):
            with self.assertWarnsRegex(
                RuntimeWarning, "Sina.*not guaranteed.*qfq.*semantics"
            ):
                frame = download_to_qlib.download(
                    self.spec, "20240102", "20240103", "qfq"
                )

        akshare.fund_etf_hist_sina.assert_called_once_with(symbol="sh510050")
        pd.testing.assert_index_equal(
            pd.DatetimeIndex(
                pd.to_datetime(["2024-01-02", "2024-01-03"]), name="date"
            ),
            frame.index,
        )
        self.assertEqual(
            ["open", "close", "high", "low", "volume", "factor"],
            list(frame.columns),
        )
        self.assertNotIn("amount", frame.columns)
        np.testing.assert_array_equal(
            np.ones(2, dtype=np.float32), frame["factor"].to_numpy()
        )
        self.assertTrue(
            all(dtype == np.dtype("float32") for dtype in frame.dtypes)
        )

    def test_malformed_eastmoney_response_uses_sina_fallback(self) -> None:
        akshare = self.akshare_mock()
        akshare.fund_etf_hist_em.return_value = self.eastmoney_frame().drop(
            columns=["成交量"]
        )
        akshare.fund_etf_hist_sina.return_value = self.sina_frame()

        with mock.patch.dict(sys.modules, {"akshare": akshare}):
            with self.assertWarnsRegex(
                RuntimeWarning, "Sina.*not guaranteed.*qfq.*semantics"
            ):
                frame = download_to_qlib.download(
                    self.spec, "20240102", "20240103", "qfq"
                )

        akshare.fund_etf_hist_sina.assert_called_once_with(
            symbol="sh510050"
        )
        self.assertEqual(
            ["open", "close", "high", "low", "volume", "factor"],
            list(frame.columns),
        )

    def test_invalid_eastmoney_price_warns_with_cause_and_uses_sina(self) -> None:
        akshare = self.akshare_mock()
        invalid = self.eastmoney_frame()
        invalid.loc[0, "开盘"] = -1.0
        akshare.fund_etf_hist_em.return_value = invalid
        akshare.fund_etf_hist_sina.return_value = self.sina_frame()

        with mock.patch.dict(sys.modules, {"akshare": akshare}):
            with self.assertWarnsRegex(
                RuntimeWarning,
                "ValueError: sh510050.*open.*strictly positive.*"
                "Sina.*not guaranteed.*hfq.*semantics",
            ):
                frame = download_to_qlib.download(
                    self.spec, "20240102", "20240103", "hfq"
                )

        akshare.fund_etf_hist_sina.assert_called_once_with(
            symbol="sh510050"
        )
        self.assertTrue((frame["open"] > 0).all())

    def test_both_sources_fail_with_instrument_specific_chain(self) -> None:
        akshare = self.akshare_mock()
        eastmoney_error = OSError("EastMoney offline")
        sina_error = OSError("Sina offline")
        akshare.fund_etf_hist_em.side_effect = eastmoney_error
        akshare.fund_etf_hist_sina.side_effect = sina_error

        with mock.patch.dict(sys.modules, {"akshare": akshare}):
            with self.assertWarns(RuntimeWarning):
                with self.assertRaisesRegex(
                    RuntimeError, "sh510050.*510050"
                ) as raised:
                    download_to_qlib.download_all(
                        (self.spec,), "20240101", "20240103", "qfq"
                    )

        fallback_error = raised.exception.__cause__
        self.assertIsInstance(fallback_error, RuntimeError)
        self.assertRegex(str(fallback_error), "sh510050.*EastMoney.*Sina")
        self.assertIs(sina_error, fallback_error.__cause__)

    def test_all_defaults_route_to_exact_exchange_qualified_sina_symbols(self) -> None:
        akshare = self.akshare_mock()
        akshare.fund_etf_hist_em.side_effect = OSError("EastMoney offline")
        akshare.fund_etf_hist_sina.return_value = self.sina_frame()

        with mock.patch.dict(sys.modules, {"akshare": akshare}):
            with mock.patch("warnings.warn"):
                frames = download_to_qlib.download_all(
                    download_to_qlib.DEFAULT_INSTRUMENTS,
                    "20240101",
                    "20240103",
                    "qfq",
                )

        self.assertEqual(
            [spec.qlib_symbol for spec in download_to_qlib.DEFAULT_INSTRUMENTS],
            list(frames),
        )
        self.assertEqual(
            [
                mock.call(symbol=spec.qlib_symbol)
                for spec in download_to_qlib.DEFAULT_INSTRUMENTS
            ],
            akshare.fund_etf_hist_sina.call_args_list,
        )


class SafeProviderPublicationTest(unittest.TestCase):
    @staticmethod
    def make_frame(
        dates: list[str],
        offset: float = 0.0,
        include_amount: bool = True,
    ) -> pd.DataFrame:
        row_count = len(dates)
        values = np.arange(row_count, dtype=np.float32) + offset
        columns = {
            "open": values + 1,
            "close": values + 2,
            "high": values + 3,
            "low": values + 0.5,
            "volume": values + 100,
            "factor": np.ones(row_count, dtype=np.float32),
        }
        if include_amount:
            columns["amount"] = values + 1000
        return pd.DataFrame(columns, index=pd.to_datetime(dates))

    def setUp(self) -> None:
        self.spec = download_to_qlib.InstrumentSpec(
            "510050", "sh510050", "上证50 ETF"
        )

    def test_validate_frame_accepts_complete_frame(self) -> None:
        download_to_qlib.validate_frame(
            self.make_frame(["2024-01-01", "2024-01-02"]), self.spec
        )

    def test_validate_frame_accepts_frame_without_optional_amount(self) -> None:
        download_to_qlib.validate_frame(
            self.make_frame(
                ["2024-01-01", "2024-01-02"], include_amount=False
            ),
            self.spec,
        )

    def test_validate_frame_rejects_empty_frame_and_names_symbol(self) -> None:
        frame = self.make_frame([])

        with self.assertRaisesRegex(ValueError, "sh510050.*empty"):
            download_to_qlib.validate_frame(frame, self.spec)

    def test_validate_frame_rejects_missing_core_field_and_names_it(self) -> None:
        frame = self.make_frame(["2024-01-01"]).drop(columns=["factor"])

        with self.assertRaisesRegex(ValueError, "sh510050.*factor"):
            download_to_qlib.validate_frame(frame, self.spec)

    def test_validate_frame_rejects_non_datetime_index(self) -> None:
        frame = self.make_frame(["2024-01-01"])
        frame.index = ["2024-01-01"]

        with self.assertRaisesRegex(ValueError, "sh510050.*DatetimeIndex"):
            download_to_qlib.validate_frame(frame, self.spec)

    def test_validate_frame_rejects_duplicate_dates(self) -> None:
        frame = self.make_frame(["2024-01-01", "2024-01-01"])

        with self.assertRaisesRegex(ValueError, "sh510050.*duplicate"):
            download_to_qlib.validate_frame(frame, self.spec)

    def test_validate_frame_rejects_non_monotonic_dates(self) -> None:
        frame = self.make_frame(["2024-01-02", "2024-01-01"])

        with self.assertRaisesRegex(ValueError, "sh510050.*monotonic"):
            download_to_qlib.validate_frame(frame, self.spec)

    def test_validate_frame_rejects_nonfinite_or_invalid_field_values(self) -> None:
        cases = (
            ("open", 0.0, "open.*strictly positive"),
            ("close", np.inf, "close.*finite"),
            ("high", np.nan, "high.*finite"),
            ("low", -1.0, "low.*strictly positive"),
            ("volume", -1.0, "volume.*non-negative"),
            ("volume", np.inf, "volume.*finite"),
            ("amount", -1.0, "amount.*non-negative"),
            ("amount", np.nan, "amount.*finite"),
            ("factor", 0.0, "factor.*strictly positive"),
            ("factor", np.inf, "factor.*finite"),
        )

        for field, value, message in cases:
            with self.subTest(field=field, value=value):
                frame = self.make_frame(["2024-01-01"])
                frame.loc[frame.index[0], field] = value
                with self.assertRaisesRegex(
                    ValueError, f"sh510050.*{message}"
                ):
                    download_to_qlib.validate_frame(frame, self.spec)

    def test_validate_frame_rejects_invalid_ohlc_relationships(self) -> None:
        cases = (
            ("high", 0.25, "high.*low"),
            ("low", 1.5, "low.*open.*close"),
            ("high", 1.5, "high.*open.*close"),
        )

        for field, value, message in cases:
            with self.subTest(field=field, value=value):
                frame = self.make_frame(["2024-01-01"])
                frame.loc[frame.index[0], field] = value
                with self.assertRaisesRegex(
                    ValueError, f"sh510050.*{message}"
                ):
                    download_to_qlib.validate_frame(frame, self.spec)

    def test_validate_frame_allows_tiny_float32_ohlc_rounding(self) -> None:
        frame = self.make_frame(["2024-01-01"])
        frame.loc[frame.index[0], "low"] = np.nextafter(
            np.float32(1.0), np.float32(np.inf)
        )
        frame.loc[frame.index[0], "high"] = np.nextafter(
            np.float32(2.0), np.float32(-np.inf)
        )

        download_to_qlib.validate_frame(frame, self.spec)

    def test_write_and_validate_complete_multi_instrument_provider(self) -> None:
        frames = {
            "sh510050": self.make_frame(
                ["2024-01-01", "2024-01-02"], 10
            ),
            "sh588000": self.make_frame(
                ["2024-01-02", "2024-01-03"], 20
            ),
        }

        with tempfile.TemporaryDirectory() as directory:
            out_dir = Path(directory) / "provider"
            download_to_qlib.write_provider(frames, out_dir)
            download_to_qlib.validate_provider(out_dir, frames)

            calendar = (
                out_dir / "calendars/day.txt"
            ).read_text().splitlines()
            metadata = (
                out_dir / "instruments/all.txt"
            ).read_text().splitlines()
            feature_values = np.fromfile(
                out_dir / "features/sh588000/open.day.bin", dtype="<f4"
            )

        self.assertEqual(
            ["2024-01-01", "2024-01-02", "2024-01-03"], calendar
        )
        self.assertEqual(
            {"sh510050", "sh588000"},
            {line.split("\t")[0] for line in metadata},
        )
        self.assertEqual(1.0, feature_values[0])

    def test_provider_round_trips_without_optional_amount_file(self) -> None:
        frames = {
            "sh510050": self.make_frame(
                ["2024-01-01", "2024-01-02"], include_amount=False
            )
        }

        with tempfile.TemporaryDirectory() as directory:
            out_dir = Path(directory) / "provider"
            download_to_qlib.write_provider(frames, out_dir)
            download_to_qlib.validate_provider(out_dir, frames)
            feature_names = {
                path.name
                for path in (out_dir / "features/sh510050").iterdir()
            }

        self.assertEqual(
            {f"{field}.day.bin" for field in download_to_qlib.REQUIRED_FIELDS},
            feature_names,
        )

    def test_validate_provider_accepts_amount_only_for_frame_that_has_it(self) -> None:
        frames = {
            "sh510050": self.make_frame(["2024-01-01", "2024-01-02"]),
            "sh588000": self.make_frame(
                ["2024-01-02", "2024-01-03"], include_amount=False
            ),
        }

        with tempfile.TemporaryDirectory() as directory:
            out_dir = Path(directory) / "provider"
            download_to_qlib.write_provider(frames, out_dir)
            download_to_qlib.validate_provider(out_dir, frames)

            self.assertTrue(
                (out_dir / "features/sh510050/amount.day.bin").is_file()
            )
            self.assertFalse(
                (out_dir / "features/sh588000/amount.day.bin").exists()
            )

    def test_validate_provider_rejects_unexpected_optional_amount_file(self) -> None:
        frames = {
            "sh510050": self.make_frame(
                ["2024-01-01", "2024-01-02"], include_amount=False
            )
        }

        with tempfile.TemporaryDirectory() as directory:
            out_dir = Path(directory) / "provider"
            download_to_qlib.write_provider(frames, out_dir)
            unexpected = out_dir / "features/sh510050/amount.day.bin"
            np.array([0.0, 1.0, 2.0], dtype="<f4").tofile(unexpected)

            with self.assertRaisesRegex(ValueError, "unexpected.*amount"):
                download_to_qlib.validate_provider(out_dir, frames)

    def test_validate_provider_rejects_missing_feature_and_names_path(self) -> None:
        frames = {
            "sh510050": self.make_frame(["2024-01-01", "2024-01-02"])
        }

        with tempfile.TemporaryDirectory() as directory:
            out_dir = Path(directory) / "provider"
            download_to_qlib.write_provider(frames, out_dir)
            missing = out_dir / "features/sh510050/amount.day.bin"
            missing.unlink()

            with self.assertRaisesRegex(
                FileNotFoundError, "amount[.]day[.]bin"
            ):
                download_to_qlib.validate_provider(out_dir, frames)

    def test_validate_provider_names_misaligned_feature_path(self) -> None:
        frames = {
            "sh510050": self.make_frame(["2024-01-01", "2024-01-02"])
        }

        with tempfile.TemporaryDirectory() as directory:
            out_dir = Path(directory) / "provider"
            download_to_qlib.write_provider(frames, out_dir)
            corrupt = out_dir / "features/sh510050/open.day.bin"
            with corrupt.open("ab") as feature_file:
                feature_file.write(b"x")

            with self.assertRaisesRegex(
                ValueError, "open[.]day[.]bin.*float32"
            ):
                download_to_qlib.validate_provider(out_dir, frames)

    def test_validate_provider_rejects_whole_float_truncation(self) -> None:
        frames = {
            "sh510050": self.make_frame(["2024-01-01", "2024-01-02"])
        }

        with tempfile.TemporaryDirectory() as directory:
            out_dir = Path(directory) / "provider"
            download_to_qlib.write_provider(frames, out_dir)
            corrupt = out_dir / "features/sh510050/open.day.bin"
            corrupt.write_bytes(corrupt.read_bytes()[:-4])

            with self.assertRaisesRegex(
                ValueError, "open[.]day[.]bin.*length"
            ):
                download_to_qlib.validate_provider(out_dir, frames)

    def test_validate_provider_rejects_wrong_metadata_dates(self) -> None:
        frames = {
            "sh510050": self.make_frame(["2024-01-01", "2024-01-02"])
        }

        with tempfile.TemporaryDirectory() as directory:
            out_dir = Path(directory) / "provider"
            download_to_qlib.write_provider(frames, out_dir)
            metadata = out_dir / "instruments/all.txt"
            metadata.write_text("sh510050\t2020-01-01\t2020-01-02\n")

            with self.assertRaisesRegex(
                ValueError, "all[.]txt.*metadata"
            ):
                download_to_qlib.validate_provider(out_dir, frames)

    def test_validate_provider_rejects_wrong_calendar_content(self) -> None:
        frames = {
            "sh510050": self.make_frame(["2024-01-01", "2024-01-02"])
        }

        with tempfile.TemporaryDirectory() as directory:
            out_dir = Path(directory) / "provider"
            download_to_qlib.write_provider(frames, out_dir)
            calendar = out_dir / "calendars/day.txt"
            calendar.write_text("2024-01-01\n2024-01-09\n")

            with self.assertRaisesRegex(
                ValueError, "day[.]txt.*calendar"
            ):
                download_to_qlib.validate_provider(out_dir, frames)

    def test_validate_provider_rejects_wrong_feature_payload(self) -> None:
        frames = {
            "sh510050": self.make_frame(["2024-01-01", "2024-01-02"])
        }

        with tempfile.TemporaryDirectory() as directory:
            out_dir = Path(directory) / "provider"
            download_to_qlib.write_provider(frames, out_dir)
            corrupt = out_dir / "features/sh510050/open.day.bin"
            values = np.fromfile(corrupt, dtype="<f4")
            values[-1] = 999.0
            values.tofile(corrupt)

            with self.assertRaisesRegex(
                ValueError, "open[.]day[.]bin.*payload"
            ):
                download_to_qlib.validate_provider(out_dir, frames)

    def test_validate_provider_rejects_unexpected_feature_artifacts(self) -> None:
        frames = {
            "sh510050": self.make_frame(["2024-01-01", "2024-01-02"])
        }

        with tempfile.TemporaryDirectory() as directory:
            out_dir = Path(directory) / "provider"
            download_to_qlib.write_provider(frames, out_dir)
            unexpected_dir = out_dir / "features/sh999999"
            unexpected_dir.mkdir()

            with self.assertRaisesRegex(
                ValueError, "features.*unexpected"
            ):
                download_to_qlib.validate_provider(out_dir, frames)

    def test_publish_provider_restores_original_target_on_swap_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            target = parent / "qlib-data"
            staging = parent / "staging"
            target.mkdir()
            staging.mkdir()
            (target / "marker.txt").write_text("original")
            (staging / "marker.txt").write_text("replacement")

            def replace_except_staging(source: Path, destination: Path) -> None:
                if source == staging:
                    raise OSError("simulated staging swap failure")
                source.replace(destination)

            with mock.patch.object(
                download_to_qlib,
                "_replace_path",
                side_effect=replace_except_staging,
            ):
                with self.assertRaisesRegex(OSError, "staging swap failure"):
                    download_to_qlib.publish_provider(staging, target)

            self.assertEqual("original", (target / "marker.txt").read_text())
            self.assertFalse((parent / ".qlib-data.backup").exists())

    def test_publish_provider_recovers_backup_only_state_before_failed_swap(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            target = parent / "qlib-data"
            backup = parent / ".qlib-data.backup"
            staging = parent / "staging"
            backup.mkdir()
            staging.mkdir()
            (backup / "marker.txt").write_text("recoverable-original")
            (staging / "marker.txt").write_text("replacement")

            def replace_except_staging(source: Path, destination: Path) -> None:
                if source == staging:
                    raise OSError("simulated staging swap failure")
                source.replace(destination)

            with mock.patch.object(
                download_to_qlib,
                "_replace_path",
                side_effect=replace_except_staging,
            ):
                with self.assertRaisesRegex(OSError, "staging swap failure"):
                    download_to_qlib.publish_provider(staging, target)

            self.assertEqual(
                "recoverable-original", (target / "marker.txt").read_text()
            )
            self.assertFalse(backup.exists())

    def test_publish_provider_prefers_target_over_stale_backup_on_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            target = parent / "qlib-data"
            backup = parent / ".qlib-data.backup"
            staging = parent / "staging"
            target.mkdir()
            backup.mkdir()
            staging.mkdir()
            (target / "marker.txt").write_text("authoritative-target")
            (backup / "marker.txt").write_text("stale-backup")

            def replace_except_staging(source: Path, destination: Path) -> None:
                if source == staging:
                    raise OSError("simulated staging swap failure")
                source.replace(destination)

            with mock.patch.object(
                download_to_qlib,
                "_replace_path",
                side_effect=replace_except_staging,
            ):
                with self.assertRaisesRegex(OSError, "staging swap failure"):
                    download_to_qlib.publish_provider(staging, target)

            self.assertEqual(
                "authoritative-target", (target / "marker.txt").read_text()
            )
            self.assertFalse(backup.exists())

    def test_selected_instruments_uses_defaults_without_override(self) -> None:
        args = argparse.Namespace(symbol=None, qlib_symbol=None)

        self.assertEqual(
            download_to_qlib.DEFAULT_INSTRUMENTS,
            download_to_qlib.selected_instruments(args),
        )

    def test_selected_instruments_builds_paired_override(self) -> None:
        args = argparse.Namespace(symbol="123456", qlib_symbol="sz123456")

        self.assertEqual(
            (
                download_to_qlib.InstrumentSpec(
                    "123456", "sz123456", "Custom ETF"
                ),
            ),
            download_to_qlib.selected_instruments(args),
        )

    def test_selected_instruments_rejects_incomplete_override_pair(self) -> None:
        for args in (
            argparse.Namespace(symbol="510300", qlib_symbol=None),
            argparse.Namespace(symbol=None, qlib_symbol="sh510300"),
        ):
            with self.subTest(args=args):
                with self.assertRaisesRegex(
                    ValueError, "--symbol.*--qlib-symbol"
                ):
                    download_to_qlib.selected_instruments(args)

    def test_download_all_collects_every_validated_frame(self) -> None:
        specs = download_to_qlib.DEFAULT_INSTRUMENTS[:2]
        downloaded = [
            self.make_frame(["2024-01-01"], 10),
            self.make_frame(["2024-01-02"], 20),
        ]

        with mock.patch.object(
            download_to_qlib, "download", side_effect=downloaded
        ) as download_mock:
            frames = download_to_qlib.download_all(
                specs, "20240101", "20240131", "qfq"
            )

        self.assertEqual([spec.qlib_symbol for spec in specs], list(frames))
        self.assertEqual(
            [
                mock.call(specs[0], "20240101", "20240131", "qfq"),
                mock.call(specs[1], "20240101", "20240131", "qfq"),
            ],
            download_mock.call_args_list,
        )

    def test_download_all_names_failed_instrument_and_preserves_cause(self) -> None:
        specs = download_to_qlib.DEFAULT_INSTRUMENTS[:2]
        cause = ValueError("network returned no rows")

        with mock.patch.object(
            download_to_qlib,
            "download",
            side_effect=[self.make_frame(["2024-01-01"]), cause],
        ):
            with self.assertRaisesRegex(
                RuntimeError, "sh510300.*510300"
            ) as raised:
                download_to_qlib.download_all(
                    specs, "20240101", "20240131", "qfq"
                )

        self.assertIs(cause, raised.exception.__cause__)

    def test_selected_instruments_rejects_path_traversal_symbol(self) -> None:
        args = argparse.Namespace(symbol="510050", qlib_symbol="../../victim")

        with self.assertRaisesRegex(ValueError, "qlib_symbol"):
            download_to_qlib.selected_instruments(args)

    def test_selected_instruments_rejects_empty_symbol(self) -> None:
        args = argparse.Namespace(symbol="510050", qlib_symbol="   ")

        with self.assertRaisesRegex(ValueError, "qlib_symbol"):
            download_to_qlib.selected_instruments(args)

    def test_selected_instruments_rejects_invalid_source_symbol(self) -> None:
        args = argparse.Namespace(symbol="not-an-etf", qlib_symbol="sh510050")

        with self.assertRaisesRegex(ValueError, "source_symbol"):
            download_to_qlib.selected_instruments(args)

    def test_download_all_rejects_duplicate_qlib_symbols_before_download(self) -> None:
        specs = (
            download_to_qlib.InstrumentSpec("510050", "sh510050", "first"),
            download_to_qlib.InstrumentSpec("510300", "sh510050", "second"),
        )

        with mock.patch.object(download_to_qlib, "download") as download_mock:
            with self.assertRaisesRegex(ValueError, "duplicate.*sh510050"):
                download_to_qlib.download_all(
                    specs, "20240101", "20240131", "qfq"
                )

        download_mock.assert_not_called()

    def test_write_provider_rejects_path_traversal_without_external_write(self) -> None:
        frame = self.make_frame(["2024-01-01"])

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            out_dir = root / "provider"
            escaped = root / "victim"

            with self.assertRaisesRegex(ValueError, "qlib_symbol"):
                download_to_qlib.write_provider({"../../victim": frame}, out_dir)

            self.assertFalse(escaped.exists())

    def test_main_download_failure_leaves_existing_provider_untouched(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "qlib-data"
            target.mkdir()
            marker = target / "marker.txt"
            marker.write_text("original")
            args = argparse.Namespace(
                symbol="510050",
                qlib_symbol="sh510050",
                start="20240101",
                end="20240131",
                adjust="qfq",
                out_dir=str(target),
            )

            with mock.patch.object(download_to_qlib, "parse_args", return_value=args):
                with mock.patch.object(
                    download_to_qlib,
                    "download",
                    side_effect=OSError("network unavailable"),
                ):
                    with self.assertRaisesRegex(RuntimeError, "sh510050"):
                        download_to_qlib.main()

            self.assertEqual("original", marker.read_text())

    def test_main_staging_validation_failure_does_not_publish(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "qlib-data"
            target.mkdir()
            marker = target / "marker.txt"
            marker.write_text("original")
            args = argparse.Namespace(
                symbol="510050",
                qlib_symbol="sh510050",
                start="20240101",
                end="20240131",
                adjust="qfq",
                out_dir=str(target),
            )

            with mock.patch.object(download_to_qlib, "parse_args", return_value=args):
                with mock.patch.object(
                    download_to_qlib,
                    "download",
                    return_value=self.make_frame(["2024-01-01"]),
                ):
                    with mock.patch.object(
                        download_to_qlib,
                        "validate_provider",
                        side_effect=ValueError("staged provider is corrupt"),
                    ):
                        with mock.patch.object(
                            download_to_qlib, "publish_provider"
                        ) as publish_mock:
                            with self.assertRaisesRegex(
                                ValueError, "staged provider is corrupt"
                            ):
                                download_to_qlib.main()

            publish_mock.assert_not_called()
            self.assertEqual("original", marker.read_text())

    def test_parse_args_rejects_incomplete_override_with_usage_error(self) -> None:
        with mock.patch.object(
            sys,
            "argv",
            ["download_to_qlib.py", "--symbol", "510050"],
        ):
            with mock.patch("sys.stderr"):
                with self.assertRaises(SystemExit) as raised:
                    download_to_qlib.parse_args()

        self.assertEqual(2, raised.exception.code)

    def test_parse_args_defaults_to_earliest_etf_listing_date(self) -> None:
        with mock.patch.object(sys, "argv", ["download_to_qlib.py"]):
            args = download_to_qlib.parse_args()

        self.assertEqual("20050223", args.start)

    def test_parse_args_defaults_to_hfq_adjustment(self) -> None:
        with mock.patch.object(sys, "argv", ["download_to_qlib.py"]):
            args = download_to_qlib.parse_args()

        self.assertEqual("hfq", args.adjust)


if __name__ == "__main__":
    unittest.main()
