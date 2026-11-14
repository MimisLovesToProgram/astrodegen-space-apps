library;

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
}