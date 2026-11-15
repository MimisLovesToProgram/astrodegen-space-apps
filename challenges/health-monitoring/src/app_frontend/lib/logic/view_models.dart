import 'package:flutter/material.dart';
import 'package:http/http.dart';
import 'package:pocketbase/pocketbase.dart';

import 'models.dart';

/// Singleton class for handling the app's info
class AppData extends ChangeNotifier {
  AppData._();

  static AppData instance = AppData._();

  /// The list of questions asked during check-in
  List<Question> checkinQuestions = [
    Question(title: "On a scale of 1-5, how would you rate your sleep's quality?", type: QuestionType.onetofive),
    Question(title: "On a scale of 1-5, how would you rate your mood?", type: QuestionType.onetofive),
    Question(title: "Do you feel you have any symptoms? If yes, type them below (comma separated, no spaces)", type: QuestionType.list),
    Question(title: "Have you had any exercise today?", type: QuestionType.yesno),
    Question(title: "Have you had any social interactions today?", type: QuestionType.yesno),
  ];

  Map<String, dynamic> sensorAndUserData = {};
  Map<String, dynamic> domains = {};

  /// Wraps the PocketBase items list in a map keyed by the read's date.
  /// Result: { '2026-11-15': [ {sensor_type: ..., value: ...}, ... ], ... }
  Map<String, List<Map<String, dynamic>>> groupItemsByDate(List<dynamic> items) {
    final result = <String, List<Map<String, dynamic>>>{};
    for (RecordModel raw in items) {
      
      // "created" looks like "2026-11-15 11:47:42.980Z" (UTC); DateTime.parse accepts it.
      final created = DateTime.parse(raw.getStringValue("created")).toLocal();
      final key = '${created.year.toString().padLeft(4, '0')}-' '${created.month.toString().padLeft(2, '0')}-' '${created.day.toString().padLeft(2, '0')}';
      
      // Also only keep the only things you need from item
      Map<String, dynamic> cleanItem = {};
      cleanItem[raw.getStringValue("select")] = raw.getStringValue("value");

      result.putIfAbsent(key, () => []).add(cleanItem);
      
    }
    return result;

  }
  
  Future<void> loadSensorData(String crewId) async {
    final pb = PocketBase('http://10.2.110.80:8090');
    final items = await pb.collection('sensor_readings').getFullList();

    sensorAndUserData = groupItemsByDate(items);
  }
}