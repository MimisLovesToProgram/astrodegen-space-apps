import 'package:flutter/material.dart';

import 'package:app_frontend/logic/view_models.dart';

/// Status colors (0 = Good, 1 = Watch, 2 = Warning, 3 = Alert).
const List<Color> _statusColors = [
  Color(0xFF81C784), // light green
  Color(0xFFFFEB3B), // yellow
  Color(0xFFFF9800), // orange
  Color(0xFFE53935), // red
];
const List<String> _statusLabels = ['Good', 'Watch', 'Warning', 'Alert'];

/// How each metric is displayed.
enum _MetricKind { progress, number, yesNo, list }

class _MetricConfig {
  final String label;
  final _MetricKind kind;
  final double max; // used for progress kind
  final String unit;

  const _MetricConfig(
    this.label,
    this.kind, {
    this.max = 1,
    this.unit = '',
  });
}

/// Keys follow the names in your notebook table. Order = display order.
const Map<String, _MetricConfig> _metricConfigs = {
  'hrr': _MetricConfig('Resting heart rate', _MetricKind.progress,
      max: 150, unit: 'bpm'),
  'hrv': _MetricConfig('Heart rate variability', _MetricKind.progress,
      max: 100, unit: 'ms'),
  'spo2': _MetricConfig('SpO2', _MetricKind.progress, max: 100, unit: '%'),
  'temp_c': _MetricConfig('Temperature', _MetricKind.progress,
      max: 42, unit: '°C'),
  'radiation_msv_cumulative': _MetricConfig(
      'Cumulative radiation', _MetricKind.progress,
      max: 600, unit: 'mSv'),
  'sleep_h': _MetricConfig('Sleep hours', _MetricKind.number, unit: 'h'),
  'sleep_quality':
      _MetricConfig('Sleep quality', _MetricKind.progress, max: 5),
  'mood': _MetricConfig('Mood', _MetricKind.progress, max: 5),
  'symptoms': _MetricConfig('Symptoms', _MetricKind.number),
  'exercise_logged': _MetricConfig('Exercise today', _MetricKind.yesNo),
  'social_interaction':
      _MetricConfig('Social interaction today', _MetricKind.yesNo),
};

class StatusScreen extends StatefulWidget {
  const StatusScreen({super.key});

  @override
  State<StatusScreen> createState() => _StatusScreenState();
}

class _StatusScreenState extends State<StatusScreen> {
  final ScrollController _todayController = ScrollController();
  final ScrollController _historyController = ScrollController();

  @override
  void dispose() {
    _todayController.dispose();
    _historyController.dispose();
    super.dispose();
  }

  // ---------------------------------------------------------------------------
  // Data helpers
  // ---------------------------------------------------------------------------

  /// Returns today's metrics map. Assumes date keys look like "yyyy-MM-dd".
  /// Falls back to the most recent date if today has no entry.
  Map<String, dynamic> _todayData() {
    final Map<dynamic, dynamic> all = AppData.instance.sensorAndUserData;
    if (all.isEmpty) return {};

    final now = DateTime.now();
    final todayKey = '${now.year.toString().padLeft(4, '0')}-'
        '${now.month.toString().padLeft(2, '0')}-'
        '${now.day.toString().padLeft(2, '0')}';

    dynamic entry = all[todayKey];
    if (entry == null) {
      final keys = all.keys.map((k) => k.toString()).toList()..sort();
      entry = all[keys.last];
    }
    return Map<String, dynamic>.from(entry as Map);
  }

  Color _statusColor(int status) =>
      _statusColors[status.clamp(0, _statusColors.length - 1)];

  /// Domain percentage (0-100) -> color: green good, red bad.
  Color _percentColor(double percent) {
    if (percent >= 75) return _statusColors[0];
    if (percent >= 50) return _statusColors[1];
    if (percent >= 25) return _statusColors[2];
    return _statusColors[3];
  }

  String _fmt(num n) =>
      n == n.roundToDouble() ? n.toInt().toString() : n.toStringAsFixed(1);

  // ---------------------------------------------------------------------------
  // Build
  // ---------------------------------------------------------------------------

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Row(
          children: [
            Icon(Icons.rocket_launch),
            SizedBox(width: 8),
            Text('Astrocrates'),
          ],
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.logout),
            tooltip: 'Log out',
            onPressed: () {
              // TODO: implement logout.
            },
          ),
        ],
      ),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text("Today's Status",
                  style: Theme.of(context).textTheme.titleLarge),
              const SizedBox(height: 8),
              Expanded(flex: 3, child: _buildTodaySection()),
              const SizedBox(height: 16),
              Text('Historical Status',
                  style: Theme.of(context).textTheme.titleLarge),
              const SizedBox(height: 8),
              Expanded(flex: 2, child: _buildHistorySection()),
            ],
          ),
        ),
      ),
    );
  }

  // ---------------------------------------------------------------------------
  // Today's status
  // ---------------------------------------------------------------------------

  Widget _buildTodaySection() {
    final data = _todayData();
    final entries = _metricConfigs.entries
        .where((e) => data.containsKey(e.key))
        .toList();

    return _SectionCard(
      child: entries.isEmpty
          ? const Center(child: Text('No data for today'))
          : Scrollbar(
              controller: _todayController,
              thumbVisibility: true,
              child: ListView.separated(
                controller: _todayController,
                // Right padding keeps entries clear of the scrollbar.
                padding: const EdgeInsets.fromLTRB(12, 12, 20, 12),
                itemCount: entries.length,
                separatorBuilder: (_, __) => const SizedBox(height: 14),
                itemBuilder: (context, i) {
                  final key = entries[i].key;
                  final cfg = entries[i].value;
                  final list = data[key] as List;
                  return _buildMetric(cfg, list[0], (list[1] as num).toInt());
                },
              ),
            ),
    );
  }

  Widget _buildMetric(_MetricConfig cfg, dynamic value, int status) {
    final color = _statusColor(status);
    Widget body;

    switch (cfg.kind) {
      case _MetricKind.progress:
        final num v = value as num;
        final progress = (v / cfg.max).clamp(0.0, 1.0).toDouble();
        body = Row(
          children: [
            Expanded(
              child: ClipRRect(
                borderRadius: BorderRadius.circular(6),
                child: LinearProgressIndicator(
                  value: progress,
                  minHeight: 10,
                  color: color,
                  backgroundColor: color.withOpacity(0.2),
                ),
              ),
            ),
            const SizedBox(width: 10),
            Text('${_fmt(v)} / ${_fmt(cfg.max)}'),
          ],
        );
        break;
      case _MetricKind.number:
        body = Text(
          '${_fmt(value as num)}${cfg.unit.isNotEmpty ? ' ${cfg.unit}' : ''}',
          style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w500),
        );
        break;
      case _MetricKind.yesNo:
        body = Text(
          (value == true) ? 'Yes' : 'No',
          style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w500),
        );
        break;
      case _MetricKind.list:
        final items = (value is List) ? value : <dynamic>[];
        body = Text(
          items.isEmpty ? 'None' : items.join(', '),
          style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w500),
        );
        break;
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(cfg.label, style: const TextStyle(fontWeight: FontWeight.w600)),
        const SizedBox(height: 6),
        body,
        const SizedBox(height: 6),
        _StatusChip(
          label: _statusLabels[status.clamp(0, 3)],
          color: color,
        ),
      ],
    );
  }

  // ---------------------------------------------------------------------------
  // Historical status
  // ---------------------------------------------------------------------------

  Widget _buildHistorySection() {
    final Map<dynamic, dynamic> domains = AppData.instance.domains;
    final entries = domains.entries.toList();

    return _SectionCard(
      child: Column(
        children: [
          Expanded(
            child: entries.isEmpty
                ? const Center(child: Text('No data available'))
                : Scrollbar(
                    controller: _historyController,
                    thumbVisibility: true,
                    child: ListView.separated(
                      controller: _historyController,
                      padding: const EdgeInsets.fromLTRB(12, 12, 20, 8),
                      itemCount: entries.length,
                      separatorBuilder: (_, __) => const SizedBox(height: 14),
                      itemBuilder: (context, i) {
                        final name = entries[i].key.toString();
                        final percent =
                            (entries[i].value as num).toDouble().clamp(0.0, 100.0);
                        final color = _percentColor(percent);
                        return Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(name,
                                style: const TextStyle(
                                    fontWeight: FontWeight.w600)),
                            const SizedBox(height: 6),
                            Row(
                              children: [
                                Expanded(
                                  child: ClipRRect(
                                    borderRadius: BorderRadius.circular(6),
                                    child: LinearProgressIndicator(
                                      value: percent / 100,
                                      minHeight: 10,
                                      color: color,
                                      backgroundColor:
                                          color.withOpacity(0.2),
                                    ),
                                  ),
                                ),
                                const SizedBox(width: 10),
                                Text('${_fmt(percent)} / 100'),
                              ],
                            ),
                          ],
                        );
                      },
                    ),
                  ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(12, 0, 12, 12),
            child: Align(
              alignment: Alignment.centerRight,
              child: OutlinedButton.icon(
                onPressed: () {
                  // TODO: navigate to the full history screen, e.g.:
                  // Navigator.push(context, MaterialPageRoute(
                  //     builder: (_) => const HistoryScreen()));
                },
                icon: const Text('See full history'),
                label: const Icon(Icons.arrow_forward, size: 18),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

// -----------------------------------------------------------------------------
// Small reusable widgets
// -----------------------------------------------------------------------------

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

class _StatusChip extends StatelessWidget {
  final String label;
  final Color color;
  const _StatusChip({required this.label, required this.color});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 2),
      decoration: BoxDecoration(
        color: color,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Text(
        label,
        style: const TextStyle(
          color: Colors.black87,
          fontSize: 12,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }
}
