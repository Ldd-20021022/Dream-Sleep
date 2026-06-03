import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/api_service.dart';
import '../services/auth_service.dart';

class CoursesPage extends StatefulWidget {
  const CoursesPage({super.key});
  @override
  State<CoursesPage> createState() => _CoursesPageState();
}

class _CoursesPageState extends State<CoursesPage> {
  List _courses = [];
  Map<String, dynamic>? _viewing;
  List _chapters = [];

  @override
  void initState() {
    super.initState();
    _loadCourses();
  }

  Future<void> _loadCourses() async {
    final api = context.read<ApiService>();
    api.setToken(context.read<AuthService>().token);
    try {
      final data = await api.get('/api/v1/courses');
      setState(() { _courses = (data['courses'] as List?) ?? (data is List ? data : []); });
    } catch (_) {}
  }

  Future<void> _loadChapters(int id) async {
    final api = context.read<ApiService>();
    api.setToken(context.read<AuthService>().token);
    try {
      final data = await api.get('/api/v1/courses/$id/chapters');
      setState(() { _chapters = (data['chapters'] as List?) ?? (data is List ? data : []); });
    } catch (_) {}
  }

  @override
  Widget build(BuildContext context) {
    if (_viewing != null) {
      return Scaffold(
        appBar: AppBar(title: Text(_viewing!['title'] ?? '课程详情'), leading: IconButton(icon: const Icon(Icons.arrow_back), onPressed: () => setState(() { _viewing = null; _chapters = []; }))),
        body: ListView(padding: const EdgeInsets.all(16), children: [
          Text(_viewing!['title'] ?? '', style: const TextStyle(fontSize: 24, fontWeight: FontWeight.bold)),
          Text(_viewing!['description'] ?? '', style: const TextStyle(color: Colors.grey)),
          const SizedBox(height: 16),
          ElevatedButton.icon(
            icon: const Icon(Icons.school),
            label: const Text('报名学习'),
            onPressed: () async {
              final api = context.read<ApiService>();
              api.setToken(context.read<AuthService>().token);
              await api.post('/api/v1/courses/${_viewing!['id']}/enroll', {});
              if (mounted) {
                ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('报名成功')));
              }
            },
          ),
          const SizedBox(height: 16),
          const Text('课程章节', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
          ..._chapters.map((c) => Card(
            child: ListTile(
              leading: CircleAvatar(child: Text('${c['order'] ?? ''}')),
              title: Text(c['title'] ?? ''),
              subtitle: Text(c['duration'] ?? ''),
            ),
          )),
        ]),
      );
    }
    return Scaffold(
      appBar: AppBar(title: const Text('睡眠课程')),
      body: ListView(padding: const EdgeInsets.all(16), children: _courses.map((c) => Card(
        child: ListTile(
          leading: const Icon(Icons.play_circle, size: 40, color: Color(0xFF6C63FF)),
          title: Text(c['title'] ?? c['name'] ?? ''),
          subtitle: Text(c['description'] ?? '', maxLines: 2),
          trailing: const Icon(Icons.arrow_forward_ios, size: 16),
          onTap: () { setState(() => _viewing = c); _loadChapters(c['id']); },
        ),
      )).toList()),
    );
  }
}
