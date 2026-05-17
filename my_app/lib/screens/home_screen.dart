import 'dart:async';

import 'package:flutter/material.dart';
import 'package:my_app/theme/app_theme.dart';
import 'package:my_app/models/health_data.dart';
import 'package:my_app/services/firebase_service.dart';
import 'package:my_app/services/health_service.dart';
import 'package:my_app/services/app_settings.dart';
import 'package:my_app/widgets/metric_card.dart';
import 'package:my_app/widgets/risk_gauge.dart';
import 'package:my_app/screens/detail_screen.dart';
import 'package:my_app/screens/diabetes_risk_screen.dart';
import 'package:my_app/screens/ai_chat_screen.dart';
import 'package:my_app/screens/settings_screen.dart';
import 'package:my_app/screens/food_tracker_screen.dart';
import 'package:my_app/services/report_service.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  int _currentIndex = 0;
  List<HealthData> _allData = [];
  List<HealthData> _todayData = [];
  bool _loading = true;
  final _s = AppSettings();
  Timer? _realtimeTimer;


  double? _liveGlucoseMgdl;
  double? _liveGlucoseMmol;
  double? _livePulse;
  double? _liveSpo2;

  String _tr(String k) => _s.tr(k);

  @override
  void initState() {
    super.initState();
    _s.addListener(_onSettingsChanged);
    _loadData().then((_) => _startRealtimePolling());
  }

  @override
  void dispose() {
    _realtimeTimer?.cancel();
    _s.removeListener(_onSettingsChanged);
    super.dispose();
  }

  void _onSettingsChanged() {
    if (mounted) setState(() {});
  }



  void _startRealtimePolling() {
    _realtimeTimer?.cancel();

    _realtimeTimer = Timer.periodic(const Duration(seconds: 5), (timer) async {
      if (!mounted) return;

      final liveData = await FirebaseService.fetchLiveData();
      if (liveData != null && mounted) {
        setState(() {
          _liveGlucoseMgdl = (liveData['glucose_mgdl'] as num).toDouble();
          _liveGlucoseMmol = (liveData['glucose_mmol'] as num).toDouble();
          _livePulse = (liveData['pulse'] as num).toDouble();
          _liveSpo2 = (liveData['spo2'] as num).toDouble();
        });
      }
      
    });
  }

  Future<void> _downloadReport() async {
    ReportService.shareReport(_allData);
  }

  Future<void> _loadData() async {
    setState(() => _loading = true);
    
    final now = DateTime.now();
    _allData = HealthService.generateData(
      start: now.subtract(const Duration(days: 30)),
      end: now,
    );
    final todayStart = DateTime(now.year, now.month, now.day);
    _todayData = _allData
        .where((d) => d.timestamp.isAfter(todayStart))
        .toList();
    
    final liveData = await FirebaseService.fetchLiveData();
    if (liveData != null) {
      _liveGlucoseMgdl = (liveData['glucose_mgdl'] as num).toDouble();
      _liveGlucoseMmol = (liveData['glucose_mmol'] as num).toDouble();
      _livePulse = (liveData['pulse'] as num).toDouble();
      _liveSpo2 = (liveData['spo2'] as num).toDouble();
    } else {
      _liveSpo2 = 98.0;
      _livePulse = 87.0;
      _liveGlucoseMmol = 6.7;
      _liveGlucoseMgdl = 120.0;
    }

    if (mounted) setState(() => _loading = false);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.background,
      body: IndexedStack(
        index: _currentIndex,
        children: [
          _buildDashboard(),
          _buildCharts(),
          AiChatScreen(healthData: _allData),
          const FoodTrackerScreen(),
          const SettingsScreen(),
        ],
      ),
      bottomNavigationBar: Container(
        decoration: const BoxDecoration(
          border: Border(
            top: BorderSide(color: AppTheme.cardBorder, width: 0.5),
          ),
        ),
        child: BottomNavigationBar(
          currentIndex: _currentIndex,
          onTap: (i) => setState(() => _currentIndex = i),
          items: [
            BottomNavigationBarItem(
              icon: const Icon(Icons.dashboard_rounded),
              label: _tr('nav_dashboard'),
            ),
            BottomNavigationBarItem(
              icon: const Icon(Icons.show_chart_rounded),
              label: _tr('nav_charts'),
            ),
            BottomNavigationBarItem(
              icon: const Icon(Icons.smart_toy_rounded),
              label: _tr('nav_ai'),
            ),
            BottomNavigationBarItem(
              icon: const Icon(Icons.restaurant_rounded),
              label: _tr('nav_food'),
            ),
            BottomNavigationBarItem(
              icon: const Icon(Icons.settings_rounded),
              label: _tr('nav_settings'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildDashboard() {
    if (_loading) {
      return const Center(
        child: CircularProgressIndicator(color: AppTheme.accent),
      );
    }

    final name = FirebaseService.displayName ?? _tr('nav_dashboard');
    final risk = HealthService.calculateDiabetesRisk(_allData);
    final latest = _todayData.isNotEmpty
        ? _todayData.last
        : (_allData.isNotEmpty ? _allData.last : null);

    return SafeArea(
      child: RefreshIndicator(
        onRefresh: _loadData,
        color: AppTheme.accent,
        child: SingleChildScrollView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: const EdgeInsets.all(20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          '${_tr('hello')}, $name 👋',
                          style: const TextStyle(
                            color: AppTheme.textPrimary,
                            fontSize: 24,
                            fontWeight: FontWeight.w800,
                            letterSpacing: -0.5,
                          ),
                        ),
                        const SizedBox(height: 4),
                        Text(
                          _tr('health_overview'),
                          style: TextStyle(
                            color: AppTheme.textSecondary,
                            fontSize: 14,
                          ),
                        ),
                      ],
                    ),
                  ),
                  Container(
                    width: 44,
                    height: 44,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      color: AppTheme.accent.withValues(alpha: 0.15),
                    ),
                    child: const Icon(
                      Icons.notifications_none_rounded,
                      color: AppTheme.accent,
                      size: 22,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 28),

              if (!_s.isDeviceConnected) ...[
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.symmetric(vertical: 60, horizontal: 24),
                  decoration: BoxDecoration(
                    color: AppTheme.surface,
                    borderRadius: BorderRadius.circular(24),
                    border: Border.all(color: AppTheme.cardBorder, width: 0.5),
                  ),
                  child: Column(
                    children: [
                      Container(
                        padding: const EdgeInsets.all(20),
                        decoration: BoxDecoration(
                          shape: BoxShape.circle,
                          color: AppTheme.textTertiary.withValues(alpha: 0.1),
                        ),
                        child: Icon(
                          Icons.bluetooth_disabled_rounded,
                          color: AppTheme.textTertiary,
                          size: 48,
                        ),
                      ),
                      const SizedBox(height: 20),
                      Text(
                        _tr('no_data'),
                        style: const TextStyle(
                          color: AppTheme.textPrimary,
                          fontSize: 20,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                      const SizedBox(height: 8),
                      Text(
                        _tr('connect_device_hint'),
                        textAlign: TextAlign.center,
                        style: TextStyle(
                          color: AppTheme.textSecondary,
                          fontSize: 14,
                          height: 1.5,
                        ),
                      ),
                    ],
                  ),
                ),
              ],

              if (_s.isDeviceConnected) ...[
                GestureDetector(
                  onTap: () => Navigator.push(
                    context,
                    MaterialPageRoute(
                      builder: (_) => DiabetesRiskScreen(data: _allData),
                    ),
                  ),
                  child: Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(24),
                    decoration: BoxDecoration(
                      color: AppTheme.surface,
                      borderRadius: BorderRadius.circular(24),
                      border:
                          Border.all(color: AppTheme.cardBorder, width: 0.5),
                    ),
                    child: Column(
                      children: [
                        RiskGauge(risk: risk, size: 180),
                        const SizedBox(height: 12),
                        Container(
                          padding: const EdgeInsets.symmetric(
                              horizontal: 16, vertical: 8),
                          decoration: BoxDecoration(
                            color: AppTheme.riskColor(risk)
                                .withValues(alpha: 0.1),
                            borderRadius: BorderRadius.circular(20),
                          ),
                          child: Text(
                            HealthService.riskLabel(risk, _s.isRussian),
                            style: TextStyle(
                              color: AppTheme.riskColor(risk),
                              fontSize: 13,
                              fontWeight: FontWeight.w700,
                              letterSpacing: 1,
                            ),
                          ),
                        ),
                        const SizedBox(height: 8),
                        Row(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            Text(
                              _tr('tap_details'),
                              style: TextStyle(
                                color: AppTheme.textTertiary,
                                fontSize: 12,
                              ),
                            ),
                            const SizedBox(width: 4),
                            Icon(Icons.chevron_right,
                                color: AppTheme.textTertiary, size: 16),
                          ],
                        ),
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: 20),

                if (latest != null) ...[
                  MetricCard(
                    title: _tr('glucose'),
                    value: _s.useMmol
                        ? (_liveGlucoseMmol != null ? _liveGlucoseMmol!.toStringAsFixed(1) : (latest.glucose / 18.0).toStringAsFixed(1))
                        : (_liveGlucoseMgdl != null ? _liveGlucoseMgdl!.toStringAsFixed(0) : latest.glucose.toStringAsFixed(0)),
                    unit: _s.useMmol ? _tr('unit_mmol') : _tr('unit_mgdl'),
                    icon: Icons.bloodtype_rounded,
                    color: AppTheme.glucoseColor,
                    sparklineData: _todayData.map((d) => _s.useMmol ? d.glucose / 18.0 : d.glucose).toList(),
                    onTap: () => Navigator.push(
                      context,
                      MaterialPageRoute(
                        builder: (_) => DetailScreen(
                          title: _tr('blood_glucose'),
                          metricType: 'glucose',
                          color: AppTheme.glucoseColor,
                          unit: _s.useMmol ? _tr('unit_mmol') : _tr('unit_mgdl'),
                          icon: Icons.bloodtype_rounded,
                          allData: _allData,
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      Expanded(
                        child: MetricCard(
                          title: _tr('spo2'),
                          value: _liveSpo2 != null ? _liveSpo2!.toStringAsFixed(0) : latest.spo2.toStringAsFixed(0),
                          unit: '%',
                          icon: Icons.air_rounded,
                          color: AppTheme.spo2Color,
                          sparklineData:
                              _todayData.map((d) => d.spo2).toList(),
                          onTap: () => Navigator.push(
                            context,
                            MaterialPageRoute(
                              builder: (_) => DetailScreen(
                                title: _tr('spo2'),
                                metricType: 'spo2',
                                color: AppTheme.spo2Color,
                                unit: '%',
                                icon: Icons.air_rounded,
                                allData: _allData,
                              ),
                            ),
                          ),
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: MetricCard(
                          title: _tr('pulse'),
                          value: _livePulse != null ? _livePulse!.toStringAsFixed(0) : latest.pulse.toStringAsFixed(0),
                          unit: _tr('bpm'),
                          icon: Icons.favorite_rounded,
                          color: AppTheme.pulseColor,
                          sparklineData:
                              _todayData.map((d) => d.pulse).toList(),
                          onTap: () => Navigator.push(
                            context,
                            MaterialPageRoute(
                              builder: (_) => DetailScreen(
                                title: _tr('pulse'),
                                metricType: 'pulse',
                                color: AppTheme.pulseColor,
                                unit: _tr('bpm'),
                                icon: Icons.favorite_rounded,
                                allData: _allData,
                              ),
                            ),
                          ),
                        ),
                      ),
                    ],
                  ),
                ],
                const SizedBox(height: 20),

                Container(
                  padding: const EdgeInsets.all(20),
                  decoration: BoxDecoration(
                    color: AppTheme.surface,
                    borderRadius: BorderRadius.circular(20),
                    border:
                        Border.all(color: AppTheme.cardBorder, width: 0.5),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        _tr('today_summary'),
                        style: const TextStyle(
                          color: AppTheme.textSecondary,
                          fontSize: 11,
                          fontWeight: FontWeight.w600,
                          letterSpacing: 2,
                        ),
                      ),
                      const SizedBox(height: 16),
                      _buildStatRow(
                        _tr('readings_today'),
                        '${_todayData.length}',
                        Icons.data_usage_rounded,
                      ),
                      const SizedBox(height: 12),
                      if (_todayData.isNotEmpty) ...[
                        Builder(
                          builder: (ctx) {
                            final avgGluc = _todayData.map((d) => d.glucose).reduce((a, b) => a + b) / _todayData.length;
                            final avgStr = _s.useMmol ? (avgGluc / 18.0).toStringAsFixed(1) : avgGluc.toStringAsFixed(0);
                            final unitStr = _s.useMmol ? _tr('unit_mmol') : _tr('unit_mgdl');
                            return _buildStatRow(
                              _tr('avg_glucose'),
                              '$avgStr $unitStr',
                              Icons.show_chart_rounded,
                            );
                          },
                        ),
                        const SizedBox(height: 12),
                        _buildStatRow(
                          _tr('avg_pulse'),
                          '${(_todayData.map((d) => d.pulse).reduce((a, b) => a + b) / _todayData.length).toStringAsFixed(0)} ${_tr('bpm')}',
                          Icons.favorite_border_rounded,
                        ),
                      ],
                    ],
                  ),
                ),

                const SizedBox(height: 20),
                GestureDetector(
                  onTap: () => _downloadReport(),
                  child: Container(
                    width: double.infinity,
                    padding: const EdgeInsets.symmetric(vertical: 16, horizontal: 20),
                    decoration: BoxDecoration(
                      color: AppTheme.surface,
                      borderRadius: BorderRadius.circular(20),
                      border: Border.all(color: AppTheme.cardBorder, width: 0.5),
                    ),
                    child: Row(
                      children: [
                        Container(
                          padding: const EdgeInsets.all(10),
                          decoration: BoxDecoration(
                            color: AppTheme.accent.withValues(alpha: 0.15),
                            borderRadius: BorderRadius.circular(12),
                          ),
                          child: const Icon(Icons.download_rounded,
                              color: AppTheme.accent, size: 22),
                        ),
                        const SizedBox(width: 16),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                _tr('download_report'),
                                style: const TextStyle(
                                  color: AppTheme.textPrimary,
                                  fontSize: 15,
                                  fontWeight: FontWeight.w600,
                                ),
                              ),
                              const SizedBox(height: 2),
                              Text(
                                _tr('report_subtitle'),
                                style: const TextStyle(
                                  color: AppTheme.textTertiary,
                                  fontSize: 12,
                                ),
                              ),
                            ],
                          ),
                        ),
                        const Icon(Icons.chevron_right,
                            color: AppTheme.textTertiary, size: 22),
                      ],
                    ),
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildStatRow(String label, String value, IconData icon) {
    return Row(
      children: [
        Icon(icon, color: AppTheme.textTertiary, size: 18),
        const SizedBox(width: 12),
        Flexible(
          child: Text(label,
              style: const TextStyle(
                  color: AppTheme.textSecondary, fontSize: 13),
              overflow: TextOverflow.ellipsis),
        ),
        const SizedBox(width: 8),
        Text(
          value,
          style: const TextStyle(
            color: AppTheme.textPrimary,
            fontSize: 14,
            fontWeight: FontWeight.w600,
          ),
          overflow: TextOverflow.ellipsis,
        ),
      ],
    );
  }

  Widget _buildCharts() {
    return SafeArea(
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              _tr('health_charts'),
              style: const TextStyle(
                color: AppTheme.textPrimary,
                fontSize: 28,
                fontWeight: FontWeight.w800,
                letterSpacing: -0.5,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              _tr('detailed_analytics'),
              style: const TextStyle(
                  color: AppTheme.textSecondary, fontSize: 14),
            ),
            const SizedBox(height: 24),
            _chartCard(
              _tr('blood_glucose'),
              'glucose',
              _s.useMmol ? _tr('unit_mmol') : _tr('unit_mgdl'),
              Icons.bloodtype_rounded,
              AppTheme.glucoseColor,
            ),
            const SizedBox(height: 16),
            _chartCard(
              _tr('spo2'),
              'spo2',
              '%',
              Icons.air_rounded,
              AppTheme.spo2Color,
            ),
            const SizedBox(height: 16),
            _chartCard(
              _tr('pulse'),
              'pulse',
              _tr('bpm'),
              Icons.favorite_rounded,
              AppTheme.pulseColor,
            ),
            const SizedBox(height: 16),
            _chartCard(
              _tr('diabetes_risk'),
              'risk',
              '%',
              Icons.warning_amber_rounded,
              AppTheme.riskMedium,
            ),
          ],
        ),
      ),
    );
  }

  Widget _chartCard(
    String title,
    String type,
    String unit,
    IconData icon,
    Color color,
  ) {
    return GestureDetector(
      onTap: () {
        if (type == 'risk') {
          Navigator.push(
            context,
            MaterialPageRoute(
              builder: (_) => DiabetesRiskScreen(data: _allData),
            ),
          );
        } else {
          Navigator.push(
            context,
            MaterialPageRoute(
              builder: (_) => DetailScreen(
                title: title,
                metricType: type,
                color: color,
                unit: unit,
                icon: icon,
                allData: _allData,
              ),
            ),
          );
        }
      },
      child: Container(
        padding: const EdgeInsets.all(20),
        decoration: BoxDecoration(
          color: AppTheme.surface,
          borderRadius: BorderRadius.circular(20),
          border: Border.all(color: AppTheme.cardBorder, width: 0.5),
        ),
        child: Row(
          children: [
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: color.withValues(alpha: 0.15),
                borderRadius: BorderRadius.circular(14),
              ),
              child: Icon(icon, color: color, size: 24),
            ),
            const SizedBox(width: 16),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    style: const TextStyle(
                      color: AppTheme.textPrimary,
                      fontSize: 16,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    _tr('view_charts'),
                    style: const TextStyle(
                      color: AppTheme.textSecondary,
                      fontSize: 12,
                    ),
                  ),
                ],
              ),
            ),
            Icon(Icons.chevron_right, color: AppTheme.textTertiary),
          ],
        ),
      ),
    );
  }
}
