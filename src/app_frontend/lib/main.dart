import 'package:material_ui/material_ui.dart';

import 'screens/login_screen.dart';
import 'logic/models.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await DateStorage.instance.init();

  runApp(const MainApp());
}

class MainApp extends StatelessWidget {
  const MainApp({super.key});

  @override
  Widget build(BuildContext context) {
    return const MaterialApp(
      debugShowCheckedModeBanner: false,
      home: Scaffold(resizeToAvoidBottomInset: false, body: LoginScreen()),
    );
  }
}
