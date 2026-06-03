import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/api_service.dart';
import '../services/auth_service.dart';

class AssessmentPage extends StatefulWidget {
  const AssessmentPage({super.key});
  @override
  State<AssessmentPage> createState() => _AssessmentPageState();
}

class _AssessmentPageState extends State<AssessmentPage> {
  List _scales = [];
  Map<String, dynamic>? _scale;
  Map<String, dynamic>? _result;
  int _qIndex = 0;
  Map<String, dynamic> _answers = {};
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _loadScales();
  }

  Future<void> _loadScales() async {
    final api = context.read<ApiService>();
    api.setToken(context.read<AuthService>().token);
    try {
      final data = await api.get('/api/v1/wellness/assessments');
      setState(() { _scales = (data['scales'] as List?) ?? (data is List ? data : []); _loading = false; });
    } catch (e) {
      setState(() => _loading = false);
    }
  }

  Future<void> _loadQuestions(String id) async {
    final api = context.read<ApiService>();
    api.setToken(context.read<AuthService>().token);
    try {
      final data = await api.get('/api/v1/wellness/assessments/$id');
      setState(() { _scale = data; _qIndex = 0; _answers = {}; _result = null; });
    } catch (_) {}
  }

  Future<void> _submit() async {
    final api = context.read<ApiService>();
    api.setToken(context.read<AuthService>().token);
    try {
      final data = await api.post('/api/v1/wellness/assessments/${_scale!['id']}/submit', {
        'answers': _answers,
      });
      setState(() => _result = data);
    } catch (_) {}
  }

  @override
  Widget build(BuildContext context) {
    if (_result != null) {
      return Scaffold(
        appBar: AppBar(title: const Text('评估结果')),
        body: Padding(padding: const EdgeInsets.all(16), child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
          const Icon(Icons.check_circle, size: 80, color: Colors.green),
          const SizedBox(height: 16),
          Text('${_result!['score'] ?? '--'} 分', style: const TextStyle(fontSize: 48, fontWeight: FontWeight.bold)),
          Text(_result!['level'] ?? _result!['interpretation'] ?? '', style: const TextStyle(fontSize: 18)),
          const SizedBox(height: 16),
          if (_result!['analysis'] != null) Card(child: Padding(padding: const EdgeInsets.all(16), child: Text(_result!['analysis']))),
          const SizedBox(height: 24),
          ElevatedButton(onPressed: () => setState(() { _scale = null; _result = null; }), child: const Text('返回列表')),
        ])),
      );
    }

    if (_scale != null) {
      final questions = (_scale!['questions'] as List?) ?? [];
      if (_qIndex >= questions.length) {
        _submit();
        return const Scaffold(body: Center(child: CircularProgressIndicator()));
      }
      final q = questions[_qIndex];
      final options = (q['options'] as List?) ?? [];
      return Scaffold(
        appBar: AppBar(title: Text(_scale!['name'] ?? _scale!['title'] ?? '评估'), leading: IconButton(icon: const Icon(Icons.arrow_back), onPressed: () => setState(() => _scale = null))),
        body: Padding(padding: const EdgeInsets.all(16), child: Column(children: [
          LinearProgressIndicator(value: questions.isNotEmpty ? (_qIndex + 1) / questions.length : 0),
          const SizedBox(height: 4),
          Text('${_qIndex + 1} / ${questions.length}', style: const TextStyle(color: Colors.grey, fontSize: 12)),
          const SizedBox(height: 24),
          Text(q['text'] ?? q['question'] ?? '', style: const TextStyle(fontSize: 18)),
          const SizedBox(height: 24),
          ...options.asMap().entries.map((entry) {
            final i = entry.key;
            final opt = entry.value;
            final label = opt is String ? opt : (opt['text'] ?? opt['label'] ?? '');
            final value = opt is Map ? (opt['value'] ?? i) : i;
            return Card(
              child: ListTile(
                title: Text(label),
                selected: _answers['${q['id']}'] == value,
                onTap: () {
                  setState(() { _answers['${q['id']}'] = value; _qIndex++; });
                },
              ),
            );
          }),
        ])),
      );
    }

    return Scaffold(
      appBar: AppBar(title: const Text('睡眠评估')),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : ListView(padding: const EdgeInsets.all(16), children: [
              const Text('选择评估量表', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
              const SizedBox(height: 12),
              ..._scales.map((s) => Card(
                    child: ListTile(
                      leading: const Icon(Icons.assignment, color: Color(0xFF6C63FF)),
                      title: Text(s['name'] ?? s['title'] ?? ''),
                      subtitle: Text(s['description'] ?? '', maxLines: 2),
                      trailing: const Icon(Icons.arrow_forward_ios, size: 16),
                      onTap: () => _loadQuestions(s['id'] ?? s['scale_id'] ?? ''),
                    ),
                  )),
            ]),
    );
  }
}
