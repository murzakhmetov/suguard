import 'package:flutter/material.dart';
import 'package:f_app/theme/app_theme.dart';
import 'package:f_app/models/health_data.dart';
import 'package:f_app/services/health_service.dart';
import 'package:f_app/services/app_settings.dart';
import 'package:f_app/services/resend_service.dart';
import 'package:f_app/services/firebase_service.dart';
import 'package:f_app/widgets/risk_gauge.dart';
import 'package:f_app/widgets/health_chart.dart';

class DiabetesRiskScreen extends StatefulWidget {
  final List<HealthData> data;
  const DiabetesRiskScreen({super.key, required this.data});

  @override
  State<DiabetesRiskScreen> createState() => _DiabetesRiskScreenState();
}

class _DiabetesRiskScreenState extends State<DiabetesRiskScreen> {
  final _s = AppSettings();
  String _tr(String k) => _s.tr(k);
  bool _emergencySent = false;

  @override
  void initState() {
    super.initState();
    _checkAndSendEmergency();
  }

  Future<void> _checkAndSendEmergency() async {
    final risk = HealthService.calculateDiabetesRisk(widget.data);
    if (risk < 70) return;

    final email = _s.emergencyEmail;
    if (email == null || email.isEmpty) return;

    if (_emergencySent) return;
    _emergencySent = true;

    final stats = HealthService.getStats(widget.data);
    final avgGlucose = stats['glucose']?['avg'] ?? 0;
    final avgPulse = stats['pulse']?['avg'] ?? 0;
    final avgSpo2 = stats['spo2']?['avg'] ?? 0;

    final summary = _s.isRussian
        ? 'Глюкоза: ${(_s.useMmol ? avgGlucose / 18.0 : avgGlucose).toStringAsFixed(1)} ${_s.useMmol ? 'ммоль/л' : 'мг/дл'}\n'
            'Пульс: ${avgPulse.toStringAsFixed(0)} уд/мин\n'
            'SpO2: ${avgSpo2.toStringAsFixed(1)}%\n'
            'Риск диабета: ${risk.toStringAsFixed(0)}%'
        : 'Glucose: ${(_s.useMmol ? avgGlucose / 18.0 : avgGlucose).toStringAsFixed(1)} ${_s.useMmol ? 'mmol/L' : 'mg/dL'}\n'
            'Pulse: ${avgPulse.toStringAsFixed(0)} bpm\n'
            'SpO2: ${avgSpo2.toStringAsFixed(1)}%\n'
            'Diabetes Risk: ${risk.toStringAsFixed(0)}%';

    final sent = await ResendService.sendEmergencyEmail(
      toEmail: email,
      userName: FirebaseService.displayName ?? 'User',
      riskPercent: risk,
      healthSummary: summary,
    );

    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            sent ? _tr('emergency_email_sent') : _tr('emergency_email_failed'),
          ),
          backgroundColor: sent
              ? AppTheme.accent.withValues(alpha: 0.9)
              : AppTheme.riskHigh.withValues(alpha: 0.9),
          behavior: SnackBarBehavior.floating,
          shape:
              RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final risk = HealthService.calculateDiabetesRisk(widget.data);
    final stats = HealthService.getStats(widget.data);
    final avgGlucose = stats['glucose']?['avg'] ?? 0;
    final avgPulse = stats['pulse']?['avg'] ?? 0;
    final avgSpo2 = stats['spo2']?['avg'] ?? 0;

    return Scaffold(
      backgroundColor: AppTheme.background,
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        title: Text(_tr('diabetes_risk_title')),
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
            Center(
              child: Container(
                padding: const EdgeInsets.all(32),
                decoration: BoxDecoration(
                  color: AppTheme.surface,
                  borderRadius: BorderRadius.circular(24),
                  border: Border.all(color: AppTheme.cardBorder, width: 0.5),
                ),
                child: Column(
                  children: [
                    RiskGauge(risk: risk, size: 220),
                    const SizedBox(height: 16),
                    Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 20, vertical: 10),
                      decoration: BoxDecoration(
                        color:
                            AppTheme.riskColor(risk).withValues(alpha: 0.1),
                        borderRadius: BorderRadius.circular(20),
                      ),
                      child: Text(
                        HealthService.riskLabel(risk, _s.isRussian),
                        style: TextStyle(
                          color: AppTheme.riskColor(risk),
                          fontSize: 14,
                          fontWeight: FontWeight.w700,
                          letterSpacing: 1,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 24),

            if (risk >= 70 && _s.emergencyEmail?.isNotEmpty == true)
              Container(
                padding: const EdgeInsets.all(16),
                margin: const EdgeInsets.only(bottom: 24),
                decoration: BoxDecoration(
                  color: AppTheme.riskHigh.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(16),
                  border: Border.all(
                      color: AppTheme.riskHigh.withValues(alpha: 0.3)),
                ),
                child: Row(
                  children: [
                    const Icon(Icons.email_rounded,
                        color: AppTheme.riskHigh, size: 20),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Text(
                        _s.isRussian
                            ? 'Экстренное уведомление отправлено на ${_s.emergencyEmail}'
                            : 'Emergency notification sent to ${_s.emergencyEmail}',
                        style: const TextStyle(
                          color: AppTheme.riskHigh,
                          fontSize: 12,
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                    ),
                  ],
                ),
              ),

            Text(
              _tr('risk_factors'),
              style: const TextStyle(
                color: AppTheme.textSecondary,
                fontSize: 11,
                fontWeight: FontWeight.w600,
                letterSpacing: 2,
              ),
            ),
            const SizedBox(height: 12),
            _factorCard(
              _tr('avg_glucose_level'),
              '${(_s.useMmol ? avgGlucose / 18.0 : avgGlucose).toStringAsFixed(1)} ${_s.useMmol ? _tr('unit_mmol') : _tr('unit_mgdl')}',
              _glucoseProgress(avgGlucose),
              AppTheme.glucoseColor,
            ),
            const SizedBox(height: 8),
            _factorCard(
              _tr('resting_pulse'),
              '${avgPulse.toStringAsFixed(0)} ${_tr('bpm')}',
              ((avgPulse - 60) / 40).clamp(0, 1),
              AppTheme.pulseColor,
            ),
            const SizedBox(height: 8),
            _factorCard(
              _tr('spo2_level'),
              '${avgSpo2.toStringAsFixed(1)}%',
              1 - ((avgSpo2 - 90) / 10).clamp(0, 1),
              AppTheme.spo2Color,
            ),
            const SizedBox(height: 24),

            Text(
              _tr('glucose_trend'),
              style: const TextStyle(
                color: AppTheme.textSecondary,
                fontSize: 11,
                fontWeight: FontWeight.w600,
                letterSpacing: 2,
              ),
            ),
            const SizedBox(height: 12),
            Container(
              height: 200,
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: AppTheme.surface,
                borderRadius: BorderRadius.circular(20),
                border: Border.all(color: AppTheme.cardBorder, width: 0.5),
              ),
              child: HealthChart(
                data: widget.data,
                metricType: 'glucose',
                color: AppTheme.glucoseColor,
                period: ChartPeriod.month,
              ),
            ),
            const SizedBox(height: 24),

            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: AppTheme.surfaceLight,
                borderRadius: BorderRadius.circular(16),
                border: Border.all(
                    color: AppTheme.textTertiary.withValues(alpha: 0.2)),
              ),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Icon(Icons.info_outline,
                      color: AppTheme.textTertiary, size: 18),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Text(
                      _tr('disclaimer'),
                      style: const TextStyle(
                        color: AppTheme.textTertiary,
                        fontSize: 12,
                        height: 1.4,
                      ),
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 20),
          ],
        ),
      ),
    );
  }

  double _glucoseProgress(double avg) {
    return ((avg - 70) / 130).clamp(0, 1);
  }

  Widget _factorCard(
      String title, String value, double progress, Color color) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppTheme.cardBorder, width: 0.5),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text(title,
                  style: const TextStyle(
                      color: AppTheme.textSecondary, fontSize: 13)),
              const Spacer(),
              Text(value,
                  style: TextStyle(
                      color: color,
                      fontSize: 14,
                      fontWeight: FontWeight.w700)),
            ],
          ),
          const SizedBox(height: 10),
          ClipRRect(
            borderRadius: BorderRadius.circular(4),
            child: LinearProgressIndicator(
              value: progress,
              minHeight: 6,
              backgroundColor: AppTheme.surfaceLight,
              valueColor: AlwaysStoppedAnimation<Color>(color),
            ),
          ),
        ],
      ),
    );
  }
}
