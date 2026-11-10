import 'dart:convert';
import 'dart:math';

import 'package:crypto/crypto.dart';

/// Password hashing for the profile record stored in the Realtime Database.
///
/// Current format: `sha256$<base64 salt>$<hex sha256(salt || utf8(password))>`
/// with a random 16-byte salt per user.
///
/// Older builds stored [legacyHash], a reversible base64 string. [verify]
/// still accepts it so existing users are not locked out, and
/// [needsRehash] tells the caller to rewrite the record with [hash] after
/// a successful login (lazy migration).
///
/// A single SHA-256 is fast to brute-force. This is a stop-gap: the
/// database is readable without auth, so moving to Firebase Auth (or a
/// server-side slow KDF) is the real fix.
class PasswordHasher {
  PasswordHasher._();

  static const String _prefix = 'sha256\$';
  static const int _saltLength = 16;
  static final Random _random = Random.secure();

  /// Returns a new salted hash of [password] in the current format.
  static String hash(String password) {
    final salt = List<int>.generate(_saltLength, (_) => _random.nextInt(256));
    return '$_prefix${base64Encode(salt)}\$${_digest(salt, password)}';
  }

  /// Whether [password] matches [stored], in either the current or the
  /// legacy format.
  static bool verify(String password, String? stored) {
    if (stored == null) return false;
    if (!stored.startsWith(_prefix)) {
      return _constantTimeEquals(stored, legacyHash(password));
    }
    final parts = stored.substring(_prefix.length).split('\$');
    if (parts.length != 2) return false;
    final List<int> salt;
    try {
      salt = base64Decode(parts[0]);
    } on FormatException {
      return false;
    }
    return _constantTimeEquals(parts[1], _digest(salt, password));
  }

  /// Whether [stored] is not in the current format and should be replaced.
  static bool needsRehash(String? stored) =>
      stored == null || !stored.startsWith(_prefix);

  /// The format written by earlier builds (base64 of a fixed-salted string).
  /// Reversible; only kept to verify and migrate existing records.
  static String legacyHash(String password) =>
      base64Encode(utf8.encode('suguard_${password}_salt2024'));

  static String _digest(List<int> salt, String password) =>
      sha256.convert([...salt, ...utf8.encode(password)]).toString();

  static bool _constantTimeEquals(String a, String b) {
    if (a.length != b.length) return false;
    var diff = 0;
    for (var i = 0; i < a.length; i++) {
      diff |= a.codeUnitAt(i) ^ b.codeUnitAt(i);
    }
    return diff == 0;
  }
}
