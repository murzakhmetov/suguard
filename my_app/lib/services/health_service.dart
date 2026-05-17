import 'dart:math';
import 'package:my_app/models/health_data.dart';
import 'package:my_app/services/app_settings.dart';
import 'package:uuid/uuid.dart';

class HealthService {
  static final _random = Random();
  static const _uuid = Uuid();

  static List<HealthData> generateData({
    required DateTime start,
    required DateTime end,
    Duration interval = const Duration(minutes: 30),
  }) {
    final data = <HealthData>[];
    var current = start;

    final baseSpo2 = 96.0 + _random.nextDouble() * 2;
    final basePulse = 68.0 + _random.nextDouble() * 10;
    final baseGlucose = 95.0 + _random.nextDouble() * 20;

    while (current.isBefore(end)) {
      final hour = current.hour;

      final sleepFactor = (hour >= 23 || hour < 6) ? 1.0 : 0.0;
      final mealFactor = (hour == 8 || hour == 13 || hour == 19) ? 1.0 : 0.0;
      final activityFactor =
          (hour >= 7 && hour < 9) || (hour >= 17 && hour < 19) ? 1.0 : 0.0;

      final spo2 = (baseSpo2 -
              sleepFactor * 1 +
              _random.nextDouble() * 2 -
              1)
          .clamp(90.0, 100.0);

      final pulse = (basePulse +
              activityFactor * 20 -
              sleepFactor * 10 +
              _random.nextDouble() * 8 -
              4)
          .clamp(45.0, 140.0);

      final glucose = (baseGlucose +
              mealFactor * 40 +
              _random.nextDouble() * 15 -
              7.5 -
              activityFactor * 10)
          .clamp(60.0, 250.0);

      data.add(HealthData(
        id: _uuid.v4(),
        timestamp: current,
        spo2: double.parse(spo2.toStringAsFixed(1)),
        pulse: double.parse(pulse.toStringAsFixed(0)),
        glucose: double.parse(glucose.toStringAsFixed(1)),
      ));

      current = current.add(interval);
    }

    return data;
  }

  static double calculateDiabetesRisk(List<HealthData> data) {
    if (data.isEmpty) return 0;

    final avgGlucose =
        data.map((d) => d.glucose).reduce((a, b) => a + b) / data.length;

    final glucoseMean = avgGlucose;
    final glucoseVariance = data
            .map((d) => (d.glucose - glucoseMean) * (d.glucose - glucoseMean))
            .reduce((a, b) => a + b) /
        data.length;
    final glucoseStdDev = sqrt(glucoseVariance);

    final highGlucoseCount = data.where((d) => d.glucose > 140).length;
    final highGlucosePercent = (highGlucoseCount / data.length) * 100;

    final avgPulse =
        data.map((d) => d.pulse).reduce((a, b) => a + b) / data.length;

    final avgSpo2 =
        data.map((d) => d.spo2).reduce((a, b) => a + b) / data.length;

    double risk = 0;

    risk += ((avgGlucose - 70) / 130).clamp(0, 1) * 40;

    risk += (glucoseStdDev / 30).clamp(0, 1) * 25;

    risk += (highGlucosePercent / 100).clamp(0, 1) * 20;

    if (avgPulse > 100) {
      risk += 10;
    } else if (avgPulse > 90) {
      risk += 7;
    } else if (avgPulse > 80) {
      risk += 4;
    }

    if (avgSpo2 < 94) {
      risk += 5;
    } else if (avgSpo2 < 96) {
      risk += 2;
    }

    return risk.clamp(0, 100);
  }

  static String riskLabel(double risk, [bool russian = true]) {
    if (russian) {
      if (risk < 20) return 'НИЗКИЙ РИСК';
      if (risk < 40) return 'УМЕРЕННЫЙ РИСК';
      if (risk < 60) return 'ПОВЫШЕННЫЙ РИСК';
      if (risk < 80) return 'ВЫСОКИЙ РИСК';
      return 'ОЧЕНЬ ВЫСОКИЙ РИСК';
    }
    if (risk < 20) return 'LOW RISK';
    if (risk < 40) return 'MODERATE RISK';
    if (risk < 60) return 'ELEVATED RISK';
    if (risk < 80) return 'HIGH RISK';
    return 'VERY HIGH RISK';
  }

  static Map<String, Map<String, double>> getStats(List<HealthData> data) {
    if (data.isEmpty) {
      return {
        'spo2': {'avg': 0, 'min': 0, 'max': 0},
        'pulse': {'avg': 0, 'min': 0, 'max': 0},
        'glucose': {'avg': 0, 'min': 0, 'max': 0},
      };
    }

    double avg(List<double> values) =>
        values.reduce((a, b) => a + b) / values.length;

    final spo2Values = data.map((d) => d.spo2).toList();
    final pulseValues = data.map((d) => d.pulse).toList();
    final glucoseValues = data.map((d) => d.glucose).toList();

    return {
      'spo2': {
        'avg': double.parse(avg(spo2Values).toStringAsFixed(1)),
        'min': spo2Values.reduce(min),
        'max': spo2Values.reduce(max),
      },
      'pulse': {
        'avg': double.parse(avg(pulseValues).toStringAsFixed(0)),
        'min': pulseValues.reduce(min),
        'max': pulseValues.reduce(max),
      },
      'glucose': {
        'avg': double.parse(avg(glucoseValues).toStringAsFixed(1)),
        'min': glucoseValues.reduce(min),
        'max': glucoseValues.reduce(max),
      },
    };
  }

  static String buildStatsSummary(List<HealthData> data) {
    if (data.isEmpty) return 'No health data available yet.';

    final stats = getStats(data);
    final risk = calculateDiabetesRisk(data);
    final s = AppSettings();

    final buf = StringBuffer();
    buf.writeln('User Health Statistics (last ${data.length} readings):');

    if (s.height != null) buf.writeln('- Height: ${s.height!.toStringAsFixed(0)} cm');
    if (s.weight != null) buf.writeln('- Weight: ${s.weight!.toStringAsFixed(0)} kg');
    if (s.age != null) buf.writeln('- Age: ${s.age} years');
    if (s.bmi != null) buf.writeln('- BMI: ${s.bmi!.toStringAsFixed(1)}');

    final gAvg = s.useMmol ? (stats['glucose']!['avg']! / 18.0).toStringAsFixed(1) : stats['glucose']!['avg']!.toStringAsFixed(1);
    final gMin = s.useMmol ? (stats['glucose']!['min']! / 18.0).toStringAsFixed(1) : stats['glucose']!['min']!.toStringAsFixed(1);
    final gMax = s.useMmol ? (stats['glucose']!['max']! / 18.0).toStringAsFixed(1) : stats['glucose']!['max']!.toStringAsFixed(1);
    final gUnit = s.useMmol ? 'mmol/L' : 'mg/dL';

    buf.writeln('- SpO2: avg ${stats['spo2']!['avg']}%, min ${stats['spo2']!['min']}%, max ${stats['spo2']!['max']}%');
    buf.writeln('- Pulse: avg ${stats['pulse']!['avg']} bpm, min ${stats['pulse']!['min']} bpm, max ${stats['pulse']!['max']} bpm');
    buf.writeln('- Blood Glucose: avg $gAvg $gUnit, min $gMin $gUnit, max $gMax $gUnit');
    buf.writeln('- Diabetes Risk Score: ${risk.toStringAsFixed(1)}% (${riskLabel(risk)})');
    buf.writeln('- Data period: ${data.first.timestamp.toIso8601String()} to ${data.last.timestamp.toIso8601String()}');

    return buf.toString();
  }
}
