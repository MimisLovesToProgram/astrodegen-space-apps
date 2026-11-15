import 'dart:convert';

/// Helpers for turning the DB shape
///   { '2026-11-15': [ {hr_resting: 62.0}, {hrv: 65.0}, ... ], ... }
/// into values the status screen can display, and for computing the
/// Good / Watch / Alert status from the thresholds in your notebook table.

/// Keys the DB uses -> keys the screens use.
const Map<String, String> metricKeyAliases = {
  'hr_resting': 'hrr',
};

/// Cumulative radiation limit (mSv). "Watch" starts at 80% of it.
const double radiationLimitMsv = 600;

String normalizeKey(String key) => metricKeyAliases[key] ?? key;

/// Turns one day's list of single-key maps into {metric: value}.
/// When a metric appears several times, the LAST reading wins.
Map<String, dynamic> latestReadings(dynamic dayEntry) {
  final result = <String, dynamic>{};
  if (dayEntry is! List) return result;

  for (final reading in dayEntry) {
    if (reading is! Map) continue;
    reading.forEach((k, v) {
      final key = normalizeKey(k.toString());
      result[key] = coerceValue(key, v);
    });
  }
  return result;
}

/// PocketBase text fields arrive as Strings ("62.0", "true", "[]").
/// Converts them to num / bool / List so the screens can use them.
dynamic coerceValue(String key, dynamic raw) {
  if (raw is! String) return raw;
  final s = raw.trim();

  if (key == 'symptoms') {
    if (s.isEmpty) return <dynamic>[];
    if (s.startsWith('[')) {
      try {
        final decoded = jsonDecode(s);
        if (decoded is List) return decoded;
      } catch (_) {}
    }
    final asNum = num.tryParse(s);
    if (asNum != null) return asNum; // a plain count
    return s.split(',').map((e) => e.trim()).where((e) => e.isNotEmpty).toList();
  }

  final lower = s.toLowerCase();
  if (lower == 'true') return true;
  if (lower == 'false') return false;
  return num.tryParse(s) ?? raw;
}

/// How many of the most recent days in a row had [key] == false.
/// Days without that metric are skipped.
int consecutiveDaysFalse(Map<dynamic, dynamic> all, String key) {
  final dates = all.keys.map((k) => k.toString()).toList()..sort();
  int count = 0;

  for (final date in dates.reversed) {
    final value = latestReadings(all[date])[key];
    if (value == null) continue;
    if (value == true) break;
    count++;
  }
  return count;
}

/// Status ints: 0 = Good, 1 = Watch, 3 = Alert.
/// (The notebook table only defines Normal / Watch / Alert, so "Warning" (2)
/// is never produced here.)
int statusFor(String key, dynamic value, Map<dynamic, dynamic> all) {
  switch (key) {
    case 'hrr':
      final n = value as num;
      if (n > 120 || n < 45) return 3;
      if (n > 100 || n < 50) return 1;
      return 0;

    case 'hrv':
      final n = value as num;
      if (n < 30) return 3;
      if (n < 40) return 1;
      return 0;

    case 'spo2':
      final n = value as num;
      if (n < 92) return 3;
      if (n < 95) return 1;
      return 0;

    case 'temp_c':
      final n = value as num;
      if (n >= 38.5 || n < 35.5) return 3;
      if (n > 37.5 || n < 36.0) return 1;
      return 0;

    case 'radiation_msv_cumulative':
      final n = value as num;
      if (n >= radiationLimitMsv) return 3;
      if (n >= radiationLimitMsv * 0.8) return 1;
      return 0;

    case 'sleep_h':
      final n = value as num;
      if (n < 6) return 3;
      if (n < 7) return 1;
      return 0;

    case 'sleep_quality':
    case 'mood':
      final n = value as num;
      if (n < 2) return 3;
      if (n < 3) return 1;
      return 0;

    case 'symptoms':
      final count = value is List ? value.length : (value is num ? value.toInt() : 0);
      if (count >= 2) return 3;
      if (count == 1) return 1;
      return 0;

    case 'exercise_logged':
      final days = consecutiveDaysFalse(all, key);
      if (days >= 7) return 3;
      if (days >= 3) return 1;
      return 0;

    case 'social_interaction':
      final days = consecutiveDaysFalse(all, key);
      if (days >= 3) return 3;
      if (days >= 2) return 1;
      return 0;

    default:
      return 0;
  }
}