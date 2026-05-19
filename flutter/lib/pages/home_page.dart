import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/auth_service.dart';
import '../services/api_service.dart';
import 'record_page.dart';
import 'analysis_page.dart';
import 'chat_page.dart';
import 'noise_page.dart';
import 'tasks_page.dart';
import 'community_page.dart';
import 'knowledge_page.dart';
import 'store_page.dart';
import 'courses_page.dart';
import 'game_page.dart';
import 'assessment_page.dart';
import 'alarm_page.dart';
import 'vip_page.dart';
import 'profile_page.dart';

class HomePage extends StatefulWidget {
  const HomePage({super.key});
  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> {
  int _idx = 0;
  Map<String, dynamic>? _dashboard;
  bool _loading = true;

  static const _primary = Color(0xFF5B6ABF);
  static const _teal = Color(0xFF3DAAA0);
  static const _warn = Color(0xFFC8923A);

  @override
  void initState() { super.initState(); _loadData(); }

  Future<void> _loadData() async {
    final api = context.read<ApiService>();
    api.setToken(context.read<AuthService>().token);
    try {
      final d = await api.get('/api/v1/wellness/dashboard');
      if (mounted) setState(() { _dashboard = d; _loading = false; });
    } catch (_) { if (mounted) setState(() => _loading = false); }
  }

  void _go(Widget page) => Navigator.push(context, MaterialPageRoute(builder: (_) => page));

  @override
  Widget build(BuildContext context) {
    final screens = [_buildDashboard(), const RecordPage(), const AnalysisPage(), _buildProfileHub()];
    return Scaffold(
      appBar: AppBar(title: const Text('梦眠'), actions: [
        IconButton(icon: const Icon(Icons.grid_view_rounded, size: 20), onPressed: _showAllPages),
      ]),
      body: RefreshIndicator(onRefresh: _loadData, child: IndexedStack(index: _idx, children: screens)),
      bottomNavigationBar: BottomNavigationBar(
        currentIndex: _idx,
        onTap: (i) => setState(() => _idx = i),
        selectedFontSize: 11,
        unselectedFontSize: 10,
        items: const [
          BottomNavigationBarItem(icon: Icon(Icons.dashboard_outlined), activeIcon: Icon(Icons.dashboard), label: '概览'),
          BottomNavigationBarItem(icon: Icon(Icons.edit_outlined), activeIcon: Icon(Icons.edit), label: '记录'),
          BottomNavigationBarItem(icon: Icon(Icons.analytics_outlined), activeIcon: Icon(Icons.analytics), label: '分析'),
          BottomNavigationBarItem(icon: Icon(Icons.person_outline), activeIcon: Icon(Icons.person), label: '我的'),
        ],
      ),
    );
  }

  Widget _buildDashboard() {
    if (_loading) return const Center(child: CircularProgressIndicator(color: _primary));
    final last = _dashboard?['last_sleep'];
    final weekly = _dashboard?['weekly_stats'];
    final insight = _dashboard?['daily_insight'] as Map<String, dynamic>?;
    final lastScore = last?['score'] ?? 0;
    final lastDur = last?['duration'] ?? '--';

    return ListView(padding: const EdgeInsets.all(20), children: [
      // Greeting header
      Padding(
        padding: const EdgeInsets.only(bottom: 20),
        child: Row(children: [
          Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            const Text('梦眠', style: TextStyle(fontSize: 26, fontWeight: FontWeight.w600, letterSpacing: 0.5)),
            const SizedBox(height: 4),
            Text('睡眠改善，从了解自己开始', style: TextStyle(fontSize: 13, color: Colors.grey[600])),
          ])),
          Container(width: 52, height: 52,
            decoration: BoxDecoration(shape: BoxShape.circle, color: _primary.withOpacity(0.1)),
            child: const Center(child: Text('☺', style: TextStyle(fontSize: 24))),
          ),
        ]),
      ),

      // Score ring + info
      Container(
        padding: const EdgeInsets.all(24),
        decoration: BoxDecoration(color: const Color(0xFF161622), borderRadius: BorderRadius.circular(22)),
        child: Row(children: [
          SizedBox(width: 130, height: 130, child: Stack(children: [
            Container(decoration: BoxDecoration(shape: BoxShape.circle, color: Colors.white.withOpacity(0.03))),
            Center(child: Column(mainAxisSize: MainAxisSize.min, children: [
              Text('$lastScore', style: const TextStyle(fontSize: 36, fontWeight: FontWeight.w600)),
              Text(lastScore >= 80 ? '优秀' : lastScore >= 60 ? '良好' : '待改善', style: TextStyle(fontSize: 12, color: Colors.grey[500])),
            ])),
          ])),
          const SizedBox(width: 24),
          Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            _infoRow('昨晚睡眠', '$lastDur h'),
            _infoRow('连续达标', '${weekly?['streak_days'] ?? 0} 天'),
            _infoRow('周均分', '${weekly?['avg_score'] ?? '--'}'),
            _infoRow('周均长', '${weekly?['avg_duration'] ?? '--'} h'),
          ])),
        ]),
      ),
      const SizedBox(height: 16),

      // Insight card
      if (insight != null) ...[
        _buildInsight(insight),
        const SizedBox(height: 16),
      ],

      // Quick actions
      Container(
        padding: const EdgeInsets.all(20),
        decoration: BoxDecoration(color: const Color(0xFF161622), borderRadius: BorderRadius.circular(22)),
        child: Wrap(spacing: 4, runSpacing: 4, children: [
          _qa('✎', '记录', () => _go(const RecordPage())),
          _qa('♫', '白噪音', () => _go(const NoisePage())),
          _qa('🤖', 'AI教练', () => _go(const ChatPage())),
          _qa('✅', '任务', () => _go(const TasksPage())),
          _qa('🎮', '游戏', () => _go(const GamePage())),
          _qa('📚', '知识库', () => _go(const KnowledgePage())),
          _qa('🎓', '课程', () => _go(const CoursesPage())),
          _qa('🌐', '社区', () => _go(const CommunityPage())),
        ]),
      ),
    ]);
  }

  Widget _infoRow(String label, String value) => Padding(
    padding: const EdgeInsets.only(bottom: 8),
    child: Row(children: [
      SizedBox(width: 72, child: Text(label, style: TextStyle(fontSize: 12, color: Colors.grey[500]))),
      Text(value, style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600)),
    ]),
  );

  Widget _qa(String icon, String label, VoidCallback onTap) => GestureDetector(
    onTap: onTap,
    child: Container(
      width: (MediaQuery.of(context).size.width - 64) / 4,
      padding: const EdgeInsets.symmetric(vertical: 16),
      decoration: BoxDecoration(borderRadius: BorderRadius.circular(16)),
      child: Column(mainAxisSize: MainAxisSize.min, children: [
        Text(icon, style: const TextStyle(fontSize: 24)),
        const SizedBox(height: 6),
        Text(label, style: TextStyle(fontSize: 12, color: Colors.grey[400])),
      ]),
    ),
  );

  Widget _buildInsight(Map<String, dynamic> i) {
    final priColors = {'success': _teal, 'info': _primary, 'warning': _warn, 'critical': const Color(0xFFC4544A)};
    final c = priColors[i['priority']] ?? _primary;
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(color: const Color(0xFF161622), borderRadius: BorderRadius.circular(22),
        border: Border(left: BorderSide(color: c, width: 3))),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Container(padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 3),
          decoration: BoxDecoration(color: c.withOpacity(0.1), borderRadius: BorderRadius.circular(10)),
          child: Text(i['title'] ?? '', style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: c))),
        const SizedBox(height: 10),
        Text(i['body'] ?? '', style: TextStyle(fontSize: 14, color: Colors.grey[400], height: 1.5)),
      ]),
    );
  }

  Widget _buildProfileHub() {
    final auth = context.read<AuthService>();
    return ListView(padding: const EdgeInsets.all(20), children: [
      Container(
        padding: const EdgeInsets.all(20),
        decoration: BoxDecoration(color: const Color(0xFF161622), borderRadius: BorderRadius.circular(22)),
        child: Row(children: [
          Container(width: 48, height: 48, decoration: BoxDecoration(shape: BoxShape.circle, color: _primary.withOpacity(0.1)),
            child: const Center(child: Text('☺', style: TextStyle(fontSize: 22)))),
          const SizedBox(width: 14),
          Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(auth.user?['nickname'] ?? auth.user?['username'] ?? '用户', style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
            const SizedBox(height: 2),
            Text('查看和编辑个人资料', style: TextStyle(fontSize: 12, color: Colors.grey[500])),
          ])),
          const Icon(Icons.chevron_right, size: 18, color: Colors.grey),
        ]),
      ),
      const SizedBox(height: 12),
      ...['💎 会员中心|vip', '🎮 游戏中心|game', '🌐 睡眠社区|community', '💬 AI助手|chat',
        '✅ 每日任务|tasks', '⏰ 智能闹钟|alarm', '🎵 白噪音|noise', '📋 睡眠评估|assessment',
        '📚 知识库|knowledge', '🛒 助眠商城|store', '🎓 睡眠课程|courses'].map((e) {
        final parts = e.split('|');
        return ListTile(
          leading: Text(parts[0].split(' ')[0], style: const TextStyle(fontSize: 22)),
          title: Text(parts[0].split(' ').sublist(1).join(' '), style: const TextStyle(fontSize: 14)),
          trailing: const Icon(Icons.chevron_right, size: 16, color: Colors.grey),
          onTap: () => _go(_pageFor(parts[1])),
        );
      }),
      const SizedBox(height: 20),
      SizedBox(width: double.infinity, child: OutlinedButton(
        style: OutlinedButton.styleFrom(foregroundColor: const Color(0xFFC4544A), side: const BorderSide(color: Color(0xFFC4544A))),
        onPressed: () => auth.logout(), child: const Text('退出登录'),
      )),
    ]);
  }

  Widget _pageFor(String key) {
    switch (key) {
      case 'vip': return const VipPage();
      case 'game': return const GamePage();
      case 'community': return const CommunityPage();
      case 'chat': return const ChatPage();
      case 'tasks': return const TasksPage();
      case 'alarm': return const AlarmPage();
      case 'noise': return const NoisePage();
      case 'assessment': return const AssessmentPage();
      case 'knowledge': return const KnowledgePage();
      case 'store': return const StorePage();
      case 'courses': return const CoursesPage();
      default: return const ProfilePage();
    }
  }

  void _showAllPages() {
    showModalBottomSheet(context: context, builder: (_) => SizedBox(height: 420, child: ListView(children: [
      const Padding(padding: EdgeInsets.all(16), child: Text('全部功能', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600))),
      ...['📊 睡眠概览|0', '✏️ 睡眠记录|1', '📈 睡眠分析|2', '👤 个人中心|3',
        '💎 会员中心|vip', '🤖 AI教练|chat', '🎵 白噪音|noise', '✅ 任务|tasks',
        '⏰ 闹钟|alarm', '🎮 游戏|game', '📚 知识库|knowledge', '🎓 课程|courses',
        '🌐 社区|community', '🛒 商城|store', '📋 评估|assessment'].map((e) {
        final parts = e.split('|');
        return ListTile(
          leading: Text(parts[0].split(' ')[0], style: const TextStyle(fontSize: 22)),
          title: Text(parts[0].split(' ').sublist(1).join(' '), style: const TextStyle(fontSize: 14)),
          onTap: () {
            Navigator.pop(context);
            final t = parts[1];
            if (t == '0') setState(() => _idx = 0);
            else if (t == '1') setState(() => _idx = 1);
            else if (t == '2') setState(() => _idx = 2);
            else if (t == '3') setState(() => _idx = 3);
            else _go(_pageFor(t));
          },
        );
      }),
    ])));
  }
}
