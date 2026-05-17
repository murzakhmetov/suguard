import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import 'package:my_app/models/health_data.dart';
import 'package:my_app/models/food_entry.dart';
import 'package:my_app/services/health_service.dart';

class FirebaseService {
  static const String _dbUrl =
      'https://suguard-7f535-default-rtdb.asia-southeast1.firebasedatabase.app';

  static String? _currentUid;
  static String? _currentName;
  static String? _currentEmail;

  static Future<Map<String, dynamic>?> fetchLiveData() async {
    try {
      final response = await http.get(Uri.parse('$_dbUrl/data.json'));
      if (response.statusCode == 200 && response.body != 'null') {
        final data = json.decode(response.body) as Map<String, dynamic>;
        return {
          'glucose_mgdl': (data['glucose_mgdl'] as num?)?.toDouble() ?? 0.0,
          'glucose_mmol': (data['glucose_mmol'] as num?)?.toDouble() ?? 0.0,
          'pulse': (data['bpm'] as num?)?.toDouble() ?? 0.0,
          'spo2': (data['spo2'] as num?)?.toDouble() ?? 98.0,
          'timestamp': data['timestamp'] as String?,
        };
      }
    } catch (e) {
    }
    return null;
  }


  static bool get isLoggedIn => _currentUid != null;
  static String? get uid => _currentUid;
  static String? get displayName => _currentName;
  static String? get email => _currentEmail;

  static Future<void> loadSession() async {
    final prefs = await SharedPreferences.getInstance();
    _currentUid = prefs.getString('uid');
    _currentName = prefs.getString('name');
    _currentEmail = prefs.getString('email');
  }

  static Future<void> _saveSession() async {
    final prefs = await SharedPreferences.getInstance();
    if (_currentUid != null) {
      await prefs.setString('uid', _currentUid!);
      await prefs.setString('name', _currentName ?? '');
      await prefs.setString('email', _currentEmail ?? '');
    }
  }


  static Future<void> register({
    required String email,
    required String password,
    required String name,
  }) async {
    final uid = _emailToUid(email);

    final checkUrl = Uri.parse('$_dbUrl/users/$uid/profile.json');
    final checkResp = await http.get(checkUrl);
    if (checkResp.statusCode == 200 && checkResp.body != 'null') {
      throw Exception('email-already-in-use');
    }

    final profileUrl = Uri.parse('$_dbUrl/users/$uid/profile.json');
    final profileResp = await http.put(
      profileUrl,
      body: jsonEncode({
        'name': name,
        'email': email,
        'password': _hashPassword(password),
        'createdAt': DateTime.now().toIso8601String(),
      }),
    );

    if (profileResp.statusCode != 200) {
      throw Exception('Registration failed');
    }

    _currentUid = uid;
    _currentName = name;
    _currentEmail = email;
    await _saveSession();

    await _generateInitialData(uid);
  }

  static Future<void> login({
    required String email,
    required String password,
  }) async {
    final uid = _emailToUid(email);

    final url = Uri.parse('$_dbUrl/users/$uid/profile.json');
    final resp = await http.get(url);

    if (resp.statusCode != 200 || resp.body == 'null') {
      throw Exception('User not found');
    }

    final profile = jsonDecode(resp.body) as Map<String, dynamic>;
    final storedHash = profile['password'] as String?;

    if (storedHash != _hashPassword(password)) {
      throw Exception('Invalid password');
    }

    _currentUid = uid;
    _currentName = profile['name'] as String? ?? '';
    _currentEmail = email;
    await _saveSession();
  }

  static Future<void> logout() async {
    _currentUid = null;
    _currentName = null;
    _currentEmail = null;
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove('uid');
    await prefs.remove('name');
    await prefs.remove('email');
  }


  static Future<void> _generateInitialData(String uid) async {
    final now = DateTime.now();
    final monthAgo = now.subtract(const Duration(days: 30));
    final data = HealthService.generateData(
      start: monthAgo,
      end: now,
      interval: const Duration(minutes: 30),
    );

    final batch = <String, dynamic>{};
    for (final d in data) {
      batch[d.id] = d.toJson();
    }

    final url = Uri.parse('$_dbUrl/users/$uid/healthData.json');
    await http.put(url, body: jsonEncode(batch));
  }

  static Future<List<HealthData>> getHealthData({
    DateTime? from,
    DateTime? to,
  }) async {
    if (_currentUid == null) return [];

    final url = Uri.parse('$_dbUrl/users/$_currentUid/healthData.json');
    final resp = await http.get(url);

    if (resp.statusCode != 200 || resp.body == 'null') return [];

    final map = jsonDecode(resp.body) as Map<String, dynamic>;
    final list = map.values
        .map((v) => HealthData.fromJson(Map<String, dynamic>.from(v as Map)))
        .toList();

    list.sort((a, b) => a.timestamp.compareTo(b.timestamp));

    if (from != null) {
      list.removeWhere((d) => d.timestamp.isBefore(from));
    }
    if (to != null) {
      list.removeWhere((d) => d.timestamp.isAfter(to));
    }

    return list;
  }

  static Future<void> saveHealthData(HealthData data) async {
    if (_currentUid == null) return;
    final url =
        Uri.parse('$_dbUrl/users/$_currentUid/healthData/${data.id}.json');
    await http.put(url, body: jsonEncode(data.toJson()));
  }


  static Future<Map<String, dynamic>?> getUserProfile() async {
    if (_currentUid == null) return null;
    final url = Uri.parse('$_dbUrl/users/$_currentUid/profile.json');
    final resp = await http.get(url);
    if (resp.statusCode != 200 || resp.body == 'null') return null;
    return jsonDecode(resp.body) as Map<String, dynamic>;
  }

  static Future<void> updateProfile(Map<String, dynamic> data) async {
    if (_currentUid == null) return;
    final url = Uri.parse('$_dbUrl/users/$_currentUid/profile.json');
    await http.patch(url, body: jsonEncode(data));
    if (data.containsKey('name')) {
      _currentName = data['name'] as String;
      await _saveSession();
    }
  }


  static Future<void> saveFoodEntry(FoodEntry entry) async {
    if (_currentUid == null) return;
    final url =
        Uri.parse('$_dbUrl/users/$_currentUid/foodLog/${entry.id}.json');
    await http.put(url, body: jsonEncode(entry.toJson()));
  }

  static Future<List<FoodEntry>> getFoodLog({DateTime? date}) async {
    if (_currentUid == null) return [];

    final url = Uri.parse('$_dbUrl/users/$_currentUid/foodLog.json');
    final resp = await http.get(url);

    if (resp.statusCode != 200 || resp.body == 'null') return [];

    final map = jsonDecode(resp.body) as Map<String, dynamic>;
    final list = map.values
        .map((v) => FoodEntry.fromJson(Map<String, dynamic>.from(v as Map)))
        .toList();

    list.sort((a, b) => b.timestamp.compareTo(a.timestamp));

    if (date != null) {
      final dayStart = DateTime(date.year, date.month, date.day);
      final dayEnd = dayStart.add(const Duration(days: 1));
      list.removeWhere(
          (e) => e.timestamp.isBefore(dayStart) || e.timestamp.isAfter(dayEnd));
    }

    return list;
  }

  static Future<void> deleteFoodEntry(String id) async {
    if (_currentUid == null) return;
    final url = Uri.parse('$_dbUrl/users/$_currentUid/foodLog/$id.json');
    await http.delete(url);
  }


  static Future<void> saveEmergencyEmail(String email) async {
    if (_currentUid == null) return;
    final url = Uri.parse('$_dbUrl/users/$_currentUid/profile.json');
    await http.patch(url, body: jsonEncode({'emergencyEmail': email}));
  }

  static Future<String?> getEmergencyEmail() async {
    if (_currentUid == null) return null;
    final profile = await getUserProfile();
    return profile?['emergencyEmail'] as String?;
  }


  static String _emailToUid(String email) {
    return email
        .toLowerCase()
        .trim()
        .replaceAll('.', '_dot_')
        .replaceAll('@', '_at_');
  }

  static String _hashPassword(String password) {
    final salted = 'suguard_${password}_salt2024';
    return base64Encode(utf8.encode(salted));
  }
}
