"""Check the team's time and point rules against independent synthetic cases."""

import copy
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from assessment import assess_history
from assessment.policy import load_policy
from assessment.temporal import evaluate_feature
from assessment_fixtures import observation, sample_policy


class TeamAssessmentTests(unittest.TestCase):
    def setUp(self):
        self.clock = datetime(2026, 11, 10, 12, tzinfo=timezone.utc)
        self.policy = sample_policy()

    def result(self, history, rule):
        self.policy['domains']['immune']['rules'] = [rule]
        return assess_history(history, 'a', self.policy, as_of=self.clock)['domains']['immune']

    def rule(self, **changes):
        value = dict(id='rule', metric='hr_resting', feature='value', operator='gt', threshold=80, points=30, level=1)
        return {**value, **changes}

    def test_many_readings_on_one_day_cannot_form_daily_streak(self):
        history = [observation(90, day=10, captured_at=f'2026-11-10T{hour:02d}:00:00Z') for hour in (8,9,10)]
        domain = self.result(history, self.rule(daily=True, consecutive=3))
        self.assertIsNone(domain['level'])
        self.assertEqual(domain['rules'][0]['reason'], 'insufficient_streak')

    def test_missing_day_breaks_streak_and_latest_daily_value_wins(self):
        rule = self.rule(daily=True, consecutive=3)
        self.assertIsNone(self.result([observation(90, day=day) for day in (7,9,10)], rule)['level'])
        history = [observation(90, day=day) for day in (8,9,10)]
        self.assertEqual(self.result(history, rule)['known_points'], 30)
        history.append(observation(60, day=9, captured_at='2026-11-09T13:00:00Z'))
        self.assertEqual(self.result(history, rule)['risk_score'], 0)

    def test_baseline_requires_seven_prior_calendar_days(self):
        rule = self.rule(feature='baseline_change', threshold=15, window_days=7)
        history = [observation(60, day=day) for day in range(3,10)] + [observation(90,day=10)]
        self.assertEqual(self.result(history,rule)['known_points'], 30)
        history = [item for item in history if item['captured_at'][:10] != '2026-11-06']
        history.extend(observation(60,day=9,captured_at=f'2026-11-09T{hour:02d}:00:00Z') for hour in (13,14,15))
        self.assertIsNone(self.result(history,rule)['level'])

    def test_symptom_names_control_points_not_just_count(self):
        rule = self.rule(metric='symptoms',feature='contains_any',operator='eq',threshold=1,matches=['fatigue','sore throat'])
        self.assertEqual(self.result([observation(['headache','nausea'],day=10,metric='symptoms')],rule)['risk_score'],0)
        self.assertEqual(self.result([observation(['fatigue'],day=10,metric='symptoms')],rule)['risk_score'],30)

    def test_social_absence_uses_elapsed_hours_and_continuous_logs(self):
        rule = self.rule(metric='social_interaction',feature='hours_since_true',operator='gte',threshold=48,max_gap_seconds=129600)
        history = [observation(value,day=day,metric='social_interaction') for day,value in ((8,True),(9,False),(10,False))]
        self.assertEqual(self.result(history,rule)['known_points'],30)
        self.assertIsNone(self.result([history[0],history[2]],rule)['level'])
        self.assertIsNone(self.result([history[-1]],rule)['level'])

    def test_missed_days_require_mission_coverage_and_count_each_day_once(self):
        rule = self.rule(metric='exercise_logged',feature='missed_mission_days',operator='gt',threshold=0,points=2,points_per_unit=True,daily=True)
        history = [observation(value,day=day,metric='exercise_logged') for day,value in ((8,False),(9,True),(10,False))]
        history += [observation(day-7,day=day,metric='mission_day') for day in (8,9,10)]
        self.assertEqual(self.result(history,rule)['known_points'],4)
        history.append(observation(False,day=9,metric='exercise_logged',captured_at='2026-11-09T13:00:00Z'))
        self.assertEqual(self.result(history,rule)['known_points'],6)
        history = [item for item in history if item['captured_at'][:10] != '2026-11-08']
        self.assertIsNone(self.result(history,rule)['risk_score'])

    def test_exercise_absence_uses_actual_fourteen_days(self):
        rule = self.rule(metric='exercise_logged',feature='hours_since_true',operator='gt',threshold=336,max_gap_seconds=129600)
        readings = [observation(index==0,metric='exercise_logged',captured_at=(self.clock-timedelta(days=15-index)).isoformat()) for index in range(16)]
        self.assertEqual(self.result(readings,rule)['known_points'],30)
        self.assertEqual(evaluate_feature(rule,readings,14,{},self.clock-timedelta(days=1))['value'],336)

    def test_policies_match_team_points_and_trigger_thresholds(self):
        path=Path(__file__).resolve().parents[1]/'config'
        for filename in ('assessment-team.json','assessment-team-synthetic.json'):
            policy=load_policy(path/filename)
            self.assertEqual([band['min_points'] for band in policy['domains']['immune']['bands']],[0,20,60,80])
            self.assertEqual(sum(rule['points'] for rule in policy['domains']['cardiovascular']['rules']),60)
            self.assertEqual(policy['domains']['cardiovascular']['rules'][2]['metric'],'activity_pct_target')

    def test_partial_warning_is_not_a_complete_assessment(self):
        rule=self.rule(feature='baseline_change',threshold=15,window_days=7)
        self.assertIsNone(self.result([observation(90,day=10)],rule)['risk_score'])
