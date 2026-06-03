import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/api_service.dart';
import '../services/auth_service.dart';

class KnowledgePage extends StatefulWidget {
  const KnowledgePage({super.key});
  @override
  State<KnowledgePage> createState() => _KnowledgePageState();
}

class _KnowledgePageState extends State<KnowledgePage> {
  List _categories = [];
  List _articles = [];
  Map<String, dynamic>? _article;

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
        api.get('/api/v1/wellness/knowledge/categories'),
        api.get('/api/v1/wellness/knowledge/articles'),
      ]);
      setState(() {
        _categories = (results[0]['categories'] as List?) ?? (results[0] is List ? results[0] : []);
        _articles = (results[1]['articles'] as List?) ?? (results[1] is List ? results[1] : []);
      });
    } catch (_) {}
  }

  Future<void> _loadArticle(int id) async {
    final api = context.read<ApiService>();
    api.setToken(context.read<AuthService>().token);
    try {
      final data = await api.get('/api/v1/wellness/knowledge/articles/$id');
      setState(() => _article = data);
    } catch (_) {}
  }

  @override
  Widget build(BuildContext context) {
    if (_article != null) {
      return Scaffold(
        appBar: AppBar(title: Text(_article!['title'] ?? '文章详情'), leading: IconButton(icon: const Icon(Icons.arrow_back), onPressed: () => setState(() => _article = null))),
        body: Padding(padding: const EdgeInsets.all(16), child: SingleChildScrollView(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(_article!['title'] ?? '', style: const TextStyle(fontSize: 24, fontWeight: FontWeight.bold)),
          const SizedBox(height: 8),
          Text(_article!['category'] ?? '', style: const TextStyle(color: Colors.grey)),
          const SizedBox(height: 16),
          Text(_article!['content'] ?? ''),
        ]))),
      );
    }
    return Scaffold(
      appBar: AppBar(title: const Text('睡眠知识库')),
      body: ListView(padding: const EdgeInsets.all(16), children: [
        if (_categories.isNotEmpty) ...[
          Wrap(spacing: 8, children: _categories.map((c) => Chip(
            label: Text(c is String ? c : (c['name'] ?? '')),
          )).toList()),
          const SizedBox(height: 16),
        ],
        ..._articles.map((a) => Card(
          child: ListTile(
            title: Text(a['title'] ?? '', maxLines: 1),
            subtitle: Text(a['summary'] ?? a['category'] ?? '', maxLines: 2),
            trailing: const Icon(Icons.arrow_forward_ios, size: 16),
            onTap: () => _loadArticle(a['id']),
          ),
        )),
      ]),
    );
  }
}
