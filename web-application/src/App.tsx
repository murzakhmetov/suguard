import { useEffect, useRef, useState } from 'react';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import './App.css';
import { type Language, translations } from './translations';
import { Bracelet3DShowcase } from './Bracelet3DShowcase';

gsap.registerPlugin(ScrollTrigger);

// Живой биометрический график PPG + Глюкоза
const LiveTelemetryCanvas = () => {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d')!;
    let animId: number;
    let phase = 0;

    const render = () => {
      animId = requestAnimationFrame(render);
      const clientW = canvas.clientWidth;
      const clientH = canvas.clientHeight;
      if (!clientW || !clientH) return;
      const w = (canvas.width = clientW * window.devicePixelRatio);
      const h = (canvas.height = clientH * window.devicePixelRatio);
      ctx.clearRect(0, 0, w, h);

      ctx.strokeStyle = 'rgba(255, 255, 255, 0.04)';
      ctx.lineWidth = 1;
      const step = 28 * window.devicePixelRatio;
      for (let x = 0; x < w; x += step) {
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, h);
        ctx.stroke();
      }
      for (let y = 0; y < h; y += step) {
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(w, y);
        ctx.stroke();
      }

      // Кривая тренда глюкозы
      ctx.beginPath();
      for (let x = 0; x < w; x += 3) {
        const normX = x / w;
        const y =
          h * 0.58 +
          Math.sin(normX * 5 + phase * 0.6) * (h * 0.14) +
          Math.cos(normX * 11 - phase * 0.4) * (h * 0.05);
        if (x === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.strokeStyle = 'rgba(251, 191, 36, 0.45)';
      ctx.lineWidth = 2 * window.devicePixelRatio;
      ctx.stroke();

      // Пульсовая волна PPG 660/880nm
      ctx.beginPath();
      for (let x = 0; x < w; x += 2) {
        const normX = x / w;
        const cycle = (normX * 4.5 + phase) % 1;
        const systolic = Math.exp(-Math.pow((cycle - 0.22) * 11, 2)) * 0.36;
        const dicrotic = Math.exp(-Math.pow((cycle - 0.46) * 14, 2)) * 0.14;
        const y = h * 0.62 - (systolic + dicrotic) * h;
        if (x === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.strokeStyle = '#00f19f';
      ctx.lineWidth = 2.5 * window.devicePixelRatio;
      ctx.shadowColor = 'rgba(0, 241, 159, 0.5)';
      ctx.shadowBlur = 12;
      ctx.stroke();
      ctx.shadowBlur = 0;

      ctx.lineTo(w, h);
      ctx.lineTo(0, h);
      ctx.closePath();
      const grad = ctx.createLinearGradient(0, h * 0.2, 0, h);
      grad.addColorStop(0, 'rgba(0, 241, 159, 0.22)');
      grad.addColorStop(1, 'rgba(0, 241, 159, 0.0)');
      ctx.fillStyle = grad;
      ctx.fill();

      phase += 0.012;
    };

    render();
    return () => cancelAnimationFrame(animId);
  }, []);

  return <canvas ref={canvasRef} className="telemetry-wave-canvas" />;
};

function App() {
  const [lang, setLang] = useState<Language>('ru');
  const t = translations[lang];

  const [mobileOpen, setMobileOpen] = useState(false);
  const [activeFaq, setActiveFaq] = useState<number | null>(0);
  const [activeAppScreen, setActiveAppScreen] = useState<number>(0);
  const [isVideoModalOpen, setIsVideoModalOpen] = useState(false);

  // Состояния для интерактивного киноблока WHOOP / Apple Health
  const [wristMuted, setWristMuted] = useState(true);
  const [activeCinemaTab, setActiveCinemaTab] = useState<'wrist' | 'studio'>('wrist');
  const [scanPhase, setScanPhase] = useState(0);

  const pageRef = useRef<HTMLDivElement>(null);
  const cinemaWrapRef = useRef<HTMLDivElement>(null);
  const cinemaCardRef = useRef<HTMLDivElement>(null);
  const wristVideoRef = useRef<HTMLVideoElement>(null);

  const navLinks = [
    { label: 'Оптический ИИ', href: '#optical-cinema' },
    { label: '3D Инженерия', href: '#hardware-3d' },
    { label: t.nav.ecosystem, href: '#ecosystem' },
    { label: t.nav.app, href: '#app' },
    { label: t.nav.experts, href: '#experts' },
    { label: t.nav.partners, href: '#partners' },
    { label: t.nav.pricing, href: '#pricing' },
  ];

  const appScreens = [
    {
      id: 'dashboard',
      tag: '01 / LIVE TELEMETRY',
      title: t.appSection.screen1Title,
      desc: t.appSection.screen1Desc,
      img: '/suguard2.jpeg',
      metric: '5.8 mmol/L • 98% SpO2',
    },
    {
      id: 'analytics',
      tag: '02 / GLUCOSE DYNAMICS',
      title: t.appSection.screen2Title,
      desc: t.appSection.screen2Desc,
      img: '/suguard5.jpeg',
      metric: 'Day / Week / Month Trends',
    },
    {
      id: 'nutrition',
      tag: '03 / AI COMPUTER VISION',
      title: t.appSection.screen3Title,
      desc: t.appSection.screen3Desc,
      img: '/suguard1.jpeg',
      metric: 'Auto BJU & Glycemic Load',
    },
    {
      id: 'consultant',
      tag: '04 / 24/7 AI ENDOCRINOLOGIST',
      title: t.appSection.screen4Title,
      desc: t.appSection.screen4Desc,
      img: '/suguard3.jpeg',
      metric: 'Personalized Clinical Insights',
    },
  ];

  const faqsList = [
    { q: t.faq.q1, a: t.faq.a1 },
    { q: t.faq.q2, a: t.faq.a2 },
    { q: t.faq.q3, a: t.faq.a3 },
    { q: t.faq.q4, a: t.faq.a4 },
    { q: t.faq.q5, a: t.faq.a5 },
  ];

  // Синхронизация телеметрии с таймкодом видео на руке (0..9 сек)
  const handleWristTimeUpdate = () => {
    const v = wristVideoRef.current;
    if (!v) return;
    if (v.currentTime < 3.0) setScanPhase(0);
    else if (v.currentTime < 6.0) setScanPhase(1);
    else setScanPhase(2);
  };

  const toggleWristSound = () => {
    const v = wristVideoRef.current;
    if (!v) return;
    v.muted = !wristMuted;
    setWristMuted(!wristMuted);
  };

  // GSAP ScrollTrigger анимации
  useEffect(() => {
    const ctx = gsap.context(() => {
      // Входная анимация Hero
      gsap.fromTo(
        '.hero-gsap-fade',
        { y: 36, opacity: 0 },
        {
          y: 0,
          opacity: 1,
          duration: 1.05,
          stagger: 0.11,
          ease: 'power3.out',
        }
      );

      // Парящие HUD-капсулы вокруг видео в Hero
      gsap.to('.hero-floating-pill-left', {
        y: -18,
        duration: 2.8,
        repeat: -1,
        yoyo: true,
        ease: 'sine.inOut',
      });
      gsap.to('.hero-floating-pill-right', {
        y: 18,
        duration: 3.2,
        repeat: -1,
        yoyo: true,
        ease: 'sine.inOut',
      });

      // Расширяющийся киноэкран в стиле Apple Health / WHOOP при скролле
      if (cinemaWrapRef.current && cinemaCardRef.current) {
        gsap.fromTo(
          cinemaCardRef.current,
          {
            scale: 0.86,
            borderRadius: '44px',
          },
          {
            scale: 1,
            borderRadius: '20px',
            ease: 'none',
            scrollTrigger: {
              trigger: cinemaWrapRef.current,
              start: 'top 85%',
              end: 'top 15%',
              scrub: 0.8,
            },
          }
        );
      }

      // Плавное появление секций
      gsap.utils.toArray<HTMLElement>('.gsap-section-reveal').forEach((el) => {
        gsap.fromTo(
          el,
          { y: 48, opacity: 0 },
          {
            y: 0,
            opacity: 1,
            duration: 0.9,
            ease: 'power3.out',
            scrollTrigger: {
              trigger: el,
              start: 'top 86%',
              toggleActions: 'play none none none',
            },
          }
        );
      });
    }, pageRef);

    return () => ctx.revert();
  }, [lang]);

  return (
    <div ref={pageRef} className="whoop-app-shell">
      {/* ПЛАВАЮЩИЙ НАВБАР В СТИЛЕ APPLE / WHOOP */}
      <header className="whoop-navbar-wrapper">
        <nav className="whoop-navbar">
          <a href="#" className="whoop-brand">
            <span className="whoop-brand-dot" />
            <span className="whoop-brand-text">SUGUARD</span>
          </a>

          <div className="whoop-nav-links">
            {navLinks.map((link) => (
              <a key={link.href} href={link.href} className="whoop-nav-link">
                {link.label}
              </a>
            ))}
          </div>

          <div className="whoop-nav-actions">
            <div className="whoop-lang-pill">
              {(['ru', 'en', 'kk'] as Language[]).map((l) => (
                <button
                  key={l}
                  onClick={() => setLang(l)}
                  className={`whoop-lang-btn ${lang === l ? 'active' : ''}`}
                >
                  {l.toUpperCase()}
                </button>
              ))}
            </div>

            <a href="#pricing" className="whoop-nav-cta">
              {t.hero.orderDevice}
            </a>

            <button
              className="whoop-burger"
              onClick={() => setMobileOpen(!mobileOpen)}
              aria-label="Menu"
            >
              <span />
              <span />
            </button>
          </div>
        </nav>
      </header>

      {mobileOpen && (
        <div className="whoop-mobile-drawer">
          {navLinks.map((link) => (
            <a
              key={link.href}
              href={link.href}
              onClick={() => setMobileOpen(false)}
              className="whoop-mobile-link"
            >
              {link.label}
            </a>
          ))}
          <div className="whoop-mobile-bottom">
            <a
              href="/app-release.apk"
              download
              className="whoop-btn-primary"
              onClick={() => setMobileOpen(false)}
            >
              Download Android .APK
            </a>
          </div>
        </div>
      )}

      {/* =================================================================
          1. HERO СЕКЦИЯ С ПАРЯЩИМ 3D-ВИДЕО БРАСЛЕТА В НЕВЕСОМОСТИ
          ================================================================= */}
      <section className="whoop-hero">
        <div className="whoop-hero-glow" />

        <div className="whoop-container">
          <div className="whoop-hero-Copy">
            <div className="whoop-eyebrow-pill hero-gsap-fade">
              <span className="eyebrow-live-dot" />
              <span>{t.hero.badge}</span>
              <span className="eyebrow-divider">|</span>
              <span className="eyebrow-mono">660nm / 880nm PPG</span>
            </div>

            <h1 className="whoop-hero-title hero-gsap-fade">{t.hero.title}</h1>

            <p className="whoop-hero-sub hero-gsap-fade">{t.hero.subtitle}</p>

            <div className="whoop-hero-buttons hero-gsap-fade">
              <a href="/app-release.apk" download className="whoop-btn-primary">
                <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4">
                  <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" />
                  <polyline points="7 10 12 15 17 10" />
                  <line x1="12" y1="15" x2="12" y2="3" />
                </svg>
                <span>Download App (.APK)</span>
              </a>

              <a href="#optical-cinema" className="whoop-btn-glass">
                <span className="play-icon-circle">▶</span>
                <span>Как работает лазер (Видео)</span>
              </a>

              <a href="#hardware-3d" className="whoop-btn-outline">
                3D Разборка устройства →
              </a>
            </div>
          </div>

          {/* БЕСШОВНАЯ СТУДИЙНАЯ ВИДЕО-СЦЕНА С ПАРЯЩИМ БРАСЛЕТОМ SUGUARD */}
          <div className="hero-studio-video-stage hero-gsap-fade">
            <div className="studio-video-wrapper">
              <video
                src="/suguard-studio.mp4"
                autoPlay
                loop
                muted
                playsInline
                className="studio-blend-video"
              />
              <div className="studio-video-vignette" />
            </div>

            {/* Парящие телеметрические капсулы Apple Health вокруг вращающегося браслета */}
            <div className="hero-hud-pill pill-top-left hero-floating-pill-left">
              <span className="hud-pill-dot red" />
              <div>
                <div className="hud-pill-label">ОПТИЧЕСКИЙ ЛАЗЕР MAX30102</div>
                <div className="hud-pill-value">660 нм Red + 880 нм IR</div>
              </div>
            </div>

            <div className="hero-hud-pill pill-bottom-left hero-floating-pill-right">
              <span className="hud-pill-dot teal" />
              <div>
                <div className="hud-pill-label">НЕИНВАЗИВНАЯ ГЛЮКОЗА</div>
                <div className="hud-pill-value">5.8 ммоль/л • Норма</div>
              </div>
            </div>

            <div className="hero-hud-pill pill-top-right hero-floating-pill-right">
              <span className="hud-pill-dot blue" />
              <div>
                <div className="hud-pill-label">САТУРАЦИЯ И ПУЛЬС</div>
                <div className="hud-pill-value">98% SpO2 • 72 BPM</div>
              </div>
            </div>

            <div className="hero-hud-pill pill-bottom-right hero-floating-pill-left">
              <span className="hud-pill-dot amber" />
              <div>
                <div className="hud-pill-label">АВТОНОМНОСТЬ И СВЯЗЬ</div>
                <div className="hud-pill-value">7 дней • Bluetooth 5.3</div>
              </div>
            </div>
          </div>

          {/* Архитектурная строка ключевых цифр */}
          <div className="whoop-metrics-bar gsap-section-reveal" id="achievements">
            <div className="whoop-metric-cell">
              <div className="metric-giant">{t.hero.statAccuracy}</div>
              <div className="metric-title">{t.achievements.accTitle}</div>
              <div className="metric-sub">{t.achievements.accDesc}</div>
            </div>
            <div className="whoop-metric-cell">
              <div className="metric-giant">{t.hero.statTests}</div>
              <div className="metric-title">{t.achievements.testsTitle}</div>
              <div className="metric-sub">{t.achievements.testsDesc}</div>
            </div>
            <div className="whoop-metric-cell">
              <div className="metric-giant">{t.hero.statInvestment}</div>
              <div className="metric-title">{t.achievements.invTitle}</div>
              <div className="metric-sub">{t.achievements.invDesc}</div>
            </div>
            <div className="whoop-metric-cell">
              <div className="metric-giant">{t.hero.statSync}</div>
              <div className="metric-title">{t.hero.statSyncSub}</div>
              <div className="metric-sub">{t.achievements.partnersDesc}</div>
            </div>
          </div>
        </div>
      </section>

      {/* =================================================================
          2. ДИНАМИЧНЫЙ КИНОЭКРАН WHOOP / APPLE HEALTH (ВИДЕО НА РУКЕ С ЛАЗЕРОМ)
          ================================================================= */}
      <section ref={cinemaWrapRef} className="whoop-cinema-section" id="optical-cinema">
        <div className="whoop-container">
          <div className="cinema-header-row gsap-section-reveal">
            <div>
              <span className="whoop-kicker">OPTICAL PPG BIO-SENSING IN ACTION</span>
              <h2 className="whoop-h2">Точность в каждом импульсе.</h2>
            </div>

            {/* Переключатель между двумя твоими видеороликами */}
            <div className="cinema-tabs">
              <button
                type="button"
                onClick={() => setActiveCinemaTab('wrist')}
                className={`cinema-tab-btn ${activeCinemaTab === 'wrist' ? 'active' : ''}`}
              >
                01. Сканирование на руке (Лазер + Пульс)
              </button>
              <button
                type="button"
                onClick={() => setActiveCinemaTab('studio')}
                className={`cinema-tab-btn ${activeCinemaTab === 'studio' ? 'active' : ''}`}
              >
                02. Обзор браслета 360° в студии
              </button>
            </div>
          </div>
        </div>

        {/* Расширяющийся при скролле широкоформатный плеер с живым HUD-оверлеем */}
        <div className="cinema-expanding-container">
          <div ref={cinemaCardRef} className="cinema-stage-card">
            <video
              ref={wristVideoRef}
              key={activeCinemaTab}
              src={activeCinemaTab === 'wrist' ? '/suguard-wrist.mp4' : '/suguard-studio.mp4'}
              autoPlay
              loop
              muted={wristMuted}
              playsInline
              onTimeUpdate={handleWristTimeUpdate}
              className="cinema-main-video"
            />

            <div className="cinema-gradient-overlay" />

            {/* Верхняя панель телеметрии прямо поверх видео */}
            <div className="cinema-hud-top">
              <div className="cinema-live-badge">
                <span className="eyebrow-live-dot" />
                <span>
                  {activeCinemaTab === 'wrist'
                    ? 'MAX30102 LASER SPECTROSCOPY • ACTIVE SCAN'
                    : 'SUGUARD UNIBODY • 360° STUDIO ORBIT'}
                </span>
              </div>

              <button
                type="button"
                onClick={toggleWristSound}
                className="cinema-sound-btn"
              >
                {wristMuted ? '🔇 Включить звук диктора' : '🔊 Звук включен'}
              </button>
            </div>

            {/* Нижний синхронизированный с видео телеметрический бар */}
            <div className="cinema-hud-bottom">
              <div className="cinema-steps-indicator">
                <div className={`cinema-step-box ${scanPhase === 0 ? 'active' : ''}`}>
                  <span className="step-time">00:00 — 00:03</span>
                  <h4>Контакт с кожей</h4>
                  <p>Калибровка базовой линии и отсечение внешнего света</p>
                </div>

                <div className={`cinema-step-box ${scanPhase === 1 ? 'active' : ''}`}>
                  <span className="step-time">00:03 — 00:06</span>
                  <h4>Импульс 660 / 880 нм</h4>
                  <p>Красный и ИК-лазер просвечивают капилляры запястья</p>
                </div>

                <div className={`cinema-step-box ${scanPhase === 2 ? 'active' : ''}`}>
                  <span className="step-time">00:06 — 00:09</span>
                  <h4>ИИ-спектральный анализ</h4>
                  <p>Расчёт уровня глюкозы, SpO2 и волны пульса в реальном времени</p>
                </div>
              </div>

              <div className="cinema-live-readout">
                <div className="readout-item">
                  <span className="readout-lbl">ГЛЮКОЗА</span>
                  <span className="readout-val">5.8 mmol/L</span>
                </div>
                <div className="readout-item">
                  <span className="readout-lbl">КИСЛОРОД</span>
                  <span className="readout-val teal">98% SpO2</span>
                </div>
                <div className="readout-item">
                  <span className="readout-lbl">ПУЛЬС</span>
                  <span className="readout-val">72 BPM</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* =================================================================
          3. ПОЛНОЭКРАННАЯ 3D-РАЗБОРКА БРАСЛЕТА ПРИ СКРОЛЛЕ
          ================================================================= */}
      <Bracelet3DShowcase lang={lang} />

      {/* =================================================================
          4. APPLE PRO BENTO GRID (ЭКОСИСТЕМА И ТЕХНОЛОГИИ)
          ================================================================= */}
      <section className="whoop-section" id="ecosystem">
        <div className="whoop-container">
          <div className="whoop-section-head gsap-section-reveal">
            <span className="whoop-kicker">{t.ecosystem.badge}</span>
            <h2 className="whoop-h2">{t.ecosystem.title}</h2>
            <p className="whoop-lead">{t.ecosystem.subtitle}</p>
          </div>

          <div className="apple-bento-grid" id="features">
            <div className="bento-card bento-span-7 gsap-section-reveal">
              <div className="bento-top-meta">
                <span className="bento-tag">OPTICAL PPG SPECTROSCOPY</span>
                <span className="bento-status">ZERO NEEDLES</span>
              </div>
              <h3 className="bento-title">{t.features.f1Title}</h3>
              <p className="bento-desc">{t.features.f1Desc}</p>

              <div className="bento-telemetry-stage">
                <LiveTelemetryCanvas />
                <div className="bento-telemetry-overlay">
                  <div className="telemetry-chip">
                    <span className="dot-green" /> 660nm Red + 880nm Infrared
                  </div>
                  <div className="telemetry-chip">18-Bit Sigma-Delta ADC</div>
                </div>
              </div>
            </div>

            <div className="bento-card bento-span-5 gsap-section-reveal">
              <div className="bento-top-meta">
                <span className="bento-tag">AI RISK ENGINE</span>
                <span className="bento-status">PREDICTIVE</span>
              </div>
              <h3 className="bento-title">{t.features.f2Title}</h3>
              <p className="bento-desc">{t.features.f2Desc}</p>

              <div className="whoop-gauge-showcase">
                <svg viewBox="0 0 200 130" className="whoop-arc-svg">
                  <defs>
                    <linearGradient id="whoopArcGrad" x1="0%" y1="0%" x2="100%" y2="0%">
                      <stop offset="0%" stopColor="#00f19f" />
                      <stop offset="60%" stopColor="#facc15" />
                      <stop offset="100%" stopColor="#f43f5e" />
                    </linearGradient>
                  </defs>
                  <path
                    d="M 24 110 A 76 76 0 0 1 176 110"
                    fill="none"
                    stroke="rgba(255,255,255,0.08)"
                    strokeWidth="14"
                    strokeLinecap="round"
                  />
                  <path
                    d="M 24 110 A 76 76 0 0 1 176 110"
                    fill="none"
                    stroke="url(#whoopArcGrad)"
                    strokeWidth="14"
                    strokeLinecap="round"
                    strokeDasharray="240"
                    strokeDashoffset="165"
                  />
                  <text x="100" y="92" textAnchor="middle" className="arc-big-num">
                    24%
                  </text>
                  <text x="100" y="114" textAnchor="middle" className="arc-sub-txt">
                    LOW-MODERATE RISK
                  </text>
                </svg>
              </div>
            </div>

            <div className="bento-card bento-span-5 bento-image-card gsap-section-reveal">
              <img
                src="/hardwear.jpeg"
                alt="SuGuard Hardware"
                className="bento-bg-photo"
              />
              <div className="bento-image-overlay">
                <span className="bento-tag">{t.ecosystem.hardwareBadge}</span>
                <h3 className="bento-title">{t.ecosystem.hardwareTitle}</h3>
                <p className="bento-desc">{t.ecosystem.hardwareDesc}</p>
                <div className="bento-pills-row">
                  <span className="spec-mini-pill">Bluetooth 5.3 LE</span>
                  <span className="spec-mini-pill">7 Days Battery</span>
                  <span className="spec-mini-pill">IP67 Case</span>
                </div>
              </div>
            </div>

            <div className="bento-card bento-span-7 gsap-section-reveal">
              <div className="bento-top-meta">
                <span className="bento-tag">COMPUTER VISION & AI ASSISTANT</span>
                <span className="bento-status">REAL-TIME</span>
              </div>
              <h3 className="bento-title">
                {t.features.f3Title} & {t.features.f5Title}
              </h3>
              <p className="bento-desc">{t.features.f3Desc}</p>

              <div className="bento-macros-grid">
                <div className="macro-box">
                  <span className="macro-name">Углеводы (Carbs)</span>
                  <span className="macro-val">14.0 г</span>
                  <div className="macro-bar">
                    <div className="macro-fill" style={{ width: '45%', background: '#f43f5e' }} />
                  </div>
                </div>
                <div className="macro-box">
                  <span className="macro-name">Белки (Protein)</span>
                  <span className="macro-val">18.5 г</span>
                  <div className="macro-bar">
                    <div className="macro-fill" style={{ width: '68%', background: '#38bdf8' }} />
                  </div>
                </div>
                <div className="macro-box">
                  <span className="macro-name">Гликемический отклик</span>
                  <span className="macro-val" style={{ color: '#00f19f' }}>
                    Стабильный (+0.4 ммоль/л)
                  </span>
                  <div className="macro-bar">
                    <div className="macro-fill" style={{ width: '28%', background: '#00f19f' }} />
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* =================================================================
          5. ИНТЕРАКТИВНЫЙ СТЕНД МОБИЛЬНОГО ПРИЛОЖЕНИЯ
          ================================================================= */}
      <section className="whoop-section whoop-app-showcase" id="app">
        <div className="whoop-container">
          <div className="whoop-section-head gsap-section-reveal">
            <span className="whoop-kicker">{t.appSection.badge}</span>
            <h2 className="whoop-h2">{t.appSection.title}</h2>
            <p className="whoop-lead">{t.appSection.subtitle}</p>
          </div>

          <div className="app-interactive-layout gsap-section-reveal">
            <div className="app-chapters-list">
              {appScreens.map((scr, idx) => (
                <button
                  key={scr.id}
                  type="button"
                  onClick={() => setActiveAppScreen(idx)}
                  className={`app-chapter-card ${activeAppScreen === idx ? 'active' : ''}`}
                >
                  <div className="chapter-tag">{scr.tag}</div>
                  <h3 className="chapter-title">{scr.title}</h3>
                  <p className="chapter-desc">{scr.desc}</p>
                  <div className="chapter-metric">{scr.metric}</div>
                </button>
              ))}
            </div>

            <div className="app-device-preview">
              <div className="app-device-ambient" />
              <div className="titanium-phone-large">
                <img
                  key={appScreens[activeAppScreen].img}
                  src={appScreens[activeAppScreen].img}
                  alt={appScreens[activeAppScreen].title}
                  className="app-screen-img"
                />
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* =================================================================
          6. НАУЧНЫЙ СОВЕТ И ЭКСПЕРТЫ
          ================================================================= */}
      <section className="whoop-section" id="experts">
        <div className="whoop-container">
          <div className="whoop-section-head gsap-section-reveal">
            <span className="whoop-kicker">{t.experts.badge}</span>
            <h2 className="whoop-h2">{t.experts.title}</h2>
            <p className="whoop-lead">{t.experts.subtitle}</p>
          </div>

          <div className="whoop-experts-grid">
            <div className="whoop-expert-card gsap-section-reveal">
              <div className="expert-top-row">
                <img src="/jerryloeb.jpeg" alt="Jerry Loeb" className="expert-photo" />
                <div>
                  <span className="expert-badge">{t.experts.jerryRole}</span>
                  <h3 className="expert-title">Prof. Jerry Loeb</h3>
                  <div className="expert-uni">{t.experts.jerryAff}</div>
                </div>
              </div>
              <p className="expert-quote">{t.experts.jerryDesc}</p>
            </div>

            <div className="whoop-expert-card gsap-section-reveal">
              <div className="expert-top-row">
                <img src="/aidaralimbayev.jpeg" alt="Aidar Alimbayev" className="expert-photo" />
                <div>
                  <span className="expert-badge">{t.experts.aidarRole}</span>
                  <h3 className="expert-title">Aidar Alimbayev</h3>
                  <div className="expert-uni">{t.experts.aidarAff}</div>
                </div>
              </div>
              <p className="expert-quote">{t.experts.aidarDesc}</p>
            </div>

            <div className="whoop-expert-card gsap-section-reveal">
              <div className="expert-top-row">
                <img src="/rustam_askaruly.jpeg" alt="Askaruly Rustam" className="expert-photo" />
                <div>
                  <span className="expert-badge">{t.experts.rustamRole}</span>
                  <h3 className="expert-title">Askaruly Rustam</h3>
                  <div className="expert-uni">{t.experts.rustamAff}</div>
                </div>
              </div>
              <p className="expert-quote">{t.experts.rustamDesc}</p>
            </div>
          </div>
        </div>
      </section>

      {/* =================================================================
          7. ПАРТНЁРЫ
          ================================================================= */}
      <section className="whoop-section whoop-partners-sec" id="partners">
        <div className="whoop-container">
          <div className="whoop-section-head gsap-section-reveal">
            <span className="whoop-kicker">{t.partners.badge}</span>
            <h2 className="whoop-h2">{t.partners.title}</h2>
            <p className="whoop-lead">{t.partners.subtitle}</p>
          </div>

          <div className="whoop-partners-table gsap-section-reveal">
            <div className="partner-cell">
              <span className="partner-index">01 / CLINICAL</span>
              <h3>{t.partners.brbTitle}</h3>
              <p>{t.partners.brbDesc}</p>
            </div>
            <div className="partner-cell">
              <span className="partner-index">02 / MEDICAL CENTER</span>
              <h3>{t.partners.avicennaTitle}</h3>
              <p>{t.partners.avicennaDesc}</p>
            </div>
            <div className="partner-cell">
              <span className="partner-index">03 / PRESIDENTIAL CLINIC</span>
              <h3>{t.partners.presidentialTitle}</h3>
              <p>{t.partners.presidentialDesc}</p>
            </div>
            <div className="partner-cell">
              <span className="partner-index">04 / PUBLIC INITIATIVE</span>
              <h3>{t.partners.amanatTitle}</h3>
              <p>{t.partners.amanatDesc}</p>
            </div>
          </div>

          <div className="whoop-academic-bar gsap-section-reveal">
            <div className="academic-bar-label">{t.partners.academicTitle}</div>
            <div className="academic-bar-items">
              <div className="academic-item">
                <h4>{t.partners.nncrzTitle}</h4>
                <p>{t.partners.nncrzDesc}</p>
              </div>
              <div className="academic-item">
                <h4>{t.partners.nuTitle}</h4>
                <p>{t.partners.nuDesc}</p>
              </div>
              <div className="academic-item">
                <h4>{t.partners.amuTitle}</h4>
                <p>{t.partners.amuDesc}</p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* =================================================================
          8. КОМПЛЕКТАЦИЯ И ЗАКАЗ
          ================================================================= */}
      <section className="whoop-section" id="pricing">
        <div className="whoop-container">
          <div className="whoop-flagship-order gsap-section-reveal">
            <div className="order-left-visual">
              <span className="whoop-kicker">{t.pricing.popularBadge}</span>
              <h2 className="order-title">SuGuard Complete Kit</h2>
              <p className="order-sub">
                Носимый оптический биосенсор SuGuard + бессрочный доступ к ИИ-экосистеме мониторинга глюкозы, SpO2 и питания.
              </p>
              <img
                src="/hardwear.jpeg"
                alt="SuGuard Kit"
                className="order-hardware-img"
              />
            </div>

            <div className="order-right-specs">
              <div className="order-price-block">
                <div className="order-price-tag">35 000 ₸</div>
                <div className="order-price-usd">≈ $70 USD • Единоразовая покупка без скрытых платежей</div>
              </div>

              <ul className="order-included-list">
                <li>
                  <span className="order-check">✓</span>
                  <span>Смарт-браслет SuGuard (MAX30102 + SuGuard.Health PCB)</span>
                </li>
                <li>
                  <span className="order-check">✓</span>
                  <span>Неинвазивный мониторинг глюкозы, SpO2 и ЧСС 24/7</span>
                </li>
                <li>
                  <span className="order-check">✓</span>
                  <span>ИИ-оценка риска диабета и компьютерное зрение для еды</span>
                </li>
                <li>
                  <span className="order-check">✓</span>
                  <span>Персональный ИИ-эндокринолог и облачная синхронизация</span>
                </li>
                <li>
                  <span className="order-check">✓</span>
                  <span>Кабель быстрой зарядки USB Type-C и гарантия 12 месяцев</span>
                </li>
              </ul>

              <div className="order-cta-group" id="contact">
                <a href="mailto:suguard.kz@gmail.com" className="whoop-btn-primary full-width">
                  {t.hero.orderDevice} — suguard.kz@gmail.com
                </a>
                <a href="/app-release.apk" download className="whoop-btn-outline full-width">
                  Скачать мобильное приложение (.APK)
                </a>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* =================================================================
          9. FAQ & FOOTER
          ================================================================= */}
      <section className="whoop-section" id="faq">
        <div className="whoop-container narrow">
          <div className="whoop-section-head gsap-section-reveal">
            <span className="whoop-kicker">{t.faq.badge}</span>
            <h2 className="whoop-h2">{t.faq.title}</h2>
          </div>

          <div className="whoop-faq-list gsap-section-reveal">
            {faqsList.map((item, idx) => {
              const isOpen = activeFaq === idx;
              return (
                <div key={idx} className={`whoop-faq-item ${isOpen ? 'open' : ''}`}>
                  <button
                    type="button"
                    onClick={() => setActiveFaq(isOpen ? null : idx)}
                    className="whoop-faq-q"
                  >
                    <span>{item.q}</span>
                    <span className="faq-plus">{isOpen ? '−' : '+'}</span>
                  </button>
                  {isOpen && <div className="whoop-faq-a">{item.a}</div>}
                </div>
              );
            })}
          </div>
        </div>
      </section>

      <footer className="whoop-footer">
        <div className="whoop-container">
          <div className="whoop-footer-grid">
            <div>
              <div className="whoop-brand">
                <span className="whoop-brand-dot" />
                <span className="whoop-brand-text">SUGUARD</span>
              </div>
              <p className="footer-desc">{t.footer.desc}</p>
            </div>

            <div className="footer-col">
              <h4>Навигация</h4>
              <a href="#optical-cinema">Оптический ИИ</a>
              <a href="#hardware-3d">3D Инженерия</a>
              <a href="#ecosystem">{t.nav.ecosystem}</a>
              <a href="#app">{t.nav.app}</a>
            </div>

            <div className="footer-col">
              <h4>Контакты</h4>
              <a href="mailto:suguard.kz@gmail.com">suguard.kz@gmail.com</a>
              <a href="tel:+77056612373">+7 705 661 2373</a>
              <a href="https://www.instagram.com/suguard_kz" target="_blank" rel="noreferrer">
                Instagram: @suguard_kz
              </a>
            </div>

            <div className="footer-col">
              <h4>Загрузки</h4>
              <a href="/app-release.apk" download>
                Android App (.APK)
              </a>
              <a href="#pricing">Предзаказ устройства</a>
            </div>
          </div>

          <div className="whoop-footer-bottom">
            <span>© 2026 SuGuard Health Technologies. {t.footer.rights}</span>
            <span>Designed & Engineered in Kazakhstan</span>
          </div>
        </div>
      </footer>

      {isVideoModalOpen && (
        <div
          className="whoop-video-modal"
          onClick={() => setIsVideoModalOpen(false)}
        >
          <div
            className="whoop-video-dialog"
            onClick={(e) => e.stopPropagation()}
          >
            <button
              type="button"
              className="whoop-video-close"
              onClick={() => setIsVideoModalOpen(false)}
            >
              ✕
            </button>
            <video
              src="/suguard-wrist.mp4"
              controls
              autoPlay
              playsInline
              className="whoop-video-player"
            />
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
