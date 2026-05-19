import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/api_service.dart';
import '../services/auth_service.dart';

class TasksPage extends StatefulWidget {
  const TasksPage({super.key});
  @override
  State<TasksPage> createState() => _TasksPageState();
}

class _TasksPageState extends State<TasksPage> {
  List _tasks = [];
  List _badges = [];
  Map<String, dynamic>? _points;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _loadData();
  }

  Future<void> _loadData() async {
    final api = context.read<ApiService>();
    api.setToken(context.read<AuthService>().token);
    setState(() => _loading = true);
    try {
      final results = await Future.wait([
        api.get('/api/v1/tasks/today'),
        api.get('/api/v1/tasks/badges'),
        api.get('/api/v1/tasks/points/summary'),
      ]);
      setState(() {
        _tasks = (results[0]['tasks'] as List?) ?? [];
        _badges = (results[1]['badges'] as List?) ?? (results[1] is List ? results[1] : []);
        _points = results[2];
        _loading = false;
      });
    } catch (e) {
      setState(() => _loading = false);
    }
  }

  Future<void> _completeTask(int taskId) async {
    final api = context.read<ApiService>();
    api.setToken(context.read<AuthService>().token);
    try {
      await api.post('/api/v1/tasks/complete', {'task_id': taskId});
      _loadData();
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('操作失败: $e')));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final completed = _tasks.where((t) => t['completed'] == true).length;
    final total = _tasks.length;
    return Scaffold(
      appBar: AppBar(title: const Text('每日任务')),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : RefreshIndicator(
              onRefresh: _loadData,
              child: ListView(padding: const EdgeInsets.all(16), children: [
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(children: [
                      Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
                        const Text('今日进度', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
                        Text('🏆 ${_points?['total_points'] ?? 0} 积分', style: const TextStyle(fontSize: 14)),
                      ]),
                      const SizedBox(height: 12),
                      LinearProgressIndicator(value: total > 0 ? completed / total : 0),
                      const SizedBox(height: 4),
                      Text('$completed / $total', style: const TextStyle(color: Colors.grey, fontSize: 12)),
                    ]),
                  ),
                ),
                const SizedBox(height: 16),
                ..._tasks.map((t) => Card(
                      child: ListTile(
                        leading: Icon(t['completed'] == true ? Icons.check_circle : Icons.circle_outlined,
                            color: t['completed'] == true ? Colors.green : Colors.grey),
                        title: Text(t['title'] ?? t['name'] ?? ''),
                        subtitle: Text('+${t['xp'] ?? t['points'] ?? 0} XP', style: const TextStyle(fontSize: 12)),
                        trailing: t['completed'] != true
                            ? IconButton(icon: const Icon(Icons.check, color: Color(0xFF6C63FF)), onPressed: () => _completeTask(t['id']))
                            : null,
                      ),
                    )),
                const SizedBox(height: 16),
                if (_badges.isNotEmpty) ...[
                  const Text('🏅 徽章', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
                  const SizedBox(height: 8),
                  Wrap(spacing: 8, children: _badges.map((b) => Chip(
                    avatar: Text(b['icon'] ?? '🏅'),
                    label: Text(b['title'] ?? b['name'] ?? '', style: TextStyle(fontSize: 12, color: b['unlocked'] == true ? null : Colors.grey)),
                  )).toList()),
                ],
              ]),
            ),
    );
  }
}
