import { useEffect, useRef, useState } from 'react';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import './App.css';
import { type Language, translations } from './translations';
import { Bracelet3DShowcase } from './Bracelet3DShowcase';

gsap.registerPlugin(ScrollTrigger);

// Премиальная кнопка, которая плавно раскрывается через GSAP при наведении
const GsapButton = ({
  label,
  badge,
  href,
  onClick,
  download,
  variant = 'primary',
}: {
  label: string;
  badge?: string;
  href?: string;
  onClick?: () => void;
  download?: boolean;
  variant?: 'primary' | 'glass' | 'outline';
}) => {
  const btnRef = useRef<any>(null);
  const drawerRef = useRef<HTMLSpanElement>(null);
  const arrowRef = useRef<HTMLSpanElement>(null);

  const handleEnter = () => {
    if (btnRef.current) {
      gsap.to(btnRef.current, {
        scale: 1.03,
        duration: 0.4,
        ease: 'power3.out',
      });
    }
    if (drawerRef.current) {
      gsap.to(drawerRef.current, {
        width: 'auto',
        opacity: 1,
        marginLeft: 10,
        duration: 0.45,
        ease: 'power3.out',
      });
    }
    if (arrowRef.current) {
      gsap.to(arrowRef.current, {
        x: 4,
        duration: 0.35,
        ease: 'power2.out',
      });
    }
  };

  const handleLeave = () => {
    if (btnRef.current) {
      gsap.to(btnRef.current, {
        scale: 1,
        duration: 0.4,
        ease: 'power3.out',
      });
    }
    if (drawerRef.current) {
      gsap.to(drawerRef.current, {
        width: 0,
        opacity: 0,
        marginLeft: 0,
        duration: 0.35,
        ease: 'power3.inOut',
      });
    }
    if (arrowRef.current) {
      gsap.to(arrowRef.current, {
        x: 0,
        duration: 0.35,
        ease: 'power2.out',
      });
    }
  };

  const content = (
    <>
      <span className="gsap-btn-label">{label}</span>
      {badge && (
        <span ref={drawerRef} className="gsap-btn-drawer">
          <span className="gsap-btn-badge">{badge}</span>
        </span>
      )}
      <span ref={arrowRef} className="gsap-btn-arrow">
        →
      </span>
    </>
  );

  const cls = `gsap-expanding-btn ${variant}`;

  if (href) {
    return (
      <a
        ref={btnRef}
        href={href}
        download={download}
        onMouseEnter={handleEnter}
        onMouseLeave={handleLeave}
        className={cls}
      >
        {content}
      </a>
    );
  }

  return (
    <button
      ref={btnRef}
      type="button"
      onClick={onClick}
      onMouseEnter={handleEnter}
      onMouseLeave={handleLeave}
      className={cls}
    >
      {content}
    </button>
  );
};

function App() {
  const [lang, setLang] = useState<Language>('ru');
  const t = translations[lang];

  const [mobileOpen, setMobileOpen] = useState(false);
  const [activeFeature, setActiveFeature] = useState<number>(0);
  const [activeAppScreen, setActiveAppScreen] = useState<number>(0);
  const [appScrollProgress, setAppScrollProgress] = useState<number>(0);
  const [activeFaq, setActiveFaq] = useState<number | null>(0);
  const [isVideoModalOpen, setIsVideoModalOpen] = useState(false);

  const pageRef = useRef<HTMLDivElement>(null);
  const featureBodyRefs = useRef<(HTMLDivElement | null)[]>([]);
  const featureMediaRef = useRef<HTMLDivElement>(null);
  const appScrollSectionRef = useRef<HTMLDivElement>(null);
  const appPhoneCardRef = useRef<HTMLDivElement>(null);
  const faqBodyRefs = useRef<(HTMLDivElement | null)[]>([]);

  const navLinks = [
    { label: t.nav.ecosystem, href: '#ecosystem' },
    { label: '3D Инженерия', href: '#hardware-3d' },
    { label: t.nav.app, href: '#app' },
    { label: t.nav.experts, href: '#experts' },
    { label: t.nav.partners, href: '#partners' },
    { label: t.nav.pricing, href: '#pricing' },
    { label: t.nav.faq, href: '#faq' },
  ];

  // 4 интерактивных модуля для секции Экосистемы (вместо старых 4 коробок со скриншота 1)
  const ecosystemModules = [
    {
      num: '01',
      tag: 'OPTICAL PPG SPECTROSCOPY',
      title: t.features.f1Title,
      subtitle: 'Двухволновое лазерное зондирование капилляров 660 / 880 нм',
      desc: t.features.f1Desc,
      metrics: [
        { val: '660 / 880 нм', lbl: 'Длины волн' },
        { val: '18-bit I2C', lbl: 'АЦП сенсора' },
        { val: '0 проколов', lbl: 'Неинвазивно' },
      ],
      mediaType: 'video' as const,
      mediaSrc: '/suguard-wrist.mp4',
      fallbackImg: '/hardwear.jpeg',
      caption: 'Оптический биосенсор MAX30102 сканирует спектр поглощения крови',
    },
    {
      num: '02',
      tag: 'PREDICTIVE AI ENGINE',
      title: t.features.f2Title,
      subtitle: 'Нейросетевой расчёт вероятности диабета в реальном времени',
      desc: t.features.f2Desc,
      metrics: [
        { val: '94.2%', lbl: 'Точность ИИ' },
        { val: '24 / 7', lbl: 'Непрерывный анализ' },
        { val: '< 1 сек', lbl: 'Отклик модели' },
      ],
      mediaType: 'image' as const,
      mediaSrc: '/suguard4.jpeg',
      fallbackImg: '/suguard2.jpeg',
      caption: 'Многофакторная оценка гликемического профиля, пульса покоя и SpO2',
    },
    {
      num: '03',
      tag: 'WEARABLE HARDWARE',
      title: t.ecosystem.hardwareTitle,
      subtitle: 'Кастомная плата SuGuard.Health и до 7 дней автономности',
      desc: t.ecosystem.hardwareDesc,
      metrics: [
        { val: '38 грамм', lbl: 'Масса корпуса' },
        { val: '7 суток', lbl: 'Автономность Li-Po' },
        { val: 'BLE 5.3', lbl: 'Радиомодуль ESP32' },
      ],
      mediaType: 'image' as const,
      mediaSrc: '/hardwear.jpeg',
      fallbackImg: '/hardwear.jpeg',
      caption: 'Ударопрочный матовый корпус на гипоаллергенном ремешке Pin-and-Tuck',
    },
    {
      num: '04',
      tag: 'COMPUTER VISION & AI DOCTOR',
      title: `${t.features.f3Title} & ${t.features.f5Title}`,
      subtitle: 'Распознавание блюд по фотографии и персональный ИИ-эндокринолог',
      desc: t.features.f3Desc,
      metrics: [
        { val: 'Фото-ИИ', lbl: 'Расчёт БЖУ и Ккал' },
        { val: '24 / 7', lbl: 'ИИ-Консультант' },
        { val: 'PDF Отчёт', lbl: 'Экспорт для врача' },
      ],
      mediaType: 'image' as const,
      mediaSrc: '/suguard1.jpeg',
      fallbackImg: '/suguard3.jpeg',
      caption: 'Автоматический подсчёт углеводной нагрузки по одному снимку тарелки',
    },
  ];

  // 4 экрана для Scroll-Driven секции телефона (Скриншот 2)
  const appScreens = [
    {
      id: 'dashboard',
      num: '01',
      tag: 'LIVE HEALTH OVERVIEW',
      title: t.appSection.screen1Title,
      desc: t.appSection.screen1Desc,
      img: '/suguard2.jpeg',
      specs: ['Индекс риска диабета в %', 'Текущая глюкоза (ммоль/л)', 'SpO2 и ЧСС в реальном времени'],
    },
    {
      id: 'risk',
      num: '02',
      tag: 'BIOMETRIC RISK FACTORS',
      title: t.appSection.screen2Title,
      desc: t.appSection.screen2Desc,
      img: '/suguard4.jpeg',
      specs: ['Декомпозиция факторов риска', 'Динамика среднего сахара', 'Раннее предупреждение скачков'],
    },
    {
      id: 'glucose',
      num: '03',
      tag: 'CONTINUOUS GLUCOSE CHARTS',
      title: t.appSection.screen3Title,
      desc: t.appSection.screen3Desc,
      img: '/suguard5.jpeg',
      specs: ['Суточные, недельные и месячные графики', 'Минимум, максимум и среднее', 'Распознавание еды по фото (БЖУ)'],
    },
    {
      id: 'consultant',
      num: '04',
      tag: 'AI ENDOCRINOLOGIST CHAT',
      title: t.appSection.screen4Title,
      desc: t.appSection.screen4Desc,
      img: '/suguard3.jpeg',
      specs: ['Анализ ваших графиков и рациона', 'Персональные медицинские советы', 'Мгновенные ответы 24/7'],
    },
  ];

  const faqsList = [
    { q: t.faq.q1, a: t.faq.a1 },
    { q: t.faq.q2, a: t.faq.a2 },
    { q: t.faq.q3, a: t.faq.a3 },
    { q: t.faq.q4, a: t.faq.a4 },
    { q: t.faq.q5, a: t.faq.a5 },
  ];

  // GSAP-раскрытие кнопок-аккордеонов в секции Экосистемы
  useEffect(() => {
    featureBodyRefs.current.forEach((el, idx) => {
      if (!el) return;
      if (idx === activeFeature) {
        gsap.to(el, {
          height: 'auto',
          opacity: 1,
          marginTop: 14,
          duration: 0.55,
          ease: 'power3.out',
        });
      } else {
        gsap.to(el, {
          height: 0,
          opacity: 0,
          marginTop: 0,
          duration: 0.4,
          ease: 'power3.inOut',
        });
      }
    });

    if (featureMediaRef.current) {
      gsap.fromTo(
        featureMediaRef.current,
        { scale: 0.94, opacity: 0, filter: 'blur(10px)' },
        { scale: 1, opacity: 1, filter: 'blur(0px)', duration: 0.65, ease: 'power3.out' }
      );
    }
  }, [activeFeature]);

  // GSAP-раскрытие вопросов в FAQ
  useEffect(() => {
    faqBodyRefs.current.forEach((el, idx) => {
      if (!el) return;
      if (idx === activeFaq) {
        gsap.to(el, {
          height: 'auto',
          opacity: 1,
          paddingBottom: 24,
          duration: 0.45,
          ease: 'power3.out',
        });
      } else {
        gsap.to(el, {
          height: 0,
          opacity: 0,
          paddingBottom: 0,
          duration: 0.35,
          ease: 'power3.inOut',
        });
      }
    });
  }, [activeFaq]);

  // GSAP Scroll-Driven анимация для секции с телефоном (#app)
  useEffect(() => {
    const handleScroll = () => {
      if (!appScrollSectionRef.current) return;
      const rect = appScrollSectionRef.current.getBoundingClientRect();
      const scrollable = appScrollSectionRef.current.offsetHeight - window.innerHeight;
      if (scrollable <= 0) return;

      const prog = Math.max(0, Math.min(1, -rect.top / scrollable));
      setAppScrollProgress(prog);

      const nextIdx = Math.min(3, Math.floor(prog * 3.99));
      setActiveAppScreen((prev) => {
        if (prev !== nextIdx && appPhoneCardRef.current) {
          gsap.fromTo(
            appPhoneCardRef.current,
            { y: 28, scale: 0.95, opacity: 0.4, rotateY: -10 },
            { y: 0, scale: 1, opacity: 1, rotateY: 0, duration: 0.55, ease: 'power3.out' }
          );
        }
        return nextIdx;
      });
    };

    window.addEventListener('scroll', handleScroll, { passive: true });
    handleScroll();
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  // Общие входные GSAP-анимации страницы
  useEffect(() => {
    const ctx = gsap.context(() => {
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

      gsap.utils.toArray<HTMLElement>('.gsap-section-reveal').forEach((el) => {
        gsap.fromTo(
          el,
          { y: 44, opacity: 0 },
          {
            y: 0,
            opacity: 1,
            duration: 0.85,
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

  // Плавный скролл к нужному экрану телефона по клику на карточку слева
  const scrollToAppChapter = (idx: number) => {
    if (!appScrollSectionRef.current) return;
    const rect = appScrollSectionRef.current.getBoundingClientRect();
    const absTop = window.scrollY + rect.top;
    const scrollable = appScrollSectionRef.current.offsetHeight - window.innerHeight;
    window.scrollTo({
      top: absTop + scrollable * (idx / 3.2),
      behavior: 'smooth',
    });
  };

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

            <GsapButton
              label={t.hero.orderDevice}
              badge="35 000 ₸"
              href="#pricing"
              variant="primary"
            />

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
        </div>
      )}

      {/* =================================================================
          1. HERO СЕКЦИЯ (БЕЗ ПЛАВАЮЩИХ КАПСУЛ И ФЕЙКОВЫХ ОСЦИЛЛОГРАФОВ)
          ================================================================= */}
      <section className="whoop-hero">
        <div className="whoop-hero-glow" />

        <div className="whoop-container">
          <div className="whoop-hero-Copy">
            <div className="whoop-eyebrow-pill hero-gsap-fade">
              <span className="eyebrow-live-dot" />
              <span>{t.hero.badge}</span>
              <span className="eyebrow-divider">|</span>
              <span className="eyebrow-mono">OPTICAL PPG 660 / 880 NM</span>
            </div>

            <h1 className="whoop-hero-title hero-gsap-fade">{t.hero.title}</h1>

            <p className="whoop-hero-sub hero-gsap-fade">{t.hero.subtitle}</p>

            {/* Кнопки с GSAP-раскрытием при наведении */}
            <div className="whoop-hero-buttons hero-gsap-fade">
              <GsapButton
                label="Download App"
                badge="Android .APK"
                href="/app-release.apk"
                download
                variant="primary"
              />
              <GsapButton
                label={t.hero.watchDemo}
                badge="Keynote 4K"
                onClick={() => setIsVideoModalOpen(true)}
                variant="glass"
              />
              <GsapButton
                label="3D Инженерия"
                badge="5 слоёв"
                href="#hardware-3d"
                variant="outline"
              />
            </div>
          </div>

          {/* Чистая титановая витрина экранов приложения без «ИИ-слоп» виджетов по бокам */}
          <div className="hero-clean-showcase hero-gsap-fade">
            <div className="titanium-phone phone-side">
              <img src="/suguard5.jpeg" alt="Blood Glucose Chart" />
            </div>
            <div className="titanium-phone phone-main">
              <img src="/suguard2.jpeg" alt="SuGuard Main Dashboard" />
            </div>
            <div className="titanium-phone phone-side">
              <img src="/suguard1.jpeg" alt="AI Nutrition Scanner" />
            </div>
          </div>

          {/* Архитектурная линейка ключевых показателей */}
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
          2. ПОЛНОЭКРАННАЯ 3D-РАЗБОРКА БРАСЛЕТА ПРИ СКРОЛЛЕ
          ================================================================= */}
      <Bracelet3DShowcase lang={lang} />

      {/* =================================================================
          3. ПРЕМИАЛЬНЫЙ ИНТЕРАКТИВНЫЙ ШОУКЕЙС ТЕХНОЛОГИЙ (ВМЕСТО 4 КОРОБОК СО СКРИНШОТА 1)
          Каждая кнопка плавно раскрывается через GSAP и меняет медиа-сцену справа
          ================================================================= */}
      <section className="whoop-section" id="ecosystem">
        <div className="whoop-container" id="features">
          <div className="whoop-section-head gsap-section-reveal">
            <span className="whoop-kicker">{t.ecosystem.badge}</span>
            <h2 className="whoop-h2">{t.ecosystem.title}</h2>
            <p className="whoop-lead">{t.ecosystem.subtitle}</p>
          </div>

          <div className="apple-interactive-deck gsap-section-reveal">
            {/* Левая колонка: Раскрывающиеся с GSAP-анимацией кнопки технологий */}
            <div className="deck-accordion-column">
              {ecosystemModules.map((mod, idx) => {
                const isOpen = activeFeature === idx;
                return (
                  <div
                    key={mod.num}
                    onClick={() => setActiveFeature(idx)}
                    className={`deck-expanding-item ${isOpen ? 'active' : ''}`}
                  >
                    <div className="deck-item-header">
                      <div className="deck-item-left">
                        <span className="deck-item-num">{mod.num}</span>
                        <div>
                          <div className="deck-item-tag">{mod.tag}</div>
                          <h3 className="deck-item-title">{mod.title}</h3>
                        </div>
                      </div>
                      <span className="deck-item-toggle">{isOpen ? '−' : '+'}</span>
                    </div>

                    {/* Раскрывающееся тело кнопки (управляется через GSAP) */}
                    <div
                      ref={(el) => {
                        featureBodyRefs.current[idx] = el;
                      }}
                      className="deck-item-body"
                    >
                      <div className="deck-item-subtitle">{mod.subtitle}</div>
                      <p className="deck-item-desc">{mod.desc}</p>

                      <div className="deck-item-metrics">
                        {mod.metrics.map((m, mIdx) => (
                          <div key={mIdx} className="deck-mini-stat">
                            <span className="deck-mini-val">{m.val}</span>
                            <span className="deck-mini-lbl">{m.lbl}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Правая колонка: Крупная визуальная сцена с плавным GSAP-переходом */}
            <div className="deck-visual-column">
              <div ref={featureMediaRef} className="deck-visual-stage">
                {ecosystemModules[activeFeature].mediaType === 'video' ? (
                  <video
                    key={ecosystemModules[activeFeature].mediaSrc}
                    src={ecosystemModules[activeFeature].mediaSrc}
                    poster={ecosystemModules[activeFeature].fallbackImg}
                    autoPlay
                    loop
                    muted
                    playsInline
                    onError={(e) => {
                      const vid = e.currentTarget;
                      if (!vid.src.endsWith('/video.mp4')) {
                        vid.src = '/video.mp4';
                      }
                    }}
                    className="deck-stage-media"
                  />
                ) : (
                  <img
                    src={ecosystemModules[activeFeature].mediaSrc}
                    alt={ecosystemModules[activeFeature].title}
                    className="deck-stage-media"
                  />
                )}

                <div className="deck-stage-caption">
                  <span className="caption-dot" />
                  <span>{ecosystemModules[activeFeature].caption}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* =================================================================
          4. SCROLL-DRIVEN СЕКЦИЯ С ТЕЛЕФОНОМ (СКРИНШОТ 2 — АВТОСМЕНА КАРТОЧЕК И ЭКРАНОВ ПРИ СКРОЛЛЕ)
          ================================================================= */}
      <section ref={appScrollSectionRef} className="app-scrolly-section" id="app">
        <div className="app-scrolly-sticky">
          <div className="whoop-container app-scrolly-inner">
            {/* Верхний заголовок секции с правильным отступом от навбара */}
            <div className="app-scrolly-header">
              <div>
                <span className="whoop-kicker">{t.appSection.badge}</span>
                <h2 className="app-scrolly-title">{t.appSection.title}</h2>
              </div>
              <div className="app-scrolly-steps-counter">
                ЭКРАН 0{activeAppScreen + 1} / 04
              </div>
            </div>

            <div className="app-scrolly-grid">
              {/* Левая колонка: Карточки автоматически раскрываются при прокрутке страницы вниз */}
              <div className="app-scrolly-cards">
                {appScreens.map((scr, idx) => {
                  const isActive = activeAppScreen === idx;
                  // Прогресс внутри текущей карточки (0..100%)
                  const localProg = Math.max(
                    0,
                    Math.min(1, (appScrollProgress - idx * 0.25) / 0.25)
                  );

                  return (
                    <div
                      key={scr.id}
                      onClick={() => scrollToAppChapter(idx)}
                      className={`scrolly-chapter-item ${isActive ? 'active' : ''}`}
                    >
                      {/* Левая линия прогресса скролла */}
                      <div className="scrolly-rail">
                        <div
                          className="scrolly-rail-fill"
                          style={{
                            height: isActive
                              ? `${localProg * 100}%`
                              : idx < activeAppScreen
                              ? '100%'
                              : '0%',
                          }}
                        />
                      </div>

                      <div className="scrolly-chapter-content">
                        <div className="scrolly-chapter-top">
                          <span className="scrolly-num">{scr.num}</span>
                          <span className="scrolly-tag">{scr.tag}</span>
                        </div>
                        <h3 className="scrolly-h3">{scr.title}</h3>

                        {isActive && (
                          <div className="scrolly-expanded-details">
                            <p className="scrolly-p">{scr.desc}</p>
                            <div className="scrolly-specs-row">
                              {scr.specs.map((sp, sIdx) => (
                                <span key={sIdx} className="scrolly-spec-chip">
                                  {sp}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Правая колонка: Титановый смартфон с GSAP-переключением экранов */}
              <div className="app-scrolly-phone-col">
                <div className="app-device-ambient" />
                <div ref={appPhoneCardRef} className="titanium-phone-large">
                  <img
                    src={appScreens[activeAppScreen].img}
                    alt={appScreens[activeAppScreen].title}
                    className="app-screen-img"
                  />
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* =================================================================
          5. НАУЧНЫЙ СОВЕТ И ЭКСПЕРТЫ
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
          6. ПАРТНЁРЫ
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
          7. КОМПЛЕКТАЦИЯ И ЗАКАЗ
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
                <GsapButton
                  label={t.hero.orderDevice}
                  badge="suguard.kz@gmail.com"
                  href="mailto:suguard.kz@gmail.com"
                  variant="primary"
                />
                <GsapButton
                  label="Скачать мобильное приложение"
                  badge="Android .APK"
                  href="/app-release.apk"
                  download
                  variant="outline"
                />
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* =================================================================
          8. FAQ С ПЛАВНЫМ GSAP-РАСКРЫТИЕМ
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
                  <div
                    ref={(el) => {
                      faqBodyRefs.current[idx] = el;
                    }}
                    className="whoop-faq-a-gsap"
                  >
                    {item.a}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* =================================================================
          9. FOOTER
          ================================================================= */}
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
              <a href="#ecosystem">{t.nav.ecosystem}</a>
              <a href="#hardware-3d">3D Инженерия</a>
              <a href="#app">{t.nav.app}</a>
              <a href="#experts">{t.nav.experts}</a>
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
              src="/video.mp4"
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
