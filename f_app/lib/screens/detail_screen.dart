import 'package:flutter/material.dart';
import 'package:f_app/theme/app_theme.dart';
import 'package:f_app/models/health_data.dart';
import 'package:f_app/services/health_service.dart';
import 'package:f_app/services/app_settings.dart';
import 'package:f_app/widgets/health_chart.dart';

class DetailScreen extends StatefulWidget {
  final String title;
  final String metricType;
  final Color color;
  final String unit;
  final IconData icon;
  final List<HealthData> allData;

  const DetailScreen({
    super.key,
    required this.title,
    required this.metricType,
    required this.color,
    required this.unit,
    required this.icon,
    required this.allData,
  });

  @override
  State<DetailScreen> createState() => _DetailScreenState();
}

class _DetailScreenState extends State<DetailScreen> {
  int _selectedPeriod = 0; 
  final _s = AppSettings();

  String _tr(String k) => _s.tr(k);

  List<HealthData> get _filteredData {
    final now = DateTime.now();
    final cutoff = switch (_selectedPeriod) {
      0 => now.subtract(const Duration(days: 1)),
      1 => now.subtract(const Duration(days: 7)),
      _ => now.subtract(const Duration(days: 30)),
    };
    return widget.allData.where((d) => d.timestamp.isAfter(cutoff)).toList();
  }

  @override
  Widget build(BuildContext context) {
    final data = _filteredData;
    final stats = HealthService.getStats(data);
    final metricStats = stats[widget.metricType] ??
        {'avg': 0.0, 'min': 0.0, 'max': 0.0};
    
    final isMmol = widget.metricType == 'glucose' && _s.useMmol;
    final dAvg = isMmol ? (metricStats['avg']! / 18.0) : metricStats['avg']!;
    final dMin = isMmol ? (metricStats['min']! / 18.0) : metricStats['min']!;
    final dMax = isMmol ? (metricStats['max']! / 18.0) : metricStats['max']!;

    final periods = [_tr('day'), _tr('week'), _tr('month')];

    return Scaffold(
      backgroundColor: AppTheme.background,
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        title: Text(widget.title),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios, size: 20),
          onPressed: () => Navigator.pop(context),
        ),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              padding: const EdgeInsets.all(4),
              decoration: BoxDecoration(
                color: AppTheme.surface,
                borderRadius: BorderRadius.circular(14),
              ),
              child: Row(
                children: List.generate(3, (i) {
                  final selected = _selectedPeriod == i;
                  return Expanded(
                    child: GestureDetector(
                      onTap: () => setState(() => _selectedPeriod = i),
                      child: Container(
                        padding: const EdgeInsets.symmetric(vertical: 10),
                        decoration: BoxDecoration(
                          color: selected ? AppTheme.accent : Colors.transparent,
                          borderRadius: BorderRadius.circular(10),
                        ),
                        child: Center(
                          child: Text(
                            periods[i],
                            style: TextStyle(
                              color: selected ? Colors.black : AppTheme.textSecondary,
                              fontSize: 13,
                              fontWeight: selected ? FontWeight.w700 : FontWeight.w500,
                            ),
                          ),
                        ),
                      ),
                    ),
                  );
                }),
              ),
            ),
            const SizedBox(height: 24),

            Container(
              height: 280,
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: AppTheme.surface,
                borderRadius: BorderRadius.circular(20),
                border: Border.all(color: AppTheme.cardBorder, width: 0.5),
              ),
              child: HealthChart(
                data: data,
                metricType: widget.metricType,
                color: widget.color,
                period: ChartPeriod.values[_selectedPeriod],
              ),
            ),
            const SizedBox(height: 24),

            Text(
              _tr('statistics'),
              style: const TextStyle(
                color: AppTheme.textSecondary,
                fontSize: 11,
                fontWeight: FontWeight.w600,
                letterSpacing: 2,
              ),
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                _statCard(_tr('average'),
                    dAvg.toStringAsFixed(1), widget.color),
                const SizedBox(width: 12),
                _statCard(_tr('minimum'),
                    dMin.toStringAsFixed(1), AppTheme.spo2Color),
                const SizedBox(width: 12),
                _statCard(_tr('maximum'),
                    dMax.toStringAsFixed(1), AppTheme.pulseColor),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _statCard(String label, String value, Color color) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: AppTheme.surface,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: AppTheme.cardBorder, width: 0.5),
        ),
        child: Column(
          children: [
            Text(
              value,
              style: TextStyle(
                color: color,
                fontSize: 20,
                fontWeight: FontWeight.w800,
              ),
            ),
            const SizedBox(height: 4),
            Text(
              widget.unit,
              style: const TextStyle(color: AppTheme.textTertiary, fontSize: 11),
            ),
            const SizedBox(height: 4),
            Text(
              label,
              style: const TextStyle(color: AppTheme.textSecondary, fontSize: 11),
            ),
          ],
        ),
      ),
    );
  }
}
