import 'dart:convert';

/// Parses the nutrition JSON returned by the food-analysis models (Groq and
/// Gemini), tolerating a surrounding Markdown code fence.
///
/// Returns a map with `description`, `calories`, `protein`, `fat` and
/// `carbs` (missing numbers default to 0), or `null` if [raw] is not a JSON
/// object of the expected shape.
Map<String, dynamic>? parseNutritionJson(String raw) {
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
