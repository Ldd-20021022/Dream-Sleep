import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/api_service.dart';
import '../services/auth_service.dart';

class OnboardingPage extends StatefulWidget {
  const OnboardingPage({super.key});
  @override
  State<OnboardingPage> createState() => _OnboardingPageState();
}

class _OnboardingPageState extends State<OnboardingPage> {
  int _step = 0;
  final _data = <String, dynamic>{};
  bool _submitting = false;
  static const _primary = Color(0xFF5B6ABF);

  static const _steps = [
    {'title': '基本信息', 'subtitle': '让我们先认识一下你', 'icon': '👋'},
    {'title': '睡眠目标', 'subtitle': '你理想中的睡眠是什么样的？', 'icon': '🎯'},
    {'title': '睡眠困扰', 'subtitle': '你目前面临什么问题？', 'icon': '🔍'},
    {'title': '生活习惯', 'subtitle': '了解你的日常节奏', 'icon': '🏃'},
    {'title': '改善目标', 'subtitle': '最想改变什么？', 'icon': '✨'},
  ];

  final _issueOptions = ['入睡困难', '夜间醒来', '早醒', '睡眠浅', '多梦', '打鼾', '白天嗜睡', '作息不规律'];
  final _priorityOptions = ['入睡速度', '睡眠深度', '减少夜醒', '作息规律', '精力恢复', '减少焦虑'];

  Future<void> _finish() async {
    setState(() => _submitting = true);
    try {
      final api = context.read<ApiService>();
      api.setToken(context.read<AuthService>().token);
      await api.post('/api/v1/wellness/onboarding/complete', _data);
      if (mounted) Navigator.pushReplacementNamed(context, '/home');
    } catch (_) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('保存失败，请重试')));
    }
    if (mounted) setState(() => _submitting = false);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(children: [
          // Progress
          Row(mainAxisAlignment: MainAxisAlignment.center, children: List.generate(5, (i) => Container(
            width: 36, height: 36, margin: const EdgeInsets.symmetric(horizontal: 5),
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: i < _step ? _primary.withOpacity(0.15) : (i == _step ? _primary : Colors.white.withOpacity(0.04)),
              border: Border.all(color: i <= _step ? _primary : Colors.white.withOpacity(0.06)),
            ),
            child: Center(child: Text(i < _step ? '✓' : '${i + 1}', style: TextStyle(fontSize: 15, fontWeight: FontWeight.w600, color: i <= _step ? _primary : Colors.grey))),
          ))),
          const SizedBox(height: 40),
          // Header
          Text(_steps[_step]['icon']!, style: const TextStyle(fontSize: 60)),
          const SizedBox(height: 12),
          Text(_steps[_step]['title']!, style: const TextStyle(fontSize: 28, fontWeight: FontWeight.w700)),
          const SizedBox(height: 6),
          Text(_steps[_step]['subtitle']!, style: TextStyle(fontSize: 14, color: Colors.grey[500])),
          const SizedBox(height: 36),
          // Body
          Expanded(child: _buildBody()),
        ]),
      )),
      bottomNavigationBar: SafeArea(child: Padding(
        padding: const EdgeInsets.all(24),
        child: Row(children: [
          GestureDetector(onTap: () => Navigator.pop(context), child: Text('跳过', style: TextStyle(fontSize: 14, color: Colors.grey[500]))),
          const Spacer(),
          if (_step > 0)
            OutlinedButton(onPressed: () => setState(() => _step--), style: OutlinedButton.styleFrom(foregroundColor: Colors.grey[400], side: BorderSide(color: Colors.grey[600]!)), child: const Text('上一步')),
          const SizedBox(width: 10),
          FilledButton(
            onPressed: _submitting ? null : () => _step < 4 ? setState(() => _step++) : _finish(),
            style: FilledButton.styleFrom(backgroundColor: _primary),
            child: Text(_step < 4 ? '下一步' : '✓ 完成'),
          ),
        ]),
      )),
    );
  }

  Widget _buildBody() {
    switch (_step) {
      case 0: return _buildStep1();
      case 1: return _buildStep2();
      case 2: return _buildStep3();
      case 3: return _buildStep4();
      case 4: return _buildStep5();
      default: return const SizedBox();
    }
  }

  Widget _buildStep1() => ListView(children: [
    _fieldLabel('年龄'),
    TextField(decoration: const InputDecoration(hintText: '请输入年龄'), keyboardType: TextInputType.number, onChanged: (v) => _data['age'] = v),
    const SizedBox(height: 20),
    _fieldLabel('性别'),
    Wrap(spacing: 8, children: ['男', '女', '保密'].map((g) => ChoiceChip(
      label: Text(g), selected: _data['gender'] == g,
      onSelected: (v) => setState(() => _data['gender'] = v ? g : null)),
    ).toList()),
  ]);

  Widget _buildStep2() => ListView(children: [
    _fieldLabel('目标睡眠时长：${_data['sleep_goal_hours'] ?? 8} 小时'),
    Slider(value: (_data['sleep_goal_hours'] ?? 8).toDouble(), min: 5, max: 10, divisions: 10, activeColor: _primary,
      label: '${_data['sleep_goal_hours'] ?? 8}', onChanged: (v) => setState(() => _data['sleep_goal_hours'] = v)),
    const SizedBox(height: 20),
    _fieldLabel('目标就寝时间'),
    TextField(decoration: const InputDecoration(hintText: '22:30'), onChanged: (v) => _data['bedtime_target'] = v),
    const SizedBox(height: 20),
    _fieldLabel('目标起床时间'),
    TextField(decoration: const InputDecoration(hintText: '07:00'), onChanged: (v) => _data['wakeup_target'] = v),
  ]);

  Widget _buildStep3() => ListView(children: [
    _fieldLabel('选择你遇到的问题（可多选）'),
    const SizedBox(height: 10),
    Wrap(spacing: 8, runSpacing: 8, children: _issueOptions.map((o) {
      final selected = (_data['sleep_issues'] as List<String>?)?.contains(o) ?? false;
      return FilterChip(label: Text(o), selected: selected, onSelected: (v) {
        final list = List<String>.from(_data['sleep_issues'] ?? []);
        v ? list.add(o) : list.remove(o);
        setState(() => _data['sleep_issues'] = list);
      });
    }).toList()),
  ]);

  Widget _buildStep4() => ListView(children: [
    _fieldLabel('咖啡因摄入'),
    _chipBar(['不喝', '偶尔', '每天1-2杯', '每天3杯以上'], 'caffeine_intake'),
    const SizedBox(height: 24),
    _fieldLabel('运动频率'),
    _chipBar(['几乎不运动', '每周1-2次', '每周3-5次', '每天运动'], 'exercise_frequency'),
    const SizedBox(height: 24),
    _fieldLabel('压力水平'),
    _chipBar(['低', '中', '高', '极高'], 'stress_level'),
  ]);

  Widget _buildStep5() => ListView(children: [
    _fieldLabel('你最想改善什么？（最多选3项）'),
    const SizedBox(height: 10),
    Wrap(spacing: 8, runSpacing: 8, children: _priorityOptions.map((o) {
      final selected = (_data['improvement_priority'] as List<String>?)?.contains(o) ?? false;
      return FilterChip(label: Text(o), selected: selected, onSelected: (v) {
        final list = List<String>.from(_data['improvement_priority'] ?? []);
        if (v && list.length >= 3) return;
        v ? list.add(o) : list.remove(o);
        setState(() => _data['improvement_priority'] = list);
      });
    }).toList()),
    const SizedBox(height: 24),
    _fieldLabel('你的主要目标'),
    TextField(decoration: const InputDecoration(hintText: '例如：希望每晚11点前入睡...'), maxLines: 2, onChanged: (v) => _data['primary_goal'] = v),
  ]);

  Widget _fieldLabel(String text) => Padding(
    padding: const EdgeInsets.only(bottom: 8),
    child: Text(text, style: TextStyle(fontSize: 14, color: Colors.grey[400], fontWeight: FontWeight.w500)),
  );

  Widget _chipBar(List<String> options, String key) => Wrap(spacing: 8, children: options.map((o) => ChoiceChip(
    label: Text(o, style: const TextStyle(fontSize: 13)),
    selected: _data[key] == o,
    onSelected: (v) => setState(() => _data[key] = v ? o : null),
  )).toList());
}
