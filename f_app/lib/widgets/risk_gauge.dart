import 'dart:math';
import 'package:flutter/material.dart';
import 'package:f_app/theme/app_theme.dart';

class RiskGauge extends StatefulWidget {
  final double risk;
  final double size;
  final bool showLabel;

  const RiskGauge({
    super.key,
    required this.risk,
    this.size = 200,
    this.showLabel = true,
  });

  @override
  State<RiskGauge> createState() => _RiskGaugeState();
}

class _RiskGaugeState extends State<RiskGauge>
    with SingleTickerProviderStateMixin {
  late AnimationController _controller;
  late Animation<double> _animation;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      duration: const Duration(milliseconds: 1500),
      vsync: this,
    );
    _animation = Tween<double>(begin: 0, end: widget.risk).animate(
      CurvedAnimation(parent: _controller, curve: Curves.easeOutCubic),
    );
    _controller.forward();
  }

  @override
  void didUpdateWidget(RiskGauge oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.risk != widget.risk) {
      _animation = Tween<double>(begin: _animation.value, end: widget.risk)
          .animate(
              CurvedAnimation(parent: _controller, curve: Curves.easeOutCubic));
      _controller
        ..reset()
        ..forward();
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _animation,
      builder: (context, child) {
        final value = _animation.value;
        final color = AppTheme.riskColor(value);
        return Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            SizedBox(
              width: widget.size,
              height: widget.size,
              child: CustomPaint(
                painter: _RiskGaugePainter(
                  risk: value,
                  color: color,
                ),
                child: Center(
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Text(
                        '${value.toStringAsFixed(0)}%',
                        style: TextStyle(
                          color: color,
                          fontSize: widget.size * 0.22,
                          fontWeight: FontWeight.w800,
                          letterSpacing: -2,
                        ),
                      ),
                      if (widget.showLabel)
                        Text(
                          'DIABETES RISK',
                          style: TextStyle(
                            color: AppTheme.textSecondary,
                            fontSize: widget.size * 0.055,
                            fontWeight: FontWeight.w600,
                            letterSpacing: 2,
                          ),
                        ),
                    ],
                  ),
                ),
              ),
            ),
          ],
        );
      },
    );
  }
}

class _RiskGaugePainter extends CustomPainter {
  final double risk;
  final Color color;

  _RiskGaugePainter({required this.risk, required this.color});

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final radius = size.width / 2 - 16;
    const strokeWidth = 12.0;
    const startAngle = 135.0 * (pi / 180);
    const sweepTotal = 270.0 * (pi / 180);

    final bgPaint = Paint()
      ..color = AppTheme.surfaceLight
      ..strokeWidth = strokeWidth
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round;

    canvas.drawArc(
      Rect.fromCircle(center: center, radius: radius),
      startAngle,
      sweepTotal,
      false,
      bgPaint,
    );

    final valueSweep = sweepTotal * (risk / 100).clamp(0, 1);
    final valuePaint = Paint()
      ..shader = SweepGradient(
        startAngle: startAngle,
        endAngle: startAngle + valueSweep,
        colors: [
          AppTheme.riskLow,
          AppTheme.riskMedium,
          AppTheme.riskHigh,
        ],
        stops: const [0.0, 0.5, 1.0],
      ).createShader(Rect.fromCircle(center: center, radius: radius))
      ..strokeWidth = strokeWidth
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round;

    if (risk > 0) {
      canvas.drawArc(
        Rect.fromCircle(center: center, radius: radius),
        startAngle,
        valueSweep,
        false,
        valuePaint,
      );
    }

    final glowPaint = Paint()
      ..color = color.withValues(alpha: 0.3)
      ..strokeWidth = strokeWidth + 8
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round
      ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 8);

    if (risk > 0) {
      canvas.drawArc(
        Rect.fromCircle(center: center, radius: radius),
        startAngle,
        valueSweep,
        false,
        glowPaint,
      );
    }

    for (int i = 0; i <= 10; i++) {
      final angle = startAngle + sweepTotal * (i / 10);
      final tickStart =
          center + Offset(cos(angle), sin(angle)) * (radius + 10);
      final tickEnd = center + Offset(cos(angle), sin(angle)) * (radius + 16);

      canvas.drawLine(
        tickStart,
        tickEnd,
        Paint()
          ..color = AppTheme.textTertiary
          ..strokeWidth = 1.5
          ..strokeCap = StrokeCap.round,
      );
    }
  }

  @override
  bool shouldRepaint(covariant _RiskGaugePainter oldDelegate) =>
      oldDelegate.risk != risk || oldDelegate.color != color;
}
