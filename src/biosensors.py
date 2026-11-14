import json
import random
import time
from datetime import datetime, timedelta

INTERVAL = 3
MODE = 'story'

# 3 astronauts each on a differeent trajectory:
# a -> deteoriates over the week hits ORANGE by day 5 (immune)
# b -> remains stable and heatlhy all time GREEN
# c -> slow bone loss (bone)

Crew = {
    'a': [{'hr': 62, 'hrv': 65, 'spo2': 98, 'temp': 36.6, 'rad': 0.5, 'sleep': 7.8, 'sq': 4, 'mood': 4, 'sym': [], 'ex': True, 'soc': True},
          {'hr': 64, 'hrv': 62, 'spo2': 98, 'temp': 36.7, 'rad': 1.0,
           'sleep': 7.5, 'sq': 4, 'mood': 4, 'sym': [], 'ex': True, 'soc': True},
          {'hr': 68, 'hrv': 55, 'spo2': 97, 'temp': 36.8, 'rad': 1.5,
           'sleep': 6.4, 'sq': 3, 'mood': 3, 'sym': [], 'ex': True, 'soc': True},
          {'hr': 72, 'hrv': 48, 'spo2': 97, 'temp': 37.0, 'rad': 2.0, 'sleep': 5.8,
           'sq': 3, 'mood': 3, 'sym': ['fatigue'], 'ex': False, 'soc': True},
          {'hr': 76, 'hrv': 46, 'spo2': 96, 'temp': 37.3, 'rad': 2.5, 'sleep': 5.5,
           'sq': 2, 'mood': 2, 'sym': ['fatigue'], 'ex': False, 'soc': False},
          {'hr': 70, 'hrv': 54, 'spo2': 97, 'temp': 36.9, 'rad': 3.0,
           'sleep': 7.2, 'sq': 4, 'mood': 3, 'sym': [], 'ex': True, 'soc': True},
          {'hr': 63, 'hrv': 63, 'spo2': 98, 'temp': 36.6, 'rad': 3.5, 'sleep': 7.6, 'sq': 4, 'mood': 4, 'sym': [], 'ex': True, 'soc': True}],
    'b': [{'hr': 58, 'hrv': 72, 'spo2': 99, 'temp': 36.5, 'rad': 0.5, 'sleep': 8.1, 'sq': 5, 'mood': 5, 'sym': [], 'ex': True, 'soc': True},
          {'hr': 59, 'hrv': 70, 'spo2': 99, 'temp': 36.6, 'rad': 1.0,
           'sleep': 7.9, 'sq': 4, 'mood': 4, 'sym': [], 'ex': True, 'soc': True},
          {'hr': 60, 'hrv': 68, 'spo2': 98, 'temp': 36.6, 'rad': 1.5,
           'sleep': 7.8, 'sq': 4, 'mood': 4, 'sym': [], 'ex': True, 'soc': True},
          {'hr': 61, 'hrv': 67, 'spo2': 98, 'temp': 36.7, 'rad': 2.0,
           'sleep': 7.6, 'sq': 4, 'mood': 4, 'sym': [], 'ex': True, 'soc': True},
          {'hr': 62, 'hrv': 66, 'spo2': 98, 'temp': 36.7, 'rad': 2.5,
           'sleep': 7.5, 'sq': 4, 'mood': 4, 'sym': [], 'ex': True, 'soc': True},
          {'hr': 60, 'hrv': 69, 'spo2': 98, 'temp': 36.6, 'rad': 3.0,
           'sleep': 7.8, 'sq': 4, 'mood': 3, 'sym': [], 'ex': True, 'soc': True},
          {'hr': 59, 'hrv': 71, 'spo2': 99, 'temp': 36.6, 'rad': 3.5, 'sleep': 8.0, 'sq': 5, 'mood': 5, 'sym': [], 'ex': True, 'soc': True}],
    'c': [{'hr': 70, 'hrv': 58, 'spo2': 98, 'temp': 36.7, 'rad': 0.5, 'sleep': 7.2, 'sq': 4, 'mood': 4, 'sym': [], 'ex': True, 'soc': True},
          {'hr': 72, 'hrv': 56, 'spo2': 98, 'temp': 36.7, 'rad': 1.0,
           'sleep': 7.0, 'sq': 3, 'mood': 4, 'sym': [], 'ex': True, 'soc': True},
          {'hr': 75, 'hrv': 52, 'spo2': 98, 'temp': 36.8, 'rad': 1.5,
           'sleep': 6.8, 'sq': 3, 'mood': 3, 'sym': [], 'ex': False, 'soc': True},
          {'hr': 78, 'hrv': 48, 'spo2': 97, 'temp': 36.8, 'rad': 2.0, 'sleep': 6.5,
           'sq': 3, 'mood': 3, 'sym': ['fatigue'], 'ex': False, 'soc': True},
          {'hr': 82, 'hrv': 44, 'spo2': 97, 'temp': 36.9, 'rad': 2.5, 'sleep': 6.2,
           'sq': 3, 'mood': 3, 'sym': ['fatigue'], 'ex': False, 'soc': True},
          {'hr': 84, 'hrv': 42, 'spo2': 97, 'temp': 36.9, 'rad': 3.0, 'sleep': 6.0,
           'sq': 2, 'mood': 2, 'sym': ['fatigue'], 'ex': False, 'soc': False},
          {'hr': 86, 'hrv': 40, 'spo2': 96, 'temp': 37.0, 'rad': 3.5, 'sleep': 5.8, 'sq': 2, 'mood': 2, 'sym': ['fatigue'], 'ex': False, 'soc': False}]
}


def reading_from(crew_id, d, day):
    return {
        'crew_id': crew_id,
        'mission_day': day,
        'timestamp': (datetime(2026, 11, 15, 8) + timedelta(days=day - 1)).isoformat(),
        'hr': float(d['hr']),
        'hrv': float(d['hrv']),
        'spo2': float(d['spo2']),
        'temp_c': float(d['temp']),
        'radiation_msv_cumulative': float(d['rad']),
        'sleep_h': float(d['sleep']),
        'sleep_quality': float(d['sq']),
        'mood': float(d['mood']),
        'symptoms': d['sym'],
        'exercise_logged': d['ex'],
        'social_interaction': d['soc'],

    }


def noise_from(crew_id, i):
    r = random
    return {
        'crew_id': crew_id,
        'mission_day': 1+i//20,
        'timestamp': datetime.now().isoformat(),
        'hr': round(64 + r.gauss(0, 4), 1),
        'hrv': round(62 + r.gauss(0, 3), 1),
        'spo2': round(min(100, max(92, 98 + r.gauss(0, 0.5))), 1),
        'temp_c': round(36.6 + r.gauss(0, 0.1), 2),
        'radiation_msv_cumulative': round(0.5 + i * 0.05, 2),
        'sleep_h': 7.5,
        'sleep_quality': 4,
        'mood': 4,
        'symptoms': ['fatigue'] if r.random() < 0.05 else [],
        'exercise_logged': r.random() > 0.05,
        "social_interaction": r.random() > 0.03,
    }


if __name__ == "__main__":
    try:
        if MODE == "story":
            for day in range(1, 8):
                for crew_id, arc in Crew.items():
                    d = arc[day - 1]
                    print(json.dumps(reading_from(crew_id, d, day)), flush=True)
                time.sleep(INTERVAL)
        else:
            i = 0
            while True:
                for crew_id in Crew:
                    print(json.dumps(noise_from(crew_id, i)), flush=True)
                i += 1
                time.sleep(INTERVAL)
    except KeyboardInterrupt:
        pass
