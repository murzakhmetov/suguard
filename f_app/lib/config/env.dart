/// Build-time configuration.
///
/// Values are injected at compile time, e.g.
///
///     flutter run --dart-define-from-file=.env
///
/// (see `.env.example`). A missing key compiles to an empty string, so a
/// fresh clone still builds; the feature that needs the key just fails at
/// request time with an error message.
///
/// Anything compiled into a client build can be extracted from the binary.
/// These keys are NOT secret; real secrecy needs a backend proxy.
class Env {
  Env._();

  static const String groqApiKey = String.fromEnvironment('GROQ_API_KEY');
  static const String geminiApiKey = String.fromEnvironment('GEMINI_API_KEY');
  static const String resendApiKey = String.fromEnvironment('RESEND_API_KEY');
}
