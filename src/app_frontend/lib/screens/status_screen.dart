import 'package:material_ui/material_ui.dart';

import '../logic/crew_api.dart';
import '../logic/models.dart';
import '../logic/view_models.dart';
import 'history_screen.dart';
import 'login_screen.dart';

/// Status colors (0 = Good, 1 = Watch, 2 = Warning, 3 = Alert).
const List<Color> _statusColors = [
  Color(0xFF81C784), // light green
  Color(0xFFFFEB3B), // yellow
  Color(0xFFFF9800), // orange
  Color(0xFFE53935), // red
];
const List<String> _statusLabels = ['Good', 'Watch', 'Warning', 'Alert'];

/// We use grey for readings that have not been assessed yet. A missing level
/// must never look like a healthy green reading.
const Color _unknownColor = Color(0xFFBDBDBD);
const String _unknownLabel = 'Not assessed';

/// How each metric is displayed.
enum _MetricKind { progress, number, yesNo, list }

class _MetricConfig {
  final String label;
  final _MetricKind kind;
  final double max; // used for progress kind
  final String unit;

  const _MetricConfig(this.label, this.kind, {this.max = 1, this.unit = ''});
}

/// Keys match the field names returned by the crew history API.
/// Order = display order.
const Map<String, _MetricConfig> _metricConfigs = {
  'hrr': _MetricConfig(
    'Resting heart rate',
    _MetricKind.progress,
    max: 150,
    unit: 'bpm',
  ),
  'hrv': _MetricConfig(
    'Heart rate variability',
    _MetricKind.progress,
    max: 100,
    unit: 'ms',
  ),
  'spo2': _MetricConfig('SpO2', _MetricKind.progress, max: 100, unit: '%'),
  'temp_c': _MetricConfig(
    'Temperature',
    _MetricKind.progress,
    max: 42,
    unit: '°C',
  ),
  'radiation_msv_cumulative': _MetricConfig(
    'Cumulative radiation',
    _MetricKind.progress,
    max: 600,
    unit: 'mSv',
  ),
  'sleep_h': _MetricConfig('Sleep hours', _MetricKind.number, unit: 'h'),
  'sleep_quality': _MetricConfig('Sleep quality', _MetricKind.progress, max: 5),
  'mood': _MetricConfig('Mood', _MetricKind.progress, max: 5),
  'activity_pct_target': _MetricConfig(
    'Activity vs target',
    _MetricKind.progress,
    max: 100,
    unit: '%',
  ),
  'symptoms': _MetricConfig('Symptoms', _MetricKind.list),
  'exercise_logged': _MetricConfig('Exercise today', _MetricKind.yesNo),
  'social_interaction': _MetricConfig(
    'Social interaction today',
    _MetricKind.yesNo,
  ),
};

class StatusScreen extends StatefulWidget {
  const StatusScreen({super.key});

  @override
  State<StatusScreen> createState() => _StatusScreenState();
}

class _StatusScreenState extends State<StatusScreen> {
  final ScrollController _todayController = ScrollController();
  final ScrollController _historyController = ScrollController();

  bool isLoading = false;
  String? error;

  @override
  void dispose() {
    _todayController.dispose();
    _historyController.dispose();
    super.dispose();
  }

  Future<void> _refresh() async {
    setState(() {
      isLoading = true;
      error = null;
    });
    try {
      await AppData.instance.loadSensorData(CurrentUser.instance.crewId);
    } catch (failure) {
      if (mounted) setState(() => error = failure.toString());
    } finally {
      if (mounted) setState(() => isLoading = false);
    }
  }

  void _signOut() {
    CurrentUser.instance.logout();
    AppData.instance.reset();
    Navigator.pushAndRemoveUntil(
      context,
      MaterialPageRoute(builder: (_) => const LoginScreen()),
      (_) => false,
    );
  }

  // ---------------------------------------------------------------------------
  // Data helpers
  // ---------------------------------------------------------------------------

  /// Day keys from the API, newest first. Keys look like "yyyy-MM-dd".
  List<String> _daysNewestFirst() =>
      AppData.instance.sensorData.keys.toList()..sort((a, b) => b.compareTo(a));

  /// We show the most recent day that has data. When there is no reading for
  /// today yet, the title says which day the values come from.
  String? _latestDay() {
    final days = _daysNewestFirst();
    return days.isEmpty ? null : days.first;
  }

  Color _statusColor(int? status) =>
      status == null ? _unknownColor : _statusColors[status];

  String _statusLabel(int? status) =>
      status == null ? _unknownLabel : _statusLabels[status];

  /// The worst assessed level of a day, or null if nothing was assessed.
  int? _worstLevel(Map<String, MetricReading> day) {
    int? worst;
    for (final reading in day.values) {
      final level = reading.level;
      if (level != null && (worst == null || level > worst)) worst = level;
    }
    return worst;
  }

  String _fmt(num n) =>
      n == n.roundToDouble() ? n.toInt().toString() : n.toStringAsFixed(1);

  // ---------------------------------------------------------------------------
  // Build
  // ---------------------------------------------------------------------------

  @override
  Widget build(BuildContext context) {
    final data = AppData.instance;
    final latest = _latestDay();
    final todayKey = DateTime.now().toIso8601String().substring(0, 10);
    final todayTitle = latest == null || latest == todayKey
        ? "Today's Status"
        : 'Latest Status ($latest)';

    return Scaffold(
      appBar: AppBar(
        title: Row(
          children: [
            const Icon(Icons.rocket_launch),
            const SizedBox(width: 8),
            Flexible(
              child: Text(
                data.profile['name'] as String? ?? 'Astrocrates',
                overflow: TextOverflow.ellipsis,
              ),
            ),
          ],
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            tooltip: 'Refresh',
            onPressed: isLoading ? null : _refresh,
          ),
          IconButton(
            icon: const Icon(Icons.logout),
            tooltip: 'Log out',
            onPressed: isLoading ? null : _signOut,
          ),
        ],
      ),
      body: Stack(
        children: [
          SafeArea(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  if (error != null)
                    Padding(
                      padding: const EdgeInsets.only(bottom: 8),
                      child: Text(
                        error!,
                        style: const TextStyle(color: Colors.red),
                      ),
                    ),
                  if (data.notice != null)
                    Padding(
                      padding: const EdgeInsets.only(bottom: 8),
                      child: Text(data.notice!),
                    ),
                  Text(
                    todayTitle,
                    style: Theme.of(context).textTheme.titleLarge,
                  ),
                  const SizedBox(height: 8),
                  Expanded(flex: 3, child: _buildTodaySection(latest)),
                  const SizedBox(height: 16),
                  Text(
                    'Recent Days',
                    style: Theme.of(context).textTheme.titleLarge,
                  ),
                  const SizedBox(height: 8),
                  Expanded(flex: 2, child: _buildHistorySection()),
                  const SizedBox(height: 8),
                  const Text(
                    'Prototype assessments based on simulated data. '
                    'Grey means the reading has not been assessed yet '
                    'or required data is missing.',
                    style: TextStyle(fontSize: 12),
                  ),
                ],
              ),
            ),
          ),
          if (isLoading)
            Positioned.fill(
              child: Container(
                color: const Color.fromARGB(150, 0, 0, 0),
                child: const Center(
                  child: SizedBox(
                    height: 50,
                    width: 50,
                    child: CircularProgressIndicator(
                      color: Colors.white,
                      strokeWidth: 8,
                    ),
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }

  // ---------------------------------------------------------------------------
  // Latest day's status
  // ---------------------------------------------------------------------------

  Widget _buildTodaySection(String? day) {
    final readings = day == null
        ? const <String, MetricReading>{}
        : AppData.instance.sensorData[day]!;
    final entries = _metricConfigs.entries
        .where((e) => readings.containsKey(e.key))
        .toList();

    return _SectionCard(
      child: entries.isEmpty
          ? const Center(child: Text('No validated readings yet'))
          : Scrollbar(
              controller: _todayController,
              thumbVisibility: true,
              child: ListView.separated(
                controller: _todayController,
                // Right padding keeps entries clear of the scrollbar.
                padding: const EdgeInsets.fromLTRB(12, 12, 20, 12),
                itemCount: entries.length,
                separatorBuilder: (_, _) => const SizedBox(height: 14),
                itemBuilder: (context, i) =>
                    _buildMetric(entries[i].value, readings[entries[i].key]!),
              ),
            ),
    );
  }

  Widget _buildMetric(_MetricConfig cfg, MetricReading reading) {
    final color = _statusColor(reading.level);
    final value = reading.value;
    const valueStyle = TextStyle(fontSize: 16, fontWeight: FontWeight.w500);
    Widget body;

    if (value == null) {
      body = const Text('No reading', style: valueStyle);
    } else {
      switch (cfg.kind) {
        case _MetricKind.progress:
          if (value is! num) {
            body = Text('$value', style: valueStyle);
            break;
          }
          final progress = (value / cfg.max).clamp(0.0, 1.0).toDouble();
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
              Text(
                '${_fmt(value)} / ${_fmt(cfg.max)}'
                '${cfg.unit.isNotEmpty ? ' ${cfg.unit}' : ''}',
              ),
            ],
          );
        case _MetricKind.number:
          final shown = value is num ? _fmt(value) : '$value';
          body = Text(
            '$shown${cfg.unit.isNotEmpty ? ' ${cfg.unit}' : ''}',
            style: valueStyle,
          );
        case _MetricKind.yesNo:
          body = Text(value == true ? 'Yes' : 'No', style: valueStyle);
        case _MetricKind.list:
          final items = value is List ? value : [value];
          body = Text(
            items.isEmpty ? 'None' : items.join(', '),
            style: valueStyle,
          );
      }
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(cfg.label, style: const TextStyle(fontWeight: FontWeight.w600)),
        const SizedBox(height: 6),
        body,
        const SizedBox(height: 6),
        _StatusChip(label: _statusLabel(reading.level), color: color),
      ],
    );
  }

  // ---------------------------------------------------------------------------
  // Recent days
  // ---------------------------------------------------------------------------

  Widget _buildHistorySection() {
    final days = _daysNewestFirst().take(7).toList();

    return _SectionCard(
      child: Column(
        children: [
          Expanded(
            child: days.isEmpty
                ? const Center(child: Text('No data available'))
                : Scrollbar(
                    controller: _historyController,
                    thumbVisibility: true,
                    child: ListView.separated(
                      controller: _historyController,
                      padding: const EdgeInsets.fromLTRB(12, 12, 20, 8),
                      itemCount: days.length,
                      separatorBuilder: (_, _) => const SizedBox(height: 10),
                      itemBuilder: (context, i) {
                        final day = AppData.instance.sensorData[days[i]]!;
                        final level = _worstLevel(day);
                        return Row(
                          children: [
                            Expanded(
                              child: Text(
                                days[i],
                                style: const TextStyle(
                                  fontWeight: FontWeight.w600,
                                ),
                              ),
                            ),
                            _StatusChip(
                              label: _statusLabel(level),
                              color: _statusColor(level),
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
                  Navigator.push(
                    context,
                    MaterialPageRoute(builder: (_) => const HistoryScreen()),
                  );
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
