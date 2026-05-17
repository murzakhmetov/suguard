import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class AppTheme {
  static const Color background = Color(0xFF0A0A0A);
  static const Color surface = Color(0xFF1A1A1A);
  static const Color surfaceLight = Color(0xFF2A2A2A);
  static const Color cardBorder = Color(0xFF333333);

  static const Color accent = Color(0xFF00F5D4);
  static const Color accentDim = Color(0xFF00C4AA);

  static const Color pulseColor = Color(0xFFFF006E);
  static const Color spo2Color = Color(0xFF3A86FF);
  static const Color glucoseColor = Color(0xFFFFB703);

  static const Color riskLow = Color(0xFF00F5D4);
  static const Color riskMedium = Color(0xFFFFB703);
  static const Color riskHigh = Color(0xFFFF006E);

  static const Color textPrimary = Color(0xFFFFFFFF);
  static const Color textSecondary = Color(0xFF8A8A8A);
  static const Color textTertiary = Color(0xFF555555);

  static ThemeData get darkTheme {
    return ThemeData(
      brightness: Brightness.dark,
      scaffoldBackgroundColor: background,
      primaryColor: accent,
      colorScheme: const ColorScheme.dark(
        primary: accent,
        secondary: accentDim,
        surface: surface,
        onPrimary: Color(0xFF000000),
        onSecondary: Color(0xFF000000),
        onSurface: textPrimary,
      ),
      textTheme: GoogleFonts.interTextTheme(
        const TextTheme(
          displayLarge: TextStyle(
              color: textPrimary,
              fontSize: 48,
              fontWeight: FontWeight.w800,
              letterSpacing: -1.5),
          displayMedium: TextStyle(
              color: textPrimary,
              fontSize: 36,
              fontWeight: FontWeight.w700,
              letterSpacing: -1),
          headlineLarge: TextStyle(
              color: textPrimary,
              fontSize: 28,
              fontWeight: FontWeight.w700,
              letterSpacing: -0.5),
          headlineMedium: TextStyle(
              color: textPrimary,
              fontSize: 22,
              fontWeight: FontWeight.w600),
          titleLarge: TextStyle(
              color: textPrimary,
              fontSize: 18,
              fontWeight: FontWeight.w600),
          titleMedium: TextStyle(
              color: textSecondary,
              fontSize: 14,
              fontWeight: FontWeight.w500),
          bodyLarge: TextStyle(color: textPrimary, fontSize: 16),
          bodyMedium: TextStyle(color: textSecondary, fontSize: 14),
          bodySmall: TextStyle(color: textTertiary, fontSize: 12),
          labelLarge: TextStyle(
              color: accent,
              fontSize: 14,
              fontWeight: FontWeight.w700,
              letterSpacing: 1.2),
        ),
      ),
      appBarTheme: const AppBarTheme(
        backgroundColor: background,
        elevation: 0,
        centerTitle: true,
        titleTextStyle: TextStyle(
            color: textPrimary,
            fontSize: 18,
            fontWeight: FontWeight.w600),
        iconTheme: IconThemeData(color: textPrimary),
      ),
      bottomNavigationBarTheme: const BottomNavigationBarThemeData(
        backgroundColor: surface,
        selectedItemColor: accent,
        unselectedItemColor: textTertiary,
        type: BottomNavigationBarType.fixed,
        showUnselectedLabels: true,
        selectedLabelStyle:
            TextStyle(fontSize: 11, fontWeight: FontWeight.w600),
        unselectedLabelStyle: TextStyle(fontSize: 11),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: surface,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(16),
          borderSide: const BorderSide(color: cardBorder),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(16),
          borderSide: const BorderSide(color: cardBorder),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(16),
          borderSide: const BorderSide(color: accent, width: 2),
        ),
        hintStyle: const TextStyle(color: textTertiary),
        contentPadding:
            const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: accent,
          foregroundColor: Colors.black,
          minimumSize: const Size(double.infinity, 56),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(16),
          ),
          textStyle:
              const TextStyle(fontSize: 16, fontWeight: FontWeight.w700),
        ),
      ),
      cardTheme: CardThemeData(
        color: surface,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(20),
          side: const BorderSide(color: cardBorder, width: 0.5),
        ),
      ),
    );
  }

  static Color riskColor(double risk) {
    if (risk < 30) return riskLow;
    if (risk < 60) return riskMedium;
    return riskHigh;
  }

  static LinearGradient get accentGradient => const LinearGradient(
        colors: [accent, Color(0xFF7B61FF)],
        begin: Alignment.topLeft,
        end: Alignment.bottomRight,
      );
}
