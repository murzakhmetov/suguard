import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:flutter_dotenv/flutter_dotenv.dart';

class GeminiFoodService {
  static String get _apiKey => dotenv.env['GEMINI_API_KEY'] ?? '';
  static const String _model = 'gemini-3.1-flash-lite';
  static const String _baseUrl =
      'https://generativelanguage.googleapis.com/v1beta/models';

  static Future<Map<String, dynamic>?> analyzeFoodPhoto(
      String base64Image) async {
    const systemPrompt =
        'You are a professional nutritionist AI. Analyze the food in the image. '
        'You MUST respond with ONLY a valid JSON object, no extra text. '
        'Format: {"description": "краткое описание блюда на русском", "calories": 350, "protein": 25.0, "fat": 12.0, "carbs": 40.0} '
        'Rules: description: short name of the dish in Russian, calories: estimated total kcal (number), '
        'protein: grams of protein (number), fat: grams of fat (number), carbs: grams of carbohydrates (number). '
        'Be as accurate as possible based on visual portion size. Respond ONLY with JSON, no markdown, no explanation.';

    final url = Uri.parse('$_baseUrl/$_model:generateContent?key=$_apiKey');

    try {
      final response = await http.post(
        url,
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'contents': [
            {
              'parts': [
                {'text': systemPrompt},
                {
                  'inline_data': {
                    'mime_type': 'image/jpeg',
                    'data': base64Image,
                  }
                }
              ]
            }
          ],
          'generationConfig': {
            'temperature': 0.3,
            'maxOutputTokens': 512,
          }
        }),
      );

      final data = jsonDecode(response.body);

      if (response.statusCode == 200) {
        final content =
            data['candidates'][0]['content']['parts'][0]['text'] as String;
        return _parseNutritionJson(content);
      } else {
        final errMsg = data['error']?['message'] as String?;
        throw Exception(errMsg ?? 'Gemini API Error ${response.statusCode}');
      }
    } catch (e) {
      throw Exception('Food analysis failed: $e');
    }
  }

  static Map<String, dynamic>? _parseNutritionJson(String raw) {
    try {
      var cleaned = raw.trim();
      if (cleaned.startsWith('```')) {
        cleaned = cleaned.replaceFirst(RegExp(r'^```\w*\n?'), '');
        cleaned = cleaned.replaceFirst(RegExp(r'\n?```$'), '');
        cleaned = cleaned.trim();
      }
      final map = jsonDecode(cleaned) as Map<String, dynamic>;
      return {
        'description': map['description']?.toString() ?? 'Еда',
        'calories': (map['calories'] as num?)?.toDouble() ?? 0,
        'protein': (map['protein'] as num?)?.toDouble() ?? 0,
        'fat': (map['fat'] as num?)?.toDouble() ?? 0,
        'carbs': (map['carbs'] as num?)?.toDouble() ?? 0,
      };
    } catch (_) {
      return null;
    }
  }
}
