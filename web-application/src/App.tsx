import { useState, useRef } from 'react';
import { motion, useScroll, useTransform, useSpring, useMotionValue, useMotionTemplate } from 'framer-motion';
import './App.css';
import './extreme.css';

const NAV_LINKS = [
  { label: 'Ecosystem', href: '#ecosystem' },
  { label: 'Achievements', href: '#achievements' },
  { label: 'Experts', href: '#experts' },
  { label: 'Partners', href: '#partners' },
  { label: 'Features', href: '#features' },
  { label: 'App', href: '#app' },
  { label: 'Pricing', href: '#pricing' },
  { label: 'FAQ', href: '#faq' },
];

const FEATURES = [
  {
    icon: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
      </svg>
    ),
    title: 'Glucose Monitoring',
    desc: 'Non-invasive blood glucose measurement via the wearable device with real-time data sync to your phone.',
  },
  {
    icon: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="10" />
        <path d="M12 6v6l4 2" />
      </svg>
    ),
    title: 'Diabetes Risk',
    desc: 'Algorithm-driven risk scoring based on glucose, SpO2, pulse, and historical data. Actionable insights for prevention.',
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
    title: 'Nutrition Tracking',
    desc: 'Log meals by photo or manually. Automatic macro breakdown: calories, protein, fat, and carbohydrates per day.',
  },
  {
    icon: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M20.84 4.61a5.5 5.5 0 00-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 00-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 000-7.78z" />
      </svg>
    ),
    title: 'SpO2 & Pulse',
    desc: 'Continuous oxygen saturation and heart rate monitoring via built-in sensors. Early detection of cardiovascular anomalies.',
  },
  {
    icon: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z" />
      </svg>
    ),
    title: 'AI Consultant',
    desc: 'Intelligent assistant trained on your health data. Answers questions about glucose trends, nutrition, and risk factors.',
  },
  {
    icon: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <rect x="5" y="2" width="14" height="20" rx="2" ry="2" />
        <line x1="12" y1="18" x2="12.01" y2="18" />
      </svg>
    ),
    title: 'Instant Cloud Sync',
    desc: 'The wearable device connects to the mobile app via Bluetooth. All readings are synced automatically to your dashboard.',
  },
];

const FAQS = [
  {
    q: 'What is SuGuard?',
    a: 'SuGuard is a health monitoring ecosystem consisting of a wearable device and a companion mobile application. The device measures glucose, SpO2, and pulse non-invasively, while the app provides analytics, risk assessment, nutrition tracking, and a personalized health consultant.',
  },
  {
    q: 'How does the wearable device work?',
    a: 'The SuGuard wearable is worn on the wrist and uses optical sensors to measure blood glucose, oxygen saturation (SpO2), and pulse rate. Data is transmitted to the mobile app via Bluetooth in real-time and stored securely in the cloud.',
  },
  {
    q: 'How does the diabetes risk assessment work?',
    a: 'The risk assessment algorithm analyzes your average glucose level, resting pulse rate, SpO2 levels, and historical health data to calculate a percentage-based risk score. Each contributing factor is displayed with a progress indicator so you can understand which areas need attention.',
  },
  {
    q: 'Can I track my meals and nutrition?',
    a: 'Yes. SuGuard offers two methods for logging meals: photograph your food for automatic recognition and nutritional breakdown, or enter meals manually. The app calculates calories, protein, fat, and carbohydrates for each entry and displays daily totals.',
  },
  {
    q: 'Is my health data secure?',
    a: 'All data is stored securely using Firebase with encryption. Your health information is linked exclusively to your authenticated account and is never shared with third parties.',
  },
];



const RevealText = ({ text, className = "" }: { text: string, className?: string }) => {
  const words = text.split(" ");
  return (
    <motion.div
      initial="hidden"
      whileInView="visible"
      viewport={{ once: true, margin: "-50px" }}
      variants={{
        visible: { transition: { staggerChildren: 0.1 } },
        hidden: {}
      }}
      className={className}
      style={{ display: "inline-block" }}
    >
      {words.map((word, i) => (
        <span key={i} style={{ display: "inline-block", overflow: "hidden", paddingRight: "0.25em" }}>
          <motion.span
            variants={{
              hidden: { y: "100%", opacity: 0 },
              visible: {
                y: "0%",
                opacity: 1,
                transition: { duration: 0.8, ease: [0.16, 1, 0.3, 1] }
              }
            }}
            style={{ display: "inline-block" }}
          >
            {word}
          </motion.span>
        </span>
      ))}
    </motion.div>
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
        rotateX,
        rotateY,
        transformStyle: "preserve-3d",
      }}
      whileHover={{ scale: 1.05 }}
      transition={{ type: "spring", stiffness: 400, damping: 30 }}
      className={`tilt-card ${className}`}
    >
      <div style={{ transform: "translateZ(50px)" }}>
        {children}
      </div>
    </motion.div>
  );
};


const FadeIn = ({ children, delay = 0, className = "", direction = "up" }: any) => {
  const offsets = {
    up: { y: 60, x: 0 },
    down: { y: -60, x: 0 },
    left: { x: 60, y: 0 },
    right: { x: -60, y: 0 }
  };

  return (
    <motion.div
      initial={{ opacity: 0, ...offsets[direction as keyof typeof offsets] }}
      whileInView={{ opacity: 1, x: 0, y: 0 }}
      viewport={{ once: true, margin: "-100px" }}
      transition={{ duration: 1, delay, ease: [0.16, 1, 0.3, 1] }}
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
    viewport={{ once: true, margin: "-100px" }}
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
          {NAV_LINKS.map((link) => (
            <a key={link.href} href={link.href} className="nav-link-hover magnetic-btn">
              {link.label}
            </a>
          ))}
        </div>
        <div className="navbar-right">
          <motion.a
            whileHover={{ scale: 1.05, boxShadow: "0 0 20px rgba(0, 212, 170, 0.4)" }}
            whileTap={{ scale: 0.95 }}
            href="#contact"
            className="navbar-cta glow-button"
          >
            Contact Us
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
        {NAV_LINKS.map((link) => (
          <a key={link.href} href={link.href} onClick={closeMobile}>{link.label}</a>
        ))}
        <a href="#contact" onClick={closeMobile} className="btn-primary glow-button" style={{ textAlign: 'center' }}>
          Contact Us
        </a>
      </div>

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
            Wearable Device + Mobile Application
          </motion.div>

          <h1 className="hero-title">
            <RevealText text="The complete ecosystem" />
            <br />
            <RevealText text="for health monitoring" className="accent gradient-text" />
          </h1>

          <FadeIn delay={0.4} direction="up" className="hero-subtitle">
            A wearable device that measures glucose, SpO2, and pulse non-invasively,
            paired with an intelligent mobile app for analytics, risk assessment, and nutrition tracking.
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
              Watch Demo Video
            </motion.button>
            <motion.a
              whileHover={{ scale: 1.05, backgroundColor: "rgba(255,255,255,0.05)" }}
              whileTap={{ scale: 0.95 }}
              href="#ecosystem"
              className="btn-secondary magnetic-btn"
            >
              Explore Ecosystem
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



      <section className="section ecosystem-section relative-section" id="ecosystem">
        <div className="section-glow" />
        <div className="container">
          <FadeIn className="section-header">
            <span className="section-label neon-label">Ecosystem</span>
            <h2 className="section-title"><RevealText text="Two components, one mission" /></h2>
            <p className="section-desc">
              SuGuard combines hardware and software into a unified health monitoring system
              designed for proactive diabetes prevention and daily wellness management.
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
                  <div className="ecosystem-card-label">Hardware</div>
                  <h3>SuGuard Wearable</h3>
                  <p>
                    A compact wrist-worn device with built-in optical sensors for non-invasive
                    measurement of blood glucose, SpO2 saturation, and pulse rate. Connects to
                    your phone via Bluetooth for continuous data synchronization.
                  </p>
                  <ul className="ecosystem-specs">
                    <li><span className="spec-name">Sensors</span><span className="spec-value gradient-text-subtle">Glucose, SpO2, Pulse</span></li>
                    <li><span className="spec-name">Connectivity</span><span className="spec-value">Bluetooth 5.0</span></li>
                    <li><span className="spec-name">Platform</span><span className="spec-value">ESP32 Engine</span></li>
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
                  <div className="ecosystem-card-label">Software</div>
                  <h3>SuGuard App</h3>
                  <p>
                    A feature-rich mobile application that receives data from the wearable device
                    and transforms it into actionable health insights. Includes risk assessment,
                    nutrition tracking, analytics charts, and an intelligent health consultant.
                  </p>
                  <ul className="ecosystem-specs">
                    <li><span className="spec-name">Platform</span><span className="spec-value gradient-text-subtle">Android (Flutter)</span></li>
                    <li><span className="spec-name">Backend</span><span className="spec-value">Firebase Sync</span></li>
                    <li><span className="spec-name">Analytics</span><span className="spec-value">Groq LLM AI</span></li>
                  </ul>
                </div>
              </SpotlightCard>
            </StaggerItem>
          </StaggerContainer>
        </div>
      </section>


      {/* Achievements & Impact Section */}
      <section className="section relative-section" id="achievements">
        <div className="section-glow" />
        <div className="container">
          <FadeIn className="section-header">
            <span className="section-label neon-label">Achievements & Impact</span>
            <h2 className="section-title"><RevealText text="Наши достижения и результаты" /></h2>
            <p className="section-desc">
              Ключевые показатели эффективности, привлеченные грантовые инвестиции, проверенная точность устройства и клиника CustDev.
            </p>
          </FadeIn>

          <StaggerContainer className="achievements-grid">
            <StaggerItem>
              <SpotlightCard className="achievement-card glass-panel premium-border">
                <div className="achievement-val gradient-text">$13,000</div>
                <div className="achievement-title">Привлеченные инвестиции</div>
                <div className="achievement-desc">Привлечено в проект через грантовые программы и профильные конкурсы.</div>
              </SpotlightCard>
            </StaggerItem>

            <StaggerItem>
              <SpotlightCard className="achievement-card glass-panel premium-border">
                <div className="achievement-val gradient-text">94%</div>
                <div className="achievement-title">Точность измерения</div>
                <div className="achievement-desc">Подтвержденная точность работы неинвазивного глюкометра на базе нейросетей.</div>
              </SpotlightCard>
            </StaggerItem>

            <StaggerItem>
              <SpotlightCard className="achievement-card glass-panel premium-border">
                <div className="achievement-val gradient-text">50+</div>
                <div className="achievement-title">Пользовательских тестов</div>
                <div className="achievement-desc">Успешно проведенных реальных исследований и тестирований в рамках CustDev.</div>
              </SpotlightCard>
            </StaggerItem>

            <StaggerItem>
              <SpotlightCard className="achievement-card glass-panel premium-border">
                <div className="achievement-val gradient-text">4+</div>
                <div className="achievement-title">Официальных партнера</div>
                <div className="achievement-desc">Сотрудничество с клиниками, медицинскими центрами и общественными институтами.</div>
              </SpotlightCard>
            </StaggerItem>
          </StaggerContainer>
        </div>
      </section>

      {/* Expert Advisory Board & CustDev Section */}
      <section className="section relative-section" id="experts">
        <div className="section-glow" />
        <div className="container">
          <FadeIn className="section-header">
            <span className="section-label neon-label">CustDev & Scientific Advisory Board</span>
            <h2 className="section-title"><RevealText text="Экспертный совет и CustDev" /></h2>
            <p className="section-desc">
              Ведущие международные и национальные эксперты, оказавшие профессиональную поддержку в рамках CustDev, повышении точности прибора и создании прототипа.
            </p>
          </FadeIn>

          <StaggerContainer className="experts-grid">
            <StaggerItem>
              <SpotlightCard className="expert-card glass-panel premium-border">
                <div className="expert-avatar-box">
                  <img src="/jerryloeb.jpeg" alt="Jerry Loeb" className="expert-avatar-img" />
                </div>
                <div className="expert-tag">Scientific Advisor</div>
                <h3 className="expert-name">Jerry Loeb</h3>
                <div className="expert-affiliation">University of Southern California</div>
                <p className="expert-desc">
                  AI-driven recommendations developed by bio-engineers and PhD researchers at University of Southern California. Консультации по алгоритмам ИИ и биоинженерным решениям.
                </p>
              </SpotlightCard>
            </StaggerItem>

            <StaggerItem>
              <SpotlightCard className="expert-card glass-panel premium-border">
                <div className="expert-avatar-box">
                  <img src="/aidaralimbayev.jpeg" alt="Aidar Alimbayev" className="expert-avatar-img" />
                </div>
                <div className="expert-tag">AI & Accuracy Expert</div>
                <h3 className="expert-name">Aidar Alimbayev</h3>
                <div className="expert-affiliation">PhD Student at MBZUAI • AI Researcher</div>
                <p className="expert-desc">
                  Provided recommendations on improving device accuracy and implementing AI for glucose data analysis. Исследователь в сфере ИИ, помог достигнуть точности 94%.
                </p>
              </SpotlightCard>
            </StaggerItem>

            <StaggerItem>
              <SpotlightCard className="expert-card glass-panel premium-border">
                <div className="expert-avatar-box">
                  <img src="/rustam_askaruly.jpeg" alt="Askaruly Rustam" className="expert-avatar-img" />
                </div>
                <div className="expert-tag">Hardware Prototyping Specialist</div>
                <h3 className="expert-name">Askaruly Rustam</h3>
                <div className="expert-affiliation">Fab Lab NURIS Digital Prototyping Engineer</div>
                <p className="expert-desc">
                  Prototyping specialist. Participated in the development of the first device prototype. Специалист по цифровому прототипированию, созданию первого образца устройства.
                </p>
              </SpotlightCard>
            </StaggerItem>
          </StaggerContainer>
        </div>
      </section>

      {/* Partners & Institutional Collaborations Section */}
      <section className="section partners-section relative-section" id="partners">
        <div className="section-glow-blue parallax-glow" />
        <div className="container">
          <FadeIn className="section-header">
            <span className="section-label neon-label">Partnerships & Collaborations</span>
            <h2 className="section-title"><RevealText text="Официальное сотрудничество" /></h2>
            <p className="section-desc">
              Мы активно сотрудничаем с ведущими медицинскими центрами, больницами и общественными организациями.
            </p>
          </FadeIn>

          <StaggerContainer className="partners-grid">
            <StaggerItem>
              <SpotlightCard className="partner-card glass-panel premium-border">
                <div className="partner-info">
                  <h3>ГКП на ПХВ «БРБ»</h3>
                  <p>Городская клиническая больница (Аксайская больница) - практическое сотрудничество и экспертная апробация устройства.</p>
                </div>
              </SpotlightCard>
            </StaggerItem>

            <StaggerItem>
              <SpotlightCard className="partner-card glass-panel premium-border">
                <div className="partner-info">
                  <h3>Медицинский центр «Авиценна»</h3>
                  <p>Партнерство в сфере клинических консультаций, сбора данных и тестирования методологии мониторинга.</p>
                </div>
              </SpotlightCard>
            </StaggerItem>

            <StaggerItem>
              <SpotlightCard className="partner-card glass-panel premium-border">
                <div className="partner-info">
                  <h3>Медцентр Управления делами Президента РК</h3>
                  <p>Консультационное взаимодействие и экспертная оценка технологий SuGuard от квалифицированных врачей.</p>
                </div>
              </SpotlightCard>
            </StaggerItem>

            <StaggerItem>
              <SpotlightCard className="partner-card glass-panel premium-border">
                <div className="partner-info">
                  <h3>Партия «Аманат»</h3>
                  <p>Социально-инновационная поддержка проекта и взаимодействие по программам укрепления здоровья населения.</p>
                </div>
              </SpotlightCard>
            </StaggerItem>
          </StaggerContainer>

          <FadeIn className="academic-wrapper">
            <div className="academic-title">
              <span>Научные инициативы & Предложения по сотрудничеству</span>
            </div>

            <div className="academic-grid">
              <div className="academic-card">
                <h4>ННЦРЗ им. Салидат Каирбековой</h4>
                <p>Национальный научный центр развития здравоохранения - инициативные предложения по интеграции технологических решений.</p>
              </div>
              <div className="academic-card">
                <h4>Назарбаев Университет</h4>
                <p>Nazarbayev University - научно-технологический CustDev, исследования и прототипирование на базе Fab Lab NURIS.</p>
              </div>
              <div className="academic-card">
                <h4>Медицинский Университет Астаны</h4>
                <p>Академические консультации с экспертами профильных кафедр и диабетологами университета.</p>
              </div>
            </div>
          </FadeIn>
        </div>
      </section>

      <section className="section features" id="features">
        <div className="container">
          <FadeIn className="section-header">
            <span className="section-label neon-label">Features</span>
            <h2 className="section-title"><RevealText text="Everything you need to manage your health" /></h2>
            <p className="section-desc">
              A comprehensive suite of tools combining hardware sensors and software intelligence
              for proactive diabetes prevention and daily health optimization.
            </p>
          </FadeIn>

          <StaggerContainer className="features-grid">
            {FEATURES.map((f, i) => (
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

      <div className="showcase showcase-app" id="app">
        <div className="container">
          <FadeIn className="section-header">
            <span className="section-label neon-label">Mobile Application</span>
            <h2 className="section-title"><RevealText text="Your health data, visualized" /></h2>
            <p className="section-desc">
              The companion app transforms raw sensor data into clear, actionable health insights.
            </p>
          </FadeIn>
        </div>

        <div className="showcase-row">
          <FadeIn direction="left" className="showcase-content">
            <span className="showcase-label">Dashboard</span>
            <h2>Your health at a glance</h2>
            <p>
              The main dashboard aggregates all your vital signs into a single, intuitive interface.
              Monitor diabetes risk score, glucose levels, SpO2 saturation, and pulse rate without navigating between screens.
            </p>
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
            <h2>Deep dive into your glucose data</h2>
            <p>
              Interactive charts with day, week, and month views provide granular insight into your blood glucose behavior.
              Statistical summaries highlight averages, minimums, and maximums to track progress over time.
            </p>
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

        <div className="showcase-row">
          <FadeIn direction="left" className="showcase-content">
            <span className="showcase-label">Risk Assessment</span>
            <h2>Understand your risk factor</h2>
            <p>
              A detailed breakdown of the factors contributing to your diabetes risk score.
              Each metric is visualized with progress indicators and contextual values so you know exactly what to improve.
            </p>
            <ul className="showcase-features-list">
              <li><span className="showcase-check check-glow"><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12" /></svg></span>Multi-factor risk calculation with visual gauge</li>
              <li><span className="showcase-check check-glow"><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12" /></svg></span>Individual progress bars for glucose, pulse, SpO2</li>
              <li><span className="showcase-check check-glow"><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12" /></svg></span>Glucose trend chart integrated into risk overview</li>
            </ul>
          </FadeIn>
          <FadeIn direction="right" className="showcase-image" delay={0.2}>
            <TiltCard>
              <div className="showcase-phone glass-phone advanced-glass float-slow delay-2">
                <img src="/suguard4.jpeg" alt="SuGuard risk assessment" />
              </div>
            </TiltCard>
          </FadeIn>
        </div>
      </div>

      <section className="section metrics relative-section">
        <div className="section-glow-blue parallax-glow" />
        <div className="container">
          <StaggerContainer className="metrics-grid">
            <StaggerItem className="metric-item glass-metric">
              <motion.div
                initial={{ scale: 0 }}
                whileInView={{ scale: 1, rotate: [0, 10, -10, 0] }}
                transition={{ type: "spring", delay: 0.1, duration: 1 }}
                className="metric-value counter gradient-text"
              >
                3
              </motion.div>
              <div className="metric-label">Sensors: glucose, SpO2, pulse</div>
            </StaggerItem>
            <StaggerItem className="metric-item glass-metric">
              <motion.div
                initial={{ scale: 0 }}
                whileInView={{ scale: 1, rotate: [0, -10, 10, 0] }}
                transition={{ type: "spring", delay: 0.2, duration: 1 }}
                className="metric-value gradient-text"
              >
                24/7
              </motion.div>
              <div className="metric-label">Continuous health monitoring</div>
            </StaggerItem>
            <StaggerItem className="metric-item glass-metric">
              <motion.div
                initial={{ scale: 0 }}
                whileInView={{ scale: 1, rotate: [0, 10, -10, 0] }}
                transition={{ type: "spring", delay: 0.3, duration: 1 }}
                className="metric-value counter gradient-text"
              >
                5+
              </motion.div>
              <div className="metric-label">App modules: dashboard, charts, risk</div>
            </StaggerItem>
            <StaggerItem className="metric-item glass-metric">
              <motion.div
                initial={{ scale: 0 }}
                whileInView={{ scale: 1, rotate: [0, -10, 10, 0] }}
                transition={{ type: "spring", delay: 0.4, duration: 1 }}
                className="metric-value gradient-text"
              >
                &lt;1s
              </motion.div>
              <div className="metric-label">Bluetooth sync latency</div>
            </StaggerItem>
          </StaggerContainer>
        </div>
      </section>

      <section className="section pricing-section relative-section" id="pricing">
        <div className="pricing-grid-bg" />
        <div className="container">
          <FadeIn className="section-header">
            <span className="section-label neon-label">Pricing</span>
            <h2 className="section-title"><RevealText text="One price, full ecosystem" /></h2>
            <p className="section-desc">
              Get the SuGuard wearable device and a full app subscription - everything you need for proactive health monitoring.
            </p>
          </FadeIn>
          <div className="pricing-card-wrapper perspective-container">
            <FadeIn>
              <SpotlightCard className="pricing-card advanced-glass ultra-premium-border floating-anim">
                <div className="pricing-card-glow orb-pulse" />
                <div className="pricing-badge pulse-glow">Full Ecosystem</div>
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
                  Get SuGuard Now
                </motion.a>
              </SpotlightCard>
            </FadeIn>
          </div>
        </div>
      </section>

      <section className="section" id="faq">
        <div className="container">
          <FadeIn className="section-header">
            <span className="section-label neon-label">FAQ</span>
            <h2 className="section-title"><RevealText text="Frequently asked questions" /></h2>
          </FadeIn>
          <div className="faq-list">
            {FAQS.map((faq, i) => (
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

      <section className="cta-section relative-section" id="contact">
        <div className="section-glow orb-pulse" />
        <FadeIn direction="up">
          <h2 className="hero-title"><RevealText text="Start monitoring your health today" /></h2>
          <p className="section-desc mb-10">
            Download the SuGuard app, pair your wearable device, and take control of your health data.
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
              Contact Us
            </motion.a>
          </div>
        </FadeIn>
      </section>

      <footer className="footer" id="footer">
        <div className="footer-content">
          <div className="footer-brand">
            <div className="footer-logo">
              <span className="navbar-logo-icon">SG</span>
              SuGuard
            </div>
            <p>
              An integrated health monitoring ecosystem combining a wearable sensor device
              with an intelligent mobile application. Built in Kazakhstan.
            </p>
          </div>
          <div className="footer-column">
            <h4>Product</h4>
            <ul>
              <li><a href="#ecosystem">Ecosystem</a></li>
              <li><a href="#features">Features</a></li>
              <li><a href="#device">Device</a></li>
              <li><a href="#app">App</a></li>
              <li><a href="#faq">FAQ</a></li>
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
          <p>© 2026 SuGuard. All rights reserved. Made in Kazakhstan.</p>
          <span className="footer-version">v1.2.0-ULTRA</span>
        </div>
      </footer>

      {/* Lightbox Modal Video Player */}
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
