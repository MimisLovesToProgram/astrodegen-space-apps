import 'package:flutter_test/flutter_test.dart';
import 'package:app_frontend/logic/crew_api.dart';

void main() {
  const url = String.fromEnvironment('ASTROCRATES_INTEGRATION_URL');
  const username = String.fromEnvironment('ASTROCRATES_INTEGRATION_USERNAME');
  const password = String.fromEnvironment('ASTROCRATES_INTEGRATION_PASSWORD');
  test(
    'real crew login, raw check-in, worker assessment, and typed history',
    () async {
      final api = CrewApi(baseUrl: url);
      expect(await api.login(username, password), 'a');
      expect((await api.profile())['crewId'], 'a');
      await api.checkin('a', 'live-checkin-12345', {
        'sleep_h': 5.5,
        'sleep_quality': 2,
        'mood': 2,
        'symptoms': ['fatigue'],
        'exercise_logged': false,
        'social_interaction': true,
        'activity_pct_target': 40,
      });
      Map<String, Map<String, MetricReading>> history = {};
      for (var attempt = 0; attempt < 50; attempt++) {
        history = await api.history('a');
        if (history.isNotEmpty && history.values.first['mood']?.level == 2)
          break;
        await Future<void>.delayed(const Duration(milliseconds: 100));
      }
      expect(history, hasLength(1));
      final fields = history.values.first;
      expect(fields['symptoms']!.value, ['fatigue']);
      expect(fields['activity_pct_target']!.value, 40);
      expect(fields['mood']!.level, 2);
      expect((await api.profile())['status'], 'orange');
      await expectLater(api.history('b'), throwsA(isA<CrewApiException>()));
    },
    skip: url.isEmpty
        ? 'Run through the isolated backend integration harness.'
        : false,
  );
}
