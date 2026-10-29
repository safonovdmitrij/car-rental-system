"""Regression checks for URI-reference resolution; no HTTP requests."""

import unittest

from check_scenarios import location_target


class LocationTargetTests(unittest.TestCase):
    def test_valid_uri_references(self):
        cases = [
            ('http://127.0.0.1:4010/api/v1/bookings', 'bookings/booking-example',
             '/api/v1/bookings/booking-example'),
            ('http://127.0.0.1:4010/api/v1/bookings', './bookings/booking-example',
             '/api/v1/bookings/booking-example'),
            ('http://127.0.0.1:4010/api/v1/bookings', '/api/v1/bookings/booking-example',
             '/api/v1/bookings/booking-example'),
            ('http://127.0.0.1:4010/api/v1/bookings',
             'http://127.0.0.1:4010/api/v1/bookings/booking-example', '/api/v1/bookings/booking-example'),
            ('http://127.0.0.1:4010/api/v1/bookings/booking-example/cancellation', 'cancellation',
             '/api/v1/bookings/booking-example/cancellation'),
            ('http://127.0.0.1:4010/api/v1/cars/car-example/service-unavailabilities',
             'service-unavailabilities/period-example', '/api/v1/cars/car-example/service-unavailabilities/period-example'),
        ]
        for request, header, expected_path in cases:
            with self.subTest(header=header):
                resolved, expected, matches = location_target(request, header, expected_path)
                self.assertTrue(matches)
                self.assertEqual(resolved, expected)

    def test_wrong_resource_or_address_is_rejected(self):
        request = 'http://127.0.0.1:4010/api/v1/bookings'
        for header in [
            '../dictionary', 'booking-example', '/api/v1/bookings/another-booking',
            '/api/v1/api/v1/bookings/booking-example', '/api/v1/bookings/booking-example?extra=1',
            '/api/v1/bookings/booking-example#extra',
            'http://example.invalid:4010/api/v1/bookings/booking-example',
        ]:
            with self.subTest(header=header):
                self.assertFalse(location_target(request, header, '/api/v1/bookings/booking-example')[2])


if __name__ == '__main__':
    unittest.main()
