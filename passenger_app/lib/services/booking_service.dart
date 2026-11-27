
import 'dart:convert';
import 'package:http/http.dart' as http;
import 'auth_service.dart';

class BookingService {
  static const String baseUrl = AuthService.baseUrl;

  final AuthService _authService = AuthService();

  Future<Map<String, dynamic>> createBooking({
    required int vehicleId,
    required int seatsBooked,
  }) async {
    final token = await _authService.getToken();

    if (token == null || token.isEmpty) {
      throw Exception('Please log in before booking.');
    }

    final response = await http.post(
      Uri.parse('$baseUrl/passenger/bookings'),
      headers: {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer $token',
      },
      body: jsonEncode({
        'vehicle_id': vehicleId,
        'seats_booked': seatsBooked,
      }),
    ).timeout(const Duration(seconds: 15));

    final dynamic decoded = jsonDecode(response.body);

    if (response.statusCode == 201 &&
        decoded is Map<String, dynamic>) {
      return decoded;
    }

    if (decoded is Map<String, dynamic>) {
      throw Exception(decoded['detail'] ?? 'Booking failed.');
    }

    throw Exception('Booking failed.');
  }

  Future<List<dynamic>> getMyBookings() async {
    final token = await _authService.getToken();

    if (token == null || token.isEmpty) {
      throw Exception('Please log in before viewing bookings.');
    }

    final response = await http.get(
      Uri.parse('$baseUrl/passenger/bookings'),
      headers: {
        'Authorization': 'Bearer $token',
      },
    ).timeout(const Duration(seconds: 15));

    final dynamic decoded = jsonDecode(response.body);

    if (response.statusCode == 200 && decoded is Map) {
      return List<dynamic>.from(decoded['bookings'] ?? []);
    }

    if (decoded is Map) {
      throw Exception(
        decoded['detail'] ?? 'Could not retrieve bookings.',
      );
    }

    throw Exception('Could not retrieve bookings.');
  }

  // CANCEL A PASSENGER BOOKING
  Future<void> cancelBooking(String bookingReference) async {
    final token = await _authService.getToken();

    if (token == null || token.isEmpty) {
      throw Exception('Please log in before cancelling a booking.');
    }

    final response = await http.delete(
      Uri.parse(
        '$baseUrl/passenger/bookings/${Uri.encodeComponent(bookingReference)}',
      ),
      headers: {
        'Authorization': 'Bearer $token',
      },
    ).timeout(const Duration(seconds: 15));

    if (response.statusCode == 200 ||
        response.statusCode == 204) {
      return;
    }

    try {
      final dynamic decoded = jsonDecode(response.body);

      if (decoded is Map) {
        throw Exception(
          decoded['detail'] ?? 'Could not cancel booking.',
        );
      }
    } catch (e) {
      if (e is Exception &&
          e.toString() != 'Exception: FormatException') {
        rethrow;
      }
    }

    throw Exception('Could not cancel booking.');
  }
}
