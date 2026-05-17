import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:my_app/theme/app_theme.dart';
import 'package:my_app/models/health_data.dart';
import 'package:my_app/models/chat_message.dart';
import 'package:my_app/services/groq_service.dart';
import 'package:my_app/services/health_service.dart';
import 'package:my_app/services/app_settings.dart';
import 'package:my_app/services/firebase_service.dart';
import 'package:my_app/widgets/chat_bubble.dart';

class AiChatScreen extends StatefulWidget {
  final List<HealthData> healthData;
  const AiChatScreen({super.key, required this.healthData});

  @override
  State<AiChatScreen> createState() => _AiChatScreenState();
}

class _AiChatScreenState extends State<AiChatScreen> {
  final _controller = TextEditingController();
  final _scrollController = ScrollController();
  final List<ChatMessage> _messages = [];
  bool _isTyping = false;
  final _s = AppSettings();

  String _tr(String k) => _s.tr(k);

  @override
  void initState() {
    super.initState();
    _messages.add(ChatMessage(
      role: 'assistant',
      content: _tr('ai_greeting'),
      timestamp: DateTime.now(),
    ));
  }

  @override
  void dispose() {
    _controller.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  Future<void> _send(String text) async {
    if (text.trim().isEmpty) return;
    _controller.clear();

    setState(() {
      _messages.add(ChatMessage(
        role: 'user',
        content: text.trim(),
        timestamp: DateTime.now(),
      ));
      _isTyping = true;
    });
    _scrollToBottom();

    try {
      final chatMessages = _messages
          .map((m) => {'role': m.role, 'content': m.content})
          .toList();
      var statsSummary =
          HealthService.buildStatsSummary(widget.healthData);

      final allFood = await FirebaseService.getFoodLog();
      if (allFood.isNotEmpty) {
        statsSummary += "\n\nFood Log (Past entries):\n";
        for (var e in allFood) {
          final dateStr = DateFormat('yyyy-MM-dd HH:mm').format(e.timestamp);
          statsSummary += "- [$dateStr] ${e.description} (${e.calories.toStringAsFixed(0)} kcal, P:${e.protein.toStringAsFixed(0)}g, F:${e.fat.toStringAsFixed(0)}g, C:${e.carbs.toStringAsFixed(0)}g)\n";
        }
      }

      final response = await GroqService.chat(
        messages: chatMessages,
        healthStatsSummary: statsSummary,
      );
      if (!mounted) return;
      setState(() {
        _messages.add(ChatMessage(
          role: 'assistant',
          content: response,
          timestamp: DateTime.now(),
        ));
        _isTyping = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _messages.add(ChatMessage(
          role: 'assistant',
          content: _s.isRussian
              ? 'Извините, произошла ошибка. Попробуйте позже.'
              : 'Sorry, an error occurred. Please try again later.',
          timestamp: DateTime.now(),
        ));
        _isTyping = false;
      });
    }
    _scrollToBottom();
  }

  void _scrollToBottom() {
    Future.delayed(const Duration(milliseconds: 100), () {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeOut,
        );
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final chips = [
      _tr('ai_chip_glucose'),
      _tr('ai_chip_pulse'),
      _tr('ai_chip_risk'),
      _tr('ai_chip_tips'),
    ];
    final timeFormat = DateFormat('HH:mm');

    return SafeArea(
      child: Column(
        children: [
          Padding(
            padding: const EdgeInsets.all(20),
            child: Row(
              children: [
                Container(
                  width: 44,
                  height: 44,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    gradient: AppTheme.accentGradient,
                  ),
                  child: const Icon(Icons.smart_toy_rounded,
                      color: Colors.black, size: 22),
                ),
                const SizedBox(width: 14),
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      _tr('ai_title'),
                      style: const TextStyle(
                        color: AppTheme.textPrimary,
                        fontSize: 18,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    Text(
                      _tr('ai_subtitle'),
                      style: const TextStyle(
                        color: AppTheme.accent,
                        fontSize: 12,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),

          Expanded(
            child: ListView.builder(
              controller: _scrollController,
              padding: const EdgeInsets.symmetric(horizontal: 16),
              itemCount: _messages.length + (_isTyping ? 1 : 0),
              itemBuilder: (context, index) {
                if (index == _messages.length && _isTyping) {
                  return Padding(
                    padding: const EdgeInsets.symmetric(vertical: 8),
                    child: Row(
                      children: [
                        Container(
                          padding: const EdgeInsets.symmetric(
                              horizontal: 16, vertical: 12),
                          decoration: BoxDecoration(
                            color: AppTheme.surface,
                            borderRadius: BorderRadius.circular(16),
                          ),
                          child: Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              _dot(0),
                              const SizedBox(width: 4),
                              _dot(1),
                              const SizedBox(width: 4),
                              _dot(2),
                            ],
                          ),
                        ),
                      ],
                    ),
                  );
                }
                final msg = _messages[index];
                return ChatBubble(
                  message: msg.content,
                  isUser: msg.role == 'user',
                  time: timeFormat.format(msg.timestamp),
                );
              },
            ),
          ),

          if (_messages.length <= 2)
            SizedBox(
              height: 44,
              child: ListView(
                scrollDirection: Axis.horizontal,
                padding: const EdgeInsets.symmetric(horizontal: 16),
                children: chips.map((chip) {
                  return Padding(
                    padding: const EdgeInsets.only(right: 8),
                    child: GestureDetector(
                      onTap: () => _send(chip),
                      child: Container(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 16, vertical: 10),
                        decoration: BoxDecoration(
                          color: AppTheme.surface,
                          borderRadius: BorderRadius.circular(20),
                          border: Border.all(
                              color: AppTheme.cardBorder, width: 0.5),
                        ),
                        child: Text(
                          chip,
                          style: const TextStyle(
                            color: AppTheme.textSecondary,
                            fontSize: 13,
                          ),
                        ),
                      ),
                    ),
                  );
                }).toList(),
              ),
            ),

          Container(
            padding: const EdgeInsets.all(16),
            decoration: const BoxDecoration(
              border: Border(
                top: BorderSide(color: AppTheme.cardBorder, width: 0.5),
              ),
            ),
            child: Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _controller,
                    style: const TextStyle(
                        color: AppTheme.textPrimary, fontSize: 14),
                    decoration: InputDecoration(
                      hintText: _tr('ai_hint'),
                      contentPadding: const EdgeInsets.symmetric(
                          horizontal: 20, vertical: 12),
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(24),
                        borderSide: const BorderSide(
                            color: AppTheme.cardBorder, width: 0.5),
                      ),
                      enabledBorder: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(24),
                        borderSide: const BorderSide(
                            color: AppTheme.cardBorder, width: 0.5),
                      ),
                      focusedBorder: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(24),
                        borderSide:
                            const BorderSide(color: AppTheme.accent),
                      ),
                      filled: true,
                      fillColor: AppTheme.surface,
                    ),
                    onSubmitted: _send,
                  ),
                ),
                const SizedBox(width: 12),
                GestureDetector(
                  onTap: () => _send(_controller.text),
                  child: Container(
                    width: 44,
                    height: 44,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      gradient: AppTheme.accentGradient,
                    ),
                    child: const Icon(Icons.send_rounded,
                        color: Colors.black, size: 20),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _dot(int i) {
    return TweenAnimationBuilder<double>(
      tween: Tween(begin: 0.3, end: 1.0),
      duration: Duration(milliseconds: 600 + i * 200),
      builder: (context, value, child) {
        return Opacity(
          opacity: value,
          child: Container(
            width: 8,
            height: 8,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: AppTheme.accent.withValues(alpha: value),
            ),
          ),
        );
      },
    );
  }
}
