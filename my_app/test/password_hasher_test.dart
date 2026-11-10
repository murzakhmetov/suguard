import 'package:flutter_test/flutter_test.dart';
import 'package:my_app/services/password_hasher.dart';

void main() {
  group('PasswordHasher', () {
    test('new hashes verify and are salted', () {
      final a = PasswordHasher.hash('secret123');
      final b = PasswordHasher.hash('secret123');
      expect(a, startsWith('sha256\$'));
      expect(a, isNot(equals(b)));
      expect(PasswordHasher.verify('secret123', a), isTrue);
      expect(PasswordHasher.verify('secret124', a), isFalse);
      expect(PasswordHasher.needsRehash(a), isFalse);
    });

    test('legacy base64 records still verify and need a rehash', () {
      // Exactly what earlier builds stored for "secret123".
      const legacy = 'c3VndWFyZF9zZWNyZXQxMjNfc2FsdDIwMjQ=';
      expect(PasswordHasher.legacyHash('secret123'), legacy);
      expect(PasswordHasher.verify('secret123', legacy), isTrue);
      expect(PasswordHasher.verify('wrong', legacy), isFalse);
      expect(PasswordHasher.needsRehash(legacy), isTrue);
    });

    test('malformed or missing records are rejected', () {
      expect(PasswordHasher.verify('x', null), isFalse);
      expect(PasswordHasher.verify('x', 'sha256\$broken'), isFalse);
      expect(PasswordHasher.verify('x', 'sha256\$!!!\$abc'), isFalse);
    });
  });
}
