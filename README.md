# Return distance report

This repository provides a lightweight CLI to rate daily vehicle returns using VINs, station coordinates, and GNSS positions.

## How it works
- `return_report.py` reads the three daily files:
  - `Bookings_Return_Today.csv` (VIN + return station)
  - `StationsNew.CSV` (station names with latitude/longitude)
  - `TCU health vehicle data. Timestamp fields in UTC..xlsx` (VIN + GNSS lat/long)
- The script matches VINs across files, calculates the haversine distance from each vehicle to its target station, and assigns a traffic-light status:
  - **green:** distance ≤ 200 km
  - **yellow:** 200–1000 km
  - **red:** > 1000 km
  - **missing-data:** coordinates for the station or vehicle are not available
- Output is written to `return_report.csv` (ignored by Git by default).

## Usage
```bash
python return_report.py \
  --bookings Bookings_Return_Today.csv \
  --stations StationsNew.CSV \
  --positions "TCU health vehicle data. Timestamp fields in UTC..xlsx" \
  --output return_report.csv
```
Optional tuning:
- `--green-threshold` (default `200`)
- `--yellow-threshold` (default `1000`)

The script avoids external dependencies by parsing the Excel file directly.
