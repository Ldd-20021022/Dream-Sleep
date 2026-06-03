import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/api_service.dart';
import '../services/auth_service.dart';

class AlarmPage extends StatefulWidget {
  const AlarmPage({super.key});
  @override
  State<AlarmPage> createState() => _AlarmPageState();
}

class _AlarmPageState extends State<AlarmPage> {
  final _targetTime = TextEditingController(text: '07:00');
  int _wakeWindow = 30;
  String _smartMethod = 'light';
  List _suggestions = [];
  bool _loading = false;

  @override
  void initState() {
    super.initState();
    _loadAlarm();
  }

  Future<void> _loadAlarm() async {
    final api = context.read<ApiService>();
    api.setToken(context.read<AuthService>().token);
    try {
      final data = await api.get('/api/v1/iot/alarm');
      setState(() {
        _targetTime.text = data['target_time'] ?? '07:00';
        _wakeWindow = data['wake_window'] ?? 30;
        _smartMethod = data['smart_method'] ?? 'light';
      });
    } catch (_) {}
  }

  Future<void> _saveAlarm() async {
    final api = context.read<ApiService>();
    api.setToken(context.read<AuthService>().token);
    try {
      await api.post('/api/v1/iot/alarm', {
        'target_time': _targetTime.text,
        'wake_window': _wakeWindow,
        'smart_method': _smartMethod,
      });
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('已保存')));
      }
    } catch (_) {}
  }

  Future<void> _getSmartAlarm() async {
    setState(() => _loading = true);
    final api = context.read<ApiService>();
    api.setToken(context.read<AuthService>().token);
    try {
      final data = await api.get('/api/v1/sleep-records/smart-alarm?wake_target=${_targetTime.text}');
      setState(() { _suggestions = (data['suggested_bedtime'] as List?) ?? []; });
    } catch (_) {}
    setState(() => _loading = false);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('智能闹钟')),
      body: ListView(padding: const EdgeInsets.all(16), children: [
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(children: [
              TextField(controller: _targetTime, decoration: const InputDecoration(labelText: '目标起床时间', hintText: '07:00')),
              const SizedBox(height: 16),
              const Text('唤醒窗口: ${_wakeWindow}分钟'),
              Slider(value: _wakeWindow.toDouble(), min: 10, max: 60, divisions: 10, onChanged: (v) => setState(() => _wakeWindow = v.round())),
              const SizedBox(height: 12),
              const Text('智能唤醒方式'),
              Row(mainAxisAlignment: MainAxisAlignment.center, children: [
                _methodBtn('light', '💡 光线'),
                const SizedBox(width: 8),
                _methodBtn('sound', '🔔 声音'),
                const SizedBox(width: 8),
                _methodBtn('vibrate', '📳 震动'),
              ]),
              const SizedBox(height: 16),
              Row(children: [
                Expanded(child: ElevatedButton(onPressed: _saveAlarm, child: const Text('保存设置'))),
                const SizedBox(width: 12),
                Expanded(child: OutlinedButton(onPressed: _loading ? null : _getSmartAlarm, child: Text(_loading ? '计算中...' : '智能建议'))),
              ]),
            ]),
          ),
        ),
        if (_suggestions.isNotEmpty) ...[
          const SizedBox(height: 16),
          const Text('建议就寝时间', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
          ..._suggestions.map((s) => Card(
            child: ListTile(
              leading: const Icon(Icons.bedtime, color: Color(0xFF6C63FF)),
              title: Text(s is String ? s : (s['time'] ?? '')),
              subtitle: Text(s is Map ? (s['reason'] ?? s['cycles'] ?? '') : ''),
            ),
          )),
        ],
      ]),
    );
  }

  Widget _methodBtn(String method, String label) {
    final sel = _smartMethod == method;
    return GestureDetector(
      onTap: () => setState(() => _smartMethod = method),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        decoration: BoxDecoration(
          color: sel ? const Color(0xFF6C63FF).withOpacity(0.1) : null,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: sel ? const Color(0xFF6C63FF) : Colors.grey.withOpacity(0.3)),
        ),
        child: Text(label, style: TextStyle(fontSize: 14, color: sel ? const Color(0xFF6C63FF) : null)),
      ),
    );
  }

  @override
  void dispose() { _targetTime.dispose(); super.dispose(); }
}
