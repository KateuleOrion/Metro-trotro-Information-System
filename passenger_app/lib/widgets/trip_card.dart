
import 'package:flutter/material.dart';

import '../models/trip.dart';
import '../services/booking_service.dart';

class TripCard extends StatefulWidget {
  final Trip trip;

  const TripCard({
    super.key,
    required this.trip,
  });

  @override
  State<TripCard> createState() => _TripCardState();
}

class _TripCardState extends State<TripCard> {
  final BookingService _bookingService = BookingService();

  bool _booking = false;

  Future<void> _bookSeat() async {
    final trip = widget.trip;

    if (!trip.isLive) {
      _showMessage('Booking is only available for live vehicles.');
      return;
    }

    if (trip.availableSeats <= 0) {
      _showMessage('No seats are currently available.');
      return;
    }

    final seatsBooked = await showDialog<int>(
      context: context,
      builder: (dialogContext) {
        int selectedSeats = 1;

        return StatefulBuilder(
          builder: (context, setDialogState) {
            return AlertDialog(
              title: const Text('Book seats'),
              content: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(
                    '${trip.availableSeats} seats available',
                  ),
                  const SizedBox(height: 16),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      const Text('Number of seats'),
                      Row(
                        children: [
                          IconButton(
                            onPressed: selectedSeats > 1
                                ? () {
                                    setDialogState(() {
                                      selectedSeats--;
                                    });
                                  }
                                : null,
                            icon: const Icon(Icons.remove_circle_outline),
                          ),
                          Text(
                            '$selectedSeats',
                            style: const TextStyle(
                              fontSize: 18,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                          IconButton(
                            onPressed:
                                selectedSeats < trip.availableSeats
                                    ? () {
                                        setDialogState(() {
                                          selectedSeats++;
                                        });
                                      }
                                    : null,
                            icon: const Icon(Icons.add_circle_outline),
                          ),
                        ],
                      ),
                    ],
                  ),
                ],
              ),
              actions: [
                TextButton(
                  onPressed: () {
                    Navigator.pop(dialogContext);
                  },
                  child: const Text('Cancel'),
                ),
                FilledButton(
                  onPressed: () {
                    Navigator.pop(dialogContext, selectedSeats);
                  },
                  child: const Text('Continue'),
                ),
              ],
            );
          },
        );
      },
    );

    if (seatsBooked == null || !mounted) return;

    setState(() {
      _booking = true;
    });

    try {
      final result = await _bookingService.createBooking(
        vehicleId: trip.vehicleId,
        seatsBooked: seatsBooked,
      );

      if (!mounted) return;

      final reference = result['booking_reference'] ??
          result['reference'] ??
          'Booking successful';

      _showMessage('Booking successful! Reference: $reference');
    } catch (e) {
      if (!mounted) return;

      _showMessage(
        e.toString().replaceFirst('Exception: ', ''),
      );
    } finally {
      if (mounted) {
        setState(() {
          _booking = false;
        });
      }
    }
  }

  void _showMessage(String message) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        duration: const Duration(seconds: 4),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final trip = widget.trip;

    final isFull = trip.availableSeats <= 0;

    final availabilityColor = isFull
        ? Colors.red
        : trip.availableSeats <= 5
            ? Colors.orange
            : Colors.green;

    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      elevation: 0,
      color: Colors.white,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(18),
        side: BorderSide(color: Colors.grey.shade200),
      ),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(
                    color: const Color(0xFFE8F1FF),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: const Icon(
                    Icons.directions_bus_rounded,
                    color: Color(0xFF174EA6),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        trip.operatorName,
                        style: const TextStyle(
                          fontWeight: FontWeight.w700,
                          fontSize: 15,
                        ),
                      ),
                      Text(
                        trip.vehicleType,
                        style: TextStyle(
                          color: Colors.grey.shade600,
                          fontSize: 13,
                        ),
                      ),
                    ],
                  ),
                ),
                const Icon(
                  Icons.schedule,
                  size: 16,
                  color: Colors.grey,
                ),
              ],
            ),

            const SizedBox(height: 16),

            Row(
              children: [
                Expanded(
                  child: _location(trip.origin, 'From'),
                ),
                const Icon(
                  Icons.arrow_forward_rounded,
                  color: Color(0xFF174EA6),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: _location(trip.destination, 'To'),
                ),
              ],
            ),

            const SizedBox(height: 14),

            Row(
              children: [
                Icon(
                  isFull ? Icons.event_busy : Icons.event_seat,
                  size: 18,
                  color: availabilityColor,
                ),
                const SizedBox(width: 6),
                Expanded(
                  child: Text(
                    isFull
                        ? 'No seats available'
                        : '${trip.availableSeats} seats available',
                    style: TextStyle(
                      color: availabilityColor,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
              ],
            ),

            if (trip.isLive) ...[
              const SizedBox(height: 14),
              SizedBox(
                width: double.infinity,
                child: FilledButton.icon(
                  onPressed: isFull || _booking ? null : _bookSeat,
                  icon: _booking
                      ? const SizedBox(
                          width: 18,
                          height: 18,
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                          ),
                        )
                      : const Icon(Icons.event_seat),
                  label: Text(
                    _booking ? 'Booking...' : 'Book Seat',
                  ),
                  style: FilledButton.styleFrom(
                    backgroundColor: const Color(0xFF174EA6),
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(vertical: 13),
                  ),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _location(String name, String label) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label,
          style: TextStyle(
            color: Colors.grey.shade500,
            fontSize: 11,
          ),
        ),
        const SizedBox(height: 3),
        Text(
          name,
          style: const TextStyle(
            fontSize: 15,
            fontWeight: FontWeight.w600,
          ),
        ),
      ],
    );
  }
}
