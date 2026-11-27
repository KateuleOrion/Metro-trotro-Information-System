
import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';
import 'package:http/http.dart' as http;

class VehicleMapScreen extends StatefulWidget {
  const VehicleMapScreen({super.key});

  @override
  State<VehicleMapScreen> createState() => _VehicleMapScreenState();
}

class _VehicleMapScreenState extends State<VehicleMapScreen> {
  // Android emulator address for a backend running on your computer.
  // For a physical phone, replace this with your computer's local IPv4 address.
  static const String baseUrl = 'http://10.0.2.2:8000';

  final MapController _mapController = MapController();

  List<Map<String, dynamic>> _vehicles = [];
  bool _loading = true;
  String? _error;
  DateTime? _lastFetched;
  Timer? _refreshTimer;

  @override
  void initState() {
    super.initState();

    _loadVehicles();

    // Refresh vehicle positions every 20 seconds.
    _refreshTimer = Timer.periodic(
      const Duration(seconds: 20),
      (_) => _loadVehicles(),
    );
  }

  @override
  void dispose() {
    _refreshTimer?.cancel();
    _mapController.dispose();
    super.dispose();
  }

  Future<void> _loadVehicles() async {
    try {
      final response = await http
          .get(Uri.parse('$baseUrl/tracking/vehicles'))
          .timeout(const Duration(seconds: 15));

      if (response.statusCode != 200) {
        throw Exception(
          'Server returned status ${response.statusCode}',
        );
      }

      final data = jsonDecode(response.body) as Map<String, dynamic>;
      final List<dynamic> results = data['vehicles'] ?? [];

      final vehicles = results
          .map((item) => Map<String, dynamic>.from(item as Map))
          .where((vehicle) =>
              vehicle['latitude'] != null &&
              vehicle['longitude'] != null)
          .toList();

      if (!mounted) return;

      setState(() {
        _vehicles = vehicles;
        _lastFetched = DateTime.now();
        _loading = false;
        _error = null;
      });
    } catch (e) {
      if (!mounted) return;

      setState(() {
        _loading = false;
        _error = 'Unable to load vehicle locations. Check your connection.';
      });
    }
  }

  double _number(dynamic value) {
    if (value is num) return value.toDouble();
    return double.tryParse(value?.toString() ?? '') ?? 0;
  }

  String _directionLabel(String? direction) {
    switch (direction) {
      case 'approaching':
        return 'Approaching destination';
      case 'moving_away':
        return 'Moving away from destination';
      case 'stopped':
        return 'Stopped';
      case 'arrived':
        return 'Arrived';
      case 'no_destination':
        return 'Destination location unavailable';
      default:
        return 'Direction unknown';
    }
  }

  Color _vehicleColor(Map<String, dynamic> vehicle) {
    if (vehicle['stale'] == true) return Colors.grey;

    switch (vehicle['direction']) {
      case 'approaching':
        return Colors.green;
      case 'moving_away':
        return Colors.orange;
      case 'arrived':
        return Colors.blue;
      case 'stopped':
        return Colors.deepOrange;
      default:
        return Colors.grey;
    }
  }

  void _showVehicleDetails(Map<String, dynamic> vehicle) {
    final bool stale = vehicle['stale'] == true;
    final distance = vehicle['distance_km'];
    final eta = vehicle['eta_minutes'];
    final speed = vehicle['speed_kmh'];
    final recordedAt = vehicle['recorded_at'];

    final recordedTime = recordedAt == null
        ? 'Unknown'
        : DateTime.tryParse(recordedAt.toString())
                ?.toLocal()
                .toString() ??
            recordedAt.toString();

    showModalBottomSheet(
      context: context,
      showDragHandle: true,
      builder: (context) {
        return Padding(
          padding: const EdgeInsets.fromLTRB(20, 8, 20, 24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                vehicle['registration_number']?.toString() ??
                    'Unknown vehicle',
                style: Theme.of(context).textTheme.titleLarge,
              ),
              const SizedBox(height: 8),
              Text('Route: ${vehicle['route_name'] ?? 'Unknown'}'),
              Text('Destination: ${vehicle['destination'] ?? 'Unknown'}'),
              const Divider(height: 24),

              Text(
                stale
                    ? 'No recent signal'
                    : _directionLabel(vehicle['direction']?.toString()),
                style: TextStyle(
                  fontWeight: FontWeight.bold,
                  color: stale ? Colors.grey : _vehicleColor(vehicle),
                ),
              ),

              const SizedBox(height: 8),

              Text(
                'Distance to destination: '
                '${distance == null ? 'Unavailable' : '${_number(distance).toStringAsFixed(2)} km'}',
              ),

              Text(
                'Estimated arrival: '
                '${eta == null ? 'Unavailable' : '$eta minutes'}',
              ),

              Text(
                'Reported speed: '
                '${speed == null ? 'Unavailable' : '${_number(speed).toStringAsFixed(1)} km/h'}',
              ),

              Text('Last reported: $recordedTime'),

              if (stale)
                const Padding(
                  padding: EdgeInsets.only(top: 12),
                  child: Text(
                    'This location is more than five minutes old. '
                    'The vehicle may have moved since it was reported.',
                    style: TextStyle(color: Colors.red),
                  ),
                ),
            ],
          ),
        );
      },
    );
  }

  List<Marker> _buildMarkers() {
    return _vehicles.map((vehicle) {
      final point = LatLng(
        _number(vehicle['latitude']),
        _number(vehicle['longitude']),
      );

      return Marker(
        point: point,
        width: 55,
        height: 55,
        child: GestureDetector(
          onTap: () => _showVehicleDetails(vehicle),
          child: Icon(
            Icons.directions_bus,
            color: _vehicleColor(vehicle),
            size: 38,
          ),
        ),
      );
    }).toList();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Live Vehicle Tracking'),
        actions: [
          IconButton(
            onPressed: _loadVehicles,
            tooltip: 'Refresh locations',
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: Stack(
        children: [
          FlutterMap(
            mapController: _mapController,
            options: const MapOptions(
              initialCenter: LatLng(7.9465, -1.0232),
              initialZoom: 6.5,
              minZoom: 5,
              maxZoom: 18,
            ),
            children: [
              TileLayer(
                urlTemplate:
                    'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
                userAgentPackageName: 'com.example.passenger_app',
              ),
              MarkerLayer(
                markers: _buildMarkers(),
              ),
            ],
          ),

          // OpenStreetMap attribution.
          Positioned(
            bottom: 5,
            left: 5,
            child: Container(
              color: Colors.white.withValues(alpha: 0.85),
              padding: const EdgeInsets.all(4),
              child: const Text(
                '© OpenStreetMap contributors',
                style: TextStyle(fontSize: 10),
              ),
            ),
          ),

          if (_loading)
            const Center(
              child: CircularProgressIndicator(),
            ),

          if (_error != null)
            Positioned(
              top: 12,
              left: 12,
              right: 12,
              child: Card(
                color: Colors.white,
                child: Padding(
                  padding: const EdgeInsets.all(12),
                  child: Text(
                    _error!,
                    style: const TextStyle(color: Colors.red),
                  ),
                ),
              ),
            ),

          Positioned(
            top: 12,
            right: 12,
            child: Card(
              child: Padding(
                padding: const EdgeInsets.all(10),
                child: Text(
                  '${_vehicles.length} vehicles on map',
                  style: const TextStyle(fontWeight: FontWeight.bold),
                ),
              ),
            ),
          ),

          if (_lastFetched != null)
            Positioned(
              bottom: 35,
              right: 8,
              child: Card(
                child: Padding(
                  padding: const EdgeInsets.all(8),
                  child: Text(
                    'Updated: ${TimeOfDay.fromDateTime(_lastFetched!).format(context)}',
                    style: const TextStyle(fontSize: 11),
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }
}
