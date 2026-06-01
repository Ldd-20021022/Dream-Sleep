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
    const primaryColor = Color(0xFF5B6ABF);
    return MaterialApp(
      title: '梦眠阁',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        brightness: Brightness.dark,
        primaryColor: primaryColor,
        colorScheme: ColorScheme.dark(
          primary: primaryColor,
          secondary: const Color(0xFF3DAAA0),
          surface: const Color(0xFF161622),
          error: const Color(0xFFC4544A),
        ),
        scaffoldBackgroundColor: const Color(0xFF0A0A12),
        cardColor: const Color(0xFF161622),
        cardTheme: CardThemeData(
          color: const Color(0xFF161622),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
          margin: const EdgeInsets.only(bottom: 14),
        ),
        appBarTheme: const AppBarTheme(
          backgroundColor: Color(0xFF0A0A12),
          elevation: 0,
          centerTitle: true,
          titleTextStyle: TextStyle(color: Color(0xFFE4E4EC), fontSize: 18, fontWeight: FontWeight.w600),
        ),
        bottomNavigationBarTheme: const BottomNavigationBarThemeData(
          backgroundColor: Color(0xFF0E0E18),
          selectedItemColor: primaryColor,
          unselectedItemColor: Color(0xFF585870),
          type: BottomNavigationBarType.fixed,
        ),
        fontFamily: 'PingFang SC',
      ),
      home: Consumer<AuthService>(
        builder: (_, auth, __) => auth.isLoggedIn ? const HomePage() : const LoginPage(),
      ),
    );
  }
}
