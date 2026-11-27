
import 'dart:convert';
import 'package:http/http.dart' as http;
import 'auth_service.dart';

class TripSearchService {
  static const String baseUrl = AuthService.baseUrl;

  Future<Map<String, dynamic>> searchTrips({
    String origin = '',
    String destination = '',
  }) async {
    final uri = Uri.parse('$baseUrl/passenger/search').replace(
      queryParameters: {
        'from': origin,
        'to': destination,
      },
    );

    final response = await http.get(uri).timeout(
      const Duration(seconds: 15),
    );

    final decoded = jsonDecode(response.body);

    if (response.statusCode == 200) {
      if (decoded is Map<String, dynamic>) {
        return decoded;
      }
      throw Exception('Unexpected server response.');
    }

    if (decoded is Map<String, dynamic>) {
      throw Exception(
        decoded['detail'] ?? 'Could not search for trips.',
      );
    }

    throw Exception('Could not search for trips.');
  }
}
