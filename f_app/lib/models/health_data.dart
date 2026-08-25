class HealthData {
  final String id;
  final DateTime timestamp;
  final double spo2;
  final double pulse;
  final double glucose;

  HealthData({
    required this.id,
    required this.timestamp,
    required this.spo2,
    required this.pulse,
    required this.glucose,
  });

  Map<String, dynamic> toJson() => {
        'id': id,
        'timestamp': timestamp.toIso8601String(),
        'spo2': spo2,
        'pulse': pulse,
        'glucose': glucose,
      };

  factory HealthData.fromJson(Map<String, dynamic> json) => HealthData(
        id: json['id'] ?? '',
        timestamp: DateTime.parse(json['timestamp']),
        spo2: (json['spo2'] as num).toDouble(),
        pulse: (json['pulse'] as num).toDouble(),
        glucose: (json['glucose'] as num).toDouble(),
      );
}
