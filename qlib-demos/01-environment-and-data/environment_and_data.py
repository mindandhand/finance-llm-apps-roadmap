from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qlib_demo_common import (
    end_time,
    import_qlib,
    init_qlib,
    instruments,
    print_context,
    start_time,
)


def main() -> None:
    qlib = import_qlib()
    provider_uri = init_qlib()
    from qlib.data import D

    print_context("Qlib environment")
    print("qlib module:", qlib.__file__)

    calendar = D.calendar(start_time=start_time(), end_time=end_time(), freq="day")
    print("calendar rows:", len(calendar))
    if len(calendar):
        print("calendar range:", calendar[0], "to", calendar[-1])

    requested_instruments = instruments()
    if isinstance(requested_instruments, str):
        print(
            "feature instruments: instrument pool",
            requested_instruments,
            "(feature query skipped)",
        )
    else:
        close = D.features(
            requested_instruments,
            ["$close"],
            start_time=start_time(),
            end_time=end_time(),
            freq="day",
        )
        returned = set(close.index.get_level_values("instrument"))
        available_instruments = [
            symbol
            for symbol in requested_instruments
            if symbol in returned
        ]
        print("feature instruments:", available_instruments)
        print("latest close by instrument:")
        print(close.groupby(level="instrument").tail(1))
    print("provider ready:", provider_uri)


if __name__ == "__main__":
    main()
