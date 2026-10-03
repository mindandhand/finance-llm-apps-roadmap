from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qlib_demo_common import (
    chronological_segments,
    load_features,
    print_context,
    with_datetime_instrument_index,
)


def main() -> None:
    fields = [
        "$close",
        "$close / Ref($close, 20) - 1",
        "Ref($close, -5) / $close - 1",
    ]
    names = ["close", "feature_mom20", "label_fwd5_return"]
    data = with_datetime_instrument_index(load_features(fields, names)).dropna()

    segments = chronological_segments(label_horizon=5)
    train = data.loc[slice(*segments["train"])]
    valid = data.loc[slice(*segments["valid"])]
    test = data.loc[slice(*segments["test"])]

    print_context("Qlib labels and chronological splits")
    print("full shape:", data.shape)
    print("train:", train.index.get_level_values("datetime").min(), "to", train.index.get_level_values("datetime").max(), train.shape)
    print("valid:", valid.index.get_level_values("datetime").min(), "to", valid.index.get_level_values("datetime").max(), valid.shape)
    print("test:", test.index.get_level_values("datetime").min(), "to", test.index.get_level_values("datetime").max(), test.shape)
    print(test.head(20).to_string())


if __name__ == "__main__":
    main()
