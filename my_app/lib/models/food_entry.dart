class FoodEntry {
  final String id;
  final DateTime timestamp;
  final String description;
  final double calories;
  final double protein;
  final double fat;
  final double carbs;
  final String source; 

  FoodEntry({
    required this.id,
    required this.timestamp,
    required this.description,
    required this.calories,
    required this.protein,
    required this.fat,
    required this.carbs,
    required this.source,
  });

  Map<String, dynamic> toJson() => {
        'id': id,
        'timestamp': timestamp.toIso8601String(),
        'description': description,
        'calories': calories,
        'protein': protein,
        'fat': fat,
        'carbs': carbs,
        'source': source,
      };

  factory FoodEntry.fromJson(Map<String, dynamic> json) => FoodEntry(
        id: json['id'] ?? '',
        timestamp: DateTime.parse(json['timestamp']),
        description: json['description'] ?? '',
        calories: (json['calories'] as num?)?.toDouble() ?? 0,
        protein: (json['protein'] as num?)?.toDouble() ?? 0,
        fat: (json['fat'] as num?)?.toDouble() ?? 0,
        carbs: (json['carbs'] as num?)?.toDouble() ?? 0,
        source: json['source'] ?? 'manual',
      );

  double get totalMacros => protein + fat + carbs;
}
