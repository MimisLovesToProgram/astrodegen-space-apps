import 'package:material_ui/material_ui.dart';

import '../logic/models.dart';
import '../logic/view_models.dart';
import 'login_screen.dart';

class StatusScreen extends StatefulWidget {
  const StatusScreen({super.key});
  @override
  State<StatusScreen> createState() => _StatusScreenState();
}

class _StatusScreenState extends State<StatusScreen> {
  bool loading = false;
  String? error;

  Future<void> refresh() async {
    setState(() {
      loading = true;
      error = null;
    });
    try {
      await AppData.instance.loadSensorData(CurrentUser.instance.crewId);
    } catch (failure) {
      if (mounted) setState(() => error = failure.toString());
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final data = AppData.instance;
    final days = data.sensorData.keys.toList()..sort((a, b) => b.compareTo(a));
    const colors = [Colors.green, Colors.amber, Colors.orange, Colors.red];
    const labels = ['Green', 'Yellow', 'Orange', 'Red'];
    return Scaffold(
      appBar: AppBar(
        title: Text(data.profile['name'] as String? ?? 'Crew history'),
        actions: [
          IconButton(
            tooltip: 'Refresh',
            onPressed: loading ? null : refresh,
            icon: const Icon(Icons.refresh),
          ),
          IconButton(
            tooltip: 'Sign out',
            icon: const Icon(Icons.logout),
            onPressed: () {
              CurrentUser.instance.logout();
              data.reset();
              Navigator.pushAndRemoveUntil(
                context,
                MaterialPageRoute(builder: (_) => const LoginScreen()),
                (_) => false,
              );
            },
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          if (loading) const LinearProgressIndicator(),
          if (error != null)
            Text(error!, style: const TextStyle(color: Colors.red)),
          if (data.notice != null)
            Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: Text(data.notice!),
            ),
          const Text(
            'Prototype assessments. Unknown means the reading has not been assessed or required data is missing.',
          ),
          if (days.isEmpty && !loading)
            const Padding(
              padding: EdgeInsets.all(16),
              child: Text('No validated readings yet.'),
            ),
          for (final day in days)
            Card(
              child: ExpansionTile(
                initiallyExpanded: day == days.first,
                title: Text(day),
                children: data.sensorData[day]!.entries.map((entry) {
                  final level = entry.value.level;
                  final value = entry.value.value;
                  final display = value is List
                      ? (value.isEmpty ? 'None' : value.join(', '))
                      : '$value';
                  return ListTile(
                    title: Text(entry.key.replaceAll('_', ' ')),
                    subtitle: Text(display),
                    trailing: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(
                          Icons.circle,
                          size: 12,
                          color: level == null ? Colors.grey : colors[level],
                        ),
                        const SizedBox(width: 6),
                        Text(level == null ? 'Unknown' : labels[level]),
                      ],
                    ),
                  );
                }).toList(),
              ),
            ),
        ],
      ),
    );
  }
}
