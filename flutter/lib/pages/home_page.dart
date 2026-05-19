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
  Map<String, dynamic>? _stats;
  Map<String, dynamic>? _lastRecord;
  bool _loading = true;

  final _tips = [
    '保持固定的起床时间，即使是周末也尽量不赖床。',
    '睡前1小时减少屏幕使用，蓝光会抑制褪黑素分泌。',
    '卧室温度保持在18-22°C最有利于入睡。',
    '下午2点后避免摄入咖啡因。',
    '每天30分钟户外活动有助于调节昼夜节律。',
  ];

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
        api.get('/api/v1/sleep-records/last'),
        api.get('/api/v1/sleep-records/stats/summary?days=7'),
      ]);
      setState(() {
        _lastRecord = results[0];
        _stats = results[1];
        _loading = false;
      });
    } catch (e) {
      setState(() => _loading = false);
    }
  }

  void _navigateTo(Widget page) {
    Navigator.push(context, MaterialPageRoute(builder: (_) => page));
  }

  @override
  Widget build(BuildContext context) {
    final screens = [
      _buildDashboard(),
      const RecordPage(),
      const AnalysisPage(),
      _buildProfileHub(),
    ];

    return Scaffold(
      appBar: AppBar(
        title: const Text('梦眠'),
        actions: [
          IconButton(icon: const Icon(Icons.menu), onPressed: () => _showAllPages()),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: _loadData,
        child: IndexedStack(index: _idx, children: screens),
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _idx,
        onDestinationSelected: (i) => setState(() => _idx = i),
        destinations: const [
          NavigationDestination(icon: Icon(Icons.dashboard), label: '概览'),
          NavigationDestination(icon: Icon(Icons.edit), label: '记录'),
          NavigationDestination(icon: Icon(Icons.analytics), label: '分析'),
          NavigationDestination(icon: Icon(Icons.person), label: '我的'),
        ],
      ),
    );
  }

  Widget _buildDashboard() {
    if (_loading) return const Center(child: CircularProgressIndicator());
    final lastDur = _lastRecord?['duration_hours'] ?? '--';
    final lastScore = _lastRecord?['score'] ?? '--';
    final tip = _tips[DateTime.now().millisecondsSinceEpoch % _tips.length];
    return ListView(padding: const EdgeInsets.all(16), children: [
      GridView.count(crossAxisCount: 2, shrinkWrap: true, physics: const NeverScrollableScrollPhysics(),
        childAspectRatio: 1.5, crossAxisSpacing: 12, mainAxisSpacing: 12,
        children: [
          _statCard('昨晚睡眠', '$lastDur', 'h'),
          _statCard('睡眠评分', '$lastScore', '分'),
          _statCard('连续达标', '${_stats?['streak_days'] ?? 0}', '天'),
          _statCard('本周平均', '${_stats?['avg_duration'] ?? 0}', 'h'),
        ],
      ),
      const SizedBox(height: 16),
      Card(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            const Text('快捷操作', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
            const SizedBox(height: 12),
            Wrap(spacing: 8, children: [
              _quickAction('✎', '记录睡眠', () => _navigateTo(const RecordPage())),
              _quickAction('♫', '白噪音', () => _navigateTo(const NoisePage())),
              _quickAction('🤖', 'AI助手', () => _navigateTo(const ChatPage())),
              _quickAction('✅', '每日任务', () => _navigateTo(const TasksPage())),
              _quickAction('⏰', '智能闹钟', () => _navigateTo(const AlarmPage())),
              _quickAction('🎮', '游戏中心', () => _navigateTo(const GamePage())),
            ]),
          ]),
        ),
      ),
      const SizedBox(height: 16),
      Card(
        child: Padding(padding: const EdgeInsets.all(16), child: Text('💡 $tip')),
      ),
    ]);
  }

  Widget _statCard(String label, String value, String unit) {
    return Card(
      child: Center(
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          Text(label, style: const TextStyle(fontSize: 12, color: Colors.grey)),
          const SizedBox(height: 4),
          Text.rich(TextSpan(children: [
            TextSpan(text: value, style: const TextStyle(fontSize: 28, fontWeight: FontWeight.bold)),
            TextSpan(text: unit, style: const TextStyle(fontSize: 14, color: Colors.grey)),
          ])),
        ]),
      ),
    );
  }

  Widget _quickAction(String icon, String label, VoidCallback onTap) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        decoration: BoxDecoration(
          color: const Color(0xFF16213E),
          borderRadius: BorderRadius.circular(12),
        ),
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          Text(icon, style: const TextStyle(fontSize: 24)),
          const SizedBox(height: 4),
          Text(label, style: const TextStyle(fontSize: 12)),
        ]),
      ),
    );
  }

  Widget _buildProfileHub() {
    final auth = context.read<AuthService>();
    return ListView(padding: const EdgeInsets.all(16), children: [
      Card(
        child: ListTile(
          leading: const CircleAvatar(child: Text('☺')),
          title: Text(auth.user?['nickname'] ?? auth.user?['username'] ?? '用户'),
          subtitle: const Text('查看和编辑个人资料'),
          trailing: const Icon(Icons.arrow_forward_ios, size: 16),
          onTap: () => _navigateTo(const ProfilePage()),
        ),
      ),
      const SizedBox(height: 8),
      Card(child: Column(children: [
        _menuItem('💎', '会员中心', () => _navigateTo(const VipPage())),
        _menuItem('🎮', '游戏中心', () => _navigateTo(const GamePage())),
        _menuItem('🤖', 'AI助手', () => _navigateTo(const ChatPage())),
        _menuItem('📋', '睡眠评估', () => _navigateTo(const AssessmentPage())),
        _menuItem('⏰', '智能闹钟', () => _navigateTo(const AlarmPage())),
        _menuItem('🎵', '白噪音', () => _navigateTo(const NoisePage())),
        _menuItem('✅', '每日任务', () => _navigateTo(const TasksPage())),
        _menuItem('💬', '睡眠社区', () => _navigateTo(const CommunityPage())),
        _menuItem('📚', '知识库', () => _navigateTo(const KnowledgePage())),
        _menuItem('🛒', '助眠商城', () => _navigateTo(const StorePage())),
        _menuItem('🎓', '睡眠课程', () => _navigateTo(const CoursesPage())),
      ])),
      const SizedBox(height: 24),
      SizedBox(
        width: double.infinity,
        child: OutlinedButton(
          onPressed: () => auth.logout(),
          style: OutlinedButton.styleFrom(foregroundColor: Colors.red),
          child: const Text('退出登录'),
        ),
      ),
    ]);
  }

  Widget _menuItem(String icon, String title, VoidCallback onTap) {
    return ListTile(
      leading: Text(icon, style: const TextStyle(fontSize: 24)),
      title: Text(title),
      trailing: const Icon(Icons.arrow_forward_ios, size: 16),
      onTap: onTap,
    );
  }

  void _showAllPages() {
    showModalBottomSheet(
      context: context,
      builder: (_) => SizedBox(
        height: 500,
        child: ListView(children: [
          const Padding(padding: EdgeInsets.all(16), child: Text('全部功能', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold))),
          _sheetItem('📊', '睡眠概览', () => setState(() { _idx = 0; Navigator.pop(context); })),
          _sheetItem('✏️', '睡眠记录', () => setState(() { _idx = 1; Navigator.pop(context); })),
          _sheetItem('📈', '睡眠分析', () => setState(() { _idx = 2; Navigator.pop(context); })),
          _sheetItem('👤', '健康档案', () { Navigator.pop(context); _navigateTo(const ProfilePage()); }),
          _sheetItem('💎', '会员中心', () { Navigator.pop(context); _navigateTo(const VipPage()); }),
          _sheetItem('🤖', 'AI助手', () { Navigator.pop(context); _navigateTo(const ChatPage()); }),
          _sheetItem('🎵', '白噪音', () { Navigator.pop(context); _navigateTo(const NoisePage()); }),
          _sheetItem('✅', '每日任务', () { Navigator.pop(context); _navigateTo(const TasksPage()); }),
          _sheetItem('📋', '睡眠评估', () { Navigator.pop(context); _navigateTo(const AssessmentPage()); }),
          _sheetItem('⏰', '智能闹钟', () { Navigator.pop(context); _navigateTo(const AlarmPage()); }),
          _sheetItem('🎮', '游戏中心', () { Navigator.pop(context); _navigateTo(const GamePage()); }),
          _sheetItem('💬', '睡眠社区', () { Navigator.pop(context); _navigateTo(const CommunityPage()); }),
          _sheetItem('📚', '知识库', () { Navigator.pop(context); _navigateTo(const KnowledgePage()); }),
          _sheetItem('🛒', '商城', () { Navigator.pop(context); _navigateTo(const StorePage()); }),
          _sheetItem('🎓', '课程', () { Navigator.pop(context); _navigateTo(const CoursesPage()); }),
        ]),
      ),
    );
  }

  Widget _sheetItem(String icon, String title, VoidCallback onTap) {
    return ListTile(leading: Text(icon, style: const TextStyle(fontSize: 24)), title: Text(title), onTap: onTap);
  }
}
