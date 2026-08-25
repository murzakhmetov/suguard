import { useState, useRef } from 'react';
import { motion, useScroll, useTransform, useSpring, useMotionValue, useMotionTemplate } from 'framer-motion';
import './App.css';
import './extreme.css';
import { type Language, translations } from './translations';

const RevealText = ({ text, className = "" }: { text: string, className?: string }) => {
  const words = text.split(" ");
  return (
    <motion.span
      key={text}
      initial="hidden"
      animate="visible"
      variants={{
        visible: { transition: { staggerChildren: 0.05 } },
        hidden: {}
      }}
      className={className}
      style={{ display: "inline" }}
    >
      {words.map((word, i) => (
        <span key={i} style={{ display: "inline-block", overflow: "hidden", paddingRight: "0.22em", verticalAlign: "top" }}>
          <motion.span
            variants={{
              hidden: { y: "100%", opacity: 0 },
              visible: {
                y: "0%",
                opacity: 1,
                transition: { duration: 0.6, ease: [0.16, 1, 0.3, 1] }
              }
            }}
            style={{ display: "inline-block" }}
          >
            {word}
          </motion.span>
        </span>
      ))}
    </motion.span>
  );
};

const SpotlightCard = ({ children, className = "" }: any) => {
  const mouseX = useMotionValue(0);
  const mouseY = useMotionValue(0);

  function handleMouseMove({ currentTarget, clientX, clientY }: React.MouseEvent) {
    const { left, top } = currentTarget.getBoundingClientRect();
    mouseX.set(clientX - left);
    mouseY.set(clientY - top);
  }

  return (
    <div
      className={`spotlight-wrapper ${className}`}
      onMouseMove={handleMouseMove}
    >
      <motion.div
        className="spotlight-layer"
        style={{
          background: useMotionTemplate`
            radial-gradient(
              600px circle at ${mouseX}px ${mouseY}px,
              rgba(0, 212, 170, 0.12),
              transparent 80%
            )
          `,
        }}
      />
      <div className="spotlight-content" style={{ zIndex: 2 }}>{children}</div>
    </div>
  );
};

const TiltCard = ({ children, className = "" }: any) => {
  const x = useMotionValue(0);
  const y = useMotionValue(0);

  const mouseXSpring = useSpring(x, { stiffness: 300, damping: 40 });
  const mouseYSpring = useSpring(y, { stiffness: 300, damping: 40 });

  const rotateX = useTransform(mouseYSpring, [-0.5, 0.5], ["15deg", "-15deg"]);
  const rotateY = useTransform(mouseXSpring, [-0.5, 0.5], ["-15deg", "15deg"]);

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const width = rect.width;
    const height = rect.height;

    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;

    const xPct = mouseX / width - 0.5;
    const yPct = mouseY / height - 0.5;

    x.set(xPct);
    y.set(yPct);
  };

  const handleMouseLeave = () => {
    x.set(0);
    y.set(0);
  };

  return (
    <motion.div
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      style={{
        rotateY,
        rotateX,
        transformStyle: "preserve-3d",
      }}
      className={`tilt-card ${className}`}
    >
      {children}
    </motion.div>
  );
};

const FadeIn = ({ children, direction = "up", delay = 0, className = "" }: any) => {
  const directions: any = {
    up: { y: 40, x: 0 },
    down: { y: -40, x: 0 },
    left: { x: 40, y: 0 },
    right: { x: -40, y: 0 },
  };

  return (
    <motion.div
      initial={{
        opacity: 0,
        ...directions[direction]
      }}
      whileInView={{
        opacity: 1,
        x: 0,
        y: 0
      }}
      viewport={{ once: true, margin: "-80px" }}
      transition={{
        duration: 0.8,
        delay,
        ease: [0.16, 1, 0.3, 1]
      }}
      className={className}
    >
      {children}
    </motion.div>
  );
};

const StaggerContainer = ({ children, className = "" }: any) => (
  <motion.div
    initial="hidden"
    whileInView="visible"
    viewport={{ once: true, margin: "-80px" }}
    variants={{
      visible: { transition: { staggerChildren: 0.15 } },
      hidden: {}
    }}
    className={className}
  >
    {children}
  </motion.div>
);

const StaggerItem = ({ children, className = "" }: any) => (
  <motion.div
    variants={{
      hidden: { opacity: 0, y: 50 },
      visible: { opacity: 1, y: 0, transition: { duration: 1, ease: [0.16, 1, 0.3, 1] } }
    }}
    className={className}
  >
    {children}
  </motion.div>
);

function App() {
  const [lang, setLang] = useState<Language>('ru');
  const t = translations[lang];

  const [mobileOpen, setMobileOpen] = useState(false);
  const [activeFaq, setActiveFaq] = useState<number | null>(null);
  const [isVideoModalOpen, setIsVideoModalOpen] = useState(false);

  const { scrollYProgress } = useScroll();
  const scaleX = useSpring(scrollYProgress, {
    stiffness: 100,
    damping: 30,
    restDelta: 0.001
  });

  const heroRef = useRef<HTMLDivElement>(null);
  const { scrollYProgress: heroScroll } = useScroll({
    target: heroRef,
    offset: ["start start", "end start"]
  });

  const heroY = useTransform(heroScroll, [0, 1], ["0%", "80%"]);
  const heroOpacity = useTransform(heroScroll, [0, 1], [1, 0]);

  const toggleFaq = (index: number) => {
    setActiveFaq(activeFaq === index ? null : index);
  };
  const closeMobile = () => setMobileOpen(false);

  const navLinks = [
    { label: t.nav.ecosystem, href: '#ecosystem' },
    { label: t.nav.achievements, href: '#achievements' },
    { label: t.nav.experts, href: '#experts' },
    { label: t.nav.partners, href: '#partners' },
    { label: t.nav.features, href: '#features' },
    { label: t.nav.app, href: '#app' },
    { label: t.nav.pricing, href: '#pricing' },
    { label: t.nav.faq, href: '#faq' },
  ];

  const featuresList = [
    {
      icon: (
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
        </svg>
      ),
      title: t.features.f1Title,
      desc: t.features.f1Desc,
    },
    {
      icon: (
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="10" />
          <path d="M12 6v6l4 2" />
        </svg>
      ),
      title: t.features.f2Title,
      desc: t.features.f2Desc,
    },
    {
      icon: (
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M18 8h1a4 4 0 010 8h-1" />
          <path d="M2 8h16v9a4 4 0 01-4 4H6a4 4 0 01-4-4V8z" />
          <line x1="6" y1="1" x2="6" y2="4" />
          <line x1="10" y1="1" x2="10" y2="4" />
          <line x1="14" y1="1" x2="14" y2="4" />
        </svg>
      ),
      title: t.features.f3Title,
      desc: t.features.f3Desc,
    },
    {
      icon: (
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M20.84 4.61a5.5 5.5 0 00-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 00-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 000-7.78z" />
        </svg>
      ),
      title: t.features.f4Title,
      desc: t.features.f4Desc,
    },
    {
      icon: (
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z" />
        </svg>
      ),
      title: t.features.f5Title,
      desc: t.features.f5Desc,
    },
    {
      icon: (
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <rect x="5" y="2" width="14" height="20" rx="2" ry="2" />
          <line x1="12" y1="18" x2="12.01" y2="18" />
        </svg>
      ),
      title: t.features.f6Title,
      desc: t.features.f6Desc,
    },
  ];

  const faqsList = [
    { q: t.faq.q1, a: t.faq.a1 },
    { q: t.faq.q2, a: t.faq.a2 },
    { q: t.faq.q3, a: t.faq.a3 },
    { q: t.faq.q4, a: t.faq.a4 },
    { q: t.faq.q5, a: t.faq.a5 },
  ];

  return (
    <div className="app-container">
      <motion.div className="progress-bar" style={{ scaleX }} />

      <nav className="navbar glass-nav" id="navbar">
        <a href="#" className="navbar-logo">
          <motion.span
            className="navbar-logo-icon"
            whileHover={{ rotate: 180, scale: 1.1 }}
            transition={{ type: "spring", stiffness: 300 }}
          >
            SG
          </motion.span>
          <span className="gradient-text-subtle">SuGuard</span>
        </a>
        <div className="navbar-links">
          {navLinks.map((link) => (
            <a key={link.href} href={link.href} className="nav-link-hover magnetic-btn">
              {link.label}
            </a>
          ))}
        </div>
        <div className="navbar-right">
          <div className="lang-switcher">
            {(['ru', 'en', 'kk'] as Language[]).map((l) => (
              <button
                key={l}
                className={`lang-btn ${lang === l ? 'active' : ''}`}
                onClick={() => setLang(l)}
              >
                {l.toUpperCase()}
              </button>
            ))}
          </div>
          <motion.a
            whileHover={{ scale: 1.05, boxShadow: "0 0 20px rgba(0, 212, 170, 0.4)" }}
            whileTap={{ scale: 0.95 }}
            href="#contact"
            className="navbar-cta glow-button"
          >
            {t.nav.contactUs}
          </motion.a>
        </div>
        <button
          className="navbar-mobile-toggle"
          onClick={() => setMobileOpen(!mobileOpen)}
          aria-label="Toggle navigation menu"
        >
          <span />
          <span />
          <span />
        </button>
      </nav>

      <div className={`mobile-menu${mobileOpen ? ' open' : ''}`}>
        {navLinks.map((link) => (
          <a key={link.href} href={link.href} onClick={closeMobile}>{link.label}</a>
        ))}
        <div className="mobile-lang-wrapper">
          <div className="lang-switcher">
            {(['ru', 'en', 'kk'] as Language[]).map((l) => (
              <button
                key={l}
                className={`lang-btn ${lang === l ? 'active' : ''}`}
                onClick={() => { setLang(l); closeMobile(); }}
              >
                {l.toUpperCase()}
              </button>
            ))}
          </div>
        </div>
        <a href="#contact" onClick={closeMobile} className="btn-primary glow-button" style={{ textAlign: 'center' }}>
          {t.nav.contactUs}
        </a>
      </div>

      {}
      <section className="hero" id="hero" ref={heroRef}>
        <div className="hero-cyber-bg">
          <div className="cyber-grid" />
          <div className="cyber-aurora cyber-aurora-1" />
          <div className="cyber-aurora cyber-aurora-2" />
        </div>

        <div className="bkg-glow-orb orb-1" />
        <div className="bkg-glow-orb orb-2" />
        <div className="bkg-glow-orb orb-3" />

        <motion.div style={{ y: heroY, opacity: heroOpacity }} className="hero-content-wrapper mix-blend">
          <motion.div
            initial={{ opacity: 0, scale: 0.8, filter: "blur(10px)" }}
            animate={{ opacity: 1, scale: 1, filter: "blur(0px)" }}
            transition={{ duration: 1.2, ease: [0.16, 1, 0.3, 1] }}
            className="hero-badge glitch-badge"
          >
            <span className="hero-badge-dot" />
            {t.hero.badge}
          </motion.div>

          <h1 className="hero-title">
            <RevealText text={t.hero.title} className="accent gradient-text" />
          </h1>

          <FadeIn delay={0.4} direction="up" className="hero-subtitle">
            {t.hero.subtitle}
          </FadeIn>

          <FadeIn delay={0.6} direction="up" className="hero-actions">
            <motion.a
              whileHover={{ scale: 1.05, boxShadow: "0 0 30px rgba(0, 212, 170, 0.5)" }}
              whileTap={{ scale: 0.95 }}
              href="/app-release.apk"
              download
              className="btn-primary glow-button"
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" />
                <polyline points="7 10 12 15 17 10" />
                <line x1="12" y1="15" x2="12" y2="3" />
              </svg>
              Download App
            </motion.a>
            <motion.button
              whileHover={{ scale: 1.05, boxShadow: "0 0 25px rgba(0, 212, 170, 0.4)", backgroundColor: "rgba(0, 212, 170, 0.15)" }}
              whileTap={{ scale: 0.95 }}
              onClick={() => setIsVideoModalOpen(true)}
              className="btn-secondary glow-button"
              style={{ cursor: "pointer", borderColor: "rgba(0, 212, 170, 0.5)" }}
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" style={{ color: "var(--accent)" }}>
                <path d="M8 5v14l11-7z" />
              </svg>
              {t.hero.watchDemo}
            </motion.button>
            <motion.a
              whileHover={{ scale: 1.05, backgroundColor: "rgba(255,255,255,0.05)" }}
              whileTap={{ scale: 0.95 }}
              href="#ecosystem"
              className="btn-secondary magnetic-btn"
            >
              {t.hero.orderDevice}
            </motion.a>
          </FadeIn>

          <StaggerContainer className="hero-screenshots">
            <StaggerItem>
              <TiltCard className="hero-phone hero-phone-outer floating-anim reverse-float">
                <img src="/suguard1.jpeg" alt="SuGuard nutrition tracker" loading="lazy" />
              </TiltCard>
            </StaggerItem>
            <StaggerItem>
              <TiltCard className="hero-phone hero-phone-side floating-anim delay-1">
                <img src="/suguard5.jpeg" alt="SuGuard glucose chart" loading="lazy" />
              </TiltCard>
            </StaggerItem>
            <StaggerItem>
              <TiltCard className="hero-phone hero-phone-center floating-anim hero-main-phone pulse-glow">
                <img src="/suguard2.jpeg" alt="SuGuard dashboard" />
              </TiltCard>
            </StaggerItem>
            <StaggerItem>
              <TiltCard className="hero-phone hero-phone-side floating-anim delay-2 reverse-float">
                <img src="/suguard4.jpeg" alt="SuGuard risk assessment" loading="lazy" />
              </TiltCard>
            </StaggerItem>
            <StaggerItem>
              <TiltCard className="hero-phone hero-phone-outer floating-anim delay-3">
                <img src="/suguard3.jpeg" alt="SuGuard health consultant" loading="lazy" />
              </TiltCard>
            </StaggerItem>
          </StaggerContainer>
        </motion.div>
      </section>

      {}
      <section className="section ecosystem-section relative-section" id="ecosystem">
        <div className="section-glow" />
        <div className="container">
          <FadeIn className="section-header">
            <span className="section-label neon-label">{t.ecosystem.badge}</span>
            <h2 className="section-title"><RevealText text={t.ecosystem.title} /></h2>
            <p className="section-desc">
              {t.ecosystem.subtitle}
            </p>
          </FadeIn>

          <StaggerContainer className="ecosystem-grid">
            <StaggerItem>
              <SpotlightCard className="ecosystem-card glass-panel premium-border">
                <div className="ecosystem-card-image parallax-img-container">
                  <motion.img
                    whileHover={{ scale: 1.15, rotate: 2 }}
                    transition={{ duration: 0.6, ease: "easeOut" }}
                    src="/hardwear.jpeg"
                    alt="SuGuard wearable on wrist"
                  />
                </div>
                <div className="ecosystem-card-content">
                  <div className="ecosystem-card-label">{t.ecosystem.hardwareBadge}</div>
                  <h3>{t.ecosystem.hardwareTitle}</h3>
                  <p>{t.ecosystem.hardwareDesc}</p>
                  <ul className="ecosystem-specs">
                    <li><span className="spec-name">{t.ecosystem.hardwareFeat1Title}</span><span className="spec-value gradient-text-subtle">{t.ecosystem.hardwareFeat1Desc}</span></li>
                    <li><span className="spec-name">{t.ecosystem.hardwareFeat2Title}</span><span className="spec-value">{t.ecosystem.hardwareFeat2Desc}</span></li>
                    <li><span className="spec-name">{t.ecosystem.hardwareFeat3Title}</span><span className="spec-value">{t.ecosystem.hardwareFeat3Desc}</span></li>
                  </ul>
                </div>
              </SpotlightCard>
            </StaggerItem>

            <StaggerItem>
              <SpotlightCard className="ecosystem-card glass-panel premium-border">
                <div className="ecosystem-card-image ecosystem-card-phones parallax-img-container">
                  <TiltCard>
                    <motion.img
                      whileHover={{ scale: 1.05 }}
                      transition={{ duration: 0.6 }}
                      src="/suguard2.jpeg"
                      alt="SuGuard mobile app dashboard"
                      className="eco-phone floating-anim"
                    />
                  </TiltCard>
                </div>
                <div className="ecosystem-card-content">
                  <div className="ecosystem-card-label">{t.ecosystem.appBadge}</div>
                  <h3>{t.ecosystem.appTitle}</h3>
                  <p>{t.ecosystem.appDesc}</p>
                  <ul className="ecosystem-specs">
                    <li><span className="spec-name">{t.ecosystem.appFeat1Title}</span><span className="spec-value gradient-text-subtle">{t.ecosystem.appFeat1Desc}</span></li>
                    <li><span className="spec-name">{t.ecosystem.appFeat2Title}</span><span className="spec-value">{t.ecosystem.appFeat2Desc}</span></li>
                    <li><span className="spec-name">{t.ecosystem.appFeat3Title}</span><span className="spec-value">{t.ecosystem.appFeat3Desc}</span></li>
                  </ul>
                </div>
              </SpotlightCard>
            </StaggerItem>
          </StaggerContainer>
        </div>
      </section>

      {}
      <section className="section relative-section" id="achievements">
        <div className="section-glow" />
        <div className="container">
          <FadeIn className="section-header">
            <span className="section-label neon-label">{t.achievements.badge}</span>
            <h2 className="section-title"><RevealText text={t.achievements.title} /></h2>
            <p className="section-desc">
              {t.achievements.subtitle}
            </p>
          </FadeIn>

          <StaggerContainer className="achievements-grid">
            <StaggerItem>
              <SpotlightCard className="achievement-card glass-panel premium-border">
                <div className="achievement-val gradient-text">{t.hero.statInvestment}</div>
                <div className="achievement-title">{t.achievements.invTitle}</div>
                <div className="achievement-desc">{t.achievements.invDesc}</div>
              </SpotlightCard>
            </StaggerItem>

            <StaggerItem>
              <SpotlightCard className="achievement-card glass-panel premium-border">
                <div className="achievement-val gradient-text">{t.hero.statAccuracy}</div>
                <div className="achievement-title">{t.achievements.accTitle}</div>
                <div className="achievement-desc">{t.achievements.accDesc}</div>
              </SpotlightCard>
            </StaggerItem>

            <StaggerItem>
              <SpotlightCard className="achievement-card glass-panel premium-border">
                <div className="achievement-val gradient-text">{t.hero.statTests}</div>
                <div className="achievement-title">{t.achievements.testsTitle}</div>
                <div className="achievement-desc">{t.achievements.testsDesc}</div>
              </SpotlightCard>
            </StaggerItem>

            <StaggerItem>
              <SpotlightCard className="achievement-card glass-panel premium-border">
                <div className="achievement-val gradient-text">4+</div>
                <div className="achievement-title">{t.achievements.partnersTitle}</div>
                <div className="achievement-desc">{t.achievements.partnersDesc}</div>
              </SpotlightCard>
            </StaggerItem>
          </StaggerContainer>
        </div>
      </section>

      {}
      <section className="section relative-section" id="experts">
        <div className="section-glow" />
        <div className="container">
          <FadeIn className="section-header">
            <span className="section-label neon-label">{t.experts.badge}</span>
            <h2 className="section-title"><RevealText text={t.experts.title} /></h2>
            <p className="section-desc">
              {t.experts.subtitle}
            </p>
          </FadeIn>

          <StaggerContainer className="experts-grid">
            <StaggerItem>
              <SpotlightCard className="expert-card glass-panel premium-border">
                <div className="expert-avatar-box">
                  <img src="/jerryloeb.jpeg" alt="Jerry Loeb" className="expert-avatar-img" />
                </div>
                <div className="expert-tag">{t.experts.jerryRole}</div>
                <h3 className="expert-name">Jerry Loeb</h3>
                <div className="expert-affiliation">{t.experts.jerryAff}</div>
                <p className="expert-desc">{t.experts.jerryDesc}</p>
              </SpotlightCard>
            </StaggerItem>

            <StaggerItem>
              <SpotlightCard className="expert-card glass-panel premium-border">
                <div className="expert-avatar-box">
                  <img src="/aidaralimbayev.jpeg" alt="Aidar Alimbayev" className="expert-avatar-img" />
                </div>
                <div className="expert-tag">{t.experts.aidarRole}</div>
                <h3 className="expert-name">Aidar Alimbayev</h3>
                <div className="expert-affiliation">{t.experts.aidarAff}</div>
                <p className="expert-desc">{t.experts.aidarDesc}</p>
              </SpotlightCard>
            </StaggerItem>

            <StaggerItem>
              <SpotlightCard className="expert-card glass-panel premium-border">
                <div className="expert-avatar-box">
                  <img src="/rustam_askaruly.jpeg" alt="Askaruly Rustam" className="expert-avatar-img" />
                </div>
                <div className="expert-tag">{t.experts.rustamRole}</div>
                <h3 className="expert-name">Askaruly Rustam</h3>
                <div className="expert-affiliation">{t.experts.rustamAff}</div>
                <p className="expert-desc">{t.experts.rustamDesc}</p>
              </SpotlightCard>
            </StaggerItem>
          </StaggerContainer>
        </div>
      </section>

      {}
      <section className="section partners-section relative-section" id="partners">
        <div className="section-glow-blue parallax-glow" />
        <div className="container">
          <FadeIn className="section-header">
            <span className="section-label neon-label">{t.partners.badge}</span>
            <h2 className="section-title"><RevealText text={t.partners.title} /></h2>
            <p className="section-desc">
              {t.partners.subtitle}
            </p>
          </FadeIn>

          <StaggerContainer className="partners-grid">
            <StaggerItem>
              <SpotlightCard className="partner-card glass-panel premium-border">
                <div className="partner-info">
                  <h3>{t.partners.brbTitle}</h3>
                  <p>{t.partners.brbDesc}</p>
                </div>
              </SpotlightCard>
            </StaggerItem>

            <StaggerItem>
              <SpotlightCard className="partner-card glass-panel premium-border">
                <div className="partner-info">
                  <h3>{t.partners.avicennaTitle}</h3>
                  <p>{t.partners.avicennaDesc}</p>
                </div>
              </SpotlightCard>
            </StaggerItem>

            <StaggerItem>
              <SpotlightCard className="partner-card glass-panel premium-border">
                <div className="partner-info">
                  <h3>{t.partners.presidentialTitle}</h3>
                  <p>{t.partners.presidentialDesc}</p>
                </div>
              </SpotlightCard>
            </StaggerItem>

            <StaggerItem>
              <SpotlightCard className="partner-card glass-panel premium-border">
                <div className="partner-info">
                  <h3>{t.partners.amanatTitle}</h3>
                  <p>{t.partners.amanatDesc}</p>
                </div>
              </SpotlightCard>
            </StaggerItem>
          </StaggerContainer>

          <FadeIn className="academic-wrapper">
            <div className="academic-title">
              <span>{t.partners.academicTitle}</span>
            </div>

            <div className="academic-grid">
              <div className="academic-card">
                <h4>{t.partners.nncrzTitle}</h4>
                <p>{t.partners.nncrzDesc}</p>
              </div>
              <div className="academic-card">
                <h4>{t.partners.nuTitle}</h4>
                <p>{t.partners.nuDesc}</p>
              </div>
              <div className="academic-card">
                <h4>{t.partners.amuTitle}</h4>
                <p>{t.partners.amuDesc}</p>
              </div>
            </div>
          </FadeIn>
        </div>
      </section>

      {}
      <section className="section features" id="features">
        <div className="container">
          <FadeIn className="section-header">
            <span className="section-label neon-label">{t.features.badge}</span>
            <h2 className="section-title"><RevealText text={t.features.title} /></h2>
            <p className="section-desc">
              {t.features.subtitle}
            </p>
          </FadeIn>

          <StaggerContainer className="features-grid">
            {featuresList.map((f, i) => (
              <StaggerItem key={i}>
                <SpotlightCard className="feature-card interactive-hover">
                  <motion.div
                    className="feature-icon"
                    whileHover={{ scale: 1.2, rotate: 360 }}
                    transition={{ type: "spring", stiffness: 300, damping: 20 }}
                  >
                    {f.icon}
                  </motion.div>
                  <h3>{f.title}</h3>
                  <p>{f.desc}</p>
                </SpotlightCard>
              </StaggerItem>
            ))}
          </StaggerContainer>
        </div>
      </section>

      {}
      <div className="showcase showcase-app" id="app">
        <div className="container">
          <FadeIn className="section-header">
            <span className="section-label neon-label">{t.appSection.badge}</span>
            <h2 className="section-title"><RevealText text={t.appSection.title} /></h2>
            <p className="section-desc">
              {t.appSection.subtitle}
            </p>
          </FadeIn>
        </div>

        <div className="showcase-row">
          <FadeIn direction="left" className="showcase-content">
            <span className="showcase-label">Dashboard</span>
            <h2>{t.appSection.screen1Title}</h2>
            <p>{t.appSection.screen1Desc}</p>
            <ul className="showcase-features-list">
              <li><span className="showcase-check check-glow"><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12" /></svg></span>Real-time diabetes risk gauge with percentage score</li>
              <li><span className="showcase-check check-glow"><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12" /></svg></span>Live glucose, SpO2, and pulse monitoring cards</li>
              <li><span className="showcase-check check-glow"><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12" /></svg></span>Trend sparklines for instant pattern recognition</li>
            </ul>
          </FadeIn>
          <FadeIn direction="right" className="showcase-image" delay={0.2}>
            <TiltCard>
              <div className="showcase-phone glass-phone advanced-glass float-slow">
                <img src="/suguard2.jpeg" alt="SuGuard dashboard" />
              </div>
            </TiltCard>
          </FadeIn>
        </div>

        <div className="showcase-row reverse">
          <FadeIn direction="right" className="showcase-content">
            <span className="showcase-label">Analytics</span>
            <h2>{t.appSection.screen2Title}</h2>
            <p>{t.appSection.screen2Desc}</p>
            <ul className="showcase-features-list">
              <li><span className="showcase-check check-glow"><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12" /></svg></span>Time-series charts with configurable intervals</li>
              <li><span className="showcase-check check-glow"><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12" /></svg></span>Statistical breakdown: average, min, max values</li>
              <li><span className="showcase-check check-glow"><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12" /></svg></span>Historical trend analysis for proactive management</li>
            </ul>
          </FadeIn>
          <FadeIn direction="left" className="showcase-image" delay={0.2}>
            <TiltCard>
              <div className="showcase-phone glass-phone advanced-glass float-slow delay-1">
                <img src="/suguard5.jpeg" alt="SuGuard glucose analytics" />
              </div>
            </TiltCard>
          </FadeIn>
        </div>
      </div>

      {}
      <section className="section pricing-section relative-section" id="pricing">
        <div className="pricing-grid-bg" />
        <div className="container">
          <FadeIn className="section-header">
            <span className="section-label neon-label">{t.pricing.badge}</span>
            <h2 className="section-title"><RevealText text={t.pricing.title} /></h2>
            <p className="section-desc">
              {t.pricing.subtitle}
            </p>
          </FadeIn>
          <div className="pricing-card-wrapper perspective-container">
            <FadeIn>
              <SpotlightCard className="pricing-card advanced-glass ultra-premium-border floating-anim">
                <div className="pricing-card-glow orb-pulse" />
                <div className="pricing-badge pulse-glow">{t.pricing.popularBadge}</div>
                <div className="pricing-price">
                  <span className="pricing-currency">₸</span>
                  <span className="pricing-amount counter">35,000</span>
                </div>
                <p className="pricing-note">One-time payment · Device + App Subscription (~$70 USD)</p>
                <ul className="pricing-features">
                  <li><span className="pricing-check check-glow"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12" /></svg></span>SuGuard Wearable Device</li>
                  <li><span className="pricing-check check-glow"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12" /></svg></span>Mobile App Subscription</li>
                  <li><span className="pricing-check check-glow"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12" /></svg></span>Glucose, SpO2 & Pulse Monitoring</li>
                  <li><span className="pricing-check check-glow"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12" /></svg></span>AI Health Consultant & Risk Assessment</li>
                  <li><span className="pricing-check check-glow"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12" /></svg></span>Nutrition Tracking & Analytics</li>
                  <li><span className="pricing-check check-glow"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12" /></svg></span>Free Updates & Cloud Sync</li>
                </ul>
                <motion.a
                  whileHover={{ scale: 1.05, boxShadow: "0 0 30px rgba(0, 212, 170, 0.6)" }}
                  whileTap={{ scale: 0.95 }}
                  href="#contact"
                  className="btn-primary pricing-cta glow-button"
                >
                  {t.hero.orderDevice}
                </motion.a>
              </SpotlightCard>
            </FadeIn>
          </div>
        </div>
      </section>

      {}
      <section className="section" id="faq">
        <div className="container">
          <FadeIn className="section-header">
            <span className="section-label neon-label">{t.faq.badge}</span>
            <h2 className="section-title"><RevealText text={t.faq.title} /></h2>
            <p className="section-desc">{t.faq.subtitle}</p>
          </FadeIn>
          <div className="faq-list">
            {faqsList.map((faq, i) => (
              <FadeIn className={`faq-item glass-panel ${activeFaq === i ? ' active' : ''}`} key={i} delay={i * 0.1}>
                <button className="faq-question" onClick={() => toggleFaq(i)}>
                  {faq.q}
                  <motion.span
                    animate={{ rotate: activeFaq === i ? 180 : 0 }}
                    transition={{ duration: 0.4, type: "spring" }}
                    className="faq-chevron"
                  >
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <polyline points="6 9 12 15 18 9" />
                    </svg>
                  </motion.span>
                </button>
                <motion.div
                  initial={false}
                  animate={{ height: activeFaq === i ? "auto" : 0, opacity: activeFaq === i ? 1 : 0 }}
                  transition={{ duration: 0.4, ease: "easeInOut" }}
                  className="faq-answer overflow-hidden"
                >
                  <div className="faq-answer-inner pt-2 pb-6">{faq.a}</div>
                </motion.div>
              </FadeIn>
            ))}
          </div>
        </div>
      </section>

      {}
      <section className="cta-section relative-section" id="contact">
        <div className="section-glow orb-pulse" />
        <FadeIn direction="up">
          <h2 className="hero-title"><RevealText text={t.contact.title} /></h2>
          <p className="section-desc mb-10">
            {t.contact.subtitle}
          </p>
          <div className="cta-actions">
            <motion.a
              whileHover={{ scale: 1.05, boxShadow: "0 0 30px rgba(0, 212, 170, 0.6)" }}
              whileTap={{ scale: 0.95 }}
              href="/app-release.apk"
              download
              className="btn-primary glow-button"
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" />
                <polyline points="7 10 12 15 17 10" />
                <line x1="12" y1="15" x2="12" y2="3" />
              </svg>
              Download APK
            </motion.a>
            <motion.a
              whileHover={{ scale: 1.05, backgroundColor: "rgba(255,255,255,0.05)" }}
              whileTap={{ scale: 0.95 }}
              href="mailto:alihanmurzakmetov15@gmail.com"
              className="btn-secondary"
            >
              {t.nav.contactUs}
            </motion.a>
          </div>
        </FadeIn>
      </section>

      {}
      <footer className="footer" id="footer">
        <div className="footer-content">
          <div className="footer-brand">
            <div className="footer-logo">
              <span className="navbar-logo-icon">SG</span>
              SuGuard
            </div>
            <p>{t.footer.desc}</p>
          </div>
          <div className="footer-column">
            <h4>Product</h4>
            <ul>
              <li><a href="#ecosystem">{t.nav.ecosystem}</a></li>
              <li><a href="#features">{t.nav.features}</a></li>
              <li><a href="#app">{t.nav.app}</a></li>
              <li><a href="#faq">{t.nav.faq}</a></li>
            </ul>
          </div>
          <div className="footer-column">
            <h4>Contact</h4>
            <ul>
              <li><a href="mailto:suguard.kz@gmail.com">suguard.kz@gmail.com</a></li>
              <li><a href="tel:+77056612373">+7 705 661 2373</a></li>
              <li><a href="https://www.instagram.com/suguard_kz" target="_blank" rel="noopener noreferrer">Instagram: @suguard_kz</a></li>
            </ul>
          </div>
          <div className="footer-column">
            <h4>Download</h4>
            <ul>
              <li><a href="/app-release.apk" download>Android APK</a></li>
              <li><a href="#">iOS (Coming Soon)</a></li>
            </ul>
          </div>
        </div>
        <div className="footer-bottom">
          <p>© 2026 SuGuard. {t.footer.rights} Made in Kazakhstan.</p>
          <span className="footer-version">v1.2.0-ULTRA</span>
        </div>
      </footer>

      {}
      {isVideoModalOpen && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="video-modal-backdrop"
          onClick={() => setIsVideoModalOpen(false)}
        >
          <motion.div
            initial={{ scale: 0.8, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ type: "spring", stiffness: 300, damping: 25 }}
            className="video-modal-container"
            onClick={(e) => e.stopPropagation()}
          >
            <button
              className="video-modal-close"
              onClick={() => setIsVideoModalOpen(false)}
              aria-label="Close Video"
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <line x1="18" y1="6" x2="6" y2="18" />
                <line x1="6" y1="6" x2="18" y2="18" />
              </svg>
            </button>
            <video
              src="/video.mp4"
              controls
              autoPlay
              playsInline
              className="video-modal-element"
            />
          </motion.div>
        </motion.div>
      )}
    </div>
  );
}

export default App;
