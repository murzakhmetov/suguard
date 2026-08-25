import 'package:flutter/material.dart';
import 'package:f_app/theme/app_theme.dart';
import 'package:f_app/services/firebase_service.dart';
import 'package:f_app/services/app_settings.dart';
import 'package:f_app/screens/login_screen.dart';
import 'package:f_app/screens/profile_screen.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  final _settings = AppSettings();

  @override
  void initState() {
    super.initState();
    _settings.addListener(_onSettingsChanged);
  }

  @override
  void dispose() {
    _settings.removeListener(_onSettingsChanged);
    super.dispose();
  }

  void _onSettingsChanged() {
    if (mounted) setState(() {});
  }

  String _tr(String key) => _settings.tr(key);

  @override
  Widget build(BuildContext context) {
    final name = FirebaseService.displayName ?? 'User';
    final userEmail = FirebaseService.email ?? '';

    return SafeArea(
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              _tr('settings'),
              style: const TextStyle(
                color: AppTheme.textPrimary,
                fontSize: 28,
                fontWeight: FontWeight.w800,
                letterSpacing: -0.5,
              ),
            ),
            const SizedBox(height: 28),

            GestureDetector(
              onTap: () => Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => const ProfileScreen()),
              ),
              child: Container(
                padding: const EdgeInsets.all(20),
                decoration: BoxDecoration(
                  color: AppTheme.surface,
                  borderRadius: BorderRadius.circular(20),
                  border: Border.all(color: AppTheme.cardBorder, width: 0.5),
                ),
                child: Row(
                  children: [
                    Container(
                      width: 56,
                      height: 56,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        gradient: AppTheme.accentGradient,
                      ),
                      child: Center(
                        child: Text(
                          name.isNotEmpty ? name[0].toUpperCase() : 'U',
                          style: const TextStyle(
                            color: Colors.black,
                            fontSize: 24,
                            fontWeight: FontWeight.w800,
                          ),
                        ),
                      ),
                    ),
                    const SizedBox(width: 16),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            name,
                            style: const TextStyle(
                              color: AppTheme.textPrimary,
                              fontSize: 18,
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                          const SizedBox(height: 2),
                          Text(
                            userEmail,
                            style: const TextStyle(
                              color: AppTheme.textSecondary,
                              fontSize: 13,
                            ),
                          ),
                        ],
                      ),
                    ),
                    const Icon(Icons.chevron_right,
                        color: AppTheme.textTertiary),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 28),

            _sectionTitle(_tr('general')),
            const SizedBox(height: 12),
            _settingsGroup([
              _settingsTile(
                _tr('language'),
                _settings.isRussian ? _tr('russian') : _tr('english'),
                Icons.language_rounded,
                () => _showLanguagePicker(),
              ),
              _toggleTile(
                _tr('notifications'),
                _settings.notificationsEnabled
                    ? _tr('enabled')
                    : _tr('disabled'),
                Icons.notifications_none_rounded,
                _settings.notificationsEnabled,
                (val) => _settings.setNotifications(val),
              ),
              _toggleTile(
                _tr('use_mmol'),
                _settings.useMmol ? _tr('unit_mmol') : _tr('unit_mgdl'),
                Icons.bloodtype_rounded,
                _settings.useMmol,
                (val) => _settings.setUseMmol(val),
              ),
            ]),
            const SizedBox(height: 24),

            _sectionTitle(_tr('device')),
            const SizedBox(height: 12),
            _settingsGroup([
              _settingsTile(
                _tr('suguard_device'),
                _settings.isDeviceConnected
                    ? '${_tr('connected')} (${_settings.deviceId})'
                    : _tr('not_connected'),
                Icons.bluetooth_connected_rounded,
                () => _showDeviceDialog(),
                trailing: _settings.isDeviceConnected
                    ? Container(
                        width: 8,
                        height: 8,
                        decoration: const BoxDecoration(
                          shape: BoxShape.circle,
                          color: AppTheme.accent,
                        ),
                      )
                    : null,
              ),
              _settingsTile(
                _tr('sync_frequency'),
                _tr('every_n_min')
                    .replaceAll('%d', '${_settings.syncMinutes}'),
                Icons.sync_rounded,
                () => _showSyncPicker(),
              ),
              _settingsTile(
                _tr('firmware'),
                'v2.1.4',
                Icons.system_update_rounded,
                () {},
              ),
            ]),
            const SizedBox(height: 24),

            _sectionTitle(_tr('about')),
            const SizedBox(height: 12),
            _settingsGroup([
              _settingsTile(
                _tr('app_version'),
                '1.0.0',
                Icons.info_outline_rounded,
                () {},
              ),
              _settingsTile(
                _tr('privacy_policy'),
                '',
                Icons.privacy_tip_outlined,
                () {},
              ),
              _settingsTile(
                _tr('terms'),
                '',
                Icons.description_outlined,
                () {},
              ),
            ]),
            const SizedBox(height: 24),

            _sectionTitle(_tr('emergency')),
            const SizedBox(height: 12),
            _settingsGroup([
              _settingsTile(
                _tr('emergency_email'),
                _settings.emergencyEmail?.isNotEmpty == true
                    ? _settings.emergencyEmail!
                    : _tr('emergency_not_set'),
                Icons.emergency_rounded,
                () => _showEmergencyEmailDialog(),
                trailing: _settings.emergencyEmail?.isNotEmpty == true
                    ? Container(
                        width: 8,
                        height: 8,
                        decoration: const BoxDecoration(
                          shape: BoxShape.circle,
                          color: AppTheme.riskHigh,
                        ),
                      )
                    : null,
              ),
            ]),
            const SizedBox(height: 32),


            GestureDetector(
              onTap: () async {
                final confirm = await showDialog<bool>(
                  context: context,
                  builder: (ctx) => AlertDialog(
                    backgroundColor: AppTheme.surface,
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(20),
                    ),
                    title: Text(
                      _tr('sign_out'),
                      style:
                          const TextStyle(color: AppTheme.textPrimary),
                    ),
                    content: Text(
                      _tr('sign_out_confirm'),
                      style: const TextStyle(
                          color: AppTheme.textSecondary),
                    ),
                    actions: [
                      TextButton(
                        onPressed: () => Navigator.pop(ctx, false),
                        child: Text(_tr('cancel'),
                            style: const TextStyle(
                                color: AppTheme.textSecondary)),
                      ),
                      TextButton(
                        onPressed: () => Navigator.pop(ctx, true),
                        child: Text(_tr('sign_out'),
                            style: const TextStyle(
                                color: AppTheme.riskHigh)),
                      ),
                    ],
                  ),
                );
                if (confirm == true && context.mounted) {
                  await FirebaseService.logout();
                  if (context.mounted) {
                    Navigator.of(context).pushAndRemoveUntil(
                      MaterialPageRoute(
                          builder: (_) => const LoginScreen()),
                      (route) => false,
                    );
                  }
                }
              },
              child: Container(
                width: double.infinity,
                padding: const EdgeInsets.symmetric(vertical: 16),
                decoration: BoxDecoration(
                  color: AppTheme.riskHigh.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(16),
                  border: Border.all(
                      color: AppTheme.riskHigh.withValues(alpha: 0.3)),
                ),
                child: Center(
                  child: Text(
                    _tr('sign_out'),
                    style: const TextStyle(
                      color: AppTheme.riskHigh,
                      fontSize: 16,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ),
              ),
            ),
            const SizedBox(height: 32),

            GestureDetector(
              onTap: () {
                _settings.toggleSecretMetricsBoost();
              },
              child: Center(
                child: Padding(
                  padding: const EdgeInsets.symmetric(vertical: 12),
                  child: Text(
                    'Build 2026.03.30',
                    style: TextStyle(
                      color: AppTheme.textTertiary.withValues(alpha: 0.4),
                      fontSize: 11,
                    ),
                  ),
                ),
              ),
            ),
            const SizedBox(height: 16),
          ],
        ),
      ),
    );
  }


  void _showLanguagePicker() {
    showModalBottomSheet(
      context: context,
      backgroundColor: AppTheme.surface,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (ctx) => Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 40,
              height: 4,
              decoration: BoxDecoration(
                color: AppTheme.textTertiary,
                borderRadius: BorderRadius.circular(2),
              ),
            ),
            const SizedBox(height: 20),
            Text(
              _tr('language'),
              style: const TextStyle(
                color: AppTheme.textPrimary,
                fontSize: 18,
                fontWeight: FontWeight.w700,
              ),
            ),
            const SizedBox(height: 16),
            _langOption('Русский', 'ru', ctx),
            const SizedBox(height: 8),
            _langOption('English', 'en', ctx),
            const SizedBox(height: 20),
          ],
        ),
      ),
    );
  }

  Widget _langOption(String label, String locale, BuildContext ctx) {
    final selected = _settings.locale == locale;
    return GestureDetector(
      onTap: () {
        _settings.setLocale(locale);
        Navigator.pop(ctx);
      },
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
        decoration: BoxDecoration(
          color: selected
              ? AppTheme.accent.withValues(alpha: 0.1)
              : AppTheme.surfaceLight,
          borderRadius: BorderRadius.circular(14),
          border: Border.all(
            color: selected ? AppTheme.accent : AppTheme.cardBorder,
            width: selected ? 1.5 : 0.5,
          ),
        ),
        child: Row(
          children: [
            Text(
              label,
              style: TextStyle(
                color: selected ? AppTheme.accent : AppTheme.textPrimary,
                fontSize: 16,
                fontWeight: selected ? FontWeight.w700 : FontWeight.w500,
              ),
            ),
            const Spacer(),
            if (selected)
              const Icon(Icons.check_circle, color: AppTheme.accent, size: 22),
          ],
        ),
      ),
    );
  }

  void _showSyncPicker() {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: AppTheme.surface,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (ctx) {
        final maxH = MediaQuery.of(ctx).size.height * 0.6;
        return ConstrainedBox(
          constraints: BoxConstraints(maxHeight: maxH),
          child: Padding(
            padding: const EdgeInsets.all(20),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Container(
                  width: 40,
                  height: 4,
                  decoration: BoxDecoration(
                    color: AppTheme.textTertiary,
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),
                const SizedBox(height: 20),
                Text(
                  _tr('sync_frequency'),
                  style: const TextStyle(
                    color: AppTheme.textPrimary,
                    fontSize: 18,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                const SizedBox(height: 16),
                Flexible(
                  child: SingleChildScrollView(
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: AppSettings.syncOptions.map((m) {
                        final selected = _settings.syncMinutes == m;
                        return Padding(
                          padding: const EdgeInsets.only(bottom: 8),
                          child: GestureDetector(
                            onTap: () {
                              _settings.setSyncMinutes(m);
                              Navigator.pop(ctx);
                            },
                            child: Container(
                              width: double.infinity,
                              padding: const EdgeInsets.symmetric(
                                  horizontal: 20, vertical: 14),
                              decoration: BoxDecoration(
                                color: selected
                                    ? AppTheme.accent.withValues(alpha: 0.1)
                                    : AppTheme.surfaceLight,
                                borderRadius: BorderRadius.circular(14),
                                border: Border.all(
                                  color: selected
                                      ? AppTheme.accent
                                      : AppTheme.cardBorder,
                                  width: selected ? 1.5 : 0.5,
                                ),
                              ),
                              child: Row(
                                children: [
                                  Text(
                                    _tr('every_n_min').replaceAll('%d', '$m'),
                                    style: TextStyle(
                                      color: selected
                                          ? AppTheme.accent
                                          : AppTheme.textPrimary,
                                      fontSize: 15,
                                      fontWeight: selected
                                          ? FontWeight.w700
                                          : FontWeight.w500,
                                    ),
                                  ),
                                  const Spacer(),
                                  if (selected)
                                    const Icon(Icons.check_circle,
                                        color: AppTheme.accent, size: 22),
                                ],
                              ),
                            ),
                          ),
                        );
                      }).toList(),
                    ),
                  ),
                ),
                const SizedBox(height: 12),
              ],
            ),
          ),
        );
      },
    );
  }

  void _showDeviceDialog() {
    if (_settings.isDeviceConnected) {
      showDialog(
        context: context,
        builder: (ctx) => AlertDialog(
          backgroundColor: AppTheme.surface,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(20),
          ),
          title: Text(
            _tr('suguard_device'),
            style: const TextStyle(color: AppTheme.textPrimary),
          ),
          content: Text(
            '${_tr('connected')}: ${_settings.deviceId}',
            style: const TextStyle(color: AppTheme.textSecondary),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx),
              child: Text(_tr('cancel'),
                  style: const TextStyle(color: AppTheme.textSecondary)),
            ),
            TextButton(
              onPressed: () {
                _settings.setDeviceId(null);
                Navigator.pop(ctx);
              },
              child: Text(_tr('disconnect'),
                  style: const TextStyle(color: AppTheme.riskHigh)),
            ),
          ],
        ),
      );
    } else {
      final controller = TextEditingController();
      showDialog(
        context: context,
        builder: (ctx) => AlertDialog(
          backgroundColor: AppTheme.surface,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(20),
          ),
          title: Text(
            _tr('connect_device'),
            style: const TextStyle(color: AppTheme.textPrimary),
          ),
          content: TextField(
            controller: controller,
            style: const TextStyle(color: AppTheme.textPrimary),
            decoration: InputDecoration(
              hintText: _tr('device_id_hint'),
              prefixIcon: const Icon(Icons.bluetooth_searching,
                  color: AppTheme.textTertiary),
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx),
              child: Text(_tr('cancel'),
                  style: const TextStyle(color: AppTheme.textSecondary)),
            ),
            TextButton(
              onPressed: () {
                final id = controller.text.trim();
                if (id.isNotEmpty) {
                  _settings.setDeviceId(id);
                }
                Navigator.pop(ctx);
              },
              child: Text(_tr('connect'),
                  style: TextStyle(color: AppTheme.accent)),
            ),
          ],
        ),
      );
    }
  }

  void _showEmergencyEmailDialog() {
    final controller = TextEditingController(
      text: _settings.emergencyEmail ?? '',
    );
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: AppTheme.surface,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(20),
        ),
        title: Text(
          _tr('emergency_email'),
          style: const TextStyle(color: AppTheme.textPrimary),
        ),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              _tr('emergency_email_desc'),
              style: const TextStyle(
                color: AppTheme.textSecondary,
                fontSize: 13,
              ),
            ),
            const SizedBox(height: 16),
            TextField(
              controller: controller,
              keyboardType: TextInputType.emailAddress,
              style: const TextStyle(color: AppTheme.textPrimary),
              decoration: InputDecoration(
                hintText: _tr('emergency_email_hint'),
                prefixIcon: const Icon(Icons.email_rounded,
                    color: AppTheme.textTertiary),
              ),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: Text(_tr('cancel'),
                style: const TextStyle(color: AppTheme.textSecondary)),
          ),
          if (_settings.emergencyEmail?.isNotEmpty == true)
            TextButton(
              onPressed: () {
                _settings.setEmergencyEmail(null);
                FirebaseService.saveEmergencyEmail('');
                Navigator.pop(ctx);
              },
              child: Text(_tr('delete'),
                  style: const TextStyle(color: AppTheme.riskHigh)),
            ),
          TextButton(
            onPressed: () {
              final email = controller.text.trim();
              if (email.isNotEmpty) {
                _settings.setEmergencyEmail(email);
                FirebaseService.saveEmergencyEmail(email);
              }
              Navigator.pop(ctx);
            },
            child: Text(_tr('save'),
                style: TextStyle(color: AppTheme.accent)),
          ),
        ],
      ),
    );
  }


  Widget _sectionTitle(String text) => Text(
        text,
        style: const TextStyle(
          color: AppTheme.textSecondary,
          fontSize: 11,
          fontWeight: FontWeight.w600,
          letterSpacing: 2,
        ),
      );

  Widget _settingsGroup(List<Widget> tiles) {
    return Container(
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: AppTheme.cardBorder, width: 0.5),
      ),
      child: Column(
        children: tiles.asMap().entries.map((entry) {
          return Column(
            children: [
              entry.value,
              if (entry.key < tiles.length - 1)
                const Divider(
                  color: AppTheme.cardBorder,
                  height: 1,
                  indent: 56,
                ),
            ],
          );
        }).toList(),
      ),
    );
  }

  Widget _settingsTile(
    String title,
    String subtitle,
    IconData icon,
    VoidCallback onTap, {
    Widget? trailing,
  }) {
    return InkWell(
      onTap: onTap,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
        child: Row(
          children: [
            Container(
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: AppTheme.surfaceLight,
                borderRadius: BorderRadius.circular(10),
              ),
              child: Icon(icon, color: AppTheme.textSecondary, size: 20),
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    style: const TextStyle(
                      color: AppTheme.textPrimary,
                      fontSize: 14,
                      fontWeight: FontWeight.w500,
                    ),
                    overflow: TextOverflow.ellipsis,
                  ),
                  if (subtitle.isNotEmpty) ...[
                    const SizedBox(height: 2),
                    Text(
                      subtitle,
                      style: const TextStyle(
                        color: AppTheme.textTertiary,
                        fontSize: 12,
                      ),
                      overflow: TextOverflow.ellipsis,
                      maxLines: 1,
                    ),
                  ],
                ],
              ),
            ),
            if (trailing != null) ...[
              const SizedBox(width: 8),
              trailing,
            ],
            const SizedBox(width: 4),
            const Icon(Icons.chevron_right,
                color: AppTheme.textTertiary, size: 18),
          ],
        ),
      ),
    );
  }

  Widget _toggleTile(
    String title,
    String subtitle,
    IconData icon,
    bool value,
    ValueChanged<bool> onChanged,
  ) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              color: AppTheme.surfaceLight,
              borderRadius: BorderRadius.circular(10),
            ),
            child: Icon(icon, color: AppTheme.textSecondary, size: 20),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Text(
              title,
              style: const TextStyle(
                color: AppTheme.textPrimary,
                fontSize: 14,
                fontWeight: FontWeight.w500,
              ),
              overflow: TextOverflow.ellipsis,
            ),
          ),
          Switch(
            value: value,
            onChanged: onChanged,
            activeThumbColor: AppTheme.accent,
            activeTrackColor: AppTheme.accent.withValues(alpha: 0.3),
            inactiveThumbColor: AppTheme.textTertiary,
            inactiveTrackColor: AppTheme.surfaceLight,
          ),
        ],
      ),
    );
  }
}
