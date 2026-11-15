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
import 'package:app_frontend/screens/history_screen.dart';
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
    'domain scores keep unknown domains and reject half-known ones',
    () async {
      final api = CrewApi(
        client: MockClient((request) async {
          if (request.url.path.endsWith('/login')) {
            return http.Response('{"crewId":"a","token":"token"}', 200);
          }
          expect(request.url.path, endsWith('/domains'));
          expect(jsonDecode(request.body), {'crewId': 'a'});
          return http.Response(
            '{"assessedAt":"2026-11-15T12:00:00Z","mode":"synthetic_demo",'
            '"domains":{"cardiovascular":{"score":45,"level":1,"complete":true,'
            '"lowerBound":false},"immune":{"score":null,"level":null,'
            '"complete":false,"lowerBound":false}}}',
            200,
          );
        }),
      );
      await api.login('crew_a', 'right');
      final (assessedAt, domains) = await api.domains('a');
      expect(assessedAt, '2026-11-15T12:00:00Z');
      expect(domains['cardiovascular']!.score, 45);
      expect(domains['cardiovascular']!.level, 1);
      expect(domains['immune']!.level, isNull);
      expect(domains['immune']!.score, isNull);
      expect(
        () => DomainScore.fromJson({'score': 10, 'level': null}),
        throwsA(isA<CrewApiException>()),
      );
      expect(
        () => DomainScore.fromJson({'score': 10, 'level': 5}),
        throwsA(isA<CrewApiException>()),
      );
    },
  );

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
    // The sleep reading has no level, so it must not be shown as good.
    expect(find.text('Not assessed'), findsOneWidget);
    expect(find.text('Good'), findsOneWidget);
    expect(find.text('Symptoms'), findsNothing);
    expect(find.text('No assessment yet'), findsOneWidget);
    data.reset();
  });

  testWidgets('domain card shows risk points and unknown domains in grey', (
    tester,
  ) async {
    final data = AppData.instance;
    data.reset();
    // We use a phone-sized tall screen so every domain row is built.
    tester.view.physicalSize = const Size(1080, 2400);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.reset);
    data.domainsAssessedAt = '2026-11-15T12:00:00Z';
    data.domains = {
      'cardiovascular': const DomainScore(55, 2, complete: true),
      'immune': const DomainScore(70, 2, lowerBound: true),
      'behavioral': const DomainScore(null, null),
    };
    await tester.pumpWidget(const MaterialApp(home: StatusScreen()));
    await tester.pumpAndSettle();
    expect(find.text('Cardiovascular'), findsOneWidget);
    expect(find.text('55 / 100 risk points'), findsOneWidget);
    expect(find.text('at least 70 / 100 risk points'), findsOneWidget);
    expect(find.text('Warning'), findsNWidgets(2));
    // The unknown domain shows "Not assessed" on its chip and its score line.
    expect(find.text('Not assessed'), findsNWidgets(2));
    expect(find.text('Assessed 2026-11-15 12:00 UTC'), findsOneWidget);
    data.reset();
  });

  testWidgets('history screen averages real readings and symptom lists', (
    tester,
  ) async {
    final data = AppData.instance;
    data.reset();
    final today = DateTime.now().toIso8601String().substring(0, 10);
    data.sensorData = {
      today: {
        'sleep_h': const MetricReading(7.0, 0),
        'mood': const MetricReading(null, null),
        'symptoms': const MetricReading(['headache', 'fatigue'], 1),
        'exercise_logged': const MetricReading(true, 0),
      },
    };
    await tester.pumpWidget(const MaterialApp(home: HistoryScreen()));
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
    expect(find.text('Symptoms per day'), findsWidgets);
    expect(find.text('2'), findsWidgets);
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
