library;

import 'package:http/http.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:intl/intl.dart';

enum QuestionType {num, onetofive, yesno}

class Question {
  Question({
    required this.title,
    required this.type,
  });

  String title;
  QuestionType type;

  /// The answer depends on the type:
  /// For (num), just an integer.
  /// For onetofive, an int 1-5.
  /// For yesno, 1 for yes, 0 for no.
  /// Null means yet unanswered.
  int? answer;
  int? defaultAns;
}

/// Singleton class for the current user
class CurrentUser {
  CurrentUser._();

  static CurrentUser instance = CurrentUser._();

  late String crewId;

  Future<bool> loginUser(String username, String password) async {
    // TODO: For now just give a random one. Simulate a wait
    await Future.delayed(Duration(seconds: 5));

    crewId = "a";

    return true; // for success
  }
}


/// Singleton class for storing the last date the user opened the app (and finished the checkin)
class DateStorage {

  DateStorage._();

  static DateStorage instance = DateStorage._();

  /// Our instance of shared prefs
  late SharedPreferences shPref;

  late DateTime lastDateEntered;

  Future<void> init() async {
    shPref = await SharedPreferences.getInstance();
  
    final lastDateStr = shPref.getString("lastDate");
    if (lastDateStr != null) {

      lastDateEntered = DateFormat("yyyy-MM-dd").parse(lastDateStr);

    } else {
      lastDateEntered = DateTime.now().subtract(Duration(days: 1));
    }
  }

  Future<void> updateLastDate() async {
    final now = DateTime.now();
    lastDateEntered = now;
    await shPref.setString("lastDate", "${now.year}-${now.month}-${now.day}");
  }

}