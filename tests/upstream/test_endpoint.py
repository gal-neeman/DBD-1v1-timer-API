import unittest

from api.upstream import Endpoint


class EndpointTest(unittest.TestCase):
    def test_params_are_quoted(self):
        path = Endpoint("GET", "/player/{user_id}").build_path(user_id="../x y?")
        self.assertEqual(path, "/player/..%2Fx%20y%3F")

    def test_missing_param_raises(self):
        with self.assertRaises(KeyError):
            Endpoint("GET", "/{guild_id}/player/{user_id}").build_path(user_id="1")

    def test_query(self):
        endpoint = Endpoint("GET", "/match/batch", query_params=("limit", "userId"))
        self.assertEqual(endpoint.build_query(None), "")
        self.assertEqual(endpoint.build_query({"limit": "10", "userId": "1"}), "?limit=10&userId=1")

    def test_unknown_query_param_raises(self):
        with self.assertRaisesRegex(ValueError, "cursor"):
            Endpoint("GET", "/match/batch", query_params=("limit",)).build_query({"cursor": "1"})


if __name__ == "__main__":
    unittest.main()
