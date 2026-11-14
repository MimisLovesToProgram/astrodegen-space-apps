library;

import 'package:http/http.dart';

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