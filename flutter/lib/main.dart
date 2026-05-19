import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'services/api_service.dart';
import 'services/auth_service.dart';
import 'pages/login_page.dart';
import 'pages/home_page.dart';

void main() {
  runApp(
    MultiProvider(
      providers: [
        ChangeNotifierProvider(create: (_) => AuthService()),
        Provider(create: (_) => ApiService()),
      ],
      child: const MengMianApp(),
    ),
  );
}

class MengMianApp extends StatelessWidget {
  const MengMianApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: '梦眠',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        brightness: Brightness.dark,
        primaryColor: const Color(0xFF6C63FF),
        scaffoldBackgroundColor: const Color(0xFF0F0F1A),
        cardColor: const Color(0xFF16213E),
        fontFamily: 'PingFang SC',
      ),
      home: Consumer<AuthService>(
        builder: (_, auth, __) => auth.isLoggedIn ? const HomePage() : const LoginPage(),
      ),
    );
  }
}
