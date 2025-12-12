import argparse
import csv
import math
import zipfile
from datetime import datetime
from pathlib import Path
import xml.etree.ElementTree as ET

# XML namespace for XLSX worksheet and shared strings
_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


def _column_index(cell_ref: str) -> int:
    """Convert an Excel column reference (e.g., 'C5') to a zero-based index."""
    letters = ''.join(filter(str.isalpha, cell_ref))
    idx = 0
    for ch in letters:
        idx = idx * 26 + (ord(ch.upper()) - 64)
    return idx - 1


def _load_shared_strings(zf: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in zf.namelist():
        return []
    root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
    shared_strings = []
    for si in root.findall(f".//{_NS}si"):
        text = "".join(t.text or "" for t in si.iter(f"{_NS}t"))
        shared_strings.append(text)
    return shared_strings


def load_first_sheet(path: Path) -> list[dict[str, str]]:
    """Read the first worksheet of an XLSX file without external dependencies."""
    with zipfile.ZipFile(path) as zf:
        shared_strings = _load_shared_strings(zf)
        sheet = ET.fromstring(zf.read("xl/worksheets/sheet1.xml"))

    rows: list[list[str]] = []
    for row in sheet.findall(f".//{_NS}row"):
        idxs: list[int] = []
        values: list[str] = []
        for cell in row.findall(f"{_NS}c"):
            ref = cell.get("r") or ""
            idx = _column_index(ref)
            v_elem = cell.find(f"{_NS}v")
            if v_elem is None:
                value = ""
            elif cell.get("t") == "s":
                value = shared_strings[int(v_elem.text)]
            else:
                value = v_elem.text or ""
            idxs.append(idx)
            values.append(value)

        if not idxs:
            continue

        max_idx = max(idxs)
        row_values = [""] * (max_idx + 1)
        for idx, value in zip(idxs, values):
            row_values[idx] = value
        rows.append(row_values)

    if not rows:
        return []

    headers = [header.strip() for header in rows[0]]
    records: list[dict[str, str]] = []
    for row in rows[1:]:
        if all(cell == "" for cell in row):
            continue
        record = {headers[i]: row[i] if i < len(row) else "" for i in range(len(headers))}
        records.append(record)
    return records


def parse_float(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return None


def parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def load_positions(path: Path) -> dict[str, dict[str, float | datetime]]:
    records = load_first_sheet(path)
    positions: dict[str, dict[str, float | datetime]] = {}
    for record in records:
        vin = (record.get("vin") or "").strip().upper()
        if not vin:
            continue
        lat = parse_float(record.get("gnss_latitude"))
        lon = parse_float(record.get("gnss_longitude"))
        if lat is None or lon is None:
            continue
        timestamp = parse_timestamp(record.get("gnss_longitude_updated_at")) or parse_timestamp(
            record.get("updated_at")
        )
        existing = positions.get(vin)
        if existing is None or (
            timestamp and (existing.get("timestamp") is None or timestamp > existing["timestamp"])
        ):
            positions[vin] = {"lat": lat, "lon": lon, "timestamp": timestamp}
    return positions


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    for encoding in ("utf-8-sig", "latin-1"):
        try:
            with path.open(newline="", encoding=encoding) as f:
                return list(csv.DictReader(f))
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError("utf-8", b"", 0, 1, "Unable to decode file")


def load_stations(path: Path) -> dict[str, tuple[float, float]]:
    stations: dict[str, tuple[float, float]] = {}
    for row in _read_csv_rows(path):
        name = (row.get("Station_Fix") or row.get("Station_Master") or "").strip()
        lat = parse_float(row.get("Latitude"))
        lon = parse_float(row.get("Longitude"))
        if name and lat is not None and lon is not None:
            stations[name] = (lat, lon)
    return stations


def load_bookings(path: Path) -> list[dict[str, str]]:
    return _read_csv_rows(path)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)

    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return r * c


def classify(distance_km: float | None, green_threshold: float, yellow_threshold: float) -> str:
    if distance_km is None:
        return "missing-data"
    if distance_km <= green_threshold:
        return "green"
    if distance_km <= yellow_threshold:
        return "yellow"
    return "red"


def build_report(
    bookings_path: Path,
    positions_path: Path,
    stations_path: Path,
    output_path: Path,
    green_threshold: float,
    yellow_threshold: float,
) -> list[dict[str, str]]:
    stations = load_stations(stations_path)
    bookings = load_bookings(bookings_path)
    positions = load_positions(positions_path)

    report_rows: list[dict[str, str]] = []
    for booking in bookings:
        vin = (booking.get("vehicle_id") or booking.get("vin") or "").strip().upper()
        station_name = (booking.get("station") or booking.get("Station") or "").strip()

        station_coords = stations.get(station_name)
        vehicle_position = positions.get(vin)

        distance = None
        if station_coords and vehicle_position:
            distance = haversine_km(
                station_coords[0], station_coords[1], vehicle_position["lat"], vehicle_position["lon"]
            )

        status = classify(distance, green_threshold, yellow_threshold)
        report_rows.append(
            {
                "vin": vin,
                "station": station_name,
                "station_lat": station_coords[0] if station_coords else "",
                "station_lon": station_coords[1] if station_coords else "",
                "vehicle_lat": vehicle_position["lat"] if vehicle_position else "",
                "vehicle_lon": vehicle_position["lon"] if vehicle_position else "",
                "distance_km": round(distance, 2) if distance is not None else "",
                "status": status,
            }
        )

    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "vin",
                "station",
                "station_lat",
                "station_lon",
                "vehicle_lat",
                "vehicle_lon",
                "distance_km",
                "status",
            ],
        )
        writer.writeheader()
        writer.writerows(report_rows)

    return report_rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a daily return report with distance-based traffic light statuses."
    )
    parser.add_argument("--bookings", type=Path, default=Path("Bookings_Return_Today.csv"))
    parser.add_argument(
        "--positions",
        type=Path,
        default=Path("TCU health vehicle data. Timestamp fields in UTC..xlsx"),
    )
    parser.add_argument("--stations", type=Path, default=Path("StationsNew.CSV"))
    parser.add_argument("--output", type=Path, default=Path("return_report.csv"))
    parser.add_argument("--green-threshold", type=float, default=200.0)
    parser.add_argument("--yellow-threshold", type=float, default=1000.0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report_rows = build_report(
        bookings_path=args.bookings,
        positions_path=args.positions,
        stations_path=args.stations,
        output_path=args.output,
        green_threshold=args.green_threshold,
        yellow_threshold=args.yellow_threshold,
    )

    total = len(report_rows)
    status_counts: dict[str, int] = {}
    for row in report_rows:
        status_counts[row["status"]] = status_counts.get(row["status"], 0) + 1

    print(f"Report written to {args.output} ({total} vehicles)")
    for status, count in sorted(status_counts.items()):
        print(f"  {status}: {count}")


if __name__ == "__main__":
    main()
