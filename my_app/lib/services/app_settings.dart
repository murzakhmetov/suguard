import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

class AppSettings extends ChangeNotifier {
  static final AppSettings _instance = AppSettings._();
  factory AppSettings() => _instance;
  AppSettings._();

  String _locale = 'ru'; 
  String get locale => _locale;
  bool get isRussian => _locale == 'ru';

  bool _notificationsEnabled = true;
  bool get notificationsEnabled => _notificationsEnabled;

  int _syncMinutes = 30;
  int get syncMinutes => _syncMinutes;
  static const List<int> syncOptions = [1, 3, 5, 10, 20, 30];

  String? _deviceId;
  String? get deviceId => _deviceId;
  bool get isDeviceConnected => _deviceId != null && _deviceId!.isNotEmpty;

  bool _useMmol = true;
  bool get useMmol => _useMmol;

  String? _emergencyEmail;
  String? get emergencyEmail => _emergencyEmail;

  bool _highGlucoseMode = false;
  bool get highGlucoseMode => _highGlucoseMode;
  void toggleHighGlucoseMode() {
    _highGlucoseMode = !_highGlucoseMode;
    notifyListeners();
  }

  double? _height; 
  double? _weight; 
  int? _age;
  double? get height => _height;
  double? get weight => _weight;
  int? get age => _age;
  double? get bmi => (_height != null && _weight != null && _height! > 0)
      ? _weight! / ((_height! / 100) * (_height! / 100))
      : null;

  Future<void> load() async {
    final prefs = await SharedPreferences.getInstance();
    _locale = prefs.getString('locale') ?? 'ru';
    _notificationsEnabled = prefs.getBool('notifications') ?? true;
    _syncMinutes = prefs.getInt('syncMinutes') ?? 30;
    _deviceId = prefs.getString('deviceId');
    _useMmol = prefs.getBool('useMmol') ?? true;
    _height = prefs.getDouble('height');
    _weight = prefs.getDouble('weight');
    _age = prefs.getInt('age');
    _emergencyEmail = prefs.getString('emergencyEmail');
    notifyListeners();
  }

  Future<void> setUseMmol(bool val) async {
    _useMmol = val;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool('useMmol', val);
    notifyListeners();
  }

  Future<void> setLocale(String locale) async {
    _locale = locale;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('locale', locale);
    notifyListeners();
  }

  Future<void> setNotifications(bool enabled) async {
    _notificationsEnabled = enabled;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool('notifications', enabled);
    notifyListeners();
  }

  Future<void> setSyncMinutes(int minutes) async {
    _syncMinutes = minutes;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setInt('syncMinutes', minutes);
    notifyListeners();
  }

  Future<void> setDeviceId(String? id) async {
    _deviceId = id;
    final prefs = await SharedPreferences.getInstance();
    if (id != null && id.isNotEmpty) {
      await prefs.setString('deviceId', id);
    } else {
      await prefs.remove('deviceId');
    }
    notifyListeners();
  }

  Future<void> setHeight(double? v) async {
    _height = v;
    final prefs = await SharedPreferences.getInstance();
    if (v != null) { await prefs.setDouble('height', v); } else { await prefs.remove('height'); }
    notifyListeners();
  }

  Future<void> setWeight(double? v) async {
    _weight = v;
    final prefs = await SharedPreferences.getInstance();
    if (v != null) { await prefs.setDouble('weight', v); } else { await prefs.remove('weight'); }
    notifyListeners();
  }

  Future<void> setAge(int? v) async {
    _age = v;
    final prefs = await SharedPreferences.getInstance();
    if (v != null) { await prefs.setInt('age', v); } else { await prefs.remove('age'); }
    notifyListeners();
  }

  Future<void> setEmergencyEmail(String? email) async {
    _emergencyEmail = email;
    final prefs = await SharedPreferences.getInstance();
    if (email != null && email.isNotEmpty) {
      await prefs.setString('emergencyEmail', email);
    } else {
      await prefs.remove('emergencyEmail');
    }
    notifyListeners();
  }

  String tr(String key) => isRussian ? (_ru[key] ?? key) : (_en[key] ?? key);

  static const Map<String, String> _ru = {
    'nav_dashboard': 'Главная',
    'nav_charts': 'Графики',
    'nav_ai': 'ИИ',
    'nav_settings': 'Настройки',
    'hello': 'Привет',
    'health_overview': 'Обзор здоровья',
    'tap_details': 'Нажмите для подробностей',
    'glucose': 'Глюкоза',
    'blood_glucose': 'Глюкоза в крови',
    'spo2': 'Кислород SpO2',
    'pulse': 'Пульс',
    'mg_dl': 'мг/дл',
    'bpm': 'уд/мин',
    'today_summary': 'СВОДКА ЗА ДЕНЬ',
    'readings_today': 'Показаний сегодня',
    'avg_glucose': 'Сред. глюкоза',
    'avg_pulse': 'Сред. пульс',
    'health_charts': 'Графики здоровья',
    'detailed_analytics': 'Детальная аналитика показателей',
    'diabetes_risk': 'Риск диабета',
    'view_charts': 'Подробные графики',
    'day': 'День',
    'week': 'Неделя',
    'month': 'Месяц',
    'average': 'Среднее',
    'minimum': 'Минимум',
    'maximum': 'Максимум',
    'statistics': 'СТАТИСТИКА',
    'diabetes_risk_title': 'Риск диабета',
    'risk_factors': 'ФАКТОРЫ РИСКА',
    'avg_glucose_level': 'Средний уровень глюкозы',
    'glucose_variability': 'Вариабельность глюкозы',
    'high_glucose_freq': 'Частота высокой глюкозы',
    'resting_pulse': 'Пульс в покое',
    'spo2_level': 'Уровень SpO2',
    'glucose_trend': 'ТРЕНД ГЛЮКОЗЫ',
    'disclaimer': 'Данные носят информационный характер и не являются медицинским диагнозом. Обратитесь к врачу для профессиональной оценки.',
    'risk_low': 'НИЗКИЙ РИСК',
    'risk_moderate': 'УМЕРЕННЫЙ РИСК',
    'risk_elevated': 'ПОВЫШЕННЫЙ РИСК',
    'risk_high': 'ВЫСОКИЙ РИСК',
    'ai_title': 'ИИ Консультант',
    'ai_subtitle': 'Здоровье • Аналитика',
    'ai_greeting': 'Здравствуйте! Я ваш ИИ-консультант по здоровью. Я имею доступ к вашим показателям и могу помочь разобраться в них. Что вас интересует?',
    'ai_hint': 'Задайте вопрос...',
    'ai_chip_glucose': '📊 Тренды глюкозы',
    'ai_chip_pulse': '❤️ Анализ пульса',
    'ai_chip_risk': '⚠️ Риск диабета',
    'ai_chip_tips': '💡 Советы по здоровью',
    'settings': 'Настройки',
    'general': 'ОСНОВНЫЕ',
    'language': 'Язык',
    'russian': 'Русский',
    'english': 'English',
    'notifications': 'Уведомления',
    'enabled': 'Включены',
    'disabled': 'Выключены',
    'device': 'УСТРОЙСТВО',
    'suguard_device': 'SuGuard Device',
    'connected': 'Подключено',
    'not_connected': 'Не подключено',
    'connect_device': 'Подключить устройство',
    'disconnect': 'Отключить',
    'device_id_hint': 'Введите Device ID (напр. SG-001)',
    'cancel': 'Отмена',
    'connect': 'Подключить',
    'sync_frequency': 'Частота синхронизации',
    'every_n_min': 'Каждые %d мин',
    'firmware': 'Прошивка',
    'about': 'О ПРОГРАММЕ',
    'app_version': 'Версия приложения',
    'privacy_policy': 'Политика конфиденциальности',
    'terms': 'Условия использования',
    'sign_out': 'Выйти',
    'sign_out_confirm': 'Вы уверены, что хотите выйти?',
    'profile': 'Профиль',
    'display_name': 'ОТОБРАЖАЕМОЕ ИМЯ',
    'email': 'ЭЛЕКТРОННАЯ ПОЧТА',
    'verified': 'Подтверждён',
    'save_changes': 'Сохранить',
    'saved': '✓ Сохранено',
    'user_id': 'ID пользователя',
    'biometrics': 'БИОМЕТРИЯ',
    'use_mmol': 'Глюкоза в ммоль/л',
    'unit_mmol': 'ммоль/л',
    'unit_mgdl': 'мг/дл',
    'height_cm': 'Рост (см)',
    'weight_kg': 'Вес (кг)',
    'age_years': 'Возраст',
    'bmi': 'ИМТ',
    'not_set': 'Не указано',
    'download_report': 'Скачать отчёт',
    'report_subtitle': 'TXT-отчёт для врача',
    'report_saved': 'Отчёт сохранён',
    'report_title': 'Медицинский отчёт SuGuard',
    'report_patient': 'Пациент',
    'report_date': 'Дата отчёта',
    'report_period': 'Период данных',
    'report_readings': 'Количество измерений',
    'report_risk_score': 'Оценка риска диабета',
    'needle_free': 'БЕЗЫГОЛЬНЫЙ МОНИТОРИНГ ГЛЮКОЗЫ',
    'no_data': 'Нет данных',
    'connect_device_hint': 'Подключите устройство SuGuard\nв настройках для отображения данных',
    'nav_food': 'Питание',
    'food_tracker': 'Трекер питания',
    'food_today': 'Приёмы пищи сегодня',
    'food_add_photo': 'Сфотографировать еду',
    'food_add_manual': 'Записать вручную',
    'food_description': 'Описание еды',
    'food_grams': 'Граммовка',
    'food_time': 'Время приёма',
    'food_calories': 'Ккал',
    'food_protein': 'Белки',
    'food_fat': 'Жиры',
    'food_carbs': 'Углеводы',
    'food_total_today': 'ИТОГО ЗА ДЕНЬ',
    'food_analyzing': 'Анализ еды...',
    'food_analysis_error': 'Не удалось проанализировать еду',
    'food_saved': 'Запись сохранена',
    'food_deleted': 'Запись удалена',
    'food_empty': 'Нет записей за сегодня',
    'food_empty_hint': 'Нажмите + чтобы добавить приём пищи',
    'food_photo_source': 'Источник фото',
    'food_camera': 'Камера',
    'food_gallery': 'Галерея',
    'food_g': 'г',
    'food_add': 'Добавить',
    'food_history': 'История',
    'emergency': 'БЕЗОПАСНОСТЬ',
    'emergency_email': 'Экстренный email',
    'emergency_email_hint': 'Email для экстренных уведомлений',
    'emergency_email_desc': 'Уведомление при высоком риске',
    'emergency_not_set': 'Не указан',
    'emergency_email_sent': 'Экстренное уведомление отправлено',
    'emergency_email_failed': 'Не удалось отправить уведомление',
    'save': 'Сохранить',
    'delete': 'Удалить',
  };

  static const Map<String, String> _en = {
    'nav_dashboard': 'Dashboard',
    'nav_charts': 'Charts',
    'nav_ai': 'AI',
    'nav_settings': 'Settings',
    'hello': 'Hello',
    'health_overview': 'Your health overview',
    'tap_details': 'Tap for details',
    'glucose': 'Glucose',
    'blood_glucose': 'Blood Glucose',
    'spo2': 'SpO2',
    'pulse': 'Pulse',
    'mg_dl': 'mg/dL',
    'bpm': 'bpm',
    'today_summary': 'TODAY\'S SUMMARY',
    'readings_today': 'Readings today',
    'avg_glucose': 'Avg Glucose',
    'avg_pulse': 'Avg Pulse',
    'health_charts': 'Health Charts',
    'detailed_analytics': 'Detailed analytics of your vitals',
    'diabetes_risk': 'Diabetes Risk',
    'view_charts': 'View detailed charts',
    'day': 'Day',
    'week': 'Week',
    'month': 'Month',
    'average': 'Average',
    'minimum': 'Minimum',
    'maximum': 'Maximum',
    'statistics': 'STATISTICS',
    'diabetes_risk_title': 'Diabetes Risk',
    'risk_factors': 'RISK FACTORS',
    'avg_glucose_level': 'Average Glucose Level',
    'glucose_variability': 'Glucose Variability',
    'high_glucose_freq': 'High Glucose Frequency',
    'resting_pulse': 'Resting Pulse',
    'spo2_level': 'SpO2 Level',
    'glucose_trend': 'GLUCOSE TREND',
    'disclaimer': 'This data is for informational purposes only and does not constitute a medical diagnosis. Consult a doctor for professional evaluation.',
    'risk_low': 'LOW RISK',
    'risk_moderate': 'MODERATE RISK',
    'risk_elevated': 'ELEVATED RISK',
    'risk_high': 'HIGH RISK',
    'ai_title': 'AI Consultant',
    'ai_subtitle': 'Health • Analytics',
    'ai_greeting': 'Hello! I\'m your AI health consultant. I have access to your health data and can help you understand it. What would you like to know?',
    'ai_hint': 'Ask a question...',
    'ai_chip_glucose': '📊 Glucose trends',
    'ai_chip_pulse': '❤️ Pulse analysis',
    'ai_chip_risk': '⚠️ Diabetes risk',
    'ai_chip_tips': '💡 Health tips',
    'settings': 'Settings',
    'general': 'GENERAL',
    'language': 'Language',
    'russian': 'Русский',
    'english': 'English',
    'notifications': 'Notifications',
    'enabled': 'Enabled',
    'disabled': 'Disabled',
    'device': 'DEVICE',
    'suguard_device': 'SuGuard Device',
    'connected': 'Connected',
    'not_connected': 'Not connected',
    'connect_device': 'Connect Device',
    'disconnect': 'Disconnect',
    'device_id_hint': 'Enter Device ID (e.g. SG-001)',
    'cancel': 'Cancel',
    'connect': 'Connect',
    'sync_frequency': 'Sync Frequency',
    'every_n_min': 'Every %d min',
    'firmware': 'Firmware',
    'about': 'ABOUT',
    'app_version': 'App Version',
    'privacy_policy': 'Privacy Policy',
    'terms': 'Terms of Service',
    'sign_out': 'Sign Out',
    'sign_out_confirm': 'Are you sure you want to sign out?',
    'profile': 'Profile',
    'display_name': 'DISPLAY NAME',
    'email': 'EMAIL',
    'verified': 'Verified',
    'save_changes': 'Save Changes',
    'saved': '✓ Saved',
    'user_id': 'User ID',
    'biometrics': 'BIOMETRICS',
    'use_mmol': 'Glucose in mmol/L',
    'unit_mmol': 'mmol/L',
    'unit_mgdl': 'mg/dL',
    'height_cm': 'Height (cm)',
    'weight_kg': 'Weight (kg)',
    'age_years': 'Age',
    'bmi': 'BMI',
    'not_set': 'Not set',
    'download_report': 'Download Report',
    'report_subtitle': 'TXT report for doctor',
    'report_saved': 'Report saved',
    'report_title': 'SuGuard Medical Report',
    'report_patient': 'Patient',
    'report_date': 'Report Date',
    'report_period': 'Data Period',
    'report_readings': 'Number of Readings',
    'report_risk_score': 'Diabetes Risk Score',
    'needle_free': 'NEEDLE-FREE GLUCOSE MONITORING',
    'no_data': 'No data available',
    'connect_device_hint': 'Connect your SuGuard device\nin Settings to see health data',
    'nav_food': 'Food',
    'food_tracker': 'Food Tracker',
    'food_today': 'Today\'s meals',
    'food_add_photo': 'Take food photo',
    'food_add_manual': 'Enter manually',
    'food_description': 'Food description',
    'food_grams': 'Portion (grams)',
    'food_time': 'Meal time',
    'food_calories': 'Kcal',
    'food_protein': 'Protein',
    'food_fat': 'Fat',
    'food_carbs': 'Carbs',
    'food_total_today': 'TODAY\'S TOTAL',
    'food_analyzing': 'Analyzing food...',
    'food_analysis_error': 'Failed to analyze food',
    'food_saved': 'Entry saved',
    'food_deleted': 'Entry deleted',
    'food_empty': 'No entries today',
    'food_empty_hint': 'Tap + to add a meal',
    'food_photo_source': 'Photo source',
    'food_camera': 'Camera',
    'food_gallery': 'Gallery',
    'food_g': 'g',
    'food_add': 'Add',
    'food_history': 'History',
    'emergency': 'SAFETY',
    'emergency_email': 'Emergency email',
    'emergency_email_hint': 'Email for emergency notifications',
    'emergency_email_desc': 'Notification on high risk',
    'emergency_not_set': 'Not set',
    'emergency_email_sent': 'Emergency notification sent',
    'emergency_email_failed': 'Failed to send notification',
    'save': 'Save',
    'delete': 'Delete',
  };
}
