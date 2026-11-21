# passenger_app

Flutter passenger mobile-app prototype for route searching, trip availability and departure browsing.

## Features
- Search trips by origin and destination
- Displays vehicle/operator, departure time, route, total and available seats
- Offline local database (SQLite)
- Sample records seeded into SQLite on first run
- Shows the local/sample-data freshness status
- Refresh button and pull-to-refresh

## Setup
1. Install Flutter SDK and Android Studio (or another supported Flutter IDE).
2. From this folder, run `flutter pub get`.
3. Run `flutter run` on an emulator or connected device.

## Current limitations
- The app currently uses demonstration data saved locally; it is not connected to a backend.
- The last-synchronised timestamp support is prepared, but a successful API sync is not implemented yet.
- Sample station names and operators should be replaced with approved project data.

## Planned integration
Implement a REST client in `lib/data/` and call it when connectivity is available. After a successful response, replace/update SQLite records and save the sync timestamp using `TripRepository.saveSyncTime()`.
