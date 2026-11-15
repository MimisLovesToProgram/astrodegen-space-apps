import 'dart:convert';

import 'package:material_ui/material_ui.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:app_frontend/logic/crew_api.dart';
import 'package:app_frontend/logic/models.dart';
import 'package:app_frontend/logic/view_models.dart';
import 'package:app_frontend/screens/checkin_screen.dart';
import 'package:app_frontend/screens/status_screen.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test(
    'login passes credentials and uses the returned crew token for history',
    () async {
      final api = CrewApi(
        client: MockClient((request) async {
          if (request.url.path.endsWith('/login')) {
            expect(jsonDecode(request.body), {
              'username': 'crew_b',
              'password': 'private',
            });
            expect(request.headers.containsKey('Authorization'), isFalse);
            return http.Response('{"crewId":"b","token":"user-token"}', 200);
          }
          expect(request.headers['Authorization'], 'Bearer user-token');
          expect(jsonDecode(request.body), {'crewId': 'b'});
          return http.Response(
            '{"2026-11-15":{"sleep_h":[5.8,null],"mood":[2,2]}}',
            200,
          );
        }),
      );
      expect(await api.login('crew_b', 'private'), 'b');
      final history = await api.history('b');
      expect(history['2026-11-15']!['sleep_h']!.value, 5.8);
      expect(history['2026-11-15']!['sleep_h']!.level, isNull);
      expect(history['2026-11-15']!['mood']!.level, 2);
    },
  );

  test('failed login cannot retain a previous session', () async {
    var attempts = 0;
    final api = CrewApi(
      client: MockClient((request) async {
        attempts++;
        return http.Response(
          attempts == 1 ? '{"crewId":"a","token":"old"}' : '{"crewId":""}',
          200,
        );
      }),
    );
    await api.login('crew_a', 'right');
    expect(await api.login('crew_b', 'wrong'), isNull);
    await expectLater(api.history('a'), throwsA(isA<CrewApiException>()));
    expect(attempts, 2);
  });

  test('expired tokens are cleared and unknown levels stay unknown', () async {
    final api = CrewApi(
      client: MockClient(
        (request) async => http.Response(
          request.url.path.endsWith('/login')
              ? '{"crewId":"a","token":"expired"}'
              : '{}',
          request.url.path.endsWith('/login') ? 200 : 401,
        ),
      ),
    );
    await api.login('crew_a', 'right');
    await expectLater(api.history('a'), throwsA(isA<CrewApiException>()));
    await expectLater(api.profile(), throwsA(isA<CrewApiException>()));
    expect(MetricReading.fromJson([true, null]).level, isNull);
    expect(
      () => MetricReading.fromJson([4, 8]),
      throwsA(isA<CrewApiException>()),
    );
  });

  test(
    'check-in submits symptom names, activity percentage, and stable key',
    () async {
      final api = CrewApi(
        client: MockClient((request) async {
          if (request.url.path.endsWith('/login')) {
            return http.Response('{"crewId":"a","token":"token"}', 200);
          }
          final body = jsonDecode(request.body) as Map<String, dynamic>;
          expect(body['deliveryKey'], 'stable-key-123');
          expect(body['values']['symptoms'], ['fatigue']);
          expect(body['values']['activity_pct_target'], 40);
          return http.Response('{"id":"packet","status":"pending"}', 202);
        }),
      );
      await api.login('crew_a', 'right');
      await api.checkin('a', 'stable-key-123', {
        'symptoms': ['fatigue'],
        'activity_pct_target': 40,
      });
    },
  );

  test(
    'check-in reminders are isolated by crew and use calendar dates',
    () async {
      SharedPreferences.setMockInitialValues({});
      final dates = DateStorage.instance;
      await dates.init();
      await dates.loadForCrew('a');
      expect(dates.needsCheckin, isTrue);
      await dates.updateLastDate();
      expect(dates.needsCheckin, isFalse);
      await dates.loadForCrew('b');
      expect(dates.needsCheckin, isTrue);
      await dates.loadForCrew('a');
      expect(dates.needsCheckin, isFalse);
      expect(DateStorage.dayKey(DateTime(2026, 1, 2)), '2026-01-02');
    },
  );

  testWidgets('unknown measurements are visibly distinct from green', (
    tester,
  ) async {
    final data = AppData.instance;
    data.reset();
    data.sensorData = {
      '2026-11-15': {
        'sleep_h': const MetricReading(5.8, null),
        'mood': const MetricReading(4, 0),
      },
    };
    await tester.pumpWidget(const MaterialApp(home: StatusScreen()));
    await tester.pumpAndSettle();
    expect(find.text('Unknown'), findsOneWidget);
    expect(find.text('Green'), findsOneWidget);
    data.reset();
  });

  testWidgets('moving the quality slider updates the submitted answer', (
    tester,
  ) async {
    final question = Question(
      title: 'Quality',
      type: QuestionType.onetofive,
      field: 'sleep_quality',
    );
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(body: OneToFiveSlider(q: question)),
      ),
    );
    tester.widget<Slider>(find.byType(Slider)).onChanged!(5);
    await tester.pump();
    expect(question.answer, 5);
  });
}
