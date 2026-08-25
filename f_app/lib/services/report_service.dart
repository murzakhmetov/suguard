import 'dart:io';
import 'package:flutter/services.dart' show rootBundle;
import 'package:intl/intl.dart';
import 'package:path_provider/path_provider.dart';
import 'package:share_plus/share_plus.dart';
import 'package:pdf/pdf.dart';
import 'package:pdf/widgets.dart' as pw;
import 'package:printing/printing.dart';
import 'package:f_app/models/health_data.dart';
import 'package:f_app/services/health_service.dart';
import 'package:f_app/services/app_settings.dart';
import 'package:f_app/services/firebase_service.dart';

class ReportService {
  static Future<void> shareReport(List<HealthData> data) async {
    final content = _buildReport(data);
    final dateStr = DateFormat('yyyy-MM-dd_HH-mm').format(DateTime.now());
    
    final fileName = 'SuGuard_Report_$dateStr.txt';
    final tempDir = await getTemporaryDirectory();
    final file = File('${tempDir.path}/$fileName');
    await file.writeAsString(content);

    await Share.shareXFiles(
      [XFile(file.path)],
      subject: AppSettings().isRussian
          ? 'Медицинский отчёт SuGuard'
          : 'SuGuard Medical Report',
    );
  }

  static String _buildReport(List<HealthData> data) {
    final s = AppSettings();
    final isRu = s.isRussian;
    final df = DateFormat('dd.MM.yyyy HH:mm');
    final now = DateTime.now();
    final stats = HealthService.getStats(data);
    final risk = HealthService.calculateDiabetesRisk(data);
    final name = FirebaseService.displayName ?? (isRu ? 'Не указано' : 'N/A');
    const d = '════════════════════════════════════════════════════';
    const s1 = '────────────────────────────────────────────────────';

    final b = StringBuffer();

    b.writeln(d);
    b.writeln(isRu ? '   МЕДИЦИНСКИЙ ОТЧЁТ SuGuard' : '   SuGuard MEDICAL REPORT');
    b.writeln(d);
    b.writeln();

    b.writeln(isRu ? '▌ ДАННЫЕ ПАЦИЕНТА' : '▌ PATIENT INFO');
    b.writeln(s1);
    b.writeln('  ${isRu ? "Имя" : "Name"}: $name');
    b.writeln('  Email: ${FirebaseService.email ?? "N/A"}');
    if (s.height != null) b.writeln('  ${isRu ? "Рост" : "Height"}: ${s.height!.toStringAsFixed(0)} ${isRu ? "см" : "cm"}');
    if (s.weight != null) b.writeln('  ${isRu ? "Вес" : "Weight"}: ${s.weight!.toStringAsFixed(0)} ${isRu ? "кг" : "kg"}');
    if (s.age != null) b.writeln('  ${isRu ? "Возраст" : "Age"}: ${s.age} ${isRu ? "лет" : "years"}');
    if (s.bmi != null) b.writeln('  ${isRu ? "ИМТ" : "BMI"}: ${s.bmi!.toStringAsFixed(1)}');
    b.writeln('  ${isRu ? "Дата отчёта" : "Report date"}: ${df.format(now)}');
    b.writeln();

    b.writeln(isRu ? '▌ ПЕРИОД ДАННЫХ' : '▌ DATA PERIOD');
    b.writeln(s1);
    if (data.isNotEmpty) {
      b.writeln('  ${isRu ? "С" : "From"}: ${df.format(data.first.timestamp)}');
      b.writeln('  ${isRu ? "По" : "To"}:   ${df.format(data.last.timestamp)}');
      b.writeln('  ${isRu ? "Всего измерений" : "Total readings"}: ${data.length}');
    }
    b.writeln();

    b.writeln(isRu ? '▌ КИСЛОРОД (SpO2)' : '▌ OXYGEN (SpO2)');
    b.writeln(s1);
    b.writeln('  ${isRu ? "Среднее" : "Average"}:  ${stats["spo2"]!["avg"]}%');
    b.writeln('  ${isRu ? "Минимум" : "Minimum"}:  ${stats["spo2"]!["min"]}%');
    b.writeln('  ${isRu ? "Максимум" : "Maximum"}: ${stats["spo2"]!["max"]}%');
    b.writeln();

    b.writeln(isRu ? '▌ ПУЛЬС' : '▌ PULSE');
    b.writeln(s1);
    b.writeln('  ${isRu ? "Среднее" : "Average"}:  ${stats["pulse"]!["avg"]?.toStringAsFixed(0)} ${isRu ? "уд/мин" : "bpm"}');
    b.writeln('  ${isRu ? "Минимум" : "Minimum"}:  ${stats["pulse"]!["min"]?.toStringAsFixed(0)} ${isRu ? "уд/мин" : "bpm"}');
    b.writeln('  ${isRu ? "Максимум" : "Maximum"}: ${stats["pulse"]!["max"]?.toStringAsFixed(0)} ${isRu ? "уд/мин" : "bpm"}');
    b.writeln();

    final gUnit = s.useMmol ? (isRu ? 'ммоль/л' : 'mmol/L') : (isRu ? 'мг/дл' : 'mg/dL');
    final gAvg = s.useMmol ? (stats['glucose']!['avg']! / 18.0).toStringAsFixed(1) : stats['glucose']!['avg'];
    final gMin = s.useMmol ? (stats['glucose']!['min']! / 18.0).toStringAsFixed(1) : stats['glucose']!['min'];
    final gMax = s.useMmol ? (stats['glucose']!['max']! / 18.0).toStringAsFixed(1) : stats['glucose']!['max'];

    b.writeln(isRu ? '▌ ГЛЮКОЗА В КРОВИ' : '▌ BLOOD GLUCOSE');
    b.writeln(s1);
    b.writeln('  ${isRu ? "Среднее" : "Average"}:  $gAvg $gUnit');
    b.writeln('  ${isRu ? "Минимум" : "Minimum"}:  $gMin $gUnit');
    b.writeln('  ${isRu ? "Максимум" : "Maximum"}: $gMax $gUnit');
    b.writeln();

    b.writeln(isRu ? '▌ РИСК ДИАБЕТА' : '▌ DIABETES RISK');
    b.writeln(s1);
    b.writeln('  ${isRu ? "Оценка" : "Score"}: ${risk.toStringAsFixed(1)}%');
    b.writeln('  ${isRu ? "Уровень" : "Level"}: ${HealthService.riskLabel(risk, s.isRussian)}');
    b.writeln();

    b.writeln(isRu ? '▌ ДАННЫЕ ПО ДНЯМ (7 дней)' : '▌ DAILY BREAKDOWN (7 days)');
    b.writeln(s1);
    final dayFmt = DateFormat('dd.MM');
    final weekAgo = now.subtract(const Duration(days: 7));
    for (int i = 0; i < 7; i++) {
      final day = weekAgo.add(Duration(days: i + 1));
      final dd = data.where((x) =>
          x.timestamp.year == day.year &&
          x.timestamp.month == day.month &&
          x.timestamp.day == day.day).toList();
      if (dd.isEmpty) continue;
      final ds = HealthService.getStats(dd);
      final dayGAvg = s.useMmol ? (ds["glucose"]!["avg"]! / 18.0).toStringAsFixed(1) : ds["glucose"]!["avg"];
      b.writeln('  ${dayFmt.format(day)}: '
          'SpO2 ${ds["spo2"]!["avg"]}% | '
          '${isRu ? "Пульс" : "Pulse"} ${ds["pulse"]!["avg"]?.toStringAsFixed(0)} | '
          '${isRu ? "Глюкоза" : "Glucose"} $dayGAvg $gUnit');
    }
    b.writeln();

    b.writeln(d);
    b.writeln(isRu
        ? '  Данные предоставлены устройством SuGuard.'
        : '  Data provided by SuGuard device.');
    b.writeln(isRu
        ? '  Не является медицинским диагнозом.'
        : '  Not a medical diagnosis.');
    b.writeln(d);

    return b.toString();
  }
}
