"""Regression tests for hostile timestamp input at the ingestion boundary."""
import datetime as dt
import unittest

from sentinel.core import ValidationError, parse_event


class TimestampValidationTests(unittest.TestCase):
    def setUp(self):
        self.valid = {
            "id": "timestamp_0001",
            "host": "node-1",
            "kind": "host_up",
            "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
            "detail": "healthy",
        }

    def test_reject_non_string_timestamps(self):
        for value in (None, 0, 1.5, True, [], {}, ["2026-01-01"], b"2026-01-01"):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                parse_event({**self.valid, "timestamp": value})

    def test_reject_oversized_timestamp(self):
        with self.assertRaisesRegex(ValidationError, "invalid timestamp"):
            parse_event({**self.valid, "timestamp": "2" * 10000})

    def test_timezone_offsets_normalize_to_utc(self):
        fixed = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
        eastern = fixed.astimezone(dt.timezone(dt.timedelta(hours=-4)))
        parsed = parse_event({**self.valid, "timestamp": eastern.isoformat()}, now=fixed)
        self.assertEqual(parsed["timestamp"], fixed.isoformat())

    def test_reject_naive_timestamp(self):
        with self.assertRaisesRegex(ValidationError, "timezone"):
            parse_event({**self.valid, "timestamp": dt.datetime.now().isoformat()})

    def test_reject_outside_time_window(self):
        now = dt.datetime(2026, 11, 5, tzinfo=dt.timezone.utc)
        for timestamp in (now - dt.timedelta(days=8), now + dt.timedelta(minutes=6)):
            with self.subTest(timestamp=timestamp), self.assertRaisesRegex(ValidationError, "outside accepted window"):
                parse_event({**self.valid, "timestamp": timestamp.isoformat()}, now=now)

    def test_accept_current_utc_timestamp(self):
        self.assertEqual(parse_event(self.valid)["host"], "node-1")


if __name__ == "__main__":
    unittest.main()
