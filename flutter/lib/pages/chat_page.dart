import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/api_service.dart';
import '../services/auth_service.dart';

class ChatPage extends StatefulWidget {
  const ChatPage({super.key});
  @override
  State<ChatPage> createState() => _ChatPageState();
}

class _ChatPageState extends State<ChatPage> {
  List _messages = [];
  List _sessions = [];
  int? _activeSession;
  final _input = TextEditingController();
  bool _sending = false;
  final _scrollCtrl = ScrollController();

  final _quickQs = ['如何改善失眠问题？', '什么是最佳睡眠时间？', '睡前应该做什么？', '分析一下我的睡眠数据'];

  @override
  void initState() {
    super.initState();
    _loadSessions();
  }

  Future<void> _loadSessions() async {
    final api = context.read<ApiService>();
    api.setToken(context.read<AuthService>().token);
    try {
      final data = await api.get('/api/v1/chat/sessions');
      setState(() { _sessions = (data is List) ? data : []; });
    } catch (_) {}
  }

  Future<void> _openSession(int id) async {
    final api = context.read<ApiService>();
    api.setToken(context.read<AuthService>().token);
    try {
      final data = await api.get('/api/v1/chat/sessions/$id');
      setState(() {
        _activeSession = id;
        _messages = (data['messages'] as List?) ?? [];
      });
    } catch (_) {}
  }

  Future<void> _sendMessage() async {
    final text = _input.text.trim();
    if (text.isEmpty || _sending) return;
    setState(() { _sending = true; _input.clear(); });
    final api = context.read<ApiService>();
    api.setToken(context.read<AuthService>().token);
    _messages.add({'role': 'user', 'content': text, 'id': DateTime.now().millisecondsSinceEpoch});
    try {
      final data = await api.post('/api/v1/chat/send', {
        'session_id': _activeSession,
        'message': text,
      });
      _messages.add({'role': data['role'], 'content': data['content'], 'id': data['id']});
      if (_activeSession == null) {
        _activeSession = data['session_id'];
        _loadSessions();
      }
    } catch (_) {
      _messages.add({'role': 'assistant', 'content': '抱歉，暂时无法回复。', 'id': DateTime.now().millisecondsSinceEpoch + 1});
    }
    setState(() { _messages = List.from(_messages); _sending = false; });
    _scrollCtrl.animateTo(_scrollCtrl.position.maxScrollExtent, duration: const Duration(milliseconds: 300), curve: Curves.easeOut);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('AI睡眠助手'), actions: [
        IconButton(icon: const Icon(Icons.add), onPressed: () => setState(() { _activeSession = null; _messages = []; })),
      ]),
      drawer: Drawer(
        child: ListView(children: [
          const DrawerHeader(child: Text('会话历史')),
          ..._sessions.map((s) => ListTile(
            title: Text(s['title'] ?? '会话 ${s['id']}'),
            selected: _activeSession == s['id'],
            onTap: () { Navigator.pop(context); _openSession(s['id']); },
          )),
        ]),
      ),
      body: Column(children: [
        if (_messages.isEmpty) Expanded(child: Center(
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            const Text('👋 我是你的AI睡眠助手', style: TextStyle(fontSize: 18)),
            const SizedBox(height: 8),
            const Text('有什么可以帮你的？', style: TextStyle(color: Colors.grey)),
            const SizedBox(height: 16),
            Wrap(spacing: 8, children: _quickQs.map((q) => ActionChip(
              label: Text(q, style: const TextStyle(fontSize: 12)),
              onPressed: () { _input.text = q; _sendMessage(); },
            )).toList()),
          ]),
        )),
        if (_messages.isNotEmpty) Expanded(
          child: ListView.builder(
            controller: _scrollCtrl,
            padding: const EdgeInsets.all(16),
            itemCount: _messages.length,
            itemBuilder: (_, i) {
              final m = _messages[i];
              final isUser = m['role'] == 'user';
              return Align(
                alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
                child: Container(
                  margin: const EdgeInsets.only(top: 8),
                  padding: const EdgeInsets.all(12),
                  constraints: BoxConstraints(maxWidth: MediaQuery.of(context).size.width * 0.75),
                  decoration: BoxDecoration(
                    color: isUser ? const Color(0xFF6C63FF) : const Color(0xFF16213E),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Text(m['content'] ?? '', style: const TextStyle(color: Colors.white)),
                ),
              );
            },
          ),
        ),
        Padding(
          padding: const EdgeInsets.all(12),
          child: Row(children: [
            Expanded(
              child: TextField(controller: _input, decoration: const InputDecoration(hintText: '输入消息...', border: OutlineInputBorder())),
            ),
            const SizedBox(width: 8),
            IconButton(onPressed: _sending ? null : _sendMessage, icon: Icon(_sending ? Icons.hourglass_empty : Icons.send, color: const Color(0xFF6C63FF))),
          ]),
        ),
      ]),
    );
  }

  @override
  void dispose() { _input.dispose(); _scrollCtrl.dispose(); super.dispose(); }
}
