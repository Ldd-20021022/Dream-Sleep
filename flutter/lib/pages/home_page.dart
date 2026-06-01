import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/auth_service.dart';
import '../services/api_service.dart';
import 'record_page.dart';
import 'analysis_page.dart';
import 'chat_page.dart';
import 'noise_page.dart';
import 'tasks_page.dart';
import 'courses_page.dart';
import 'game_page.dart';
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
    // 4-tab: 概览 | 分析 | 记录 | 我的
    final screens = [_buildDashboard(), const AnalysisPage(), const RecordPage(), _buildProfileHub()];
    return Scaffold(
      appBar: AppBar(title: const Text('梦眠阁')),
      body: RefreshIndicator(onRefresh: _loadData, child: IndexedStack(index: _idx, children: screens)),
      bottomNavigationBar: BottomNavigationBar(
        currentIndex: _idx,
        onTap: (i) => setState(() => _idx = i),
        selectedFontSize: 11, unselectedFontSize: 10,
        items: const [
          BottomNavigationBarItem(icon: Icon(Icons.dashboard_outlined), activeIcon: Icon(Icons.dashboard), label: '概览'),
          BottomNavigationBarItem(icon: Icon(Icons.analytics_outlined), activeIcon: Icon(Icons.analytics), label: '分析'),
          BottomNavigationBarItem(icon: Icon(Icons.edit_outlined), activeIcon: Icon(Icons.edit), label: '记录'),
          BottomNavigationBarItem(icon: Icon(Icons.person_outline), activeIcon: Icon(Icons.person), label: '我的'),
        ],
      ),
    );
  }

  // ===== 1. Dashboard (Home) =====
  Widget _buildDashboard() {
    if (_loading) return const Center(child: CircularProgressIndicator(color: _primary));
    final last = _dashboard?['last_sleep'];
    final lastScore = last?['score'] ?? 0;
    final lastDur = last?['duration'] ?? '--';
    final streak = _dashboard?['streak_days'] ?? 0;
    final level = _dashboard?['game']?['level'] ?? 1;
    final levelName = _dashboard?['game']?['level_name'] ?? '入门';
    final daysSinceJoin = _dashboard?['user']?['days_since_join'] ?? 0;

    return ListView(padding: const EdgeInsets.all(16), children: [
      // 1. Dream Scene
      _buildDreamScene(lastScore),
      const SizedBox(height: 12),

      // 2. Stats Grid — 4 cards
      _buildStatsGrid(lastDur, lastScore, streak, level, levelName),
      const SizedBox(height: 12),

      // 3. Streak Motivation
      if (streak > 0) _buildStreakMotivation(streak),

      // 4. Quick Actions — 4 core: 记录/任务/AI教练/白噪音
      _buildQuickActions(daysSinceJoin),
      const SizedBox(height: 12),

      // 5. Daily Tip
      _buildDailyTip(),
    ]);
  }

  Widget _buildDreamScene(int score) {
    final isGood = score >= 80;
    return Container(
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(20),
        gradient: LinearGradient(
          begin: Alignment.topCenter,
          colors: isGood ? [const Color(0xFF0a1628), const Color(0xFF0d2137)] : [const Color(0xFF1a1520), const Color(0xFF201825)],
        ),
        border: Border.all(color: const Color(0xFF5B6ABF).withOpacity(0.08)),
      ),
      child: Column(children: [
        Text(isGood ? '🌟' : '🌙', style: const TextStyle(fontSize: 48)),
        const SizedBox(height: 8),
        Text(isGood ? '梦境海 · 晴朗星空' : '梦境海 · 等待记录', style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w600)),
        const SizedBox(height: 4),
        Text(isGood ? '守护者在安静地巡视着这片海域' : '记录昨晚的睡眠，开启你的梦境世界', style: TextStyle(fontSize: 13, color: Colors.grey[500])),
        const SizedBox(height: 16),
        Row(mainAxisAlignment: MainAxisAlignment.center, children: [
          ElevatedButton.icon(
            onPressed: () => setState(() => _idx = 2),
            icon: const Text('📝'), label: const Text('记录睡眠'),
            style: ElevatedButton.styleFrom(backgroundColor: _primary, foregroundColor: Colors.white, shape: StadiumBorder()),
          ),
          const SizedBox(width: 10),
          OutlinedButton.icon(
            onPressed: () => _go(const NoisePage()),
            icon: const Text('🎵'), label: const Text('白噪音'),
            style: OutlinedButton.styleFrom(foregroundColor: Colors.white70, side: BorderSide(color: Colors.white.withOpacity(0.1)), shape: StadiumBorder()),
          ),
        ]),
      ]),
    );
  }

  Widget _buildStatsGrid(String lastDur, int lastScore, int streak, int level, String levelName) {
    return GridView.count(crossAxisCount: 2, shrinkWrap: true, physics: const NeverScrollableScrollPhysics(),
      crossAxisSpacing: 10, mainAxisSpacing: 10, childAspectRatio: 1.6,
      children: [
        _statCard('昨晚睡眠', '$lastDur h'),
        _statCard('睡眠评分', '$lastScore', valColor: lastScore >= 80 ? _teal : _warn, sub: lastScore >= 80 ? '优秀' : lastScore >= 60 ? '良好' : '待改善'),
        _statCard('连续达标', '${streak >= 21 ? "🌟" : streak >= 7 ? "🔥🔥" : streak >= 3 ? "🔥" : ""}$streak 天', valColor: _warn),
        _statCard('守护者', 'Lv.$level', valColor: _primary, sub: levelName, subFontSize: 11),
      ],
    );
  }

  Widget _statCard(String label, String value, {Color? valColor, String? sub, double? subFontSize}) => Container(
    padding: const EdgeInsets.all(14),
    decoration: BoxDecoration(color: const Color(0xFF161622), borderRadius: BorderRadius.circular(14)),
    child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
      Text(label, style: TextStyle(fontSize: 11, color: Colors.grey[500])),
      const SizedBox(height: 4),
      Text(value, style: TextStyle(fontSize: 24, fontWeight: FontWeight.w700, color: valColor ?? Colors.white)),
      if (sub != null) Text(sub, style: TextStyle(fontSize: subFontSize ?? 10, color: Colors.grey[500])),
    ]),
  );

  Widget _buildStreakMotivation(int streak) {
    final isMaster = streak >= 21;
    final isPro = streak >= 7;
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: isMaster ? _primary.withOpacity(0.08) : isPro ? _teal.withOpacity(0.08) : _warn.withOpacity(0.08),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: isMaster ? _primary.withOpacity(0.2) : isPro ? _teal.withOpacity(0.2) : _warn.withOpacity(0.2)),
      ),
      child: Text(
        isMaster ? '🌟 连续 $streak 天！你已经是睡眠大师' :
        isPro ? '🔥🔥 连续 $streak 天达标！已解锁「规律达人」徽章 🌟' :
        '🔥 连续打卡 $streak 天，正在养成好习惯',
        textAlign: TextAlign.center,
        style: TextStyle(fontSize: 13, color: isMaster ? _primary : isPro ? _teal : _warn),
      ),
    );
  }

  Widget _buildQuickActions(int daysSinceJoin) => Container(
    padding: const EdgeInsets.all(16),
    decoration: BoxDecoration(color: const Color(0xFF161622), borderRadius: BorderRadius.circular(20)),
    child: GridView.count(crossAxisCount: 4, shrinkWrap: true, physics: const NeverScrollableScrollPhysics(),
      crossAxisSpacing: 8, mainAxisSpacing: 8, childAspectRatio: 0.9,
      children: [
        _qaItem('📝', '记录', () => setState(() => _idx = 2)),
        if (daysSinceJoin >= 1) _qaItem('🎯', '任务', () => _go(const TasksPage())),
        if (daysSinceJoin < 1) _qaItem('🔒', 'Day2解锁', null, locked: true),
        if (daysSinceJoin >= 2) _qaItem('🤖', 'AI教练', () => _go(const ChatPage())),
        if (daysSinceJoin < 2) _qaItem('🔒', 'Day3解锁', null, locked: true),
        _qaItem('🎵', '白噪音', () => _go(const NoisePage())),
      ],
    ),
  );

  Widget _qaItem(String icon, String label, VoidCallback? onTap, {bool locked = false}) => GestureDetector(
    onTap: onTap,
    child: Opacity(opacity: locked ? 0.4 : 1.0, child: Container(
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(12),
        color: locked ? null : Colors.white.withOpacity(0.03),
      ),
      padding: const EdgeInsets.symmetric(vertical: 12),
      child: Column(mainAxisSize: MainAxisSize.min, children: [
        Text(icon, style: const TextStyle(fontSize: 22)),
        const SizedBox(height: 6),
        Text(label, style: TextStyle(fontSize: 10, color: locked ? Colors.grey[600] : Colors.grey[400]), textAlign: TextAlign.center),
      ]),
    )),
  );

  Widget _buildDailyTip() => Container(
    padding: const EdgeInsets.all(16),
    decoration: BoxDecoration(
      gradient: LinearGradient(colors: [_primary.withOpacity(0.05), _teal.withOpacity(0.05)]),
      borderRadius: BorderRadius.circular(16),
    ),
    child: Row(children: [
      const Text('💡', style: TextStyle(fontSize: 22)),
      const SizedBox(width: 10),
      Expanded(child: Text('今晚试试4-7-8呼吸法：吸气4秒、屏息7秒、呼气8秒', style: TextStyle(fontSize: 12, color: Colors.grey[400], height: 1.5))),
    ]),
  );

  // ===== 4. Profile =====
  Widget _buildProfileHub() {
    final auth = context.read<AuthService>();
    return ListView(padding: const EdgeInsets.all(16), children: [
      const SizedBox(height: 16),
      // Avatar + name
      Column(children: [
        Container(width: 64, height: 64, decoration: BoxDecoration(shape: BoxShape.circle, color: _primary.withOpacity(0.1), border: Border.all(color: _primary, width: 2)),
          child: const Center(child: Text('☺', style: TextStyle(fontSize: 28)))),
        const SizedBox(height: 8),
        Text(auth.user?['nickname'] ?? auth.user?['username'] ?? '用户', style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w600)),
        const SizedBox(height: 2),
        Text('Lv.5 · 已加入 47 天', style: TextStyle(fontSize: 12, color: Colors.grey[500])),
      ]),
      const SizedBox(height: 20),

      // Stats row
      Row(mainAxisAlignment: MainAxisAlignment.spaceEvenly, children: [
        _pStat('47', '累计记录'),
        _pStat('47天', '加入梦眠阁'),
        _pStat('5/8', '徽章'),
      ]),
      const SizedBox(height: 16),

      // Simplified menu — 5 items
      Container(
        decoration: BoxDecoration(color: const Color(0xFF161622), borderRadius: BorderRadius.circular(20)),
        child: Column(children: [
          _menuItem('📊', '睡眠分析', () => setState(() => _idx = 1)),
          _menuItem('🎯', '每日任务', () => _go(const TasksPage())),
          _menuItem('📚', '改善课程', () => _go(const CoursesPage())),
          _menuItem('⚙️', '设置', () => _go(const ProfilePage())),
        ]),
      ),
      const SizedBox(height: 16),

      // Logout — danger style
      SizedBox(width: double.infinity, child: OutlinedButton(
        style: OutlinedButton.styleFrom(foregroundColor: const Color(0xFFC4544A), side: const BorderSide(color: Color(0xFFC4544A)), shape: StadiumBorder(), padding: const EdgeInsets.symmetric(vertical: 14)),
        onPressed: () => auth.logout(), child: const Text('退出登录'),
      )),
    ]);
  }

  Widget _pStat(String val, String label) => Column(children: [
    Text(val, style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w700)),
    const SizedBox(height: 2),
    Text(label, style: TextStyle(fontSize: 10, color: Colors.grey[500])),
  ]);

  Widget _menuItem(String icon, String label, VoidCallback onTap) => ListTile(
    leading: Text(icon, style: const TextStyle(fontSize: 22)),
    title: Text(label, style: const TextStyle(fontSize: 14)),
    trailing: const Icon(Icons.chevron_right, size: 16, color: Colors.grey),
    onTap: onTap,
  );
}
