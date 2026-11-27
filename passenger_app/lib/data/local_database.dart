import 'package:path/path.dart' as p;
import 'package:sqflite/sqflite.dart';
import '../models/trip.dart';

class LocalDatabase {
  LocalDatabase._();
  static final LocalDatabase instance = LocalDatabase._();
  Database? _db;

  Future<Database> get database async {
    if (_db != null) return _db!;
    final dbPath = await getDatabasesPath();
    _db = await openDatabase(
      p.join(dbPath, 'passenger_app.db'),
      version: 1,
      onCreate: (db, version) async {
        await db.execute('''
          CREATE TABLE trips (
            id INTEGER PRIMARY KEY,
            origin TEXT NOT NULL,
            destination TEXT NOT NULL,
            operatorName TEXT NOT NULL,
            vehicleType TEXT NOT NULL,
            departureTime TEXT NOT NULL,
            totalSeats INTEGER NOT NULL,
            availableSeats INTEGER NOT NULL,
            status TEXT NOT NULL
          )
        ''');
      },
    );
    await _seedIfEmpty(_db!);
    return _db!;
  }

  Future<void> _seedIfEmpty(Database db) async {
    final count = Sqflite.firstIntValue(await db.rawQuery('SELECT COUNT(*) FROM trips')) ?? 0;
    if (count > 0) return;
    final sampleTrips = <Trip>[
      const Trip(id: 1, origin: 'Accra', destination: 'Kumasi', operatorName: 'Demo Transport', vehicleType: 'VIP Coach', departureTime: '06:30', totalSeats: 45, availableSeats: 12, status: 'Scheduled'),
      const Trip(id: 2, origin: 'Accra', destination: 'Kumasi', operatorName: 'Demo Transport', vehicleType: 'Sprinter', departureTime: '07:15', totalSeats: 25, availableSeats: 4, status: 'Scheduled'),
      const Trip(id: 3, origin: 'Accra', destination: 'Cape Coast', operatorName: 'Coastal Travels', vehicleType: 'Bus', departureTime: '08:00', totalSeats: 40, availableSeats: 21, status: 'Scheduled'),
      const Trip(id: 4, origin: 'Kumasi', destination: 'Accra', operatorName: 'Demo Transport', vehicleType: 'VIP Coach', departureTime: '09:00', totalSeats: 45, availableSeats: 0, status: 'Full'),
      const Trip(id: 5, origin: 'Accra', destination: 'Tamale', operatorName: 'Northern Line', vehicleType: 'Coach', departureTime: '18:30', totalSeats: 50, availableSeats: 17, status: 'Scheduled'),
      const Trip(id: 6, origin: 'Cape Coast', destination: 'Accra', operatorName: 'Coastal Travels', vehicleType: 'Bus', departureTime: '10:45', totalSeats: 40, availableSeats: 8, status: 'Scheduled'),
    ];
    final batch = db.batch();
    for (final trip in sampleTrips) {
      batch.insert('trips', trip.toMap());
    }
    await batch.commit(noResult: true);
  }

  Future<List<Trip>> getTrips({String? origin, String? destination}) async {
    final db = await database;
    final clauses = <String>[];
    final args = <Object>[];
    if (origin != null && origin.trim().isNotEmpty) {
      clauses.add('LOWER(origin) LIKE ?');
      args.add('%${origin.trim().toLowerCase()}%');
    }
    if (destination != null && destination.trim().isNotEmpty) {
      clauses.add('LOWER(destination) LIKE ?');
      args.add('%${destination.trim().toLowerCase()}%');
    }
    final where = clauses.isEmpty ? null : clauses.join(' AND ');
    final rows = await db.query('trips', where: where, whereArgs: args, orderBy: 'departureTime ASC');
    return rows.map(Trip.fromMap).toList();
  }

  Future<void> replaceTrips(List<Trip> trips) async {
    final db = await database;
    await db.transaction((txn) async {
      await txn.delete('trips');
      for (final trip in trips) {
        await txn.insert('trips', trip.toMap(), conflictAlgorithm: ConflictAlgorithm.replace);
      }
    });
  }
}
