import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/api_service.dart';
import '../services/auth_service.dart';
class ProfilePage extends StatefulWidget {
  const ProfilePage({super.key});
  @override
  State<ProfilePage> createState() => _ProfilePageState();
}

class _ProfilePageState extends State<ProfilePage> {
  Map<String, dynamic>? _profile;
  Map<String, dynamic>? _premium;
  Map<String, dynamic>? _points;
  bool _loading = true;
  bool _saving = false;

  final _age = TextEditingController();
  final _gender = TextEditingController();
  final _height = TextEditingController();
  final _weight = TextEditingController();
  final _occupation = TextEditingController();
  final _sleepGoal = TextEditingController();
  final _bedTarget = TextEditingController();
  final _wakeTarget = TextEditingController();
  final _notes = TextEditingController();

  @override
  void initState() {
    super.initState();
    _loadData();
  }

  Future<void> _loadData() async {
    final api = context.read<ApiService>();
    api.setToken(context.read<AuthService>().token);
    setState(() => _loading = true);
    try {
      final results = await Future.wait([
        api.get('/api/v1/profiles'),
        api.get('/api/v1/premium/status'),
        api.get('/api/v1/tasks/points/summary'),
      ]);
      final p = results[0] is Map ? results[0] : null;
      setState(() {
        _profile = p;
        _premium = results[1];
        _points = results[2];
        if (p != null) {
          _age.text = '${p['age'] ?? ''}';
          _gender.text = p['gender'] ?? '';
          _height.text = '${p['height'] ?? ''}';
          _weight.text = '${p['weight'] ?? ''}';
          _occupation.text = p['occupation'] ?? '';
          _sleepGoal.text = '${p['sleep_goal_hours'] ?? ''}';
          _bedTarget.text = p['bedtime_target'] ?? '';
          _wakeTarget.text = p['wakeup_target'] ?? '';
          _notes.text = p['notes'] ?? '';
        }
        _loading = false;
      });
    } catch (e) {
      setState(() => _loading = false);
    }
  }

  Future<void> _saveProfile() async {
    setState(() => _saving = true);
    final api = context.read<ApiService>();
    api.setToken(context.read<AuthService>().token);
    try {
      await api.put('/api/v1/profiles', {
        'age': int.tryParse(_age.text),
        'gender': _gender.text,
        'height': double.tryParse(_height.text),
        'weight': double.tryParse(_weight.text),
        'occupation': _occupation.text,
        'sleep_goal_hours': double.tryParse(_sleepGoal.text),
        'bedtime_target': _bedTarget.text,
        'wakeup_target': _wakeTarget.text,
        'notes': _notes.text,
      });
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('保存成功')));
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('保存失败: $e')));
      }
    }
    setState(() => _saving = false);
  }

  @override
  Widget build(BuildContext context) {
    final tier = _premium?['tier'] ?? 'free';
    return Scaffold(
      appBar: AppBar(title: const Text('健康档案')),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : ListView(padding: const EdgeInsets.all(16), children: [
              // Quick Premium Status
              Card(
                child: ListTile(
                  leading: Text(tier == 'premium' ? '👑' : tier == 'pro' ? '⭐' : '🌱', style: const TextStyle(fontSize: 32)),
                  title: Text(_premium?['tier_info']?['name'] ?? '免费版'),
                  subtitle: Text('🏆 ${_points?['total_points'] ?? 0} 积分'),
                  trailing: const Icon(Icons.arrow_forward_ios, size: 16),
                  onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const VipPage())),
                ),
              ),
              const SizedBox(height: 16),

              // Form
              Card(child: Padding(padding: const EdgeInsets.all(16), child: Column(children: [
                const Text('基本信息', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
                const SizedBox(height: 12),
                Row(children: [
                  Expanded(child: TextField(controller: _age, decoration: const InputDecoration(labelText: '年龄'), keyboardType: TextInputType.number)),
                  const SizedBox(width: 12),
                  Expanded(child: TextField(controller: _gender, decoration: const InputDecoration(labelText: '性别'))),
                ]),
                const SizedBox(height: 12),
                Row(children: [
                  Expanded(child: TextField(controller: _height, decoration: const InputDecoration(labelText: '身高(cm)'), keyboardType: TextInputType.number)),
                  const SizedBox(width: 12),
                  Expanded(child: TextField(controller: _weight, decoration: const InputDecoration(labelText: '体重(kg)'), keyboardType: TextInputType.number)),
                ]),
                const SizedBox(height: 12),
                TextField(controller: _occupation, decoration: const InputDecoration(labelText: '职业')),
              ]))),

              Card(child: Padding(padding: const EdgeInsets.all(16), child: Column(children: [
                const Text('睡眠目标', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
                const SizedBox(height: 12),
                TextField(controller: _sleepGoal, decoration: const InputDecoration(labelText: '目标时长(h)'), keyboardType: TextInputType.number),
                const SizedBox(height: 12),
                Row(children: [
                  Expanded(child: TextField(controller: _bedTarget, decoration: const InputDecoration(labelText: '目标入睡'))),
                  const SizedBox(width: 12),
                  Expanded(child: TextField(controller: _wakeTarget, decoration: const InputDecoration(labelText: '目标起床'))),
                ]),
              ]))),

              Card(child: Padding(padding: const EdgeInsets.all(16), child: Column(children: [
                const Text('补充说明', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
                const SizedBox(height: 12),
                TextField(controller: _notes, decoration: const InputDecoration(labelText: '备注'), maxLines: 3),
              ]))),

              const SizedBox(height: 16),
              SizedBox(width: double.infinity, child: ElevatedButton(
                onPressed: _saving ? null : _saveProfile,
                child: Text(_saving ? '保存中...' : '保存档案'),
              )),
            ]),
    );
  }

  @override
  void dispose() {
    _age.dispose(); _gender.dispose(); _height.dispose(); _weight.dispose();
    _occupation.dispose(); _sleepGoal.dispose(); _bedTarget.dispose();
    _wakeTarget.dispose(); _notes.dispose();
    super.dispose();
  }
}
