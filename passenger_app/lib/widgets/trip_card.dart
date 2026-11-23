import 'package:flutter/material.dart';
import '../models/trip.dart';

class TripCard extends StatelessWidget {
  final Trip trip;
  const TripCard({super.key, required this.trip});

  @override
  Widget build(BuildContext context) {
    final isFull = trip.availableSeats <= 0;
    final availabilityColor = isFull ? Colors.red : trip.availableSeats <= 5 ? Colors.orange : Colors.green;
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      elevation: 0,
      color: Colors.white,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(18), side: BorderSide(color: Colors.grey.shade200)),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Container(padding: const EdgeInsets.all(10), decoration: BoxDecoration(color: const Color(0xFFE8F1FF), borderRadius: BorderRadius.circular(12)), child: const Icon(Icons.directions_bus_rounded, color: Color(0xFF174EA6))),
            const SizedBox(width: 12),
            Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(trip.operatorName, style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 15)),
              Text(trip.vehicleType, style: TextStyle(color: Colors.grey.shade600, fontSize: 13)),
            ])),
            Text(trip.departureTime, style: const TextStyle(fontSize: 17, fontWeight: FontWeight.bold)),
          ]),
          const SizedBox(height: 16),
          Row(children: [
            Expanded(child: _location(trip.origin, 'From')),
            const Icon(Icons.arrow_forward_rounded, color: Color(0xFF174EA6)),
            const SizedBox(width: 8),
            Expanded(child: _location(trip.destination, 'To')),
          ]),
          const SizedBox(height: 14),
          Row(children: [
            Icon(isFull ? Icons.event_busy : Icons.event_seat, size: 18, color: availabilityColor),
            const SizedBox(width: 6),
            Text(isFull ? 'No seats available' : '${trip.availableSeats} seats available', style: TextStyle(color: availabilityColor, fontWeight: FontWeight.w600)),
            const Spacer(),
            Text('${trip.totalSeats} seats total', style: TextStyle(color: Colors.grey.shade600, fontSize: 12)),
          ]),
        ]),
      ),
    );
  }

  Widget _location(String name, String label) => Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
    Text(label, style: TextStyle(color: Colors.grey.shade500, fontSize: 11)),
    const SizedBox(height: 3),
    Text(name, style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600)),
  ]);
}
