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


FEATURE_FIELDS = [
    "$close / Ref($close, 5) - 1",
    "$close / Ref($close, 20) - 1",
    "Std($close / Ref($close, 1) - 1, 20)",
    "Mean($volume, 5) / Mean($volume, 20)",
]
FEATURE_NAMES = ["MOM5", "MOM20", "RETURN_VOLATILITY_20", "VOLUME_RATIO_5_20"]
LABEL_FIELDS = ["Ref($close, -2) / Ref($close, -1) - 1"]
LABEL_NAMES = ["LABEL0"]


def build_dataset():
    """Build chronological train, validation, and test segments."""
    from qlib.data.dataset import DatasetH
    from qlib.data.dataset.handler import DataHandlerLP

    handler = DataHandlerLP(
        instruments=instruments(),
        start_time=start_time(),
        end_time=end_time(),
        data_loader={
            "class": "QlibDataLoader",
            "kwargs": {
                "config": {
                    "feature": (FEATURE_FIELDS, FEATURE_NAMES),
                    "label": (LABEL_FIELDS, LABEL_NAMES),
                }
            },
        },
        learn_processors=[
            {"class": "DropnaLabel"},
        ],
    )
    return DatasetH(
        handler=handler,
        segments={
            "train": (start_time(), train_end_time()),
            "valid": (valid_start_time(), valid_end_time()),
            "test": (test_start_time(), end_time()),
        },
    )


def main() -> None:
    init_qlib()
    print_context("Qlib DataHandlerLP / DatasetH")
    dataset = build_dataset()

    from qlib.data.dataset.handler import DataHandlerLP

    for data_key in [DataHandlerLP.DK_R, DataHandlerLP.DK_L]:
        print("\ndata_key:", data_key)
        train = dataset.prepare("train", col_set=["feature", "label"], data_key=data_key)
        print("train shape:", train.shape)
        print(train.head(10).to_string())


if __name__ == "__main__":
    main()
