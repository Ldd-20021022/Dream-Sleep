import 'dart:convert';
import 'package:http/http.dart' as http;

class ApiService {
  static const String _devHost = 'http://192.168.3.64:8000';
  static const String _prodHost = 'https://your-domain.com';
  String get baseUrl => _devHost;

  String? _token;

  void setToken(String? t) => _token = t;

  Map<String, String> _headers({bool auth = true}) {
    final h = {'Content-Type': 'application/json'};
    if (auth && _token != null) h['Authorization'] = 'Bearer $_token';
    return h;
  }

  Future<dynamic> get(String path, {bool auth = true}) async {
    final r = await http.get(Uri.parse('$baseUrl$path'), headers: _headers(auth: auth));
    if (r.statusCode == 200) return jsonDecode(r.body);
    throw Exception('${r.statusCode}: ${r.body}');
  }

  Future<dynamic> post(String path, dynamic data, {bool auth = true}) async {
    final r = await http.post(Uri.parse('$baseUrl$path'), headers: _headers(auth: auth), body: jsonEncode(data));
    if (r.statusCode == 200) return jsonDecode(r.body);
    throw Exception('${r.statusCode}: ${r.body}');
  }

  Future<dynamic> put(String path, dynamic data, {bool auth = true}) async {
    final r = await http.put(Uri.parse('$baseUrl$path'), headers: _headers(auth: auth), body: jsonEncode(data));
    if (r.statusCode == 200) return jsonDecode(r.body);
    throw Exception('${r.statusCode}: ${r.body}');
  }

  Future<dynamic> del(String path, {bool auth = true}) async {
    final r = await http.delete(Uri.parse('$baseUrl$path'), headers: _headers(auth: auth));
    if (r.statusCode == 200) return jsonDecode(r.body);
    throw Exception('${r.statusCode}: ${r.body}');
  }
}
