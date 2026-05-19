import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'api_service.dart';

class AuthService extends ChangeNotifier {
  bool _isLoggedIn = false;
  Map<String, dynamic>? _user;
  String? _token;

  bool get isLoggedIn => _isLoggedIn;
  Map<String, dynamic>? get user => _user;
  String? get token => _token;

  Future<void> init() async {
    final prefs = await SharedPreferences.getInstance();
    _token = prefs.getString('access_token');
    if (_token != null) {
      _isLoggedIn = true;
      notifyListeners();
    }
  }

  Future<void> login(String username, String password) async {
    final api = ApiService();
    final res = await api.post('/api/v1/auth/login', {'username': username, 'password': password}, auth: false);
    _token = res['access_token'];
    api.setToken(_token);
    final userData = await api.get('/api/v1/auth/me');
    _user = userData;
    _isLoggedIn = true;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('access_token', res['access_token']);
    await prefs.setString('refresh_token', res['refresh_token']);
    notifyListeners();
  }

  Future<void> logout() async {
    _token = null;
    _user = null;
    _isLoggedIn = false;
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove('access_token');
    await prefs.remove('refresh_token');
    notifyListeners();
  }
}
