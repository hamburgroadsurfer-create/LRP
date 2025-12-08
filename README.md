# LRP Fleet Monitor

Ein kleines Python-Tool, das aktuelle Fahrzeugpositionen, Stationskoordinaten und Buchungsdaten aus CSV-Dateien einliest und abschätzt, ob jedes Fahrzeug rechtzeitig zu seiner nächsten Station zurückkehren kann. Die Berechnung nutzt die Haversine-Distanz, einen frei wählbaren Durchschnittstempo-Parameter sowie einstellbare Heuristiken (z. B. maximale Tagesdistanz und Zeitpuffer), um die Buchungen als **reachable**, **tight** oder **unreachable** zu markieren.

## Installation
Python 3.10+ genügt; es werden keine zusätzlichen Bibliotheken benötigt. Optional können die Unittests mit `python -m unittest` ausgeführt werden.

## CSV-Formate
Alle Dateien müssen Kopfzeilen besitzen.

### Locations (PowerBI-Export)
- `vin` (oder `fin`): eindeutige Fahrzeug-ID
- `latitude`, `longitude`: Koordinaten in Dezimalgrad
- `timestamp`: ISO-8601 (ohne Zeitzone wird als UTC interpretiert)

Nur die jüngste Position pro VIN wird genutzt.

### Stations
- `station_id` (alternativ `id`): eindeutige Stations-ID
- `name`: Klartextname der Station
- `latitude`, `longitude`: Koordinaten in Dezimalgrad

### Bookings
- `vin` (oder `fin`): zugehöriges Fahrzeug
- `return_time`: nächster Rückgabezeitpunkt (ISO-8601)
- `station_id` (optional): Zielstation; ohne Angabe wird die nächstgelegene Station anhand der GPS-Position gewählt

## Nutzung
Beispielaufruf mit Standardgeschwindigkeit 45 km/h:

```bash
python fleet_monitor.py \
  --locations data/locations.csv \
  --stations data/stations.csv \
  --bookings data/bookings.csv \
  --avg-speed-kmh 50 \
  --buffer-hours 2 \
  --max-same-day-distance-km 1000 \
  [--skip-missing]
```

Die Ausgabe ist eine kleine CSV-Tabelle mit Distanz, benötigter Fahrzeit, verbleibender Zeit bis zur Buchung und einer Ja/Nein-Aussage (`can_reach`) plus einem Status-Feld (`reachable`, `tight`, `unreachable`, `missing_location`). Mit `--skip-missing` können Buchungen ohne aktuelle Fahrzeugposition unterdrückt werden, andernfalls erscheinen sie als `missing_location` mit unerreichbar-Markierung.

### Beispiel mit den beigefügten CSVs
Im Ordner `examples/` liegen kleine Testdateien ohne externe Abhängigkeiten (nur die Python-Standardbibliothek wird benötigt). Du kannst das Tool damit direkt ausprobieren:

```bash
python fleet_monitor.py \
  --locations examples/locations_sample.csv \
  --stations examples/stations_sample.csv \
  --bookings examples/bookings_sample.csv \
  --avg-speed-kmh 50
```

Die Ausgabe erscheint auf STDOUT; bei Bedarf kannst du sie in eine Datei umleiten:

```bash
python fleet_monitor.py ... > ergebnis.csv
```

## Architektur
- `fleet_monitor.py` enthält die Datamodelle, CSV-Parser und die Bewertungslogik.
- Die Distanz wird per Haversine-Formel berechnet; Reisezeit = Distanz / Durchschnittstempo.
- Offene Buchungen ohne bekannte Station werden der nächstgelegenen Station zugeordnet.

## Tests
```bash
python -m unittest
```
