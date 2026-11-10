import 'package:flutter_test/flutter_test.dart';
import 'package:my_app/services/nutrition_parser.dart';

void main() {
  group('parseNutritionJson', () {
    test('parses plain JSON', () {
      final r = parseNutritionJson(
          '{"description": "Борщ", "calories": 350, "protein": 12.5, "fat": 8, "carbs": 40}');
      expect(r, {
        'description': 'Борщ',
        'calories': 350.0,
        'protein': 12.5,
        'fat': 8.0,
        'carbs': 40.0,
      });
    });

    test('strips a Markdown code fence and defaults missing fields', () {
      final r = parseNutritionJson('```json\n{"calories": 100}\n```');
      expect(r, isNotNull);
      expect(r!['description'], 'Еда');
      expect(r['calories'], 100.0);
      expect(r['protein'], 0);
    });

    test('returns null on invalid input', () {
      expect(parseNutritionJson('not json'), isNull);
      expect(parseNutritionJson('[1, 2]'), isNull);
    });
  });
}
