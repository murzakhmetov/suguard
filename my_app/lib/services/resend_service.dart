import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:flutter_dotenv/flutter_dotenv.dart';

class ResendService {
  static String get _apiKey => dotenv.env['RESEND_API_KEY'] ?? '';
  static const String _baseUrl = 'https://api.resend.com/emails';

  static Future<bool> sendEmergencyEmail({
    required String toEmail,
    required String userName,
    required double riskPercent,
    required String healthSummary,
  }) async {
    try {
      final riskLevel = riskPercent >= 70
          ? 'ВЫСОКИЙ'
          : riskPercent >= 50
              ? 'ПОВЫШЕННЫЙ'
              : 'УМЕРЕННЫЙ';

      final htmlBody = '''
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0a0a0a; color: #ffffff; padding: 40px 20px;">
  <div style="max-width: 600px; margin: 0 auto; background: #1a1a1a; border-radius: 20px; padding: 40px; border: 1px solid #333;">
    <div style="text-align: center; margin-bottom: 30px;">
      <div style="display: inline-block; background: linear-gradient(135deg, #FF006E, #FF4444); color: white; padding: 8px 20px; border-radius: 20px; font-size: 12px; font-weight: 700; letter-spacing: 2px;">
        ⚠️ ЭКСТРЕННОЕ УВЕДОМЛЕНИЕ
      </div>
    </div>
    
    <h1 style="color: #FF006E; font-size: 24px; text-align: center; margin-bottom: 10px;">
      Обнаружен $riskLevel риск
    </h1>
    
    <p style="color: #8a8a8a; text-align: center; font-size: 14px; margin-bottom: 30px;">
      Приложение SuGuard обнаружило тревожные показатели здоровья
    </p>
    
    <div style="background: #2a2a2a; border-radius: 16px; padding: 24px; margin-bottom: 24px;">
      <table style="width: 100%; border-collapse: collapse;">
        <tr>
          <td style="color: #8a8a8a; padding: 8px 0; font-size: 14px;">Пациент</td>
          <td style="color: #fff; padding: 8px 0; text-align: right; font-weight: 600;">$userName</td>
        </tr>
        <tr>
          <td style="color: #8a8a8a; padding: 8px 0; font-size: 14px;">Уровень риска</td>
          <td style="color: #FF006E; padding: 8px 0; text-align: right; font-weight: 700;">${riskPercent.toStringAsFixed(0)}%</td>
        </tr>
      </table>
    </div>
    
    <div style="background: #2a2a2a; border-radius: 16px; padding: 24px; margin-bottom: 24px;">
      <p style="color: #8a8a8a; font-size: 12px; text-transform: uppercase; letter-spacing: 2px; margin-bottom: 12px;">Показатели здоровья</p>
      <p style="color: #fff; font-size: 14px; line-height: 1.8; white-space: pre-line;">$healthSummary</p>
    </div>
    
    <div style="background: rgba(255, 0, 110, 0.1); border: 1px solid rgba(255, 0, 110, 0.3); border-radius: 12px; padding: 16px; margin-bottom: 24px;">
      <p style="color: #FF006E; font-size: 13px; margin: 0;">
        ⚡ Рекомендуется немедленно связаться с пациентом и при необходимости обратиться к врачу.
      </p>
    </div>
    
    <p style="color: #555; font-size: 11px; text-align: center;">
      Это автоматическое уведомление от приложения SuGuard.<br>
      Данные носят информационный характер и не являются медицинским диагнозом.
    </p>
  </div>
</body>
</html>
''';

      final response = await http.post(
        Uri.parse(_baseUrl),
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer $_apiKey',
        },
        body: jsonEncode({
          'from': 'SuGuard Alert <onboarding@resend.dev>',
          'to': [toEmail],
          'subject': '⚠️ SuGuard: $riskLevel риск у пациента $userName',
          'html': htmlBody,
        }),
      );

      return response.statusCode == 200 || response.statusCode == 201;
    } catch (e) {
      return false;
    }
  }
}
