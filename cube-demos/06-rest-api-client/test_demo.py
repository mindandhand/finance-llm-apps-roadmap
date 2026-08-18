from io import BytesIO
from pathlib import Path
import importlib.util
import unittest


ROOT = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("cube_rest_client", ROOT / "client.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(MODULE)


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self.body = BytesIO(__import__("json").dumps(payload).encode())

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self) -> bytes:
        return self.body.read()


class RestClientTest(unittest.TestCase):
    def test_meta_and_load_use_structured_http_requests(self) -> None:
        requests = []

        def transport(request, timeout):
            requests.append((request.full_url, timeout))
            if request.full_url.endswith("/meta"):
                return FakeResponse({"cubes": [{"name": "transactions"}]})
            return FakeResponse({"data": [{"transactions.count": "8"}]})

        client = MODULE.CubeClient("http://cube.test/", timeout=3, transport=transport)
        self.assertEqual(client.meta()["cubes"][0]["name"], "transactions")
        self.assertEqual(
            client.load({"measures": ["transactions.count"]})["data"][0]["transactions.count"],
            "8",
        )
        self.assertEqual([timeout for _, timeout in requests], [3, 3])
        self.assertIn("query=", requests[1][0])

    def test_timeout_must_be_positive(self) -> None:
        with self.assertRaises(ValueError):
            MODULE.CubeClient("http://cube.test", timeout=0)


if __name__ == "__main__":
    unittest.main()
