import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:f_app/theme/app_theme.dart';
import 'package:f_app/services/firebase_service.dart';
import 'package:f_app/services/app_settings.dart';

class ProfileScreen extends StatefulWidget {
  const ProfileScreen({super.key});

  @override
  State<ProfileScreen> createState() => _ProfileScreenState();
}

class _ProfileScreenState extends State<ProfileScreen> {
  final _nameController = TextEditingController();
  final _heightController = TextEditingController();
  final _weightController = TextEditingController();
  final _ageController = TextEditingController();
  bool _loading = false;
  bool _saved = false;
  final _s = AppSettings();

  String _tr(String k) => _s.tr(k);

  @override
  void initState() {
    super.initState();
    _nameController.text = FirebaseService.displayName ?? '';
    if (_s.height != null) _heightController.text = _s.height!.toStringAsFixed(0);
    if (_s.weight != null) _weightController.text = _s.weight!.toStringAsFixed(0);
    if (_s.age != null) _ageController.text = '${_s.age}';
  }

  Future<void> _save() async {
    setState(() => _loading = true);
    try {
      await FirebaseService.updateProfile({
        'name': _nameController.text.trim(),
      });
      final h = double.tryParse(_heightController.text.trim());
      final w = double.tryParse(_weightController.text.trim());
      final a = int.tryParse(_ageController.text.trim());
      await _s.setHeight(h);
      await _s.setWeight(w);
      await _s.setAge(a);

      if (mounted) {
        setState(() {
          _saved = true;
          _loading = false;
        });
        Future.delayed(const Duration(seconds: 2), () {
          if (mounted) setState(() => _saved = false);
        });
      }
    } catch (e) {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  void dispose() {
    _nameController.dispose();
    _heightController.dispose();
    _weightController.dispose();
    _ageController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final name = FirebaseService.displayName ?? 'U';
    final userEmail = FirebaseService.email ?? '';
    final bmi = _s.bmi;

    return Scaffold(
      backgroundColor: AppTheme.background,
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        title: Text(_tr('profile')),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios, size: 20),
          onPressed: () => Navigator.pop(context),
        ),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Column(
          children: [
            const SizedBox(height: 12),
            Container(
              width: 90,
              height: 90,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                gradient: AppTheme.accentGradient,
                boxShadow: [
                  BoxShadow(
                    color: AppTheme.accent.withValues(alpha: 0.3),
                    blurRadius: 20,
                  ),
                ],
              ),
              child: Center(
                child: Text(
                  name.isNotEmpty ? name[0].toUpperCase() : 'U',
                  style: const TextStyle(
                    color: Colors.black,
                    fontSize: 36,
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ),
            ),
            const SizedBox(height: 24),

            _sectionLabel(_tr('display_name')),
            const SizedBox(height: 8),
            TextField(
              controller: _nameController,
              style: const TextStyle(color: AppTheme.textPrimary),
              decoration: const InputDecoration(
                prefixIcon:
                    Icon(Icons.person_outline, color: AppTheme.textTertiary),
              ),
            ),
            const SizedBox(height: 20),

            _sectionLabel(_tr('email')),
            const SizedBox(height: 8),
            Container(
              width: double.infinity,
              padding:
                  const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
              decoration: BoxDecoration(
                color: AppTheme.surface,
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: AppTheme.cardBorder),
              ),
              child: Row(
                children: [
                  const Icon(Icons.email_outlined,
                      color: AppTheme.textTertiary, size: 20),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Text(
                      userEmail,
                      style: const TextStyle(
                        color: AppTheme.textSecondary,
                        fontSize: 14,
                      ),
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 24),

            _sectionLabel(_tr('biometrics')),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: _bioField(
                    _tr('height_cm'),
                    _heightController,
                    Icons.height_rounded,
                    '170',
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: _bioField(
                    _tr('weight_kg'),
                    _weightController,
                    Icons.monitor_weight_outlined,
                    '70',
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: _bioField(
                    _tr('age_years'),
                    _ageController,
                    Icons.cake_outlined,
                    '25',
                  ),
                ),
              ],
            ),
            if (bmi != null) ...[
              const SizedBox(height: 12),
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: AppTheme.surface,
                  borderRadius: BorderRadius.circular(16),
                  border: Border.all(color: AppTheme.cardBorder, width: 0.5),
                ),
                child: Row(
                  children: [
                    const Icon(Icons.speed_rounded,
                        color: AppTheme.accent, size: 22),
                    const SizedBox(width: 12),
                    Text('${_tr('bmi')}: ',
                        style: const TextStyle(
                            color: AppTheme.textSecondary, fontSize: 14)),
                    Text(
                      bmi.toStringAsFixed(1),
                      style: TextStyle(
                        color: _bmiColor(bmi),
                        fontSize: 18,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                    const SizedBox(width: 8),
                    Text(
                      _bmiLabel(bmi),
                      style: TextStyle(
                        color: _bmiColor(bmi),
                        fontSize: 12,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ],
                ),
              ),
            ],
            const SizedBox(height: 28),

            ElevatedButton(
              onPressed: _loading ? null : _save,
              child: _loading
                  ? const SizedBox(
                      height: 20,
                      width: 20,
                      child: CircularProgressIndicator(
                        strokeWidth: 2,
                        color: Colors.black,
                      ),
                    )
                  : Text(_saved ? _tr('saved') : _tr('save_changes')),
            ),
            const SizedBox(height: 32),
          ],
        ),
      ),
    );
  }

  Widget _sectionLabel(String text) => Align(
        alignment: Alignment.centerLeft,
        child: Text(
          text,
          style: const TextStyle(
            color: AppTheme.textSecondary,
            fontSize: 11,
            fontWeight: FontWeight.w600,
            letterSpacing: 2,
          ),
        ),
      );

  Widget _bioField(String label, TextEditingController ctrl,
      IconData icon, String hint) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label,
            style: const TextStyle(
                color: AppTheme.textTertiary, fontSize: 11)),
        const SizedBox(height: 6),
        TextField(
          controller: ctrl,
          keyboardType: TextInputType.number,
          inputFormatters: [FilteringTextInputFormatter.digitsOnly],
          style: const TextStyle(color: AppTheme.textPrimary, fontSize: 16),
          textAlign: TextAlign.center,
          decoration: InputDecoration(
            hintText: hint,
            contentPadding:
                const EdgeInsets.symmetric(horizontal: 12, vertical: 14),
          ),
        ),
      ],
    );
  }

  Color _bmiColor(double bmi) {
    if (bmi < 18.5) return Colors.blueAccent;
    if (bmi < 25) return AppTheme.accent;
    if (bmi < 30) return Colors.orangeAccent;
    return AppTheme.riskHigh;
  }

  String _bmiLabel(double bmi) {
    if (_s.isRussian) {
      if (bmi < 18.5) return 'Недовес';
      if (bmi < 25) return 'Норма';
      if (bmi < 30) return 'Избыт. вес';
      return 'Ожирение';
    }
    if (bmi < 18.5) return 'Underweight';
    if (bmi < 25) return 'Normal';
    if (bmi < 30) return 'Overweight';
    return 'Obese';
  }
}
