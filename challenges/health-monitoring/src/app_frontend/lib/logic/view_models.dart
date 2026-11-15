import 'package:flutter/material.dart';
import 'package:http/http.dart';

import 'models.dart';

/// Singleton class for handling the app's info
class AppData extends ChangeNotifier {
  AppData._();

  static AppData instance = AppData._();

  /// The list of questions asked during check-in
  List<Question> checkinQuestions = [
    Question(title: "On a scale of 1-5, how would you rate your sleep's quality?", type: QuestionType.onetofive),
    Question(title: "On a scale of 1-5, how would you rate your mood?", type: QuestionType.onetofive),
    Question(title: "Do you feel you have any symptoms? If yes, how many?", type: QuestionType.num),
    Question(title: "Have you had any exercise today?", type: QuestionType.yesno),
    Question(title: "Have you had any social interactions today?", type: QuestionType.yesno),
  ];

  Map<String, dynamic> sensorAndUserData = {};
  Map<String, dynamic> domains = {};

  Future<void> loadSensorData(String crewId) async {
    await Future.delayed(Duration(seconds: 4));
  }
}