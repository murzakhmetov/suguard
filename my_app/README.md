# SuGuard

Flutter app for glucose / SpO2 / pulse monitoring. Health data is stored in the
Firebase Realtime Database; AI features use Groq (chat, text food analysis) and
Google Gemini (food photo analysis); emergency e-mails go through Resend.

## Build & run

API keys are passed at compile time, not bundled as an asset:

```sh
cp .env.example .env        # then fill in your keys (.env is gitignored)
flutter pub get
flutter run --dart-define-from-file=.env
# release build
flutter build apk --dart-define-from-file=.env
```

A fresh clone also builds without `.env` (`flutter run`); the AI and e-mail
features then fail at request time because their keys are empty.

You can also pass individual keys: `--dart-define=GROQ_API_KEY=...`.

> **Security note:** keys compiled into a client build can be extracted from the
> APK/IPA/JS bundle. They are not secret once shipped. Real secrecy requires
> routing the Groq/Gemini/Resend calls through a backend proxy.
