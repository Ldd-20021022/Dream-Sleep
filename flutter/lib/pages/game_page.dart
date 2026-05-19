import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/api_service.dart';
import '../services/auth_service.dart';

class GamePage extends StatefulWidget {
  const GamePage({super.key});
  @override
  State<GamePage> createState() => _GamePageState();
}

class _GamePageState extends State<GamePage> {
  Map<String, dynamic>? _status;
  List _achievements = [];
  List _leaderboard = [];

  @override
  void initState() {
    super.initState();
    _loadData();
  }

  Future<void> _loadData() async {
    final api = context.read<ApiService>();
    api.setToken(context.read<AuthService>().token);
    try {
      final results = await Future.wait([
        api.get('/api/v1/game/status'),
        api.get('/api/v1/game/achievements'),
        api.get('/api/v1/game/leaderboard'),
      ]);
      setState(() {
        _status = results[0];
        _achievements = (results[1]['achievements'] as List?) ?? [];
        _leaderboard = (results[2]['leaderboard'] as List?) ?? [];
      });
    } catch (_) {}
  }

  Future<void> _checkin() async {
    final api = context.read<ApiService>();
    api.setToken(context.read<AuthService>().token);
    try {
      final data = await api.post('/api/v1/game/checkin', {});
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(data['message'] ?? '签到成功')));
      }
      _loadData();
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('今日已签到')));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final unlocked = _achievements.where((a) => a['unlocked'] == true).length;
    final xpNeeded = _status?['xp_needed'] ?? 100;
    final currentXp = _status?['current_xp'] ?? 0;
    return Scaffold(
      appBar: AppBar(title: const Text('游戏化中心')),
      body: RefreshIndicator(
        onRefresh: _loadData,
        child: ListView(padding: const EdgeInsets.all(16), children: [
          if (_status != null) Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(children: [
                Text(_status!['level_name'] ?? '', style: const TextStyle(fontSize: 32, fontWeight: FontWeight.bold)),
                const SizedBox(height: 4),
                Text('Lv.${_status!['level'] ?? 1} · ${_status!['total_xp'] ?? 0} XP', style: const TextStyle(color: Colors.grey)),
                const SizedBox(height: 12),
                LinearProgressIndicator(value: xpNeeded > 0 ? currentXp / xpNeeded : 0),
                const SizedBox(height: 4),
                Text('$currentXp / $xpNeeded XP', style: const TextStyle(color: Colors.grey, fontSize: 12)),
                const SizedBox(height: 12),
                Row(mainAxisAlignment: MainAxisAlignment.center, children: [
                  ElevatedButton.icon(icon: const Icon(Icons.card_giftcard), label: const Text('每日签到 +15XP'), onPressed: _checkin),
                  const SizedBox(width: 8),
                  OutlinedButton.icon(icon: const Icon(Icons.emoji_events), label: const Text('检查成就'), onPressed: () async {
                    final api = context.read<ApiService>();
                    api.setToken(context.read<AuthService>().token);
                    try {
                      final data = await api.post('/api/v1/game/achievements/check', {});
                      final unlocks = (data['new_unlocks'] as List?) ?? [];
                      if (mounted) {
                        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('解锁 ${unlocks.length} 个成就')));
                      }
                      _loadData();
                    } catch (_) {}
                  }),
                ]),
                const SizedBox(height: 8),
                Text('🔥 连续${_status!['streak_days']}天 · 最高${_status!['max_streak']}天', style: const TextStyle(color: Colors.grey, fontSize: 12)),
              ]),
            ),
          ),
          const SizedBox(height: 16),
          Text('🏆 成就 ($unlocked/${_achievements.length})', style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
          const SizedBox(height: 8),
          Wrap(spacing: 8, children: _achievements.map((a) => Chip(
            avatar: Text(a['icon'] ?? '🏅'),
            label: Text(a['unlocked'] == true ? (a['title'] ?? '') : '??', style: TextStyle(color: a['unlocked'] == true ? null : Colors.grey)),
          )).toList()),
          const SizedBox(height: 16),
          const Text('🏅 XP 排行榜', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
          ..._leaderboard.map((l) => ListTile(
            leading: CircleAvatar(child: Text('${l['rank'] ?? ''}')),
            title: Text(l['nickname'] ?? ''),
            subtitle: Text('Lv${l['level'] ?? 1} ${l['total_xp'] ?? 0}XP'),
          )),
        ]),
      ),
    );
  }
}
