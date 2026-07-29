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
FEATURE_NAMES = ["MOM5", "MOM20", "VOL20", "VOLUME_RATIO_5_20"]
LABEL_FIELDS = ["Ref($close, -2) / Ref($close, -1) - 1"]
LABEL_NAMES = ["LABEL0"]


def build_dataset():
    """Build chronological segments; LightGBM uses valid for model selection."""
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
            {"class": "Fillna", "kwargs": {"fields_group": "feature"}},
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
    print_context("Qlib model training baseline")

    from qlib.contrib.model.gbdt import LGBModel
    from qlib.data.dataset.handler import DataHandlerLP

    dataset = build_dataset()
    model = LGBModel(
        loss="mse",
        learning_rate=0.05,
        num_leaves=32,
        max_depth=6,
        num_threads=4,
    )
    model.fit(dataset)

    pred = model.predict(dataset, segment="test")
    label = dataset.prepare("test", col_set="label", data_key=DataHandlerLP.DK_L).iloc[:, 0]
    joined = pred.rename("score").to_frame().join(label.rename("label"), how="inner").dropna()
    daily_ic = joined.groupby(level="datetime").apply(lambda g: g["score"].corr(g["label"]))

    print("prediction rows:", len(pred))
    print("mean test IC:", round(float(daily_ic.mean()), 6))
    print(joined.head(20).to_string())


if __name__ == "__main__":
    main()
