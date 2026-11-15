library;

import 'package:shared_preferences/shared_preferences.dart';

import 'crew_api.dart';

enum QuestionType { num, onetofive, yesno, symptoms }

class Question {
  Question({required this.title, required this.type, required this.field});
  final String title;
  final QuestionType type;
  final String field;
  Object? answer;
}

class CurrentUser {
  CurrentUser._();
  static final CurrentUser instance = CurrentUser._();
  final CrewApi api = CrewApi();
  String crewId = '';

  Future<bool> loginUser(String username, String password) async {
    crewId = '';
    final id = await api.login(username, password);
    if (id == null) return false;
    crewId = id;
    await DateStorage.instance.loadForCrew(id);
    return true;
  }

  void logout() {
    api.clearSession();
    crewId = '';
  }
}

class DateStorage {
  DateStorage._();
  static final DateStorage instance = DateStorage._();
  late SharedPreferences shPref;
  String? _crewId;
  String? _lastDay;

  static String dayKey(DateTime value) =>
      value.toIso8601String().substring(0, 10);

  Future<void> init() async {
    shPref = await SharedPreferences.getInstance();
  }

  Future<void> loadForCrew(String id) async {
    _crewId = id;
    _lastDay = shPref.getString('checkin-day-$id');
  }

  bool get needsCheckin => _lastDay != dayKey(DateTime.now());

  Future<void> updateLastDate() async {
    if (_crewId == null) throw StateError('A crew session is required.');
    final day = dayKey(DateTime.now());
    if (!await shPref.setString('checkin-day-$_crewId', day)) {
      throw const CrewApiException(
        'Check-in saved, but the local reminder could not be updated.',
      );
    }
    _lastDay = day;
  }
}
