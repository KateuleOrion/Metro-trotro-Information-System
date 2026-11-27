import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../data/local_database.dart';
import '../data/trip_repository.dart';
import '../models/trip.dart';
import '../widgets/trip_card.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});
  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  final _originController = TextEditingController();
  final _destinationController = TextEditingController();
  final _repository = TripRepository(LocalDatabase.instance);
  List<Trip> _trips = [];
  bool _loading = true;
  DateTime? _lastUpdated;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadTrips();
  }

  Future<void> _loadTrips({bool search = false}) async {
    setState(() { _loading = true; _error = null; });
    try {
      final trips = await _repository.search(
        origin: search ? _originController.text : null,
        destination: search ? _destinationController.text : null,
      );
      final syncTime = await _repository.lastSyncTime();
      if (!mounted) return;
      setState(() { _trips = trips; _lastUpdated = syncTime; _loading = false; });
    } catch (e) {
      if (!mounted) return;
      setState(() { _error = 'Could not load saved trip information.'; _loading = false; });
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
    final timeText = _lastUpdated == null ? 'Sample information • Not synced with a server yet' : 'Last updated ${DateFormat('MMM d, h:mm a').format(_lastUpdated!.toLocal())}';
    return Scaffold(
      backgroundColor: const Color(0xFFF5F7FB),
      appBar: AppBar(
        backgroundColor: const Color(0xFF123C75),
        foregroundColor: Colors.white,
        title: const Text('Trip Finder', style: TextStyle(fontWeight: FontWeight.bold)),
        actions: [IconButton(tooltip: 'Refresh saved data', onPressed: () => _loadTrips(search: true), icon: const Icon(Icons.refresh))],
      ),
      body: RefreshIndicator(onRefresh: () => _loadTrips(search: true), child: ListView(
        padding: const EdgeInsets.fromLTRB(16, 18, 16, 28),
        children: [
          Container(
            padding: const EdgeInsets.all(18),
            decoration: BoxDecoration(color: const Color(0xFF123C75), borderRadius: BorderRadius.circular(22)),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              const Text('Where are you going?', style: TextStyle(color: Colors.white, fontSize: 21, fontWeight: FontWeight.bold)),
              const SizedBox(height: 6),
              const Text('Find routes and upcoming departures.', style: TextStyle(color: Colors.white70)),
              const SizedBox(height: 18),
              _searchField(_originController, 'Departure station', Icons.trip_origin),
              const SizedBox(height: 10),
              _searchField(_destinationController, 'Destination', Icons.location_on_outlined),
              const SizedBox(height: 12),
              SizedBox(width: double.infinity, child: FilledButton(
                style: FilledButton.styleFrom(backgroundColor: const Color(0xFFFFC857), foregroundColor: const Color(0xFF182B49), padding: const EdgeInsets.symmetric(vertical: 14)),
                onPressed: () => _loadTrips(search: true),
                child: const Text('Search trips', style: TextStyle(fontWeight: FontWeight.bold)),
              )),
              TextButton(onPressed: () { _originController.clear(); _destinationController.clear(); _loadTrips(); }, child: const Text('Show all trips', style: TextStyle(color: Colors.white70))),
            ]),
          ),
          const SizedBox(height: 14),
          Container(padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10), decoration: BoxDecoration(color: const Color(0xFFFFF4D7), borderRadius: BorderRadius.circular(12)), child: Row(children: [
            const Icon(Icons.cloud_off_outlined, color: Color(0xFF8A5A00), size: 18), const SizedBox(width: 8),
            Expanded(child: Text(timeText, style: const TextStyle(color: Color(0xFF704A00), fontSize: 12))),
          ])),
          const SizedBox(height: 22),
          Row(children: [const Expanded(child: Text('Available trips', style: TextStyle(fontSize: 19, fontWeight: FontWeight.bold))), Text('${_trips.length} found', style: TextStyle(color: Colors.grey.shade600))]),
          const SizedBox(height: 12),
          if (_loading) const Center(child: Padding(padding: EdgeInsets.all(32), child: CircularProgressIndicator()))
          else if (_error != null) Center(child: Padding(padding: const EdgeInsets.all(24), child: Text(_error!, textAlign: TextAlign.center)))
          else if (_trips.isEmpty) const Center(child: Padding(padding: EdgeInsets.all(28), child: Text('No trips match your search. Try different stations.')))
          else ..._trips.map((trip) => TripCard(trip: trip)),
          const SizedBox(height: 10),
          const Text('Availability is based on the last information saved on this device. Confirm details with station staff.', style: TextStyle(color: Colors.grey, fontSize: 12)),
        ],
      )),
    );
  }

  Widget _searchField(TextEditingController controller, String hint, IconData icon) => TextField(
    controller: controller,
    textCapitalization: TextCapitalization.words,
    decoration: InputDecoration(
      hintText: hint,
      prefixIcon: Icon(icon, color: const Color(0xFF174EA6)),
      filled: true,
      fillColor: Colors.white,
      border: OutlineInputBorder(borderRadius: BorderRadius.circular(13), borderSide: BorderSide.none),
      contentPadding: const EdgeInsets.symmetric(vertical: 14),
    ),
  );
}
