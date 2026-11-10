import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:my_app/config/env.dart';
import 'package:my_app/services/nutrition_parser.dart';

class GroqService {
  static const String _apiKey = Env.groqApiKey;
  static const String _baseUrl =
      'https://api.groq.com/openai/v1/chat/completions';
  static const String _model = 'llama-3.3-70b-versatile';

  static Future<String> chat({
    required List<Map<String, String>> messages,
    required String healthStatsSummary,
  }) async {
    final systemPrompt = '''
You are SuGuard AI Health Consultant  a friendly, knowledgeable health assistant built into the SuGuard glucose monitoring app. 
You have access to the user's real-time health statistics from their SuGuard device.

$healthStatsSummary

IMPORTANT GUIDELINES:
- You are NOT a doctor. Always recommend consulting a healthcare professional for medical decisions.
- Provide helpful, evidence-based health insights based on the user's data.
- Explain trends in their SpO2, pulse, and blood glucose data.
- Offer lifestyle tips (diet, exercise, sleep) to help maintain healthy levels.
- If their diabetes risk is elevated, explain contributing factors and prevention strategies.
- Be empathetic, supportive, and encouraging.
- Keep responses concise but informative.
- Use emojis sparingly for friendliness.
- Answer in the same language the user writes to you.
''';

    final allMessages = [
      {'role': 'system', 'content': systemPrompt},
      ...messages,
    ];

    try {
      final response = await http.post(
        Uri.parse(_baseUrl),
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer $_apiKey',
        },
        body: jsonEncode({
          'model': _model,
          'messages': allMessages,
          'temperature': 0.7,
          'max_tokens': 1024,
        }),
      );

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        return data['choices'][0]['message']['content'] as String;
      } else {
        return 'Sorry, I encountered an error. Please try again. (${response.statusCode})';
      }
    } catch (e) {
      return 'Unable to connect to AI service. Please check your internet connection.';
    }
  }

  static Future<Map<String, dynamic>?> analyzeFoodText({
    required String foodDescription,
    required String grams,
  }) async {
    final systemPrompt = '''
You are a professional nutritionist AI. The user describes what they ate and the portion size.
You MUST respond with ONLY a valid JSON object, no extra text.
Format:
{"description": "краткое описание блюда на русском", "calories": 350, "protein": 25.0, "fat": 12.0, "carbs": 40.0}

Rules:
- description: short summary of what was eaten in Russian
- calories: estimated total kcal for the given portion (number)
- protein: grams of protein (number)
- fat: grams of fat (number)
- carbs: grams of carbohydrates (number)
- Calculate based on the portion size provided
- Respond ONLY with JSON, no markdown, no explanation
''';

    try {
      final response = await http.post(
        Uri.parse(_baseUrl),
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer $_apiKey',
        },
        body: jsonEncode({
          'model': _model,
          'messages': [
            {'role': 'system', 'content': systemPrompt},
            {
              'role': 'user',
              'content': 'Еда: $foodDescription\nПорция: $grams грамм',
            },
          ],
          'temperature': 0.3,
          'max_tokens': 512,
        }),
      );

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        final content = data['choices'][0]['message']['content'] as String;
        return parseNutritionJson(content);
      }
    } catch (e) {
    }
    return null;
  }
}
