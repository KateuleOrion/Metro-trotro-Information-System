
import 'dart:convert';
import 'package:http/http.dart' as http;

class PassengerApi {
  // Address for Android Emulator
  static const String baseUrl = 'http://10.0.2.2:8000';
  
  Future<Map<String, dynamic>> searchTrips({
    String origin = '',
    String destination = '',
  }) async {
    final uri = Uri.parse(
      '$baseUrl/passenger/search',
    ).replace(
      queryParameters: {
        'from': origin,
        'to': destination,
      },
    );

    final response = await http.get(uri).timeout(
      const Duration(seconds: 15),
    );

    if (response.statusCode == 200) {
      return jsonDecode(response.body)
          as Map<String, dynamic>;
    }

    throw Exception(
      'Failed to load trips: ${response.statusCode}',
    );
  }

  Future<Map<String, dynamic>> downloadData() async {
    final uri = Uri.parse('$baseUrl/sync/download');

    final response = await http.get(uri).timeout(
      const Duration(seconds: 15),
    );

    if (response.statusCode == 200) {
      return jsonDecode(response.body)
          as Map<String, dynamic>;
    }

    throw Exception(
      'Failed to download data: ${response.statusCode}',
    );
  }
}
