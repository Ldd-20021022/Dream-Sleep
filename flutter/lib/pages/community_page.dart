import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/api_service.dart';
import '../services/auth_service.dart';

class CommunityPage extends StatefulWidget {
  const CommunityPage({super.key});
  @override
  State<CommunityPage> createState() => _CommunityPageState();
}

class _CommunityPageState extends State<CommunityPage> {
  List _groups = [];
  List _challenges = [];
  List _posts = [];
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
        api.get('/api/v1/community/groups'),
        api.get('/api/v1/community/challenges'),
        api.get('/api/v1/community/posts'),
        api.get('/api/v1/community/leaderboard'),
      ]);
      setState(() {
        _groups = (results[0]['groups'] as List?) ?? (results[0] is List ? results[0] : []);
        _challenges = (results[1]['challenges'] as List?) ?? (results[1] is List ? results[1] : []);
        _posts = (results[2]['posts'] as List?) ?? (results[2] is List ? results[2] : []);
        _leaderboard = (results[3]['leaderboard'] as List?) ?? (results[3] is List ? results[3] : []);
      });
    } catch (_) {}
  }

  Future<void> _joinGroup(int id) async {
    final api = context.read<ApiService>();
    api.setToken(context.read<AuthService>().token);
    try {
      await api.post('/api/v1/community/groups/$id/join', {});
      _loadData();
    } catch (_) {}
  }

  Future<void> _likePost(int id) async {
    final api = context.read<ApiService>();
    api.setToken(context.read<AuthService>().token);
    try {
      await api.post('/api/v1/community/posts/$id/like', {});
      _loadData();
    } catch (_) {}
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('睡眠社区')),
      body: DefaultTabController(
        length: 3,
        child: Column(children: [
          const TabBar(tabs: [
            Tab(text: '群组'),
            Tab(text: '帖子'),
            Tab(text: '排行榜'),
          ]),
          Expanded(child: TabBarView(children: [
            ListView(padding: const EdgeInsets.all(16), children: [
              ..._groups.map((g) => Card(
                child: ListTile(
                  title: Text(g['name'] ?? ''),
                  subtitle: Text('${g['member_count'] ?? 0} 成员'),
                  trailing: ElevatedButton(onPressed: () => _joinGroup(g['id']), child: const Text('加入')),
                ),
              )),
              if (_challenges.isNotEmpty) const Text('挑战', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
              ..._challenges.map((c) => Card(
                child: ListTile(
                  title: Text(c['title'] ?? c['name'] ?? ''),
                  subtitle: Text(c['description'] ?? ''),
                ),
              )),
            ]),
            ListView(padding: const EdgeInsets.all(16), children: _posts.map((p) => Card(
              child: ListTile(
                title: Text(p['content'] ?? '', maxLines: 2),
                subtitle: Text('${p['nickname'] ?? p['username'] ?? ''} · ${p['like_count'] ?? 0} 赞'),
                trailing: IconButton(icon: const Icon(Icons.favorite_border), onPressed: () => _likePost(p['id'])),
              ),
            )).toList()),
            ListView(padding: const EdgeInsets.all(16), children: _leaderboard.map((l) => Card(
              child: ListTile(
                leading: CircleAvatar(child: Text('${l['rank'] ?? ''}')),
                title: Text(l['nickname'] ?? l['username'] ?? ''),
                subtitle: Text('${l['total_xp'] ?? 0} XP · Lv${l['level'] ?? 1}'),
              ),
            )).toList()),
          ])),
        ]),
      ),
    );
  }
}
