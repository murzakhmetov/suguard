import 'dart:convert';
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:intl/intl.dart';
import 'package:uuid/uuid.dart';
import 'package:my_app/theme/app_theme.dart';
import 'package:my_app/models/food_entry.dart';
import 'package:my_app/services/app_settings.dart';
import 'package:my_app/services/firebase_service.dart';
import 'package:my_app/services/groq_service.dart';

class FoodTrackerScreen extends StatefulWidget {
  const FoodTrackerScreen({super.key});

  @override
  State<FoodTrackerScreen> createState() => _FoodTrackerScreenState();
}

class _FoodTrackerScreenState extends State<FoodTrackerScreen>
    with SingleTickerProviderStateMixin {
  final _s = AppSettings();
  String _tr(String k) => _s.tr(k);

  List<FoodEntry> _entries = [];
  bool _loading = true;
  bool _analyzing = false;
  DateTime _selectedDate = DateTime.now();

  late AnimationController _fabController;

  @override
  void initState() {
    super.initState();
    _fabController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 300),
    );
    _s.addListener(_onSettingsChanged);
    _loadEntries();
  }

  @override
  void dispose() {
    _fabController.dispose();
    _s.removeListener(_onSettingsChanged);
    super.dispose();
  }

  void _onSettingsChanged() {
    if (mounted) setState(() {});
  }

  Future<void> _loadEntries() async {
    setState(() => _loading = true);
    try {
      _entries = await FirebaseService.getFoodLog(date: _selectedDate);
    } catch (_) {
      _entries = [];
    }
    if (mounted) setState(() => _loading = false);
  }

  bool _isToday(DateTime d) {
    final now = DateTime.now();
    return d.year == now.year && d.month == now.month && d.day == now.day;
  }

  String _monthName(int m) {
    const ru = ['янв', 'фев', 'мар', 'апр', 'мая', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек'];
    const en = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    return _s.isRussian ? ru[m-1] : en[m-1];
  }

  String _fullMonthName(int m) {
    const ru = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря'];
    const en = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
    return _s.isRussian ? ru[m-1] : en[m-1];
  }

  String _dayNameShort(int w) {
    const ru = ['ПН', 'ВТ', 'СР', 'ЧТ', 'ПТ', 'СБ', 'ВС'];
    const en = ['MO', 'TU', 'WE', 'TH', 'FR', 'SA', 'SU'];
    return _s.isRussian ? ru[w-1] : en[w-1];
  }


  double get _totalCalories =>
      _entries.fold(0, (sum, e) => sum + e.calories);
  double get _totalProtein =>
      _entries.fold(0, (sum, e) => sum + e.protein);
  double get _totalFat => _entries.fold(0, (sum, e) => sum + e.fat);
  double get _totalCarbs => _entries.fold(0, (sum, e) => sum + e.carbs);


  Future<void> _takePhoto() async {
    final source = await showModalBottomSheet<ImageSource>(
      context: context,
      backgroundColor: AppTheme.surface,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (ctx) => Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 40,
              height: 4,
              decoration: BoxDecoration(
                color: AppTheme.textTertiary,
                borderRadius: BorderRadius.circular(2),
              ),
            ),
            const SizedBox(height: 20),
            Text(
              _tr('food_photo_source'),
              style: const TextStyle(
                color: AppTheme.textPrimary,
                fontSize: 18,
                fontWeight: FontWeight.w700,
              ),
            ),
            const SizedBox(height: 16),
            _sourceOption(
              _tr('food_camera'),
              Icons.camera_alt_rounded,
              () => Navigator.pop(ctx, ImageSource.camera),
            ),
            const SizedBox(height: 8),
            _sourceOption(
              _tr('food_gallery'),
              Icons.photo_library_rounded,
              () => Navigator.pop(ctx, ImageSource.gallery),
            ),
            const SizedBox(height: 20),
          ],
        ),
      ),
    );

    if (source == null) return;

    final picker = ImagePicker();
    final picked = await picker.pickImage(
      source: source,
      maxWidth: 1024,
      maxHeight: 1024,
      imageQuality: 85,
    );
    if (picked == null) return;

    setState(() => _analyzing = true);

    try {
      final bytes = await File(picked.path).readAsBytes();
      final base64Img = base64Encode(bytes);

      final result = await GroqService.analyzeFoodPhoto(base64Img);

      if (result != null && mounted) {
        final entry = FoodEntry(
          id: const Uuid().v4(),
          timestamp: DateTime(
            _selectedDate.year,
            _selectedDate.month,
            _selectedDate.day,
            DateTime.now().hour,
            DateTime.now().minute,
          ),
          description: result['description'] as String,
          calories: (result['calories'] as num).toDouble(),
          protein: (result['protein'] as num).toDouble(),
          fat: (result['fat'] as num).toDouble(),
          carbs: (result['carbs'] as num).toDouble(),
          source: 'photo',
        );
        await _saveEntry(entry);
      } else if (mounted) {
        _showError(_tr('food_analysis_error'));
      }
    } catch (e) {
      if (mounted) _showError(e.toString());
    }

    if (mounted) setState(() => _analyzing = false);
  }


  Future<void> _manualEntry() async {
    final descController = TextEditingController();
    final gramsController = TextEditingController();
    TimeOfDay selectedTime = TimeOfDay.now();

    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setDialogState) => AlertDialog(
          backgroundColor: AppTheme.surface,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(20),
          ),
          title: Text(
            _tr('food_add_manual'),
            style: const TextStyle(color: AppTheme.textPrimary),
          ),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                GestureDetector(
                  onTap: () async {
                    final time = await showTimePicker(
                      context: ctx,
                      initialTime: selectedTime,
                      builder: (context, child) => Theme(
                        data: AppTheme.darkTheme.copyWith(
                          timePickerTheme: TimePickerThemeData(
                            backgroundColor: AppTheme.surface,
                            dialBackgroundColor: AppTheme.surfaceLight,
                            hourMinuteColor: AppTheme.surfaceLight,
                          ),
                        ),
                        child: child!,
                      ),
                    );
                    if (time != null) {
                      setDialogState(() => selectedTime = time);
                    }
                  },
                  child: Container(
                    width: double.infinity,
                    padding: const EdgeInsets.symmetric(
                        horizontal: 16, vertical: 14),
                    decoration: BoxDecoration(
                      color: AppTheme.surfaceLight,
                      borderRadius: BorderRadius.circular(14),
                      border: Border.all(color: AppTheme.cardBorder),
                    ),
                    child: Row(
                      children: [
                        const Icon(Icons.access_time_rounded,
                            color: AppTheme.textSecondary, size: 20),
                        const SizedBox(width: 12),
                        Text(
                          '${_tr('food_time')}: ${selectedTime.format(ctx)}',
                          style: const TextStyle(
                            color: AppTheme.textPrimary,
                            fontSize: 15,
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: descController,
                  style: const TextStyle(color: AppTheme.textPrimary),
                  maxLines: 2,
                  decoration: InputDecoration(
                    hintText: _tr('food_description'),
                    prefixIcon: const Icon(Icons.restaurant_rounded,
                        color: AppTheme.textTertiary),
                  ),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: gramsController,
                  style: const TextStyle(color: AppTheme.textPrimary),
                  keyboardType: TextInputType.number,
                  decoration: InputDecoration(
                    hintText: _tr('food_grams'),
                    prefixIcon: const Icon(Icons.scale_rounded,
                        color: AppTheme.textTertiary),
                    suffixText: _tr('food_g'),
                    suffixStyle:
                        const TextStyle(color: AppTheme.textSecondary),
                  ),
                ),
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: Text(_tr('cancel'),
                  style: const TextStyle(color: AppTheme.textSecondary)),
            ),
            TextButton(
              onPressed: () => Navigator.pop(ctx, true),
              child: Text(_tr('food_add'),
                  style: TextStyle(color: AppTheme.accent)),
            ),
          ],
        ),
      ),
    );

    if (confirmed != true) return;

    final desc = descController.text.trim();
    final grams = gramsController.text.trim();
    if (desc.isEmpty) return;

    setState(() => _analyzing = true);

    try {
      final result = await GroqService.analyzeFoodText(
        foodDescription: desc,
        grams: grams.isNotEmpty ? grams : '100',
      );

      if (result != null && mounted) {
        final entryTime = DateTime(
          _selectedDate.year,
          _selectedDate.month,
          _selectedDate.day,
          selectedTime.hour,
          selectedTime.minute,
        );

        final entry = FoodEntry(
          id: const Uuid().v4(),
          timestamp: entryTime,
          description: result['description'] as String,
          calories: (result['calories'] as num).toDouble(),
          protein: (result['protein'] as num).toDouble(),
          fat: (result['fat'] as num).toDouble(),
          carbs: (result['carbs'] as num).toDouble(),
          source: 'manual',
        );
        await _saveEntry(entry);
      } else if (mounted) {
        _showError(_tr('food_analysis_error'));
      }
    } catch (_) {
      if (mounted) _showError(_tr('food_analysis_error'));
    }

    if (mounted) setState(() => _analyzing = false);
  }

  Future<void> _saveEntry(FoodEntry entry) async {
    await FirebaseService.saveFoodEntry(entry);
    await _loadEntries();
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(_tr('food_saved')),
          backgroundColor: AppTheme.accent.withValues(alpha: 0.9),
          behavior: SnackBarBehavior.floating,
          shape:
              RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
        ),
      );
    }
  }

  Future<void> _deleteEntry(FoodEntry entry) async {
    await FirebaseService.deleteFoodEntry(entry.id);
    await _loadEntries();
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(_tr('food_deleted')),
          backgroundColor: AppTheme.riskHigh.withValues(alpha: 0.9),
          behavior: SnackBarBehavior.floating,
          shape:
              RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
        ),
      );
    }
  }

  void _showError(String msg) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(msg),
        backgroundColor: AppTheme.riskHigh.withValues(alpha: 0.9),
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      ),
    );
  }

  Widget _sourceOption(String label, IconData icon, VoidCallback onTap) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
        decoration: BoxDecoration(
          color: AppTheme.surfaceLight,
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: AppTheme.cardBorder, width: 0.5),
        ),
        child: Row(
          children: [
            Icon(icon, color: AppTheme.accent, size: 24),
            const SizedBox(width: 16),
            Text(
              label,
              style: const TextStyle(
                color: AppTheme.textPrimary,
                fontSize: 16,
                fontWeight: FontWeight.w500,
              ),
            ),
          ],
        ),
      ),
    );
  }


  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: Stack(
        children: [
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Padding(
                padding: const EdgeInsets.fromLTRB(20, 20, 20, 0),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      _tr('food_tracker'),
                      style: const TextStyle(
                        color: AppTheme.textPrimary,
                        fontSize: 28,
                        fontWeight: FontWeight.w800,
                        letterSpacing: -0.5,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      _isToday(_selectedDate)
                          ? _tr('food_today')
                          : '${_selectedDate.day} ${_fullMonthName(_selectedDate.month)} ${_selectedDate.year}',
                      style: const TextStyle(
                        color: AppTheme.textSecondary,
                        fontSize: 14,
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 16),

              SizedBox(
                height: 56,
                child: _buildDateSelector(),
              ),
              const SizedBox(height: 16),

              if (_entries.isNotEmpty)
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 20),
                  child: _buildTotalsCard(),
                ),

              if (_entries.isNotEmpty) const SizedBox(height: 16),

              Expanded(
                child: _loading
                    ? const Center(
                        child: CircularProgressIndicator(
                            color: AppTheme.accent),
                      )
                    : _entries.isEmpty
                        ? _buildEmptyState()
                        : _buildEntryList(),
              ),
            ],
          ),

          if (_analyzing)
            Container(
              color: Colors.black54,
              child: Center(
                child: Container(
                  padding: const EdgeInsets.all(32),
                  decoration: BoxDecoration(
                    color: AppTheme.surface,
                    borderRadius: BorderRadius.circular(24),
                    border:
                        Border.all(color: AppTheme.cardBorder, width: 0.5),
                  ),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const SizedBox(
                        width: 48,
                        height: 48,
                        child: CircularProgressIndicator(
                          color: AppTheme.accent,
                          strokeWidth: 3,
                        ),
                      ),
                      const SizedBox(height: 20),
                      Text(
                        _tr('food_analyzing'),
                        style: const TextStyle(
                          color: AppTheme.textPrimary,
                          fontSize: 16,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),

          if (!_analyzing)
            Positioned(
              right: 20,
              bottom: 20,
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  _buildMiniFab(
                    icon: Icons.edit_rounded,
                    label: _tr('food_add_manual'),
                    onTap: _manualEntry,
                    color: AppTheme.spo2Color,
                  ),
                  const SizedBox(height: 12),
                  _buildMiniFab(
                    icon: Icons.camera_alt_rounded,
                    label: _tr('food_add_photo'),
                    onTap: _takePhoto,
                    color: AppTheme.glucoseColor,
                  ),
                  const SizedBox(height: 12),
                ],
              ),
            ),
        ],
      ),
    );
  }

  Widget _buildMiniFab({
    required IconData icon,
    required String label,
    required VoidCallback onTap,
    required Color color,
  }) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        decoration: BoxDecoration(
          color: color.withValues(alpha: 0.15),
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: color.withValues(alpha: 0.3)),
          boxShadow: [
            BoxShadow(
              color: color.withValues(alpha: 0.2),
              blurRadius: 12,
              offset: const Offset(0, 4),
            ),
          ],
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, color: color, size: 20),
            const SizedBox(width: 10),
            Text(
              label,
              style: TextStyle(
                color: color,
                fontSize: 13,
                fontWeight: FontWeight.w600,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildDateSelector() {
    DateTime endDate = DateTime.now();
    final difference = DateTime(endDate.year, endDate.month, endDate.day)
        .difference(DateTime(_selectedDate.year, _selectedDate.month, _selectedDate.day))
        .inDays;
        
    if (difference > 6) {
      endDate = _selectedDate.add(const Duration(days: 3));
      if (endDate.isAfter(DateTime.now())) {
        endDate = DateTime.now();
      }
    }

    final days = List.generate(7, (i) => endDate.subtract(Duration(days: 6 - i)));

    return Row(
      children: [
        GestureDetector(
          onTap: () async {
            final date = await showDatePicker(
              context: context,
              initialDate: _selectedDate,
              firstDate: DateTime(2020),
              lastDate: DateTime.now(),
              builder: (context, child) {
                return Theme(
                  data: AppTheme.darkTheme.copyWith(
                    colorScheme: const ColorScheme.dark(
                      primary: AppTheme.accent,
                      onPrimary: Colors.white,
                      surface: AppTheme.surface,
                      onSurface: AppTheme.textPrimary,
                    ),
                  ),
                  child: child!,
                );
              },
            );
            if (date != null) {
              setState(() => _selectedDate = date);
              _loadEntries();
            }
          },
          child: Container(
            width: 52,
            margin: const EdgeInsets.only(left: 16),
            decoration: BoxDecoration(
              color: AppTheme.surfaceLight,
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: AppTheme.cardBorder, width: 0.5),
            ),
            child: const Center(
              child: Icon(Icons.calendar_month_rounded, color: AppTheme.accent),
            ),
          ),
        ),
        const SizedBox(width: 8),
        Expanded(
          child: ListView.builder(
            scrollDirection: Axis.horizontal,
            padding: const EdgeInsets.only(right: 16),
            itemCount: days.length,
            itemBuilder: (ctx, i) {
              final d = days[i];
              final selected = d.year == _selectedDate.year &&
                  d.month == _selectedDate.month &&
                  d.day == _selectedDate.day;
              final isToday = _isToday(d);
              final dayName = _dayNameShort(d.weekday);

              return GestureDetector(
                onTap: () {
                  setState(() => _selectedDate = d);
                  _loadEntries();
                },
                child: Container(
                  width: 52,
                  margin: const EdgeInsets.symmetric(horizontal: 4),
                  decoration: BoxDecoration(
                    color: selected
                        ? AppTheme.accent.withValues(alpha: 0.15)
                        : AppTheme.surface,
                    borderRadius: BorderRadius.circular(16),
                    border: Border.all(
                      color: selected ? AppTheme.accent : AppTheme.cardBorder,
                      width: selected ? 1.5 : 0.5,
                    ),
                  ),
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Text(
                        dayName,
                        style: TextStyle(
                          color: selected
                              ? AppTheme.accent
                              : AppTheme.textSecondary,
                          fontSize: 10,
                          fontWeight: FontWeight.w600,
                          letterSpacing: 1,
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        '${d.day}',
                        style: TextStyle(
                          color: selected
                              ? AppTheme.accent
                              : AppTheme.textPrimary,
                          fontSize: 18,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                      if (isToday)
                        Container(
                          margin: const EdgeInsets.only(top: 4),
                          width: 4,
                          height: 4,
                          decoration: BoxDecoration(
                            shape: BoxShape.circle,
                            color: selected
                                ? AppTheme.accent
                                : AppTheme.textTertiary,
                          ),
                        ),
                    ],
                  ),
                ),
              );
            },
          ),
        ),
      ],
    );
  }

  Widget _buildTotalsCard() {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: AppTheme.cardBorder, width: 0.5),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            _isToday(_selectedDate)
                ? _tr('food_total_today')
                : '${_selectedDate.day} ${_monthName(_selectedDate.month)}'.toUpperCase(),
            style: const TextStyle(
              color: AppTheme.textSecondary,
              fontSize: 11,
              fontWeight: FontWeight.w600,
              letterSpacing: 2,
            ),
          ),
          const SizedBox(height: 16),
          Row(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Text(
                _totalCalories.toStringAsFixed(0),
                style: const TextStyle(
                  color: AppTheme.textPrimary,
                  fontSize: 40,
                  fontWeight: FontWeight.w800,
                  letterSpacing: -1,
                ),
              ),
              const SizedBox(width: 6),
              Padding(
                padding: const EdgeInsets.only(bottom: 6),
                child: Text(
                  _tr('food_calories'),
                  style: const TextStyle(
                    color: AppTheme.textSecondary,
                    fontSize: 16,
                    fontWeight: FontWeight.w500,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 20),
          Row(
            children: [
              _macroWidget(
                _tr('food_protein'),
                _totalProtein,
                AppTheme.spo2Color,
              ),
              const SizedBox(width: 12),
              _macroWidget(
                _tr('food_fat'),
                _totalFat,
                AppTheme.glucoseColor,
              ),
              const SizedBox(width: 12),
              _macroWidget(
                _tr('food_carbs'),
                _totalCarbs,
                AppTheme.pulseColor,
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _macroWidget(String label, double value, Color color) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: color.withValues(alpha: 0.08),
          borderRadius: BorderRadius.circular(14),
        ),
        child: Column(
          children: [
            Text(
              '${value.toStringAsFixed(1)}${_tr('food_g')}',
              style: TextStyle(
                color: color,
                fontSize: 18,
                fontWeight: FontWeight.w700,
              ),
            ),
            const SizedBox(height: 4),
            Text(
              label,
              style: TextStyle(
                color: color.withValues(alpha: 0.7),
                fontSize: 11,
                fontWeight: FontWeight.w500,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildEmptyState() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Container(
            padding: const EdgeInsets.all(24),
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: AppTheme.textTertiary.withValues(alpha: 0.1),
            ),
            child: const Icon(
              Icons.restaurant_rounded,
              color: AppTheme.textTertiary,
              size: 48,
            ),
          ),
          const SizedBox(height: 20),
          Text(
            _tr('food_empty'),
            style: const TextStyle(
              color: AppTheme.textPrimary,
              fontSize: 18,
              fontWeight: FontWeight.w600,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            _tr('food_empty_hint'),
            style: const TextStyle(
              color: AppTheme.textSecondary,
              fontSize: 14,
            ),
          ),
          const SizedBox(height: 80), 
        ],
      ),
    );
  }

  Widget _buildEntryList() {
    return ListView.builder(
      padding: const EdgeInsets.fromLTRB(20, 0, 20, 100),
      itemCount: _entries.length,
      itemBuilder: (ctx, i) {
        final e = _entries[i];
        return Dismissible(
          key: Key(e.id),
          direction: DismissDirection.endToStart,
          background: Container(
            alignment: Alignment.centerRight,
            padding: const EdgeInsets.only(right: 20),
            margin: const EdgeInsets.only(bottom: 10),
            decoration: BoxDecoration(
              color: AppTheme.riskHigh.withValues(alpha: 0.15),
              borderRadius: BorderRadius.circular(18),
            ),
            child: const Icon(Icons.delete_rounded,
                color: AppTheme.riskHigh, size: 24),
          ),
          onDismissed: (_) => _deleteEntry(e),
          child: Container(
            margin: const EdgeInsets.only(bottom: 10),
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: AppTheme.surface,
              borderRadius: BorderRadius.circular(18),
              border: Border.all(color: AppTheme.cardBorder, width: 0.5),
            ),
            child: Row(
              children: [
                Container(
                  width: 48,
                  height: 48,
                  decoration: BoxDecoration(
                    color: (e.source == 'photo'
                            ? AppTheme.glucoseColor
                            : AppTheme.spo2Color)
                        .withValues(alpha: 0.12),
                    borderRadius: BorderRadius.circular(14),
                  ),
                  child: Icon(
                    e.source == 'photo'
                        ? Icons.camera_alt_rounded
                        : Icons.edit_rounded,
                    color: e.source == 'photo'
                        ? AppTheme.glucoseColor
                        : AppTheme.spo2Color,
                    size: 22,
                  ),
                ),
                const SizedBox(width: 14),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        e.description,
                        style: const TextStyle(
                          color: AppTheme.textPrimary,
                          fontSize: 14,
                          fontWeight: FontWeight.w600,
                        ),
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                      ),
                      const SizedBox(height: 4),
                      Text(
                        DateFormat('HH:mm').format(e.timestamp),
                        style: const TextStyle(
                          color: AppTheme.textTertiary,
                          fontSize: 12,
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(width: 8),
                Column(
                  crossAxisAlignment: CrossAxisAlignment.end,
                  children: [
                    Text(
                      '${e.calories.toStringAsFixed(0)} ${_tr('food_calories')}',
                      style: const TextStyle(
                        color: AppTheme.textPrimary,
                        fontSize: 15,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      'Б${e.protein.toStringAsFixed(0)} '
                      'Ж${e.fat.toStringAsFixed(0)} '
                      'У${e.carbs.toStringAsFixed(0)}',
                      style: const TextStyle(
                        color: AppTheme.textTertiary,
                        fontSize: 11,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
        );
      },
    );
  }
}
