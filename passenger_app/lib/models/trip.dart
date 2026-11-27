
class Trip {
  final int vehicleId;
  final bool isLive;

  final int routeId;
  final String origin;
  final String destination;
  final String routeName;

  final String operatorName;
  final String vehicleType;
  final String departureTime;

  final int totalSeats;
  final int availableSeats;

  final String status;

  const Trip({
    int? id,
    int? vehicleId,
    this.isLive = false,
    this.routeId = 0,
    required this.origin,
    required this.destination,
    this.routeName = '',
    required this.operatorName,
    required this.vehicleType,
    required this.departureTime,
    required this.totalSeats,
    required this.availableSeats,
    required this.status,
  }) : vehicleId = vehicleId ?? id ?? 0;

  factory Trip.fromApi({
    required Map<String, dynamic> route,
    required Map<String, dynamic> vehicle,
  }) {
    return Trip(
      vehicleId: vehicle['vehicle_id'] as int,
      isLive: true,
      routeId: route['route_id'] as int,
      origin: route['origin']?.toString() ?? '',
      destination: route['destination']?.toString() ?? '',
      routeName: route['route_name']?.toString() ?? '',
      operatorName:
          vehicle['registration_number']?.toString() ?? 'Unknown vehicle',
      vehicleType: 'Trotro',
      departureTime:
          vehicle['arrival_time']?.toString() ?? 'Not scheduled',
      totalSeats: 0,
      availableSeats: vehicle['available_seats'] as int? ?? 0,
      status: vehicle['status_label']?.toString() ?? 'Unknown',
    );
  }

  factory Trip.fromMap(Map<String, Object?> map) {
    return Trip(
      id: map['id'] as int?,
      vehicleId: map['vehicleId'] as int?,
      isLive: false,
      routeId: map['routeId'] as int? ?? 0,
      origin: map['origin'] as String,
      destination: map['destination'] as String,
      routeName: map['routeName'] as String? ?? '',
      operatorName: map['operatorName'] as String,
      vehicleType: map['vehicleType'] as String,
      departureTime: map['departureTime'] as String,
      totalSeats: map['totalSeats'] as int,
      availableSeats: map['availableSeats'] as int,
      status: map['status'] as String,
    );
  }

  Map<String, Object?> toMap() => {
        'id': vehicleId,
        'vehicleId': vehicleId,
        'routeId': routeId,
        'origin': origin,
        'destination': destination,
        'routeName': routeName,
        'operatorName': operatorName,
        'vehicleType': vehicleType,
        'departureTime': departureTime,
        'totalSeats': totalSeats,
        'availableSeats': availableSeats,
        'status': status,
      };
}
