import unittest

from app.security import RateLimiter


class RateLimiterTests(unittest.TestCase):
    def test_allows_limit_then_returns_remaining_wait(self):
        limiter = RateLimiter()
        self.assertEqual(limiter.check(("analyze", "127.0.0.1"), 2, 60, now=100), 0)
        self.assertEqual(limiter.check(("analyze", "127.0.0.1"), 2, 60, now=110), 0)
        self.assertEqual(limiter.check(("analyze", "127.0.0.1"), 2, 60, now=120), 40)

    def test_window_expires_and_clients_are_separated(self):
        limiter = RateLimiter()
        self.assertEqual(limiter.check(("analyze", "a"), 1, 60, now=10), 0)
        self.assertEqual(limiter.check(("analyze", "b"), 1, 60, now=10), 0)
        self.assertEqual(limiter.check(("analyze", "a"), 1, 60, now=71), 0)

    def test_actions_have_independent_limits(self):
        limiter = RateLimiter()
        self.assertEqual(limiter.check(("analyze", "a"), 1, 60, now=10), 0)
        self.assertEqual(limiter.check(("map_preview", "a"), 1, 60, now=10), 0)


if __name__ == "__main__":
    unittest.main()
