import 'dart:convert';

import 'package:http/http.dart' as http;

class CrewApiException implements Exception {
  const CrewApiException(this.message);
  final String message;
  @override
  String toString() => message;
}

class MetricReading {
  const MetricReading(this.value, this.level);
  final Object? value;
  final int? level;

  factory MetricReading.fromJson(dynamic input) {
    if (input is! List ||
        input.length != 2 ||
        (input[1] != null &&
            (input[1] is! int || input[1] < 0 || input[1] > 3))) {
      throw const CrewApiException(
        'The server returned an invalid measurement.',
      );
    }
    return MetricReading(input[0], input[1] as int?);
  }
}

class CrewApi {
  CrewApi({http.Client? client, String? baseUrl})
    : _client = client ?? http.Client(),
      _baseUrl =
          baseUrl ??
          const String.fromEnvironment(
            'ASTROCRATES_API_URL',
            defaultValue: 'http://127.0.0.1:8090',
          );

  final http.Client _client;
  final String _baseUrl;
  String? _token;

  void clearSession() => _token = null;

  Future<Map<String, dynamic>> _request(
    String path, {
    Map<String, dynamic>? body,
    bool authenticated = true,
  }) async {
    if (authenticated && _token == null) {
      throw const CrewApiException('Please sign in again.');
    }
    final uri = Uri.parse('$_baseUrl/api/astrocrates/$path');
    final headers = <String, String>{'Content-Type': 'application/json'};
    if (authenticated) headers['Authorization'] = 'Bearer $_token';
    try {
      final response =
          await (body == null
                  ? _client.get(uri, headers: headers)
                  : _client.post(uri, headers: headers, body: jsonEncode(body)))
              .timeout(const Duration(seconds: 15));
      if (response.statusCode == 401) {
        clearSession();
        throw const CrewApiException(
          'Your session expired. Please sign in again.',
        );
      }
      if (response.statusCode == 429) {
        throw const CrewApiException(
          'Too many attempts. Please try again shortly.',
        );
      }
      if (response.statusCode < 200 || response.statusCode >= 300) {
        throw const CrewApiException('The request failed. Please try again.');
      }
      final result = jsonDecode(response.body);
      if (result is! Map<String, dynamic>) {
        throw const CrewApiException(
          'The server returned an invalid response.',
        );
      }
      return result;
    } on CrewApiException {
      rethrow;
    } catch (_) {
      throw const CrewApiException(
        'Could not reach the server. Please try again.',
      );
    }
  }

  Future<String?> login(String username, String password) async {
    clearSession();
    final response = await _request(
      'login',
      authenticated: false,
      body: {'username': username.trim(), 'password': password},
    );
    if (response['crewId'] == '') return null;
    if (response['crewId'] is! String ||
        response['token'] is! String ||
        (response['token'] as String).isEmpty) {
      throw const CrewApiException('The login response is incomplete.');
    }
    _token = response['token'] as String;
    return response['crewId'] as String;
  }

  Future<Map<String, Map<String, MetricReading>>> history(String crewId) async {
    final json = await _request('sensors', body: {'crewId': crewId});
    return json.map((day, fields) {
      if (!RegExp(r'^\d{4}-\d{2}-\d{2}$').hasMatch(day) ||
          fields is! Map<String, dynamic>) {
        throw const CrewApiException('The history response is invalid.');
      }
      return MapEntry(
        day,
        fields.map(
          (name, input) => MapEntry(name, MetricReading.fromJson(input)),
        ),
      );
    });
  }

  Future<Map<String, dynamic>> profile() => _request('me');

  Future<void> checkin(
    String crewId,
    String deliveryKey,
    Map<String, dynamic> values,
  ) async {
    await _request(
      'checkin',
      body: {'crewId': crewId, 'deliveryKey': deliveryKey, 'values': values},
    );
  }
}
