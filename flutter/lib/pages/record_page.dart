import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/api_service.dart';
import '../services/auth_service.dart';

class RecordPage extends StatefulWidget {
  const RecordPage({super.key});
  @override
  State<RecordPage> createState() => _RecordPageState();
}

class _RecordPageState extends State<RecordPage> {
  List _records = [];
  bool _loading = true;
  final _sleepTime = TextEditingController(text: '23:00');
  final _wakeTime = TextEditingController(text: '07:00');
  final _quality = TextEditingController(text: '3');
  final _tags = TextEditingController();

  @override
  void initState() {
    super.initState();
    _loadRecords();
  }

  Future<void> _loadRecords() async {
    final api = context.read<ApiService>();
    api.setToken(context.read<AuthService>().token);
    try {
      final data = await api.get('/api/v1/sleep-records');
      setState(() { _records = (data is List) ? data : (data['records'] ?? []); _loading = false; });
    } catch (e) {
      setState(() => _loading = false);
    }
  }

  Future<void> _createRecord() async {
    final api = context.read<ApiService>();
    api.setToken(context.read<AuthService>().token);
    try {
      await api.post('/api/v1/sleep-records', {
        'sleep_time': _sleepTime.text,
        'wake_time': _wakeTime.text,
        'quality': int.tryParse(_quality.text) ?? 3,
        'tags': _tags.text.isNotEmpty ? _tags.text.split(',') : [],
      });
      _loadRecords();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('记录已保存')));
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('保存失败: $e')));
      }
    }
  }

  Future<void> _deleteRecord(int id) async {
    final api = context.read<ApiService>();
    api.setToken(context.read<AuthService>().token);
    try {
      await api.del('/api/v1/sleep-records/$id');
      _loadRecords();
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('删除失败: $e')));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('睡眠记录')),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : RefreshIndicator(
              onRefresh: _loadRecords,
              child: ListView(padding: const EdgeInsets.all(16), children: [
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(children: [
                      const Text('新建记录', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
                      const SizedBox(height: 12),
                      Row(children: [
                        Expanded(child: TextField(controller: _sleepTime, decoration: const InputDecoration(labelText: '入睡时间'))),
                        const SizedBox(width: 12),
                        Expanded(child: TextField(controller: _wakeTime, decoration: const InputDecoration(labelText: '起床时间'))),
                      ]),
                      const SizedBox(height: 12),
                      Row(children: [
                        Expanded(child: TextField(controller: _quality, decoration: const InputDecoration(labelText: '质量(1-5)'), keyboardType: TextInputType.number)),
                        const SizedBox(width: 12),
                        Expanded(child: TextField(controller: _tags, decoration: const InputDecoration(labelText: '标签(逗号分隔)'))),
                      ]),
                      const SizedBox(height: 16),
                      SizedBox(width: double.infinity, child: ElevatedButton(onPressed: _createRecord, child: const Text('保存记录'))),
                    ]),
                  ),
                ),
                const SizedBox(height: 16),
                const Text('历史记录', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
                ..._records.map((r) => Card(
                      child: ListTile(
                        title: Text('${r['diary_date'] ?? r['date'] ?? ''}'),
                        subtitle: Text('${r['sleep_time'] ?? ''} - ${r['wake_time'] ?? ''} | 评分: ${r['score'] ?? '--'}'),
                        trailing: IconButton(icon: const Icon(Icons.delete, color: Colors.red), onPressed: () => _deleteRecord(r['id'])),
                      ),
                    )),
              ]),
            ),
    );
  }

  @override
  void dispose() {
    _sleepTime.dispose();
    _wakeTime.dispose();
    _quality.dispose();
    _tags.dispose();
    super.dispose();
  }
}
