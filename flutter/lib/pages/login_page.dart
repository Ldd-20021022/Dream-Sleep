import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/auth_service.dart';

class LoginPage extends StatefulWidget {
  const LoginPage({super.key});
  @override
  State<LoginPage> createState() => _LoginPageState();
}

class _LoginPageState extends State<LoginPage> {
  final _u = TextEditingController();
  final _p = TextEditingController();
  String? _err;
  bool _loading = false;

  Future<void> _login() async {
    setState(() { _err = null; _loading = true; });
    try {
      await context.read<AuthService>().login(_u.text, _p.text);
    } catch (e) {
      setState(() { _err = '登录失败: $e'; });
    }
    setState(() { _loading = false; });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Center(
        child: Card(
          child: Padding(
            padding: const EdgeInsets.all(32),
            child: SizedBox(
              width: 360,
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Text('☺', style: TextStyle(fontSize: 64)),
                  const Text('梦眠阁', style: TextStyle(fontSize: 28, fontWeight: FontWeight.bold)),
                  const Text('AI智能睡眠管理', style: TextStyle(color: Colors.grey)),
                  const SizedBox(height: 24),
                  TextField(controller: _u, decoration: const InputDecoration(labelText: '用户名')),
                  const SizedBox(height: 12),
                  TextField(controller: _p, obscureText: true, decoration: const InputDecoration(labelText: '密码')),
                  if (_err != null) Padding(padding: const EdgeInsets.only(top: 12), child: Text(_err!, style: const TextStyle(color: Colors.red))),
                  const SizedBox(height: 20),
                  SizedBox(width: double.infinity, child: ElevatedButton(onPressed: _loading ? null : _login, child: Text(_loading ? '登录中...' : '登录'))),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  @override
  void dispose() { _u.dispose(); _p.dispose(); super.dispose(); }
}
