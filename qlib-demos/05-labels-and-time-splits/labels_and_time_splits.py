from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qlib_demo_common import (
    load_features,
    print_context,
    test_start_time,
    train_end_time,
    valid_end_time,
    valid_start_time,
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

    train = data.loc[:train_end_time()]
    valid = data.loc[valid_start_time():valid_end_time()]
    test = data.loc[test_start_time():]

    print_context("Qlib labels and chronological splits")
    print("full shape:", data.shape)
    print("train:", train.index.get_level_values("datetime").min(), "to", train.index.get_level_values("datetime").max(), train.shape)
    print("valid:", valid.index.get_level_values("datetime").min(), "to", valid.index.get_level_values("datetime").max(), valid.shape)
    print("test:", test.index.get_level_values("datetime").min(), "to", test.index.get_level_values("datetime").max(), test.shape)
    print(test.head(20).to_string())


if __name__ == "__main__":
    main()
