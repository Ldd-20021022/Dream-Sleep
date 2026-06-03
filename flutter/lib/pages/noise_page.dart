import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/api_service.dart';
import '../services/auth_service.dart';

class NoisePage extends StatefulWidget {
  const NoisePage({super.key});
  @override
  State<NoisePage> createState() => _NoisePageState();
}

class _NoisePageState extends State<NoisePage> {
  final _scenes = [
    {'id': 'forest', 'name': '森林夜语', 'icon': '🌲', 'desc': '深棕噪音 + 鸟鸣 + 蟋蟀'},
    {'id': 'ocean', 'name': '海浪轻拍', 'icon': '🌊', 'desc': '深海低频 + 波浪 + 气泡'},
    {'id': 'rain', 'name': '雨夜窗前', 'icon': '🌧', 'desc': '连续雨声 + 水滴 + 远雷'},
    {'id': 'campfire', 'name': '篝火星空', 'icon': '🔥', 'desc': '火焰低鸣 + 噼啪爆裂'},
    {'id': 'wind', 'name': '山谷微风', 'icon': '🍃', 'desc': '风涌主频 + 粉红漂移'},
    {'id': 'stream', 'name': '溪流潺潺', 'icon': '💧', 'desc': '水流主频 + 水滴叮咚'},
  ];

  String _activeScene = 'forest';
  bool _playing = false;
  double _volume = 0.7;
  int _timerMin = 30;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('白噪音')),
      body: ListView(padding: const EdgeInsets.all(16), children: [
        const Text('选择场景', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
        const SizedBox(height: 12),
        GridView.count(crossAxisCount: 3, shrinkWrap: true, physics: const NeverScrollableScrollPhysics(),
          crossAxisSpacing: 12, mainAxisSpacing: 12,
          children: _scenes.map((s) => GestureDetector(
            onTap: () => setState(() => _activeScene = s['id'] as String),
            child: Container(
              decoration: BoxDecoration(
                color: _activeScene == s['id'] ? const Color(0xFF6C63FF).withOpacity(0.2) : const Color(0xFF16213E),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: _activeScene == s['id'] ? const Color(0xFF6C63FF) : Colors.transparent),
              ),
              padding: const EdgeInsets.all(12),
              child: Column(mainAxisSize: MainAxisSize.min, children: [
                Text(s['icon'] as String, style: const TextStyle(fontSize: 32)),
                const SizedBox(height: 4),
                Text(s['name'] as String, style: const TextStyle(fontSize: 12, fontWeight: FontWeight.bold)),
              ]),
            ),
          )).toList(),
        ),
        const SizedBox(height: 24),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(children: [
              Row(mainAxisAlignment: MainAxisAlignment.center, children: [
                IconButton(
                  iconSize: 48,
                  icon: Icon(_playing ? Icons.pause_circle : Icons.play_circle, color: const Color(0xFF6C63FF)),
                  onPressed: () => setState(() => _playing = !_playing),
                ),
              ]),
              const SizedBox(height: 16),
              Row(children: [
                const Text('音量'),
                Expanded(
                  child: Slider(value: _volume, onChanged: (v) => setState(() => _volume = v)),
                ),
                Text('${(_volume * 100).round()}%'),
              ]),
              Row(children: [
                const Text('定时'),
                Expanded(
                  child: Slider(value: _timerMin.toDouble(), min: 5, max: 120, divisions: 23, onChanged: (v) => setState(() => _timerMin = v.round())),
                ),
                Text('${_timerMin}min'),
              ]),
            ]),
          ),
        ),
      ]),
    );
  }
}
