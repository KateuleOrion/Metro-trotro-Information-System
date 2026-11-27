
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../data/local_database.dart';
import '../data/trip_repository.dart';
import '../models/trip.dart';
import '../services/trip_search_service.dart';
import '../widgets/trip_card.dart';
import 'vehicle_map_screen.dart';
import 'my_bookings_screen.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  final _originController = TextEditingController();
  final _destinationController = TextEditingController();

  final _repository = TripRepository(LocalDatabase.instance);
  final _tripSearchService = TripSearchService();

  List<Trip> _trips = [];

  bool _loading = true;
  bool _usingOfflineData = false;

  DateTime? _lastUpdated;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadTrips();
  }

  Future<void> _loadTrips({bool search = false}) async {
    setState(() {
      _loading = true;
      _error = null;
    });

    final origin = search ? _originController.text.trim() : '';
    final destination =
        search ? _destinationController.text.trim() : '';

    try {
      final response = await _tripSearchService.searchTrips(
        origin: origin,
        destination: destination,
      );

      final List<Trip> liveTrips = [];

      final results = response['results'];

      if (results is List) {
        for (final result in results) {
          if (result is! Map) continue;

          final routeData = result['route'];
          final vehiclesData = result['vehicles'];

          if (routeData is! Map || vehiclesData is! List) {
            continue;
          }

          final route = Map<String, dynamic>.from(routeData);

          for (final vehicleData in vehiclesData) {
            if (vehicleData is! Map) continue;

            final vehicle =
                Map<String, dynamic>.from(vehicleData);

            liveTrips.add(
              Trip.fromApi(
                route: route,
                vehicle: vehicle,
              ),
            );
          }
        }
      }

      DateTime? serverUpdateTime;

      if (response['last_updated'] != null) {
        serverUpdateTime = DateTime.tryParse(
          response['last_updated'].toString(),
        );
      }

      if (!mounted) return;

      setState(() {
        _trips = liveTrips;
        _lastUpdated = serverUpdateTime;
        _usingOfflineData = false;
        _loading = false;
      });
    } catch (e) {
      try {
        final savedTrips = await _repository.search(
          origin: origin.isEmpty ? null : origin,
          destination:
              destination.isEmpty ? null : destination,
        );

        final syncTime = await _repository.lastSyncTime();

        if (!mounted) return;

        setState(() {
          _trips = savedTrips;
          _lastUpdated = syncTime;
          _usingOfflineData = true;
          _loading = false;
          _error = savedTrips.isEmpty
              ? 'The server is unavailable and no saved trips were found.'
              : null;
        });
      } catch (localError) {
        if (!mounted) return;

        setState(() {
          _trips = [];
          _usingOfflineData = true;
          _loading = false;
          _error = 'Could not load trip information.';
        });
      }
    }
  }

  @override
  void dispose() {
    _originController.dispose();
    _destinationController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final timeText = _lastUpdated == null
        ? 'No update time available'
        : 'Last updated ${DateFormat('MMM d, h:mm a').format(_lastUpdated!.toLocal())}';

    return Scaffold(
      backgroundColor: const Color(0xFFF5F7FB),

      appBar: AppBar(
        backgroundColor: const Color(0xFF123C75),
        foregroundColor: Colors.white,
        title: const Text(
          'Trip Finder',
          style: TextStyle(fontWeight: FontWeight.bold),
        ),
        actions: [
          // MY BOOKINGS
          IconButton(
            tooltip: 'My Bookings',
            icon: const Icon(Icons.confirmation_number_outlined),
            onPressed: () {
              Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (context) => const MyBookingsScreen(),
                ),
              );
            },
          ),

          // REFRESH TRIPS
          IconButton(
            tooltip: 'Refresh trips',
            onPressed: () => _loadTrips(search: true),
            icon: const Icon(Icons.refresh),
          ),

          // TRACK VEHICLES
          IconButton(
            tooltip: 'Track vehicles',
            icon: const Icon(Icons.map_outlined),
            onPressed: () {
              Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (context) => VehicleMapScreen(),
                ),
              );
            },
          ),
        ],
      ),

      body: RefreshIndicator(
        onRefresh: () => _loadTrips(search: true),
        child: ListView(
          padding: const EdgeInsets.fromLTRB(16, 18, 16, 28),
          children: [
            Container(
              padding: const EdgeInsets.all(18),
              decoration: BoxDecoration(
                color: const Color(0xFF123C75),
                borderRadius: BorderRadius.circular(22),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'Where are you going?',
                    style: TextStyle(
                      color: Colors.white,
                      fontSize: 21,
                      fontWeight: FontWeight.bold,
                    ),
                  ),

                  const SizedBox(height: 6),

                  const Text(
                    'Find routes and available vehicles.',
                    style: TextStyle(color: Colors.white70),
                  ),

                  const SizedBox(height: 18),

                  _searchField(
                    _originController,
                    'Departure station',
                    Icons.trip_origin,
                  ),

                  const SizedBox(height: 10),

                  _searchField(
                    _destinationController,
                    'Destination',
                    Icons.location_on_outlined,
                  ),

                  const SizedBox(height: 12),

                  SizedBox(
                    width: double.infinity,
                    child: FilledButton(
                      style: FilledButton.styleFrom(
                        backgroundColor: const Color(0xFFFFC857),
                        foregroundColor: const Color(0xFF182B49),
                        padding: const EdgeInsets.symmetric(
                          vertical: 14,
                        ),
                      ),
                      onPressed: _loading
                          ? null
                          : () => _loadTrips(search: true),
                      child: const Text(
                        'Search trips',
                        style: TextStyle(
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ),
                  ),

                  TextButton(
                    onPressed: _loading
                        ? null
                        : () {
                            _originController.clear();
                            _destinationController.clear();
                            _loadTrips();
                          },
                    child: const Text(
                      'Show all trips',
                      style: TextStyle(color: Colors.white70),
                    ),
                  ),
                ],
              ),
            ),

            const SizedBox(height: 14),

            Container(
              padding: const EdgeInsets.symmetric(
                horizontal: 12,
                vertical: 10,
              ),
              decoration: BoxDecoration(
                color: _usingOfflineData
                    ? const Color(0xFFFFF4D7)
                    : const Color(0xFFE5F5EA),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Row(
                children: [
                  Icon(
                    _usingOfflineData
                        ? Icons.cloud_off_outlined
                        : Icons.cloud_done_outlined,
                    color: _usingOfflineData
                        ? const Color(0xFF8A5A00)
                        : const Color(0xFF247A45),
                    size: 18,
                  ),

                  const SizedBox(width: 8),

                  Expanded(
                    child: Text(
                      _usingOfflineData
                          ? 'Offline information • $timeText'
                          : 'Connected to server • $timeText',
                      style: TextStyle(
                        color: _usingOfflineData
                            ? const Color(0xFF704A00)
                            : const Color(0xFF247A45),
                        fontSize: 12,
                      ),
                    ),
                  ),
                ],
              ),
            ),

            const SizedBox(height: 22),

            Row(
              children: [
                const Expanded(
                  child: Text(
                    'Available vehicles',
                    style: TextStyle(
                      fontSize: 19,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),

                Text(
                  '${_trips.length} found',
                  style: TextStyle(color: Colors.grey.shade600),
                ),
              ],
            ),

            const SizedBox(height: 12),

            if (_loading)
              const Center(
                child: Padding(
                  padding: EdgeInsets.all(32),
                  child: CircularProgressIndicator(),
                ),
              )
            else if (_error != null)
              Center(
                child: Padding(
                  padding: const EdgeInsets.all(24),
                  child: Text(
                    _error!,
                    textAlign: TextAlign.center,
                  ),
                ),
              )
            else if (_trips.isEmpty)
              const Center(
                child: Padding(
                  padding: EdgeInsets.all(28),
                  child: Text(
                    'No vehicles are currently available for this search.',
                    textAlign: TextAlign.center,
                  ),
                ),
              )
            else
              ..._trips.map(
                (trip) => TripCard(trip: trip),
              ),

            const SizedBox(height: 10),

            const Text(
              'Vehicle availability may change. Confirm details with station staff before travelling.',
              style: TextStyle(
                color: Colors.grey,
                fontSize: 12,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _searchField(
    TextEditingController controller,
    String hint,
    IconData icon,
  ) {
    return TextField(
      controller: controller,
      textCapitalization: TextCapitalization.words,
      decoration: InputDecoration(
        hintText: hint,
        prefixIcon: Icon(
          icon,
          color: const Color(0xFF174EA6),
        ),
        filled: true,
        fillColor: Colors.white,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(13),
          borderSide: BorderSide.none,
        ),
        contentPadding: const EdgeInsets.symmetric(
          vertical: 14,
        ),
      ),
    );
  }
}
