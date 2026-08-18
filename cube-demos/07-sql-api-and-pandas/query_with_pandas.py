from __future__ import annotations

import os

import pandas as pd
import psycopg


SEMANTIC_SQL = """
SELECT
    side,
    MEASURE(total_amount) AS total_amount
FROM transactions
GROUP BY side
ORDER BY side
""".strip()


def load_dataframe() -> pd.DataFrame:
    connection = psycopg.connect(
        host="127.0.0.1",
        port=int(os.getenv("CUBE_SQL_PORT", "15432")),
        user=os.getenv("CUBE_SQL_USER", "cube"),
        password=os.getenv("CUBE_SQL_PASSWORD", "cube_sql_password"),
        dbname="cube",
        connect_timeout=10,
    )
    try:
        return pd.read_sql_query(SEMANTIC_SQL, connection)
    finally:
        connection.close()


if __name__ == "__main__":
    frame = load_dataframe()
    print(frame.to_string(index=False))
    actual = dict(zip(frame["side"], frame["total_amount"].astype(float), strict=True))
    expected = {"buy": 203650.0, "sell": 5700.0}
    if actual != expected:
        raise SystemExit(f"SQL API mismatch: expected {expected}, got {actual}")
    print("Chapter 07 passed.")
