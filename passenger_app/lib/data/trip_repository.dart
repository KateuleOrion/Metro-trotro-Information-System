import 'package:shared_preferences/shared_preferences.dart';
import '../models/trip.dart';
import 'local_database.dart';

class TripRepository {
  final LocalDatabase database;
  TripRepository(this.database);

  Future<List<Trip>> search({String? origin, String? destination}) =>
      database.getTrips(origin: origin, destination: destination);

  // Placeholder for future API integration. On successful server sync, replace
  // local records and store the timestamp. The first version is local-only.
  Future<DateTime?> lastSyncTime() async {
    final prefs = await SharedPreferences.getInstance();
    final value = prefs.getString('last_sync');
    return value == null ? null : DateTime.tryParse(value);
  }

  Future<void> saveSyncTime(DateTime time) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('last_sync', time.toIso8601String());
  }
}
