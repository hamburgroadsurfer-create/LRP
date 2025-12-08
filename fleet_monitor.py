from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import argparse
import csv
from math import asin, cos, radians, sin, sqrt
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


@dataclass
class Station:
    station_id: str
    name: str
    latitude: float
    longitude: float


@dataclass
class LocationSample:
    vin: str
    latitude: float
    longitude: float
    timestamp: datetime


@dataclass
class Booking:
    vin: str
    return_time: datetime
    station_id: Optional[str]


@dataclass
class BookingAssessment:
    vin: str
    booking_time: datetime
    station_id: str
    station_name: str
    distance_km: float
    travel_hours: float
    hours_until_booking: float
    can_reach: bool
    status: str


def parse_iso_datetime(value: str) -> datetime:
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    d_lat = radians(lat2 - lat1)
    d_lon = radians(lon2 - lon1)
    a = sin(d_lat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(d_lon / 2) ** 2
    return 2 * r * asin(sqrt(a))


def load_stations(path: Path) -> Dict[str, Station]:
    stations: Dict[str, Station] = {}
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            station_id = row.get("station_id") or row.get("id")
            if not station_id:
                raise ValueError("Station rows must include a 'station_id' column")
            name = row.get("name", station_id)
            stations[station_id] = Station(
                station_id=station_id,
                name=name,
                latitude=float(row["latitude"]),
                longitude=float(row["longitude"]),
            )
    if not stations:
        raise ValueError("No stations loaded")
    return stations


def load_latest_locations(path: Path) -> Dict[str, LocationSample]:
    latest: Dict[str, LocationSample] = {}
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            vin = row.get("vin") or row.get("fin")
            if not vin:
                raise ValueError("Location rows must include a 'vin' column")
            sample_time = parse_iso_datetime(row["timestamp"])
            sample = LocationSample(
                vin=vin,
                latitude=float(row["latitude"]),
                longitude=float(row["longitude"]),
                timestamp=sample_time,
            )
            existing = latest.get(vin)
            if existing is None or sample_time > existing.timestamp:
                latest[vin] = sample
    if not latest:
        raise ValueError("No location samples loaded")
    return latest


def load_bookings(path: Path) -> List[Booking]:
    bookings: List[Booking] = []
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            vin = row.get("vin") or row.get("fin")
            if not vin:
                raise ValueError("Booking rows must include a 'vin' column")
            bookings.append(
                Booking(
                    vin=vin,
                    return_time=parse_iso_datetime(row["return_time"]),
                    station_id=row.get("station_id") or row.get("station") or None,
                )
            )
    if not bookings:
        raise ValueError("No bookings loaded")
    return bookings


def find_nearest_station(location: LocationSample, stations: Iterable[Station]) -> Tuple[Station, float]:
    nearest_station: Optional[Station] = None
    nearest_distance = float("inf")
    for station in stations:
        distance = haversine_distance_km(location.latitude, location.longitude, station.latitude, station.longitude)
        if distance < nearest_distance:
            nearest_distance = distance
            nearest_station = station
    if nearest_station is None:
        raise ValueError("No station available")
    return nearest_station, nearest_distance


def hours_between(start: datetime, end: datetime) -> float:
    delta = end - start
    return delta.total_seconds() / 3600


def assess_bookings(
    bookings: Sequence[Booking],
    locations: Dict[str, LocationSample],
    stations: Dict[str, Station],
    average_speed_kmh: float,
    buffer_hours: float = 2.0,
    max_same_day_distance_km: float = 1000.0,
    include_missing: bool = True,
) -> List[BookingAssessment]:
    if average_speed_kmh <= 0:
        raise ValueError("average_speed_kmh must be positive")
    if buffer_hours < 0:
        raise ValueError("buffer_hours cannot be negative")
    if max_same_day_distance_km <= 0:
        raise ValueError("max_same_day_distance_km must be positive")
    assessments: List[BookingAssessment] = []
    for booking in bookings:
        location = locations.get(booking.vin)
        if location is None:
            if include_missing:
                station_name = "unknown station"
                station_id = booking.station_id or "unknown"
                assessments.append(
                    BookingAssessment(
                        vin=booking.vin,
                        booking_time=booking.return_time,
                        station_id=station_id,
                        station_name=station_name,
                        distance_km=float("nan"),
                        travel_hours=float("nan"),
                        hours_until_booking=float("nan"),
                        can_reach=False,
                        status="missing_location",
                    )
                )
            continue

        if booking.station_id and booking.station_id in stations:
            station = stations[booking.station_id]
            distance_km = haversine_distance_km(
                location.latitude, location.longitude, station.latitude, station.longitude
            )
        else:
            station, distance_km = find_nearest_station(location, stations.values())

        travel_hours = distance_km / average_speed_kmh
        hours_until_booking = hours_between(location.timestamp, booking.return_time)
        same_day = location.timestamp.date() == booking.return_time.date()
        if same_day and distance_km > max_same_day_distance_km:
            can_reach = False
            status = "unreachable"
        elif travel_hours > hours_until_booking:
            can_reach = False
            status = "unreachable"
        elif hours_until_booking - travel_hours < buffer_hours:
            can_reach = True
            status = "tight"
        else:
            can_reach = True
            status = "reachable"

        assessments.append(
            BookingAssessment(
                vin=booking.vin,
                booking_time=booking.return_time,
                station_id=station.station_id,
                station_name=station.name,
                distance_km=distance_km,
                travel_hours=travel_hours,
                hours_until_booking=hours_until_booking,
                can_reach=can_reach,
                status=status,
            )
        )
    return assessments


def format_report(assessments: Sequence[BookingAssessment]) -> str:
    lines = [
        "VIN,Station,Distance_km,Travel_hours,Hours_until_booking,Can_reach,Status"
    ]
    for item in assessments:
        lines.append(
            f"{item.vin},{item.station_name} ({item.station_id}),"
            f"{item.distance_km:.2f},{item.travel_hours:.2f},{item.hours_until_booking:.2f},{item.can_reach},{item.status}"
        )
    return "\n".join(lines)


def run_report(
    locations_path: Path,
    stations_path: Path,
    bookings_path: Path,
    average_speed_kmh: float,
    buffer_hours: float,
    max_same_day_distance_km: float,
    include_missing: bool,
) -> str:
    stations = load_stations(stations_path)
    locations = load_latest_locations(locations_path)
    bookings = load_bookings(bookings_path)
    assessments = assess_bookings(
        bookings,
        locations,
        stations,
        average_speed_kmh,
        buffer_hours=buffer_hours,
        max_same_day_distance_km=max_same_day_distance_km,
        include_missing=include_missing,
    )
    return format_report(assessments)


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Bewertet, ob Fahrzeuge es rechtzeitig zu einer Station zurueck schaffen."
            " Erwartet CSV-Dateien fuer Positionen, Stationen und Buchungen."
        )
    )
    parser.add_argument("--locations", required=True, type=Path, help="CSV mit Spalten vin,latitude,longitude,timestamp")
    parser.add_argument("--stations", required=True, type=Path, help="CSV mit Spalten station_id,name,latitude,longitude")
    parser.add_argument("--bookings", required=True, type=Path, help="CSV mit Spalten vin,return_time[,station_id]")
    parser.add_argument(
        "--avg-speed-kmh",
        required=False,
        type=float,
        default=45.0,
        help="durchschnittliche Geschwindigkeit in km/h (Default: 45)",
    )
    parser.add_argument(
        "--buffer-hours",
        required=False,
        type=float,
        default=2.0,
        help="Zeitpuffer in Stunden, unterhalb dessen Fahrten als 'tight' markiert werden",
    )
    parser.add_argument(
        "--max-same-day-distance-km",
        required=False,
        type=float,
        default=1000.0,
        help="Schwelle in km fuer Rueckgaben am selben Tag; groessere Distanzen gelten als unerreichbar",
    )
    parser.add_argument(
        "--skip-missing",
        action="store_true",
        help="Buchungen ohne aktuelle Fahrzeugposition nicht listen",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = parse_args(argv)
    report = run_report(
        locations_path=args.locations,
        stations_path=args.stations,
        bookings_path=args.bookings,
        average_speed_kmh=args.avg_speed_kmh,
        buffer_hours=args.buffer_hours,
        max_same_day_distance_km=args.max_same_day_distance_km,
        include_missing=not args.skip_missing,
    )
    print(report)


if __name__ == "__main__":
    main()
