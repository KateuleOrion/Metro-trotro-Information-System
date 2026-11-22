class Trip {
  final int id;
  final String origin;
  final String destination;
  final String operatorName;
  final String vehicleType;
  final String departureTime;
  final int totalSeats;
  final int availableSeats;
  final String status;

  const Trip({
    required this.id,
    required this.origin,
    required this.destination,
    required this.operatorName,
    required this.vehicleType,
    required this.departureTime,
    required this.totalSeats,
    required this.availableSeats,
    required this.status,
  });

  factory Trip.fromMap(Map<String, Object?> map) => Trip(
        id: map['id'] as int,
        origin: map['origin'] as String,
        destination: map['destination'] as String,
        operatorName: map['operatorName'] as String,
        vehicleType: map['vehicleType'] as String,
        departureTime: map['departureTime'] as String,
        totalSeats: map['totalSeats'] as int,
        availableSeats: map['availableSeats'] as int,
        status: map['status'] as String,
      );

  Map<String, Object?> toMap() => {
        'id': id,
        'origin': origin,
        'destination': destination,
        'operatorName': operatorName,
        'vehicleType': vehicleType,
        'departureTime': departureTime,
        'totalSeats': totalSeats,
        'availableSeats': availableSeats,
        'status': status,
      };
}
