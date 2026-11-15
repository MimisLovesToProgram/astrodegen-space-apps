import 'package:flutter/material.dart';

import 'package:app_frontend/logic/view_models.dart';

enum _Kind { progress, number, yesNo }

class _Metric {
  final String label;
  final _Kind kind;
  final double max; // for progress metrics
  final String unit;

  const _Metric(this.label, this.kind, {this.max = 1, this.unit = ''});
}

/// Keys match the ones in AppData.instance.sensorAndUserData. Order = display order.
const Map<String, _Metric> _metrics = {
  'hrr': _Metric('Resting heart rate', _Kind.progress, max: 150, unit: 'bpm'),
  'hrv': _Metric('Heart rate variability', _Kind.progress, max: 100, unit: 'ms'),
  'spo2': _Metric('SpO2', _Kind.progress, max: 100, unit: '%'),
  'temp_c': _Metric('Temperature', _Kind.progress, max: 42, unit: '°C'),
  'radiation_msv_cumulative':
      _Metric('Cumulative radiation', _Kind.progress, max: 600, unit: 'mSv'),
  'sleep_h': _Metric('Sleep hours', _Kind.number, unit: 'h'),
  'sleep_quality': _Metric('Sleep quality', _Kind.progress, max: 5),
  'mood': _Metric('Mood', _Kind.progress, max: 5),
  'symptoms': _Metric('Symptoms', _Kind.number),
  'exercise_logged': _Metric('Exercise', _Kind.yesNo),
  'social_interaction': _Metric('Social interaction', _Kind.yesNo),
};

const List<String> _dayLetters = ['M', 'T', 'W', 'T', 'F', 'S', 'S'];
const double _sleepThresholdHours = 6;

/// Progress bar colors by "how good" the value is (0 = bad, 1 = good).
Color _goodnessColor(double goodness) {
  if (goodness >= 0.75) return const Color(0xFF81C784); // light green
  if (goodness >= 0.5) return const Color(0xFFFFEB3B); // yellow
  if (goodness >= 0.25) return const Color(0xFFFF9800); // orange
  return const Color(0xFFE53935); // red
}

class HistoryScreen extends StatefulWidget {
  const HistoryScreen({super.key});

  @override
  State<HistoryScreen> createState() => _HistoryScreenState();
}

class _HistoryScreenState extends State<HistoryScreen> {
  final ScrollController _longTermController = ScrollController();
  final ScrollController _weeklyController = ScrollController();

  @override
  void dispose() {
    _longTermController.dispose();
    _weeklyController.dispose();
    super.dispose();
  }

  // ---------------------------------------------------------------------------
  // Data helpers
  // ---------------------------------------------------------------------------

  /// date-only DateTime -> that day's metrics map (key -> [value, status]).
  Map<DateTime, Map<String, dynamic>> _daysByDate() {
    final Map<dynamic, dynamic> all = AppData.instance.sensorAndUserData;
    final result = <DateTime, Map<String, dynamic>>{};
    all.forEach((k, v) {
      final parsed = DateTime.tryParse(k.toString());
      if (parsed == null || v is! Map) return;
      result[DateTime(parsed.year, parsed.month, parsed.day)] =
          Map<String, dynamic>.from(v);
    });
    return result;
  }

  /// Value (index 0) of a metric on a given day, or null if missing.
  dynamic _valueOf(Map<String, dynamic> day, String key) {
    final entry = day[key];
    if (entry is List && entry.isNotEmpty) return entry[0];
    return null;
  }

  /// Average of a metric over the given days. For yes/no metrics this is the
  /// number of "yes" days. Returns null when there is no data.
  _Average? _average(String key, _Metric metric, Iterable<Map<String, dynamic>> days) {
    double sum = 0;
    int count = 0;
    for (final day in days) {
      final v = _valueOf(day, key);
      if (v == null) continue;
      if (metric.kind == _Kind.yesNo) {
        sum += (v == true) ? 1 : 0;
      } else if (v is num) {
        sum += v.toDouble();
      } else {
        continue;
      }
      count++;
    }
    if (count == 0) return null;
    return _Average(sum: sum, count: count);
  }

  /// Monday-to-Sunday dates of the current week.
  List<DateTime> _currentWeek() {
    final now = DateTime.now();
    final today = DateTime(now.year, now.month, now.day);
    final monday = today.subtract(Duration(days: today.weekday - 1));
    return List.generate(7, (i) => DateTime(monday.year, monday.month, monday.day + i));
  }

  String _fmt(num n) =>
      n == n.roundToDouble() ? n.toInt().toString() : n.toStringAsFixed(1);

  // ---------------------------------------------------------------------------
  // Build
  // ---------------------------------------------------------------------------

  @override
  Widget build(BuildContext context) {
    final byDate = _daysByDate();

    return Scaffold(
      // The back arrow is added automatically when this screen is pushed.
      appBar: AppBar(title: const Text('My History')),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('Long-term ratings',
                  style: Theme.of(context).textTheme.titleLarge),
              const SizedBox(height: 8),
              Expanded(flex: 1, child: _buildLongTerm(byDate)),
              const SizedBox(height: 16),
              Text('Weekly history',
                  style: Theme.of(context).textTheme.titleLarge),
              const SizedBox(height: 8),
              Expanded(flex: 1, child: _buildWeekly(byDate)),
            ],
          ),
        ),
      ),
    );
  }

  // ---------------------------------------------------------------------------
  // Long-term section
  // ---------------------------------------------------------------------------

  Widget _buildLongTerm(Map<DateTime, Map<String, dynamic>> byDate) {
    final days = byDate.values.toList();
    final items = <Widget>[];

    for (final e in _metrics.entries) {
      final avg = _average(e.key, e.value, days);
      if (avg == null) continue;
      items.add(_buildAverageRow(e.value, avg, totalLabel: 'days'));
    }

    return _SectionCard(
      child: items.isEmpty
          ? const Center(child: Text('No data available'))
          : _ScrollList(controller: _longTermController, children: items),
    );
  }

  // ---------------------------------------------------------------------------
  // Weekly section
  // ---------------------------------------------------------------------------

  Widget _buildWeekly(Map<DateTime, Map<String, dynamic>> byDate) {
    final week = _currentWeek();
    final weekDays = week.map((d) => byDate[d]).toList(); // null = no data

    final items = <Widget>[
      // Checkbox rows (as in the sketch).
      _CheckboxWeekRow(
        title: 'Sleep > ${_fmt(_sleepThresholdHours)} h',
        letters: _dayLetters,
        hasData: weekDays.map((d) => d != null && _valueOf(d, 'sleep_h') != null).toList(),
        checked: weekDays.map((d) {
          final v = d == null ? null : _valueOf(d, 'sleep_h');
          return v is num && v > _sleepThresholdHours;
        }).toList(),
      ),
      for (final key in const ['exercise_logged', 'social_interaction'])
        _CheckboxWeekRow(
          title: _metrics[key]!.label,
          letters: _dayLetters,
          hasData: weekDays.map((d) => d != null && _valueOf(d, key) != null).toList(),
          checked: weekDays.map((d) => d != null && _valueOf(d, key) == true).toList(),
        ),
    ];

    // Weekly averages for the numeric metrics.
    final presentDays = weekDays.whereType<Map<String, dynamic>>().toList();
    for (final e in _metrics.entries) {
      if (e.value.kind == _Kind.yesNo) continue; // shown as checkboxes above
      final avg = _average(e.key, e.value, presentDays);
      if (avg == null) continue;
      items.add(_buildAverageRow(e.value, avg, totalLabel: 'days'));
    }

    return _SectionCard(
      child: _ScrollList(controller: _weeklyController, children: items),
    );
  }

  // ---------------------------------------------------------------------------
  // Shared row for an averaged metric
  // ---------------------------------------------------------------------------

  Widget _buildAverageRow(_Metric metric, _Average avg, {required String totalLabel}) {
    Widget body;

    switch (metric.kind) {
      case _Kind.progress:
        final value = avg.mean;
        final progress = (value / metric.max).clamp(0.0, 1.0).toDouble();
        final color = _goodnessColor(_goodnessFor(metric, progress));
        body = Row(
          children: [
            Expanded(
              child: ClipRRect(
                borderRadius: BorderRadius.circular(6),
                child: LinearProgressIndicator(
                  value: progress,
                  minHeight: 10,
                  color: color,
                  backgroundColor: color.withValues(alpha: 0.2),
                ),
              ),
            ),
            const SizedBox(width: 10),
            Text('${_fmt(value)} / ${_fmt(metric.max)}'),
          ],
        );
        break;
      case _Kind.number:
        body = Text(
          '${_fmt(avg.mean)}${metric.unit.isNotEmpty ? ' ${metric.unit}' : ''}',
          style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w500),
        );
        break;
      case _Kind.yesNo:
        final share = avg.sum / avg.count;
        final color = _goodnessColor(share);
        body = Row(
          children: [
            Expanded(
              child: ClipRRect(
                borderRadius: BorderRadius.circular(6),
                child: LinearProgressIndicator(
                  value: share,
                  minHeight: 10,
                  color: color,
                  backgroundColor: color.withValues(alpha: 0.2),
                ),
              ),
            ),
            const SizedBox(width: 10),
            Text('${_fmt(avg.sum)} / ${avg.count} $totalLabel'),
          ],
        );
        break;
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(metric.label, style: const TextStyle(fontWeight: FontWeight.w600)),
        const SizedBox(height: 6),
        body,
      ],
    );
  }

  /// Converts a normalized value (0-1) to "how good it is" (0-1).
  /// Metrics where lower is better are inverted; temperature is judged by its
  /// distance from ~37 °C.
  double _goodnessFor(_Metric metric, double progress) {
    final key = _metrics.entries.firstWhere((e) => e.value == metric).key;
    switch (key) {
      case 'hrr':
      case 'radiation_msv_cumulative':
        return 1 - progress;
      case 'temp_c':
        final temp = progress * metric.max;
        final diff = (temp - 37).abs();
        return (1 - diff / 3).clamp(0.0, 1.0).toDouble();
      default:
        return progress; // hrv, spo2, sleep_quality, mood: higher is better
    }
  }
}

// -----------------------------------------------------------------------------
// Small helper types & widgets
// -----------------------------------------------------------------------------

class _Average {
  final double sum;
  final int count;
  const _Average({required this.sum, required this.count});
  double get mean => sum / count;
}

class _SectionCard extends StatelessWidget {
  final Widget child;
  const _SectionCard({required this.child});

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        border: Border.all(color: Theme.of(context).dividerColor),
        borderRadius: BorderRadius.circular(16),
      ),
      clipBehavior: Clip.antiAlias,
      child: child,
    );
  }
}

/// Scrollable list with an always-visible scrollbar that doesn't cover entries.
class _ScrollList extends StatelessWidget {
  final ScrollController controller;
  final List<Widget> children;
  const _ScrollList({required this.controller, required this.children});

  @override
  Widget build(BuildContext context) {
    return Scrollbar(
      controller: controller,
      thumbVisibility: true,
      child: ListView.separated(
        controller: controller,
        // Extra right padding keeps entries clear of the scrollbar.
        padding: const EdgeInsets.fromLTRB(12, 12, 20, 12),
        itemCount: children.length,
        separatorBuilder: (_, _) => const SizedBox(height: 14),
        itemBuilder: (_, i) => children[i],
      ),
    );
  }
}

/// A title plus seven read-only checkboxes (Mon-Sun).
class _CheckboxWeekRow extends StatelessWidget {
  final String title;
  final List<String> letters;
  final List<bool> checked;
  final List<bool> hasData;

  const _CheckboxWeekRow({
    required this.title,
    required this.letters,
    required this.checked,
    required this.hasData,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(title, style: const TextStyle(fontWeight: FontWeight.w600)),
        const SizedBox(height: 4),
        Row(
          children: List.generate(7, (i) {
            return Expanded(
              child: Column(
                children: [
                  // IgnorePointer makes the checkbox unchangeable while keeping
                  // its normal (enabled) look.
                  IgnorePointer(
                    child: Checkbox(
                      value: checked[i],
                      onChanged: (_) {},
                      visualDensity: VisualDensity.compact,
                    ),
                  ),
                  Text(
                    letters[i],
                    style: TextStyle(
                      fontSize: 12,
                      color: hasData[i] ? null : Theme.of(context).disabledColor,
                    ),
                  ),
                ],
              ),
            );
          }),
        ),
      ],
    );
  }
}
