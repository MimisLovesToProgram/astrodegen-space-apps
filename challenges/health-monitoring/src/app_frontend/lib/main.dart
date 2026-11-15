import 'package:app_frontend/screens/history_screen.dart';
import 'package:app_frontend/screens/status_screen.dart';
import 'package:flutter/material.dart';

import 'screens/login_screen.dart';
import 'package:app_frontend/screens/checkin_screen.dart';
import 'logic/models.dart';

void main() async {
  await DateStorage.instance.init();

  runApp(const MainApp());
}

class MainApp extends StatelessWidget {
  const MainApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      theme: ThemeData(
        fontFamily: 'Firjar',
      ),
      debugShowCheckedModeBanner: false,
      home: Scaffold(
        resizeToAvoidBottomInset: false,
        body: LoginScreen()
      ),
    );
  }
}
