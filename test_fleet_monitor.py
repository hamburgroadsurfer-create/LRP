import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
import unittest

from fleet_monitor import (
    Booking,
    LocationSample,
    Station,
    assess_bookings,
    format_report,
    haversine_distance_km,
    load_bookings,
    load_latest_locations,
    load_stations,
    parse_iso_datetime,
)


class TestFleetMonitor(unittest.TestCase):
    def test_parse_iso_datetime_adds_timezone(self) -> None:
        naive = parse_iso_datetime("2024-01-01T12:00:00")
        aware = parse_iso_datetime("2024-01-01T12:00:00+01:00")
        self.assertEqual(naive.tzinfo, timezone.utc)
        self.assertEqual(aware.utcoffset(), timedelta(hours=1))

    def test_haversine_distance(self) -> None:
        berlin = (52.5200, 13.4050)
        hamburg = (53.5511, 9.9937)
        distance = haversine_distance_km(*berlin, *hamburg)
        self.assertAlmostEqual(distance, 255, delta=5)

    def test_load_latest_locations(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "locations.csv"
            path.write_text(
                "vin,latitude,longitude,timestamp\n"
                "A,52.0,13.0,2024-01-01T10:00:00\n"
                "A,52.1,13.1,2024-01-01T12:00:00\n"
            )
            latest = load_latest_locations(path)
            self.assertEqual(latest["A"].latitude, 52.1)
            self.assertEqual(latest["A"].timestamp, parse_iso_datetime("2024-01-01T12:00:00"))

    def test_assess_bookings_uses_nearest_station(self) -> None:
        stations = {
            "S1": Station("S1", "Ost", 52.0, 13.0),
            "S2": Station("S2", "West", 52.5, 13.5),
        }
        location = LocationSample("VIN1", 52.2, 13.2, parse_iso_datetime("2024-01-01T08:00:00"))
        booking = Booking("VIN1", parse_iso_datetime("2024-01-01T10:00:00"), None)
        result = assess_bookings([booking], {"VIN1": location}, stations, average_speed_kmh=60)[0]
        self.assertEqual(result.station_id, "S1")
        self.assertTrue(result.can_reach)

    def test_format_report_outputs_csv(self) -> None:
        assessment = assess_bookings(
            [
                Booking(
                    vin="VIN2",
                    return_time=parse_iso_datetime("2024-01-01T10:00:00"),
                    station_id="S1",
                )
            ],
            {"VIN2": LocationSample("VIN2", 52.0, 13.0, parse_iso_datetime("2024-01-01T08:00:00"))},
            {"S1": Station("S1", "Ost", 52.0, 13.0)},
            average_speed_kmh=40,
        )
        csv_output = format_report(assessment)
        self.assertIn("VIN2", csv_output)
        self.assertIn("True", csv_output)

    def test_loaders_from_csv(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            stations = tmp / "stations.csv"
            stations.write_text("station_id,name,latitude,longitude\nS1,Ost,52,13\n")
            locations = tmp / "locations.csv"
            locations.write_text("vin,latitude,longitude,timestamp\nV1,52,13,2024-01-01T08:00:00\n")
            bookings = tmp / "bookings.csv"
            bookings.write_text("vin,return_time,station_id\nV1,2024-01-01T10:00:00,S1\n")

            loaded_stations = load_stations(stations)
            loaded_locations = load_latest_locations(locations)
            loaded_bookings = load_bookings(bookings)

            self.assertEqual(loaded_stations["S1"].name, "Ost")
            self.assertEqual(loaded_locations["V1"].vin, "V1")
            self.assertEqual(loaded_bookings[0].station_id, "S1")


if __name__ == "__main__":
    unittest.main()
