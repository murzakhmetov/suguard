import 'package:flutter/material.dart';
import 'package:fl_chart/fl_chart.dart';
import 'package:intl/intl.dart';
import 'package:f_app/models/health_data.dart';
import 'package:f_app/theme/app_theme.dart';
import 'package:f_app/services/app_settings.dart';

enum ChartPeriod { day, week, month }

class HealthChart extends StatelessWidget {
  final List<HealthData> data;
  final String metricType; 
  final Color color;
  final ChartPeriod period;

  const HealthChart({
    super.key,
    required this.data,
    required this.metricType,
    required this.color,
    required this.period,
  });

  double _getValue(HealthData d) {
    switch (metricType) {
      case 'spo2':
        return d.spo2;
      case 'pulse':
        return d.pulse;
      case 'glucose':
        final s = AppSettings();
        return s.useMmol ? d.glucose / 18.0 : d.glucose;
      default:
        return 0;
    }
  }

  @override
  Widget build(BuildContext context) {
    if (data.isEmpty) {
      return const Center(
        child: Text('No data available', style: TextStyle(color: AppTheme.textSecondary)),
      );
    }

    final aggregated = _aggregateData();

    final values = aggregated.map((e) => e.value).toList();
    final minY = (values.reduce((a, b) => a < b ? a : b) - 5).clamp(0.0, double.infinity);
    final maxY = values.reduce((a, b) => a > b ? a : b) + 5;

    return Padding(
      padding: const EdgeInsets.only(right: 16, top: 16),
      child: LineChart(
        LineChartData(
          gridData: FlGridData(
            show: true,
            drawVerticalLine: false,
            horizontalInterval: _getInterval(minY, maxY),
            getDrawingHorizontalLine: (value) => FlLine(
              color: AppTheme.cardBorder,
              strokeWidth: 0.5,
            ),
          ),
          titlesData: FlTitlesData(
            topTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
            rightTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
            leftTitles: AxisTitles(
              sideTitles: SideTitles(
                showTitles: true,
                reservedSize: 45,
                interval: _getInterval(minY, maxY),
                getTitlesWidget: (value, meta) => Padding(
                  padding: const EdgeInsets.only(right: 8),
                  child: Text(
                    value.toInt().toString(),
                    style: const TextStyle(
                      color: AppTheme.textTertiary,
                      fontSize: 11,
                    ),
                  ),
                ),
              ),
            ),
            bottomTitles: AxisTitles(
              sideTitles: SideTitles(
                showTitles: true,
                reservedSize: 30,
                interval: _getBottomInterval(aggregated.length),
                getTitlesWidget: (value, meta) {
                  final idx = value.toInt();
                  if (idx < 0 || idx >= aggregated.length) return const SizedBox();
                  return Padding(
                    padding: const EdgeInsets.only(top: 8),
                    child: Text(
                      aggregated[idx].label,
                      style: const TextStyle(
                        color: AppTheme.textTertiary,
                        fontSize: 10,
                      ),
                    ),
                  );
                },
              ),
            ),
          ),
          borderData: FlBorderData(show: false),
          lineTouchData: LineTouchData(
            touchTooltipData: LineTouchTooltipData(
              getTooltipColor: (_) => AppTheme.surfaceLight,
              tooltipRoundedRadius: 12,
              getTooltipItems: (touchedSpots) {
                return touchedSpots.map((spot) {
                  return LineTooltipItem(
                    spot.y.toStringAsFixed(1),
                    TextStyle(
                      color: color,
                      fontWeight: FontWeight.w700,
                      fontSize: 14,
                    ),
                  );
                }).toList();
              },
            ),
          ),
          lineBarsData: [
            LineChartBarData(
              spots: aggregated
                  .asMap()
                  .entries
                  .map((e) => FlSpot(e.key.toDouble(), e.value.value))
                  .toList(),
              isCurved: true,
              curveSmoothness: 0.3,
              color: color,
              barWidth: 3,
              isStrokeCapRound: true,
              dotData: FlDotData(
                show: period == ChartPeriod.day,
                getDotPainter: (spot, percent, bar, index) =>
                    FlDotCirclePainter(
                  radius: 3,
                  color: color,
                  strokeWidth: 2,
                  strokeColor: AppTheme.surface,
                ),
              ),
              belowBarData: BarAreaData(
                show: true,
                gradient: LinearGradient(
                  colors: [
                    color.withValues(alpha: 0.3),
                    color.withValues(alpha: 0.0),
                  ],
                  begin: Alignment.topCenter,
                  end: Alignment.bottomCenter,
                ),
              ),
            ),
          ],
          minY: minY,
          maxY: maxY,
        ),
        duration: const Duration(milliseconds: 400),
        curve: Curves.easeInOut,
      ),
    );
  }

  List<_ChartPoint> _aggregateData() {
    if (data.isEmpty) return [];

    switch (period) {
      case ChartPeriod.day:
        final Map<int, List<double>> byHour = {};
        for (final d in data) {
          byHour.putIfAbsent(d.timestamp.hour, () => []).add(_getValue(d));
        }
        return byHour.entries.map((e) {
          final avg = e.value.reduce((a, b) => a + b) / e.value.length;
          return _ChartPoint(
            label: '${e.key.toString().padLeft(2, '0')}:00',
            value: double.parse(avg.toStringAsFixed(1)),
          );
        }).toList()
          ..sort((a, b) => a.label.compareTo(b.label));

      case ChartPeriod.week:
        final Map<String, List<double>> byDay = {};
        for (final d in data) {
          final key = DateFormat('MM/dd').format(d.timestamp);
          byDay.putIfAbsent(key, () => []).add(_getValue(d));
        }
        return byDay.entries.map((e) {
          final avg = e.value.reduce((a, b) => a + b) / e.value.length;
          return _ChartPoint(
            label: e.key,
            value: double.parse(avg.toStringAsFixed(1)),
          );
        }).toList();

      case ChartPeriod.month:
        final Map<String, List<double>> byDay = {};
        for (final d in data) {
          final key = DateFormat('dd').format(d.timestamp);
          byDay.putIfAbsent(key, () => []).add(_getValue(d));
        }
        return byDay.entries.map((e) {
          final avg = e.value.reduce((a, b) => a + b) / e.value.length;
          return _ChartPoint(
            label: e.key,
            value: double.parse(avg.toStringAsFixed(1)),
          );
        }).toList();
    }
  }

  double _getInterval(double min, double max) {
    final range = max - min;
    if (range <= 20) return 5;
    if (range <= 50) return 10;
    if (range <= 100) return 20;
    return 50;
  }

  double _getBottomInterval(int count) {
    if (count <= 7) return 1;
    if (count <= 14) return 2;
    if (count <= 24) return 3;
    return (count / 8).ceilToDouble();
  }
}

class _ChartPoint {
  final String label;
  final double value;
  _ChartPoint({required this.label, required this.value});
}
