# Return distance report

This repository provides two ways to rate daily vehicle returns using VINs, station coordinates, and GNSS positions:

1. **Browser tool (no Installation/Admin rights needed):** open `return_report_web.html` locally and drop the three daily files. All parsing and distance math run client-side in JavaScript.
2. **Python CLI:** `return_report.py` (dependency-free) if Python is available.
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

## Browser usage (works without Python)

If your laptop blocks Python or installation of tools, use the browser workflow. Nothing needs to be installed.

1. Open `return_report_web.html` in any modern browser (double-click the file or drag it into a tab). On Windows you can also double-click `return_report_web.bat`, which opens the HTML for you.
2. Select the three daily files:
   - `Bookings_Return_Today.csv` (VIN + return station)
   - `StationsNew.CSV` (station names with latitude/longitude)
   - `TCU health vehicle data. Timestamp fields in UTC..xlsx` (VIN + GNSS lat/long; CSV also works)
3. Adjust thresholds if needed (default: green ≤ 200 km, yellow ≤ 1000 km).
4. Click **„Ampel berechnen“**. The table shows VIN, target station, distance, and status. Use **CSV herunterladen** to export the result.

All processing happens in the browser; no files leave your machine and no admin rights are required.

## Python CLI usage
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
