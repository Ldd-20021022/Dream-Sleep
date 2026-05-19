import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/api_service.dart';
import '../services/auth_service.dart';

class GamePage extends StatefulWidget {
  const GamePage({super.key});
  @override
  State<GamePage> createState() => _GamePageState();
}

class _GamePageState extends State<GamePage> with SingleTickerProviderStateMixin {
  List _games = [];
  Map<String, dynamic>? _dashboard;
  List _leaderboard = [];
  late TabController _tabCtrl;

  final _gameRoutes = {
    'garden': 'garden',
    'adventure': 'adventure',
    'breathing': 'breathing',
    'worry': 'worry',
    'quiz': 'quiz',
    'soundscape': 'sound',
    'runner': 'runner',
  };

  @override
  void initState() {
    super.initState();
    _tabCtrl = TabController(length: 3, vsync: this);
    _loadHall();
  }

  Future<void> _loadHall() async {
    final api = context.read<ApiService>();
    api.setToken(context.read<AuthService>().token);
    try {
      final results = await Future.wait([
        api.get('/api/v1/game/hall'),
        api.get('/api/v1/game/dashboard'),
        api.get('/api/v1/game/leaderboard'),
      ]);
      setState(() {
        _games = (results[0]['games'] as List?) ?? [];
        _dashboard = results[1];
        _leaderboard = (results[2]['leaderboard'] as List?) ?? [];
      });
    } catch (_) {}
  }

  Future<void> _checkin() async {
    final api = context.read<ApiService>();
    api.setToken(context.read<AuthService>().token);
    try {
      final d = await api.post('/api/v1/game/checkin', {});
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(d['message'] ?? '签到成功')));
      _loadHall();
    } catch (_) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('今日已签到')));
    }
  }

  void _enterGame(String id) {
    final api = context.read<ApiService>();
    api.setToken(context.read<AuthService>().token);
    api.post('/api/v1/game/hall/$id/visit', {}).catchError((_) {});
    final page = _gameRoutes[id];
    if (page != null) {
      Navigator.push(context, MaterialPageRoute(builder: (_) => _buildGamePage(id, page)));
    }
  }

  Widget _buildGamePage(String id, String page) {
    if (id == 'runner') return const RunnerGamePage();
    return GameDetailPage(gameId: id);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('游戏中心'),
        bottom: TabBar(
          controller: _tabCtrl,
          labelColor: const Color(0xFF6C63FF),
          tabs: const [
            Tab(text: '🎮 游戏大厅'),
            Tab(text: '📊 我的状态'),
            Tab(text: '🏅 排行'),
          ],
        ),
      ),
      body: TabBarView(
        controller: _tabCtrl,
        children: [
          _buildHall(),
          _buildStatus(),
          _buildLeaderboard(),
        ],
      ),
    );
  }

  Widget _buildHall() {
    return RefreshIndicator(
      onRefresh: _loadHall,
      child: ListView(padding: const EdgeInsets.all(16), children: [
        Center(
          child: Column(children: [
            const Text('🎮 睡眠游戏大厅', style: TextStyle(fontSize: 24, fontWeight: FontWeight.bold)),
            const SizedBox(height: 4),
            const Text('完成游戏获得XP，养成好睡眠习惯', style: TextStyle(color: Colors.grey, fontSize: 13)),
            const SizedBox(height: 12),
            SizedBox(width: double.infinity, child: ElevatedButton.icon(
              icon: const Icon(Icons.card_giftcard),
              label: const Text('每日签到 +15XP'),
              onPressed: _checkin,
              style: ElevatedButton.styleFrom(padding: const EdgeInsets.symmetric(vertical: 14)),
            )),
          ]),
        ),
        const SizedBox(height: 16),
        ..._games.map((g) => _gameCard(g)),
      ]),
    );
  }

  Widget _gameCard(Map<String, dynamic> g) {
    final id = g['id'] ?? '';
    final isComing = g['status'] == 'coming_soon';
    final color = _parseColor(g['color'] as String?);
    final features = (g['features'] as List?) ?? [];
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      child: InkWell(
        borderRadius: BorderRadius.circular(16),
        onTap: () => _enterGame(id as String),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Row(children: [
            Text(g['icon'] as String? ?? '🎮', style: const TextStyle(fontSize: 40)),
            const SizedBox(width: 16),
            Expanded(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Row(children: [
                  Text(g['name'] as String? ?? '', style: const TextStyle(fontSize: 17, fontWeight: FontWeight.bold)),
                  const SizedBox(width: 8),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                    decoration: BoxDecoration(color: color.withOpacity(0.2), borderRadius: BorderRadius.circular(12)),
                    child: Text(g['subtitle'] as String? ?? '', style: TextStyle(fontSize: 11, color: color)),
                  ),
                  if (isComing) ...[
                    const SizedBox(width: 6),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                      decoration: BoxDecoration(border: Border.all(color: Colors.grey.withOpacity(0.3)), borderRadius: BorderRadius.circular(12)),
                      child: const Text('即将上线', style: TextStyle(fontSize: 11, color: Colors.grey)),
                    ),
                  ],
                ]),
                const SizedBox(height: 6),
                Text(g['desc'] as String? ?? '', style: const TextStyle(color: Colors.grey, fontSize: 12, height: 1.4)),
                const SizedBox(height: 8),
                Wrap(spacing: 6, children: features.map((f) => Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                  decoration: BoxDecoration(color: Colors.white.withOpacity(0.04), borderRadius: BorderRadius.circular(8)),
                  child: Text(f.toString(), style: TextStyle(fontSize: 11, color: Colors.grey[500])),
                )).toList()),
              ]),
            ),
            const Icon(Icons.chevron_right, color: Colors.grey),
          ]),
        ),
      ),
    );
  }

  Widget _buildStatus() {
    if (_dashboard == null) return const Center(child: CircularProgressIndicator());
    final user = _dashboard!['user'] as Map<String, dynamic>? ?? {};
    final missions = (_dashboard!['daily_missions'] as List?) ?? [];
    final done = _dashboard!['daily_done'] ?? 0;
    final total = _dashboard!['daily_total'] ?? 0;
    final xpPct = (user['xp_pct'] ?? 0).toDouble() / 100;

    return RefreshIndicator(
      onRefresh: _loadHall,
      child: ListView(padding: const EdgeInsets.all(16), children: [
        // Level Card
        Card(
          color: const Color(0xFF1a1a4e),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Column(children: [
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
                decoration: BoxDecoration(color: const Color(0xFF6C63FF).withOpacity(0.2), borderRadius: BorderRadius.circular(20)),
                child: Text('Lv.${user['level']}', style: const TextStyle(color: Color(0xFF6C63FF), fontWeight: FontWeight.bold)),
              ),
              const SizedBox(height: 8),
              Text(user['level_name'] ?? '', style: const TextStyle(fontSize: 28, fontWeight: FontWeight.bold)),
              const SizedBox(height: 12),
              ClipRRect(
                borderRadius: BorderRadius.circular(6),
                child: LinearProgressIndicator(value: xpPct, minHeight: 10, backgroundColor: Colors.white.withOpacity(0.1)),
              ),
              const SizedBox(height: 4),
              Text('${user['current_xp']} / ${user['xp_needed']} XP', style: const TextStyle(color: Colors.grey, fontSize: 12)),
              if (user['next_perk'] != null) ...[
                const SizedBox(height: 8),
                Text('🔮 Lv.${(user['level'] as int) + 1}：${user['next_perk']}', style: const TextStyle(color: Color(0xFFF39C12), fontSize: 13)),
              ],
              const SizedBox(height: 16),
              SizedBox(width: double.infinity, child: ElevatedButton.icon(
                icon: const Icon(Icons.card_giftcard),
                label: const Text('每日签到 +15XP'),
                onPressed: _checkin,
              )),
            ]),
          ),
        ),
        const SizedBox(height: 16),
        // Daily Missions
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Row(children: [const Text('🎯 每日任务', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)), const Spacer(), Text('$done/$total', style: const TextStyle(color: Colors.grey))]),
              const SizedBox(height: 12),
              ...missions.map((m) => Opacity(
                opacity: m['done'] == true ? 0.5 : 1,
                child: ListTile(
                  dense: true,
                  leading: Text(m['done'] == true ? '✅' : (m['icon'] ?? '⏳'), style: const TextStyle(fontSize: 22)),
                  title: Text(m['title'] ?? '', style: const TextStyle(fontSize: 14)),
                  subtitle: Text(m['desc'] ?? '', style: const TextStyle(fontSize: 12, color: Colors.grey)),
                  trailing: Text('+${m['xp']}XP', style: const TextStyle(color: Color(0xFF0EC9A6), fontSize: 13, fontWeight: FontWeight.bold)),
                ),
              )),
            ]),
          ),
        ),
      ]),
    );
  }

  Widget _buildLeaderboard() {
    return RefreshIndicator(
      onRefresh: _loadHall,
      child: ListView(padding: const EdgeInsets.all(16), children: [
        const Text('🏅 XP 排行榜', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
        const SizedBox(height: 12),
        ..._leaderboard.asMap().entries.map((e) {
          final l = e.value as Map<String, dynamic>;
          final rank = l['rank'] ?? (e.key + 1);
          return ListTile(
            leading: CircleAvatar(
              backgroundColor: rank == 1 ? const Color(0xFFF39C12) : rank == 2 ? Colors.grey[400] : rank == 3 ? const Color(0xFFCD853F) : const Color(0xFF6C63FF),
              child: Text(rank <= 3 ? ['🥇','🥈','🥉'][rank - 1] : '$rank', style: const TextStyle(fontSize: 16)),
            ),
            title: Text(l['nickname'] ?? '', style: const TextStyle(fontSize: 14)),
            subtitle: Text('Lv.${l['level'] ?? 1}', style: const TextStyle(fontSize: 12, color: Colors.grey)),
            trailing: Text('${l['total_xp']} XP', style: const TextStyle(color: Color(0xFF0EC9A6), fontWeight: FontWeight.bold, fontSize: 13)),
          );
        }),
      ]),
    );
  }

  Color _parseColor(String? hex) {
    if (hex == null) return const Color(0xFF6C63FF);
    try {
      final h = hex.replaceAll('#', '');
      return Color(int.parse('FF$h', radix: 16));
    } catch (_) {
      return const Color(0xFF6C63FF);
    }
  }
}


// ==================== Individual Game Pages (lightweight wrappers) ====================

final _gameDetails = {
  'breathing': {'icon': '🫁', 'title': '呼吸训练', 'desc': '跟随4-7-8呼吸法圆环引导，激活副交感神经，帮助身体进入放松状态。', 'steps': ['选择引导/挑战模式', '跟随圆环节奏呼吸', '完成4轮获得XP奖励']},
  'quiz': {'icon': '🧩', 'title': '睡眠问答', 'desc': '50道睡眠科学题库随机出题，答对获得XP和拼图碎片。知识就是好睡眠的力量。', 'steps': ['阅读题目选择答案', '提交查看正确率', '获得XP+拼图碎片']},
  'worry': {'icon': '💥', 'title': '烦恼粉碎机', 'desc': 'CBT-I担忧时间技术：写下睡前烦恼 → 变成泡泡 → 一一戳破。清空焦虑，轻松入睡。', 'steps': ['写下你的烦恼', '点击开始粉碎', '戳破所有气泡']},
  'garden': {'icon': '🌻', 'title': '梦境花园', 'desc': '每完成一项睡眠任务就能获得水滴和阳光，培育你的专属梦境植物。好习惯种出好睡眠。', 'steps': ['完成每日睡眠任务', '收集水滴和阳光', '解锁5种梦境植物']},
  'adventure': {'icon': '⚔️', 'title': '睡眠大冒险', 'desc': '在失眠王国中探险，用CBT-I技能击败焦虑怪和熬夜龙。3章剧情等你挑战。', 'steps': ['学习CBT-I技能', '挑战Boss怪物', '解锁新章节地图']},
  'soundscape': {'icon': '🎛️', 'title': '音景工坊', 'desc': '12种自然音效随心混音。雨声、海浪、篝火、溪流——创造你的专属入睡音景。', 'steps': ['拖动滑杆调整音量', '试听混音效果', '保存你的专属音景']},
};

class GameDetailPage extends StatelessWidget {
  final String gameId;
  const GameDetailPage({super.key, required this.gameId});
  @override
  Widget build(BuildContext context) {
    final info = _gameDetails[gameId] ?? {};
    final steps = (info['steps'] as List?) ?? [];
    return Scaffold(
      appBar: AppBar(title: Text('${info['icon'] ?? ''} ${info['title'] ?? ''}'.trim())),
      body: ListView(padding: const EdgeInsets.all(24), children: [
        Center(child: Text(info['icon'] as String? ?? '', style: const TextStyle(fontSize: 80))),
        const SizedBox(height: 16),
        Text(info['title'] as String? ?? '', textAlign: TextAlign.center, style: const TextStyle(fontSize: 28, fontWeight: FontWeight.bold)),
        const SizedBox(height: 12),
        Text(info['desc'] as String? ?? '', textAlign: TextAlign.center, style: const TextStyle(fontSize: 15, color: Colors.grey70, height: 1.6)),
        const SizedBox(height: 32),
        const Text('玩法步骤', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
        const SizedBox(height: 12),
        ...steps.asMap().entries.map((e) => Card(
          margin: const EdgeInsets.only(bottom: 8),
          child: ListTile(
            leading: CircleAvatar(child: Text('${e.key + 1}')),
            title: Text(e.value.toString(), style: const TextStyle(fontSize: 14)),
          ),
        )),
        const SizedBox(height: 24),
        Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(color: const Color(0xFF6C63FF).withOpacity(0.08), borderRadius: BorderRadius.circular(12)),
          child: const Row(children: [
            Icon(Icons.phone_android, color: Colors.grey),
            SizedBox(width: 12),
            Expanded(child: Text('完整交互版本请使用小程序端体验。Flutter端游戏引擎开发中。', style: TextStyle(fontSize: 13, color: Colors.grey))),
          ]),
        ),
      ]),
    );
  }
}

class BreathingGamePage extends StatelessWidget { const BreathingGamePage({super.key}); @override Widget build(BuildContext c) => GameDetailPage(gameId: 'breathing'); }
class QuizGamePage extends StatelessWidget { const QuizGamePage({super.key}); @override Widget build(BuildContext c) => GameDetailPage(gameId: 'quiz'); }
class WorryGamePage extends StatelessWidget { const WorryGamePage({super.key}); @override Widget build(BuildContext c) => GameDetailPage(gameId: 'worry'); }
class GardenGamePage extends StatelessWidget { const GardenGamePage({super.key}); @override Widget build(BuildContext c) => GameDetailPage(gameId: 'garden'); }
class AdventureGamePage extends StatelessWidget { const AdventureGamePage({super.key}); @override Widget build(BuildContext c) => GameDetailPage(gameId: 'adventure'); }
class SoundGamePage extends StatelessWidget { const SoundGamePage({super.key}); @override Widget build(BuildContext c) => GameDetailPage(gameId: 'soundscape'); }

class RunnerGamePage extends StatelessWidget {
  const RunnerGamePage({super.key});
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('🏃 昼夜节律跑酷')),
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            const Text('🏃‍♂️💨', style: TextStyle(fontSize: 80)),
            const SizedBox(height: 16),
            const Text('昼夜节律跑酷', style: TextStyle(fontSize: 28, fontWeight: FontWeight.bold)),
            const SizedBox(height: 8),
            const Text('即将上线 · 2026年7月', style: TextStyle(color: Color(0xFFE67E22), fontSize: 16)),
            const SizedBox(height: 24),
            const Text('🌅 白天与黑夜交替\n🏃 躲避咖啡因陷阱\n⭐ 收集阳光能量', textAlign: TextAlign.center, style: TextStyle(color: Colors.grey, fontSize: 15, height: 1.8)),
            const SizedBox(height: 24),
            SizedBox(width: double.infinity, child: ElevatedButton.icon(
              icon: const Icon(Icons.notifications_active),
              label: const Text('预约上线通知 (+10XP)'),
              onPressed: () async {
                final api = context.read<ApiService>();
                api.setToken(context.read<AuthService>().token);
                try {
                  await api.post('/api/v1/game/runner/reserve', {});
                  if (context.mounted) {
                    ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('预约成功！')));
                  }
                } catch (_) {}
              },
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFFE67E22),
                padding: const EdgeInsets.symmetric(vertical: 16),
              ),
            )),
          ]),
        ),
      ),
    );
  }
}
