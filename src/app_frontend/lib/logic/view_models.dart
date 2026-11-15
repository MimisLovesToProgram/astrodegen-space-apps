import 'dart:convert';
import 'dart:math';

import 'package:material_ui/material_ui.dart';

import 'crew_api.dart';
import 'models.dart';

class AppData extends ChangeNotifier {
  AppData._();
  static final AppData instance = AppData._();

  final List<Question> checkinQuestions = [
    Question(
      title: 'How many hours did you sleep?',
      type: QuestionType.num,
      field: 'sleep_h',
    ),
    Question(
      title: "On a scale of 1–5, how would you rate your sleep quality?",
      type: QuestionType.onetofive,
      field: 'sleep_quality',
    ),
    Question(
      title: 'On a scale of 1–5, how would you rate your mood?',
      type: QuestionType.onetofive,
      field: 'mood',
    ),
    Question(
      title: 'Which symptoms have you experienced?',
      type: QuestionType.symptoms,
      field: 'symptoms',
    ),
    Question(
      title: 'Have you had any resistance exercise today?',
      type: QuestionType.yesno,
      field: 'exercise_logged',
    ),
    Question(
      title: 'Have you had any social interactions today?',
      type: QuestionType.yesno,
      field: 'social_interaction',
    ),
    Question(
      title: 'What percentage of your activity target did you complete?',
      type: QuestionType.num,
      field: 'activity_pct_target',
    ),
  ];

  Map<String, Map<String, MetricReading>> sensorData = {};
  Map<String, dynamic> profile = {};
  String? notice;
  String? _deliveryKey;
  String? _answers;

  void reset() {
    sensorData = {};
    profile = {};
    notice = null;
    _deliveryKey = null;
    _answers = null;
    for (final question in checkinQuestions) {
      question.answer = null;
    }
  }

  Future<void> loadSensorData(String crewId) async {
    final history = await CurrentUser.instance.api.history(crewId);
    final crew = await CurrentUser.instance.api.profile();
    sensorData = history;
    profile = crew;
    notifyListeners();
  }

  Future<void> submitCheckin() async {
    final values = <String, dynamic>{};
    for (final question in checkinQuestions) {
      if (question.answer == null) {
        throw const CrewApiException('Please answer every question.');
      }
      values[question.field] = question.type == QuestionType.yesno
          ? question.answer == 1
          : question.answer;
    }
    final encoded = jsonEncode(values);
    if (_answers != encoded) {
      _answers = encoded;
      _deliveryKey =
          '${DateTime.now().microsecondsSinceEpoch}-${Random.secure().nextInt(1 << 32)}';
    }
    // We retain the same delivery key when retrying after a lost response.
    await CurrentUser.instance.api.checkin(
      CurrentUser.instance.crewId,
      _deliveryKey!,
      values,
    );
    await DateStorage.instance.updateLastDate();
    notice = 'Check-in saved. Validation and assessment may still be pending.';
  }
}
