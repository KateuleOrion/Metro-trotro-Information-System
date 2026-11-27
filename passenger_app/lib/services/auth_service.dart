
import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

class AuthService {
  static const String baseUrl = 'http://10.0.2.2:8000';

  static const FlutterSecureStorage _storage =
      FlutterSecureStorage();

  // STAFF LOGIN
  Future<Map<String, dynamic>> login({
    required String password,
    required String role,
    String? phone,
    String? email,
  }) async {
    final response = await http.post(
      Uri.parse('$baseUrl/auth/login'),
      headers: {
        'Content-Type': 'application/json',
      },
      body: jsonEncode({
        'password': password,
        'role': role,
        if (phone != null && phone.isNotEmpty) 'phone': phone,
        if (email != null && email.isNotEmpty) 'email': email,
      }),
    ).timeout(const Duration(seconds: 15));

    final data = _decodeResponse(response);

    if (response.statusCode == 200) {
      await _storage.write(
        key: 'auth_token',
        value: data['access_token'] ?? data['token'],
      );

      await _storage.write(
        key: 'user_role',
        value: role,
      );

      return data;
    }

    throw Exception(data['detail'] ?? 'Login failed');
  }

  // PASSENGER REGISTRATION
  Future<Map<String, dynamic>> passengerRegister({
    required String fullName,
    required String phoneNumber,
    required String password,
  }) async {
    final response = await http.post(
      Uri.parse('$baseUrl/auth/passenger/register'),
      headers: {
        'Content-Type': 'application/json',
      },
      body: jsonEncode({
        'full_name': fullName,
        'phone_number': phoneNumber,
        'password': password,
      }),
    ).timeout(const Duration(seconds: 15));

    final data = _decodeResponse(response);

    if (response.statusCode == 201) {
      return data;
    }

    throw Exception(
      data['detail'] ?? 'Passenger registration failed',
    );
  }

  // PASSENGER LOGIN
  Future<Map<String, dynamic>> passengerLogin({
    required String phoneNumber,
    required String password,
  }) async {
    final response = await http.post(
      Uri.parse('$baseUrl/auth/passenger/login'),
      headers: {
        'Content-Type': 'application/json',
      },
      body: jsonEncode({
        'phone_number': phoneNumber,
        'password': password,
      }),
    ).timeout(const Duration(seconds: 15));

    final data = _decodeResponse(response);

    if (response.statusCode == 200) {
      await _storage.write(
        key: 'auth_token',
        value: data['token'],
      );

      await _storage.write(
        key: 'user_role',
        value: 'passenger',
      );

      if (data['passenger_id'] != null) {
        await _storage.write(
          key: 'passenger_id',
          value: data['passenger_id'].toString(),
        );
      }

      return data;
    }

    throw Exception(
      data['detail'] ?? 'Passenger login failed',
    );
  }

  // RESPONSE HANDLING
  Map<String, dynamic> _decodeResponse(http.Response response) {
    final decoded = jsonDecode(response.body);

    if (decoded is Map<String, dynamic>) {
      return decoded;
    }

    throw Exception('Unexpected server response');
  }

  // GET STORED TOKEN
  Future<String?> getToken() {
    return _storage.read(key: 'auth_token');
  }

  // LOGOUT
  Future<void> logout() async {
    await _storage.delete(key: 'auth_token');
    await _storage.delete(key: 'user_role');
    await _storage.delete(key: 'passenger_id');
  }
}
