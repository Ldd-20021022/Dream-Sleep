import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/api_service.dart';
import '../services/auth_service.dart';

class AnalysisPage extends StatefulWidget {
  const AnalysisPage({super.key});
  @override
  State<AnalysisPage> createState() => _AnalysisPageState();
}

class _AnalysisPageState extends State<AnalysisPage> {
  Map<String, dynamic>? _stats;
  Map<String, dynamic>? _enhanced;
  Map<String, dynamic>? _radar;
  Map<String, dynamic>? _compare;
  int _days = 7;
  bool _loading = true;

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
        api.get('/api/v1/sleep-records/stats/summary?days=$_days'),
        api.get('/api/v1/sleep-records/stats/enhanced'),
        api.get('/api/v1/sleep-records/viz/radar'),
        api.get('/api/v1/sleep-records/viz/compare'),
      ]);
      setState(() {
        _stats = results[0];
        _enhanced = results[1];
        _radar = results[2];
        _compare = results[3];
        _loading = false;
      });
    } catch (e) {
      setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('睡眠分析')),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : RefreshIndicator(
              onRefresh: _loadData,
              child: ListView(padding: const EdgeInsets.all(16), children: [
                Row(mainAxisAlignment: MainAxisAlignment.center, children: [
                  _chip(7, '7天'),
                  const SizedBox(width: 8),
                  _chip(14, '14天'),
                  const SizedBox(width: 8),
                  _chip(30, '30天'),
                ]),
                const SizedBox(height: 16),
                GridView.count(crossAxisCount: 2, shrinkWrap: true, physics: const NeverScrollableScrollPhysics(),
                  childAspectRatio: 1.5, crossAxisSpacing: 12, mainAxisSpacing: 12,
                  children: [
                    _statCard('平均时长', '${_stats?['avg_duration'] ?? '--'}h'),
                    _statCard('平均评分', '${_stats?['avg_score'] ?? '--'}'),
                    _statCard('连续达标', '${_stats?['streak_days'] ?? 0}天'),
                    _statCard('规律度', '${_stats?['regularity'] ?? '--'}%'),
                  ],
                ),
                const SizedBox(height: 16),
                if (_enhanced != null) Card(
                  child: Padding(padding: const EdgeInsets.all(16), child: Column(children: [
                    const Text('深度分析', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
                    const SizedBox(height: 8),
                    Text('睡眠效率: ${_enhanced?['sleep_efficiency'] ?? '--'}%'),
                    Text('睡眠债务: ${_enhanced?['sleep_debt'] ?? '--'}h'),
                    Text('平均入睡时间: ${_enhanced?['avg_sleep_latency'] ?? '--'}min'),
                  ])),
                ),
                if (_radar != null) Card(
                  child: Padding(padding: const EdgeInsets.all(16), child: Column(children: [
                    const Text('能力雷达', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
                    const SizedBox(height: 8),
                    ..._radar!.entries.map((e) => Text('${e.key}: ${e.value}')).toList(),
                  ])),
                ),
              ]),
            ),
    );
  }

  Widget _chip(int days, String label) {
    return ChoiceChip(
      label: Text(label),
      selected: _days == days,
      onSelected: (s) { setState(() { _days = days; }); _loadData(); },
    );
  }

  Widget _statCard(String label, String value) {
    return Card(
      child: Center(
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          Text(label, style: const TextStyle(fontSize: 12, color: Colors.grey)),
          const SizedBox(height: 4),
          Text(value, style: const TextStyle(fontSize: 28, fontWeight: FontWeight.bold)),
        ]),
      ),
    );
  }
}
