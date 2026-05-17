import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:my_app/theme/app_theme.dart';
import 'package:my_app/services/app_settings.dart';
import 'package:my_app/screens/splash_screen.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await dotenv.load(fileName: ".env");
  SystemChrome.setSystemUIOverlayStyle(const SystemUiOverlayStyle(
    statusBarColor: Colors.transparent,
    statusBarIconBrightness: Brightness.light,
    systemNavigationBarColor: AppTheme.surface,
    systemNavigationBarIconBrightness: Brightness.light,
  ));
  await AppSettings().load();
  runApp(const SuGuardApp());
}

class SuGuardApp extends StatelessWidget {
  const SuGuardApp({super.key});

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: AppSettings(),
      builder: (context, _) {
        return MaterialApp(
          title: 'SuGuard',
          debugShowCheckedModeBanner: false,
          theme: AppTheme.darkTheme,
          home: const SplashScreen(),
        );
      },
    );
  }
}
