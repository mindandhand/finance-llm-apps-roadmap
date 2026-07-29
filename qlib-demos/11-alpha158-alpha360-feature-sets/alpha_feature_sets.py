from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qlib_demo_common import (
    end_time,
    init_qlib,
    instruments,
    print_context,
    start_time,
    test_start_time,
    train_end_time,
    valid_end_time,
    valid_start_time,
)


def preview_handler(handler_cls, name: str) -> None:
    from qlib.data.dataset import DatasetH
    from qlib.data.dataset.handler import DataHandlerLP

    handler = handler_cls(
        instruments=instruments(),
        start_time=start_time(),
        end_time=end_time(),
        fit_start_time=start_time(),
        fit_end_time=train_end_time(),
        infer_processors=[],
    )
    dataset = DatasetH(
        handler=handler,
        segments={
            "train": (start_time(), train_end_time()),
            "valid": (valid_start_time(), valid_end_time()),
            "test": (test_start_time(), end_time()),
        },
    )
    train = dataset.prepare("train", col_set=["feature", "label"], data_key=DataHandlerLP.DK_L)
    print(f"\n{name}")
    print("shape:", train.shape)
    print("feature columns:", len(train["feature"].columns))
    print("first columns:", list(train["feature"].columns[:20]))
    print(train.head(5).to_string())


def main() -> None:
    init_qlib()
    print_context("Qlib Alpha158 / Alpha360 handlers")

    from qlib.contrib.data.handler import Alpha158, Alpha360

    preview_handler(Alpha158, "Alpha158")
    preview_handler(Alpha360, "Alpha360")


if __name__ == "__main__":
    main()
