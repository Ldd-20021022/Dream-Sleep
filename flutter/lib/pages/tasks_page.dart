import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/api_service.dart';
import '../services/auth_service.dart';

const _timeLabels = {
  'morning': '☀️ 晨间仪式',
  'afternoon': '🌤️ 日间习惯',
  'evening': '🌙 睡前准备',
};
const _timeOrder = ['morning', 'afternoon', 'evening'];

class TasksPage extends StatefulWidget {
  const TasksPage({super.key});
  @override
  State<TasksPage> createState() => _TasksPageState();
}

class _TasksPageState extends State<TasksPage> {
  List<Map<String, dynamic>> _groups = [];
  List _badges = [];
  int _points = 0;
  List<bool> _streakWeek = [];
  bool _loading = true;
  String? _animTaskId;
  bool _showCelebration = false;
  Map<String, dynamic>? _newBadge;
  List<String> _prevBadgeIds = [];

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

      final tasks = (results[0]['tasks'] as List?)?.cast<Map<String, dynamic>>() ?? [];
      final streakList = (results[0]['streak_week'] as List?)?.cast<bool>() ?? [];
      final badges = (results[1] is List ? results[1] : results[1]['badges'] ?? []) as List;
      final points = results[2]['total_points'] ?? 0;

      // Group by time_of_day
      final grouped = <String, List<Map<String, dynamic>>>{};
      for (final t in tasks) {
        final tod = t['time_of_day'] ?? 'evening';
        grouped.putIfAbsent(tod, () => []).add(t);
      }

      final groups = _timeOrder
          .where((k) => grouped.containsKey(k) && grouped[k]!.isNotEmpty)
          .map((k) => {'key': k, 'label': _timeLabels[k], 'tasks': grouped[k]!})
          .toList();

      // Check new badge
      final currentUnlocked = badges.where((b) => b['unlocked'] == true).map((b) => b['badge_id']).toList();
      final newBadgeId = currentUnlocked.cast<String?>().firstWhere((id) => !_prevBadgeIds.contains(id), orElse: () => null);
      Map<String, dynamic>? newBadge;
      if (newBadgeId != null) {
        newBadge = badges.cast<Map<String, dynamic>?>().firstWhere((b) => b?['badge_id'] == newBadgeId, orElse: () => null);
        _prevBadgeIds = currentUnlocked.cast<String>();
      }

      setState(() {
        _groups = groups;
        _badges = badges;
        _points = points;
        _streakWeek = streakList;
        _loading = false;
        _showCelebration = newBadge != null;
        _newBadge = newBadge;
      });
    } catch (e) {
      setState(() => _loading = false);
    }
  }

  Future<void> _completeTask(String taskId) async {
    final api = context.read<ApiService>();
    api.setToken(context.read<AuthService>().token);
    try {
      await api.post('/api/v1/tasks/complete', {'task_id': taskId});
      setState(() => _animTaskId = taskId);
      Future.delayed(const Duration(milliseconds: 1200), () {
        if (mounted) setState(() => _animTaskId = null);
      });
      _loadData();
    } catch (_) {}
  }

  @override
  Widget build(BuildContext context) {
    final totalTasks = _groups.fold<int>(0, (s, g) => s + (g['tasks'] as List).length);
    final doneTasks = _groups.fold<int>(0, (s, g) =>
        s + (g['tasks'] as List).where((t) => t['done'] == true).length);

    return Stack(children: [
      Scaffold(
        appBar: AppBar(title: const Text('每日任务')),
        body: _loading
            ? const Center(child: CircularProgressIndicator())
            : RefreshIndicator(
                onRefresh: _loadData,
                child: ListView(padding: const EdgeInsets.all(16), children: [
                  // Streak dots
                  if (_streakWeek.isNotEmpty)
                    Card(
                      child: Padding(
                        padding: const EdgeInsets.all(20),
                        child: Column(children: [
                          const Text('本周连续打卡', style: TextStyle(color: Colors.grey, fontSize: 13)),
                          const SizedBox(height: 12),
                          Row(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: _streakWeek.map((on) => Container(
                              width: 40, height: 40,
                              margin: const EdgeInsets.symmetric(horizontal: 6),
                              decoration: BoxDecoration(
                                shape: BoxShape.circle,
                                color: on ? const Color(0xFFF39C12).withOpacity(0.2) : Colors.white.withOpacity(0.04),
                                border: Border.all(color: on ? const Color(0xFFF39C12).withOpacity(0.5) : Colors.white.withOpacity(0.06)),
                              ),
                              child: Center(child: Text(on ? '🔥' : '·', style: const TextStyle(fontSize: 18))),
                            )).toList(),
                          ),
                          const SizedBox(height: 8),
                          Text('${_streakWeek.where((x) => x).length}/7 天',
                              style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 15)),
                        ]),
                      ),
                    ),
                  const SizedBox(height: 12),
                  // Progress
                  Card(
                    child: Padding(
                      padding: const EdgeInsets.all(16),
                      child: Column(children: [
                        Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
                          const Text('今日进度', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
                          Text('🏆 $_points 积分', style: const TextStyle(fontSize: 14)),
                        ]),
                        const SizedBox(height: 12),
                        LinearProgressIndicator(value: totalTasks > 0 ? doneTasks / totalTasks : 0),
                        const SizedBox(height: 4),
                        Text('$doneTasks / $totalTasks', style: const TextStyle(color: Colors.grey, fontSize: 12)),
                      ]),
                    ),
                  ),
                  const SizedBox(height: 16),
                  // Time-grouped tasks
                  ..._groups.map((g) {
                    final tasks = (g['tasks'] as List).cast<Map<String, dynamic>>();
                    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      Padding(
                        padding: const EdgeInsets.only(left: 4, bottom: 8, top: 4),
                        child: Text(g['label'] as String, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700, color: Colors.grey)),
                      ),
                      ...tasks.map((t) {
                        final done = t['done'] == true;
                        final isAnim = _animTaskId == t['id'];
                        return AnimatedOpacity(
                          opacity: done ? 0.55 : 1.0,
                          duration: const Duration(milliseconds: 300),
                          child: AnimatedContainer(
                            duration: const Duration(milliseconds: 300),
                            transform: isAnim ? Matrix4.identity()..scale(1.02) : Matrix4.identity(),
                            margin: const EdgeInsets.only(bottom: 10),
                            child: Card(
                              shape: RoundedRectangleBorder(
                                borderRadius: BorderRadius.circular(16),
                                side: isAnim ? const BorderSide(color: Color(0xFF0EC9A6)) : BorderSide.none,
                              ),
                              child: ListTile(
                                leading: AnimatedContainer(
                                  duration: const Duration(milliseconds: 300),
                                  width: 36, height: 36,
                                  decoration: BoxDecoration(
                                    shape: BoxShape.circle,
                                    border: Border.all(color: done ? const Color(0xFF2ECC71) : Colors.grey, width: 2.5),
                                    color: done ? const Color(0xFF2ECC71).withOpacity(0.2) : Colors.transparent,
                                  ),
                                  child: done ? const Icon(Icons.check, color: Color(0xFF2ECC71), size: 20) : null,
                                ),
                                title: Text(t['title'] ?? '', style: const TextStyle(fontSize: 14)),
                                subtitle: Text('+${t['points'] ?? 5} XP', style: const TextStyle(fontSize: 12)),
                                trailing: done
                                    ? null
                                    : Stack(children: [
                                        IconButton(
                                          icon: const Icon(Icons.check_circle_outline, color: Color(0xFF6C63FF)),
                                          onPressed: () => _completeTask(t['id'] as String),
                                        ),
                                        if (isAnim)
                                          Positioned(top: -8, right: 0, child: TweenAnimationBuilder<double>(
                                            tween: Tween(begin: 0, end: -60),
                                            duration: const Duration(milliseconds: 1000),
                                            builder: (_, v, child) => Transform.translate(offset: Offset(0, v), child: child),
                                            child: const Text('+5XP', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800, color: Color(0xFFF39C12))),
                                          )),
                                      ]),
                              ),
                            ),
                          ),
                        );
                      }),
                    ]);
                  }),
                  const SizedBox(height: 16),
                  // Badges
                  if (_badges.isNotEmpty) ...[
                    const Text('🏅 徽章', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
                    const SizedBox(height: 8),
                    Wrap(spacing: 8, children: _badges.map((b) => Opacity(
                      opacity: b['unlocked'] == true ? 1.0 : 0.4,
                      child: Chip(
                        avatar: Text(b['icon'] ?? '🏅'),
                        label: Text(b['name'] ?? '', style: TextStyle(fontSize: 12, color: b['unlocked'] == true ? null : Colors.grey)),
                      ),
                    )).toList()),
                  ],
                ]),
              ),
      ),
      // Celebration overlay
      if (_showCelebration && _newBadge != null)
        GestureDetector(
          onTap: () => setState(() => _showCelebration = false),
          child: Container(color: Colors.black87, child: Center(child: Column(mainAxisSize: MainAxisSize.min, children: [
            const Text('🎉✨🎊', style: TextStyle(fontSize: 40)),
            const SizedBox(height: 16),
            Text(_newBadge!['icon'] ?? '', style: const TextStyle(fontSize: 80)),
            const SizedBox(height: 16),
            const Text('🏅 新徽章解锁！', style: TextStyle(color: Colors.grey, fontSize: 16)),
            const SizedBox(height: 8),
            Text(_newBadge!['name'] ?? '', style: const TextStyle(fontSize: 32, fontWeight: FontWeight.bold, color: Color(0xFFF39C12))),
            const SizedBox(height: 8),
            Text(_newBadge!['desc'] ?? '', style: const TextStyle(color: Colors.grey, fontSize: 14)),
            const SizedBox(height: 32),
            const Text('点击继续 →', style: TextStyle(color: Color(0xFF6C63FF), fontSize: 16)),
          ]))),
        ),
    ]);
  }
}
