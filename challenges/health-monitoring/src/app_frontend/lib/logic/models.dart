library;

import 'package:http/http.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:intl/intl.dart';
import 'package:pocketbase/pocketbase.dart';

enum QuestionType {num, onetofive, yesno, list}

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
  List<String>? ansList;
}

/// Singleton class for the current user
class CurrentUser {
  CurrentUser._();

  static CurrentUser instance = CurrentUser._();

  Map<String, String> usersAndPasswds = {"a": "a1234", "b": "b1234", "c": "c1234"};

  late String crewId;

  bool loginUser(String username, String password) {
    if ( usersAndPasswds.keys.contains(username) ) {
      if ( usersAndPasswds[username] == password ) {
        crewId = username;
        return true;
      }
    }
    return false;
  }

  Future<bool> signout() async {
    await Future.delayed(Duration(seconds: 4));

    crewId = "";

    return true;
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
      lastDateEntered = DateTime.now();
    }
  }

  Future<void> updateLastDate() async {
    final now = DateTime.now();
    lastDateEntered = now;
    await shPref.setString("lastDate", "${now.year}-${now.month}-${now.day}");
  }

}