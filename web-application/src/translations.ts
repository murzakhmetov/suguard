export type Language = 'ru' | 'en' | 'kk';

export interface TranslationSchema {
  nav: {
    ecosystem: string;
    achievements: string;
    experts: string;
    partners: string;
    features: string;
    app: string;
    pricing: string;
    faq: string;
    contactUs: string;
  };
  hero: {
    badge: string;
    title: string;
    subtitle: string;
    watchDemo: string;
    orderDevice: string;
    statAccuracy: string;
    statAccuracySub: string;
    statTests: string;
    statTestsSub: string;
    statInvestment: string;
    statInvestmentSub: string;
    statSync: string;
    statSyncSub: string;
  };
  ecosystem: {
    badge: string;
    title: string;
    subtitle: string;
    hardwareTitle: string;
    hardwareBadge: string;
    hardwareDesc: string;
    hardwareFeat1Title: string;
    hardwareFeat1Desc: string;
    hardwareFeat2Title: string;
    hardwareFeat2Desc: string;
    hardwareFeat3Title: string;
    hardwareFeat3Desc: string;
    appTitle: string;
    appBadge: string;
    appDesc: string;
    appFeat1Title: string;
    appFeat1Desc: string;
    appFeat2Title: string;
    appFeat2Desc: string;
    appFeat3Title: string;
    appFeat3Desc: string;
  };
  achievements: {
    badge: string;
    title: string;
    subtitle: string;
    invTitle: string;
    invDesc: string;
    accTitle: string;
    accDesc: string;
    testsTitle: string;
    testsDesc: string;
    partnersTitle: string;
    partnersDesc: string;
  };
  experts: {
    badge: string;
    title: string;
    subtitle: string;
    jerryRole: string;
    jerryAff: string;
    jerryDesc: string;
    aidarRole: string;
    aidarAff: string;
    aidarDesc: string;
    rustamRole: string;
    rustamAff: string;
    rustamDesc: string;
  };
  partners: {
    badge: string;
    title: string;
    subtitle: string;
    brbTitle: string;
    brbDesc: string;
    avicennaTitle: string;
    avicennaDesc: string;
    presidentialTitle: string;
    presidentialDesc: string;
    amanatTitle: string;
    amanatDesc: string;
    academicTitle: string;
    nncrzTitle: string;
    nncrzDesc: string;
    nuTitle: string;
    nuDesc: string;
    amuTitle: string;
    amuDesc: string;
  };
  features: {
    badge: string;
    title: string;
    subtitle: string;
    f1Title: string;
    f1Desc: string;
    f2Title: string;
    f2Desc: string;
    f3Title: string;
    f3Desc: string;
    f4Title: string;
    f4Desc: string;
    f5Title: string;
    f5Desc: string;
    f6Title: string;
    f6Desc: string;
  };
  device: {
    badge: string;
    title: string;
    subtitle: string;
    spec1Title: string;
    spec1Desc: string;
    spec2Title: string;
    spec2Desc: string;
    spec3Title: string;
    spec3Desc: string;
    spec4Title: string;
    spec4Desc: string;
  };
  appSection: {
    badge: string;
    title: string;
    subtitle: string;
    screen1Title: string;
    screen1Desc: string;
    screen2Title: string;
    screen2Desc: string;
    screen3Title: string;
    screen3Desc: string;
    screen4Title: string;
    screen4Desc: string;
  };
  pricing: {
    badge: string;
    title: string;
    subtitle: string;
    plan1Name: string;
    plan1Price: string;
    plan1Desc: string;
    plan1Feat1: string;
    plan1Feat2: string;
    plan1Feat3: string;
    plan1Feat4: string;
    plan1Btn: string;
    plan2Name: string;
    plan2Price: string;
    plan2Desc: string;
    plan2Feat1: string;
    plan2Feat2: string;
    plan2Feat3: string;
    plan2Feat4: string;
    plan2Btn: string;
    plan3Name: string;
    plan3Price: string;
    plan3Desc: string;
    plan3Feat1: string;
    plan3Feat2: string;
    plan3Feat3: string;
    plan3Feat4: string;
    plan3Btn: string;
    popularBadge: string;
  };
  faq: {
    badge: string;
    title: string;
    subtitle: string;
    q1: string;
    a1: string;
    q2: string;
    a2: string;
    q3: string;
    a3: string;
    q4: string;
    a4: string;
    q5: string;
    a5: string;
  };
  contact: {
    badge: string;
    title: string;
    subtitle: string;
    nameLabel: string;
    namePlaceholder: string;
    emailLabel: string;
    emailPlaceholder: string;
    phoneLabel: string;
    phonePlaceholder: string;
    messageLabel: string;
    messagePlaceholder: string;
    submitBtn: string;
    submittedMsg: string;
  };
  footer: {
    rights: string;
    desc: string;
  };
}

export const translations: Record<Language, TranslationSchema> = {
  ru: {
    nav: {
      ecosystem: 'Экосистема',
      achievements: 'Достижения',
      experts: 'Эксперты',
      partners: 'Партнеры',
      features: 'Функции',
      app: 'Приложение',
      pricing: 'Тарифы',
      faq: 'FAQ',
      contactUs: 'Связаться',
    },
    hero: {
      badge: 'ИИ-Экосистема Мониторинга Здоровья',
      title: 'Умный неинвазивный мониторинг сахара и риск-анализ',
      subtitle: 'Инновационный носимый трекер и мобильное приложение для непрерывного отслеживания глюкозы, SpO2, пульса и предотвращения диабета.',
      watchDemo: 'Смотреть демо видео',
      orderDevice: 'Приобрести устройство',
      statAccuracy: '94%',
      statAccuracySub: 'Точность измерения',
      statTests: '50+',
      statTestsSub: 'Успешных тестов',
      statInvestment: '$13K',
      statInvestmentSub: 'Инвестиции и гранты',
      statSync: '< 1 сек',
      statSyncSub: 'Скорость синхронизации',
    },
    ecosystem: {
      badge: 'Двухкомпонентная экосистема',
      title: 'Носимое устройство + Мобильное приложение',
      subtitle: 'Забудьте о болезненном проколе пальцев. Получайте точные показания глюкозы на запястье и анализируйте риски в реальном времени.',
      hardwareTitle: 'Носимый сенсор SuGuard',
      hardwareBadge: 'HARDWARE',
      hardwareDesc: 'Умный смарт-браслет со встроенными спектроскопическими датчиками для неинвазивного анализа крови.',
      hardwareFeat1Title: 'Оптические PPG-сенсоры',
      hardwareFeat1Desc: 'Измерение сахара и кислорода без иголок и тест-полосок.',
      hardwareFeat2Title: 'Bluetooth 5.3 Low Energy',
      hardwareFeat2Desc: 'Мгновенная передача данных на смарт-устройство.',
      hardwareFeat3Title: 'Автономность до 7 дней',
      hardwareFeat3Desc: 'Быстрая зарядка и влагозащищенный корпус.',
      appTitle: 'Мобильное приложение SuGuard',
      appBadge: 'SOFTWARE & AI',
      appDesc: 'Персональный цифровой ассистент с ИИ-моделью оценки риска диабета и трекером питания.',
      appFeat1Title: 'ИИ-оценка риска диабета',
      appFeat1Desc: 'Расчет вероятности в % на базе глюкозы, пульса и SpO2.',
      appFeat2Title: 'Трекер питания по фото',
      appFeat2Desc: 'Автоматический подсчет БЖУ и калорий по фотографии блюда.',
      appFeat3Title: 'Персональный ИИ-Консультант',
      appFeat3Desc: 'Ответы на вопросы и рекомендации по предотвращению скачков сахара.',
    },
    achievements: {
      badge: 'Achievements & Impact',
      title: 'Наши достижения и результаты',
      subtitle: 'Ключевые показатели эффективности, привлеченные грантовые инвестиции, проверенная точность устройства и клиника CustDev.',
      invTitle: 'Привлеченные инвестиции',
      invDesc: 'Привлечено в проект через грантовые программы и профильные конкурсы.',
      accTitle: 'Точность измерения',
      accDesc: 'Подтвержденная точность работы неинвазивного глюкометра на базе нейросетей.',
      testsTitle: 'Пользовательских тестов',
      testsDesc: 'Успешно проведенных реальных исследований и тестирований в рамках CustDev.',
      partnersTitle: 'Официальных партнера',
      partnersDesc: 'Сотрудничество с клиниками, медицинскими центрами и общественными институтами.',
    },
    experts: {
      badge: 'CustDev & Scientific Advisory Board',
      title: 'Экспертный совет и CustDev',
      subtitle: 'Ведущие международные и национальные эксперты, оказавшие профессиональную поддержку в рамках CustDev, повышении точности прибора и создании прототипа.',
      jerryRole: 'Scientific Advisor',
      jerryAff: 'University of Southern California',
      jerryDesc: 'AI-driven recommendations developed by bio-engineers and PhD researchers at University of Southern California. Консультации по алгоритмам ИИ и биоинженерным решениям.',
      aidarRole: 'AI & Accuracy Expert',
      aidarAff: 'PhD Student at MBZUAI • AI Researcher',
      aidarDesc: 'Provided recommendations on improving device accuracy and implementing AI for glucose data analysis. Исследователь в сфере ИИ, помог достигнуть точности 94%.',
      rustamRole: 'Hardware Prototyping Specialist',
      rustamAff: 'Fab Lab NURIS Digital Prototyping Engineer',
      rustamDesc: 'Prototyping specialist. Participated in the development of the first device prototype. Специалист по цифровому прототипированию, созданию первого образца устройства.',
    },
    partners: {
      badge: 'Partnerships & Collaborations',
      title: 'Официальное сотрудничество',
      subtitle: 'Мы активно сотрудничаем с ведущими медицинскими центрами, больницами и общественными организациями.',
      brbTitle: 'ГКП на ПХВ «БРБ»',
      brbDesc: 'Городская клиническая больница (Аксайская больница) - практическое сотрудничество и экспертная апробация устройства.',
      avicennaTitle: 'Медицинский центр «Авиценна»',
      avicennaDesc: 'Партнерство в сфере клинических консультаций, сбора данных и тестирования методологии мониторинга.',
      presidentialTitle: 'Медцентр Управления делами Президента РК',
      presidentialDesc: 'Консультационное взаимодействие и экспертная оценка технологий SuGuard от квалифицированных врачей.',
      amanatTitle: 'Партия «Аманат»',
      amanatDesc: 'Социально-инновационная поддержка проекта и взаимодействие по программам укрепления здоровья населения.',
      academicTitle: 'Научные инициативы & Предложения по сотрудничеству',
      nncrzTitle: 'ННЦРЗ им. Салидат Каирбековой',
      nncrzDesc: 'Национальный научный центр развития здравоохранения - инициативные предложения по интеграции технологических решений.',
      nuTitle: 'Назарбаев Университет',
      nuDesc: 'Nazarbayev University - научно-технологический CustDev, исследования и прототипирование на базе Fab Lab NURIS.',
      amuTitle: 'Медицинский Университет Астаны',
      amuDesc: 'Академические консультации с экспертами профильных кафедр и диабетологами университета.',
    },
    features: {
      badge: 'Features',
      title: 'Все необходимое для контроля здоровья',
      subtitle: 'Комплексный набор инструментов, объединяющий физический сенсор и искусственный интеллект для профилактики диабета.',
      f1Title: 'Мониторинг глюкозы',
      f1Desc: 'Неинвазивный анализ уровня сахара в крови на базе оптических сенсоров с синхронизацией в реальном времени.',
      f2Title: 'Оценка риска диабета',
      f2Desc: 'Расчет вероятности возникновения диабета по алгоритмам анализа глюкозы, SpO2 и пульса.',
      f3Title: 'Трекер питания',
      f3Desc: 'Ведение дневника питания вручную или по фото с авто-расчетом белков, жиров, углеводов и калорий.',
      f4Title: 'SpO2 и Пульсометр',
      f4Desc: 'Непрерывное измерение уровня кислорода в крови и частоты сердечных сокращений.',
      f5Title: 'ИИ-Консультант',
      f5Desc: 'Персональный ИИ-ассистент, анализирующий ваши данные и отвечающий на любые вопросы о здоровье.',
      f6Title: 'Облачная синхронизация',
      f6Desc: 'Мгновенное сохранение результатов в защищенном облаке через Bluetooth 5.3.',
    },
    device: {
      badge: 'Hardware Specs',
      title: 'Инженерное превосходство сенсора',
      subtitle: 'Высокоточные оптические датчики в компактном эргономичном корпусе.',
      spec1Title: 'PPG Оптический модуль',
      spec1Desc: 'Двухволновой оптический анализатор высокой точности.',
      spec2Title: 'Корпус из авиационного алюминия',
      spec2Desc: 'Легкий, прочный и защищенный по стандарту IP67.',
      spec3Title: 'Энергоэффективный процессор',
      spec3Desc: 'Микроконтроллер с низким энергопотреблением и быстрой обработкой сигналов.',
      spec4Title: 'Гипоаллергенный ремешок',
      spec4Desc: 'Комфортное ношение 24/7 без раздражения кожи.',
    },
    appSection: {
      badge: 'App Interface',
      title: 'Интуитивный мобильный интерфейс',
      subtitle: 'Наглядная аналитика, динамические графики и моментальные уведомления.',
      screen1Title: 'Главный дашборд',
      screen1Desc: 'Текущий уровень сахара, пульс, SpO2 и статус подключения устройства.',
      screen2Title: 'Карта риска диабета',
      screen2Desc: 'Детальный разбор факторов риска и персональные рекомендации.',
      screen3Title: 'Дневник питания',
      screen3Desc: 'Распознавание блюд по фото и суточный баланс калорий.',
      screen4Title: 'Чат с ИИ-Консультантом',
      screen4Desc: 'Круглосуточная поддержка и ответы на вопросы по вашему здоровью.',
    },
    pricing: {
      badge: 'Pricing & Plans',
      title: 'Выберите подходящий вариант',
      subtitle: 'Прозрачные тарифные планы для персонального использования и заботы о близких.',
      plan1Name: 'Базовый старт',
      plan1Price: 'Free',
      plan1Desc: 'Мобильное приложение и базовый трекинг питания.',
      plan1Feat1: 'Мобильное приложение SuGuard',
      plan1Feat2: 'Ручной дневник питания',
      plan1Feat3: 'Базовая аналитика сахара',
      plan1Feat4: 'Поддержка по email',
      plan1Btn: 'Начать бесплатно',
      plan2Name: 'Устройство + Приложение',
      plan2Price: '$149',
      plan2Desc: 'Полный комплект: неинвазивный браслет + бессрочный доступ к ИИ-приложению.',
      plan2Feat1: 'Носимый браслет SuGuard Sensor',
      plan2Feat2: 'ИИ-оценка риска диабета',
      plan2Feat3: 'Сканер питания по фото',
      plan2Feat4: 'Неограниченный ИИ-Консультант',
      plan2Btn: 'Заказать комплект',
      plan3Name: 'Семейный доступ',
      plan3Price: '$269',
      plan3Desc: '2 устройства SuGuard + расширенная семейная аналитика.',
      plan3Feat1: '2 носимых браслета SuGuard',
      plan3Feat2: 'Семейный дашборд и уход',
      plan3Feat3: 'Приоритетный ИИ-Консультант',
      plan3Feat4: 'Персональный менеджер',
      plan3Btn: 'Оформить семейный',
      popularBadge: 'Самый популярный',
    },
    faq: {
      badge: 'Frequently Asked Questions',
      title: 'Часто задаваемые вопросы',
      subtitle: 'Ответы на популярные вопросы о работе устройства и приложения SuGuard.',
      q1: 'Что такое SuGuard?',
      a1: 'SuGuard — это комплексная экосистема для мониторинга здоровья, состоящая из носимого оптического устройства и смарт-приложения с ИИ.',
      q2: 'Как работает неинвазивное измерение?',
      a2: 'Сенсор на запястье использует оптическую спектроскопию (PPG) для анализа прохождения света через капилляры, измеряя глюкозу без иголок.',
      q3: 'Насколько точны показания сахара?',
      a3: 'В рамках проведенных исследований точность алгоритма достигает 94% по сравнению с лабораторными глюкометрами.',
      q4: 'Как работает сканер питания по фото?',
      a4: 'Вы сфотографируете тарелку с едой, ИИ определят блюдо, выссчитает объем и разложит состав на белки, жиры, углеводы и калории.',
      q5: 'Безопасны ли мои медицинские данные?',
      a5: 'Все данные шифруются по стандарту AES-256 и хранятся в защищенном облаке с соблюдением требований конфиденциальности.',
    },
    contact: {
      badge: 'Get in Touch',
      title: 'Остались вопросы? Свяжитесь с нами',
      subtitle: 'Оставьте заявку на предзаказ или консультацию с нашей командой.',
      nameLabel: 'Ваше имя',
      namePlaceholder: 'Иван Иванов',
      emailLabel: 'Email адрес',
      emailPlaceholder: 'ivan@example.com',
      phoneLabel: 'Номер телефона',
      phonePlaceholder: '+7 (777) 000-00-00',
      messageLabel: 'Сообщение / Вопрос',
      messagePlaceholder: 'Здравствуйте, хочу узнать подробнее о предзаказе...',
      submitBtn: 'Отправить заявку',
      submittedMsg: 'Спасибо! Ваша заявка успешно отправлена. Мы свяжемся с вами в ближайшее время.',
    },
    footer: {
      rights: 'Все права защищены.',
      desc: 'Инновационная система неинвазивного мониторинга глюкозы и профилактики диабета.',
    },
  },
  en: {
    nav: {
      ecosystem: 'Ecosystem',
      achievements: 'Achievements',
      experts: 'Experts',
      partners: 'Partners',
      features: 'Features',
      app: 'App',
      pricing: 'Pricing',
      faq: 'FAQ',
      contactUs: 'Contact Us',
    },
    hero: {
      badge: 'Next-Gen AI Health Ecosystem',
      title: 'Non-Invasive Glucose Monitoring & AI Risk Analytics',
      subtitle: 'Innovative wearable tracker and companion mobile app for continuous glucose, SpO2, pulse monitoring, and diabetes prevention.',
      watchDemo: 'Watch Demo Video',
      orderDevice: 'Get Wearable Device',
      statAccuracy: '94%',
      statAccuracySub: 'Sensor Accuracy',
      statTests: '50+',
      statTestsSub: 'Real Patient Tests',
      statInvestment: '$13K',
      statInvestmentSub: 'Grant Funding',
      statSync: '< 1 sec',
      statSyncSub: 'Sync Speed',
    },
    ecosystem: {
      badge: 'Integrated Solution',
      title: 'Hardware Device & Intelligent Mobile Platform',
      subtitle: 'Forget painful finger pricks. Track continuous optical glucose readings right from your wrist and analyze health risks in real time.',
      hardwareTitle: 'SuGuard Wearable Sensor',
      hardwareBadge: 'HARDWARE',
      hardwareDesc: 'Smart wrist tracker with multi-wavelength spectroscopic sensors for painless blood analysis.',
      hardwareFeat1Title: 'Optical PPG Sensors',
      hardwareFeat1Desc: 'Glucose and oxygen measurement without needles or test strips.',
      hardwareFeat2Title: 'Bluetooth 5.3 Low Energy',
      hardwareFeat2Desc: 'Instant data streaming directly to your smartphone.',
      hardwareFeat3Title: '7-Day Battery Life',
      hardwareFeat3Desc: 'Fast magnetic charging with IP67 water resistance.',
      appTitle: 'SuGuard Mobile App',
      appBadge: 'SOFTWARE & AI',
      appDesc: 'Personal digital health assistant with AI diabetes risk engine and photo nutrition tracker.',
      appFeat1Title: 'AI Diabetes Risk Engine',
      appFeat1Desc: 'Calculates risk percentage based on glucose, pulse, and SpO2 trends.',
      appFeat2Title: 'Photo Meal Recognition',
      appFeat2Desc: 'Automatic macro breakdown (proteins, fats, carbs, calories) from a meal photo.',
      appFeat3Title: '24/7 AI Health Consultant',
      appFeat3Desc: 'Instant answers and tailored actionable health recommendations.',
    },
    achievements: {
      badge: 'Achievements & Impact',
      title: 'Key Milestones & Results',
      subtitle: 'Core performance indicators, grant investments, validated device accuracy, and real patient testing.',
      invTitle: 'Grants & Funding',
      invDesc: 'Attracted through competitive startup competitions and grant programs.',
      accTitle: 'Measurement Accuracy',
      accDesc: 'Neural network powered glucose monitoring algorithm accuracy.',
      testsTitle: 'Patient CustDev Tests',
      testsDesc: 'Successfully completed real-world user tests and clinical validation.',
      partnersTitle: 'Official Partners',
      partnersDesc: 'Active collaboration with clinical centers and national institutions.',
    },
    experts: {
      badge: 'CustDev & Advisory Board',
      title: 'Scientific & Expert Advisory Board',
      subtitle: 'Leading international and national experts who supported our CustDev, accuracy enhancements, and prototyping.',
      jerryRole: 'Scientific Advisor',
      jerryAff: 'University of Southern California',
      jerryDesc: 'AI-driven recommendations developed by bio-engineers and PhD researchers at University of Southern California.',
      aidarRole: 'AI & Accuracy Expert',
      aidarAff: 'PhD Student at MBZUAI • AI Researcher',
      aidarDesc: 'Provided recommendations on improving device accuracy and implementing AI for glucose data analysis (achieved 94% accuracy).',
      rustamRole: 'Hardware Prototyping Specialist',
      rustamAff: 'Fab Lab NURIS Digital Prototyping Engineer',
      rustamDesc: 'Prototyping specialist. Participated in the development of the first device prototype at Fab Lab NURIS.',
    },
    partners: {
      badge: 'Partnerships & Collaborations',
      title: 'Official Institutional Collaborations',
      subtitle: 'We actively partner with leading medical centers, hospitals, and national organizations.',
      brbTitle: 'GKP on PHV "BRB"',
      brbDesc: 'City Clinical Hospital (Aksai Hospital) - practical testing and clinical evaluation of the device.',
      avicennaTitle: 'Avicenna Medical Center',
      avicennaDesc: 'Partnership in clinical consulting, data collection, and monitoring methodology testing.',
      presidentialTitle: 'Presidential Medical Center RK',
      presidentialDesc: 'Consultative feedback and expert tech evaluation from qualified medical doctors.',
      amanatTitle: 'Amanat Party',
      amanatDesc: 'Social innovation support and community health initiative engagement.',
      academicTitle: 'Research Initiatives & Academic Dialogue',
      nncrzTitle: 'Salidat Kairbekova National Center',
      nncrzDesc: 'National Scientific Center for Health Development - proposals for technological integration.',
      nuTitle: 'Nazarbayev University',
      nuDesc: 'Nazarbayev University - R&D CustDev, research, and digital prototyping at Fab Lab NURIS.',
      amuTitle: 'Astana Medical University',
      amuDesc: 'Academic consulting with faculty researchers and clinical diabetologists.',
    },
    features: {
      badge: 'Features',
      title: 'Everything You Need for Health Control',
      subtitle: 'A comprehensive suite combining wearable optical sensing and AI for proactive diabetes prevention.',
      f1Title: 'Glucose Monitoring',
      f1Desc: 'Non-invasive optical blood glucose sensing with real-time phone sync.',
      f2Title: 'Diabetes Risk Score',
      f2Desc: 'Calculates overall risk score from continuous glucose, SpO2, and heart rate data.',
      f3Title: 'Nutrition Tracking',
      f3Desc: 'Log meals via photo recognition or manual entry with complete macro breakdown.',
      f4Title: 'SpO2 & Pulse Rate',
      f4Desc: 'Continuous blood oxygen saturation and pulse rate tracking.',
      f5Title: 'AI Health Assistant',
      f5Desc: 'Smart conversational bot that analyzes your biometric data and answers health queries.',
      f6Title: 'Instant Cloud Sync',
      f6Desc: 'Secure Bluetooth 5.3 syncing to encrypted cloud storage.',
    },
    device: {
      badge: 'Hardware Specs',
      title: 'Engineered for Precision & Comfort',
      subtitle: 'Medical-grade optical sensors housed in an ergonomic aerospace aluminium casing.',
      spec1Title: 'PPG Optical Array',
      spec1Desc: 'Dual-wavelength optical sensor array for non-invasive readings.',
      spec2Title: 'Aerospace Aluminium Body',
      spec2Desc: 'Lightweight, durable casing certified IP67 water resistant.',
      spec3Title: 'Low-Power Processor',
      spec3Desc: 'Energy-efficient microcontroller for uninterrupted signal processing.',
      spec4Title: 'Hypoallergenic Band',
      spec4Desc: 'Soft silicone strap designed for comfortable 24/7 wear.',
    },
    appSection: {
      badge: 'App Interface',
      title: 'Intuitive & Powerful Mobile Dashboard',
      subtitle: 'Clear analytics, real-time metrics, and automated risk notifications.',
      screen1Title: 'Live Dashboard',
      screen1Desc: 'Real-time glucose, heart rate, SpO2, and sensor connection status.',
      screen2Title: 'Diabetes Risk Breakdown',
      screen2Desc: 'Detailed analysis of health risk factors and personalized advice.',
      screen3Title: 'Food & Calorie Journal',
      screen3Desc: 'Photo meal recognition and daily macronutrient breakdown.',
      screen4Title: 'AI Health Chat',
      screen4Desc: 'Around-the-clock AI guidance tailored to your health profile.',
    },
    pricing: {
      badge: 'Pricing & Plans',
      title: 'Choose the Right Plan for You',
      subtitle: 'Transparent pricing for individual health tracking and family care.',
      plan1Name: 'Basic Free',
      plan1Price: 'Free',
      plan1Desc: 'Mobile application and manual nutrition tracking.',
      plan1Feat1: 'SuGuard Mobile App',
      plan1Feat2: 'Manual Food Diary',
      plan1Feat3: 'Basic Glucose Analytics',
      plan1Feat4: 'Standard Email Support',
      plan1Btn: 'Start for Free',
      plan2Name: 'Device + App Bundle',
      plan2Price: '$149',
      plan2Desc: 'Complete kit: SuGuard wearable sensor + lifetime AI app access.',
      plan2Feat1: 'SuGuard Wearable Sensor',
      plan2Feat2: 'AI Diabetes Risk Assessment',
      plan2Feat3: 'AI Photo Food Scanner',
      plan2Feat4: 'Unlimited AI Health Chat',
      plan2Btn: 'Order Hardware Kit',
      plan3Name: 'Family Bundle',
      plan3Price: '$269',
      plan3Desc: '2 SuGuard Wearables + family health monitoring dashboard.',
      plan3Feat1: '2x SuGuard Wearable Sensors',
      plan3Feat2: 'Family Dashboard & Alerts',
      plan3Feat3: 'Priority AI Health Assistant',
      plan3Feat4: 'Dedicated Support Manager',
      plan3Btn: 'Get Family Plan',
      popularBadge: 'Most Popular',
    },
    faq: {
      badge: 'Frequently Asked Questions',
      title: 'Frequently Asked Questions',
      subtitle: 'Answers to common questions about the SuGuard wearable device and app.',
      q1: 'What is SuGuard?',
      a1: 'SuGuard is an end-to-end health monitoring ecosystem consisting of an optical wearable device and an AI companion mobile application.',
      q2: 'How does non-invasive glucose measurement work?',
      a2: 'The wrist sensor uses optical PPG spectroscopy to measure light absorption through skin tissue, calculating glucose levels painlessly without needles.',
      q3: 'How accurate is the sensor?',
      a3: 'Our neural network algorithms achieve up to 94% accuracy compared with standard blood glucose meters.',
      q4: 'How does the photo meal recognition work?',
      a4: 'Take a photo of your food, and our AI model automatically identifies the dish, estimates portion size, and calculates calories and macros.',
      q5: 'Is my personal health data secure?',
      a5: 'Yes. All data is encrypted using AES-256 and stored securely in cloud infrastructure complying with privacy standards.',
    },
    contact: {
      badge: 'Get in Touch',
      title: 'Have Questions? Contact Our Team',
      subtitle: 'Leave your request for pre-orders or technical inquiries.',
      nameLabel: 'Your Name',
      namePlaceholder: 'John Doe',
      emailLabel: 'Email Address',
      emailPlaceholder: 'john@example.com',
      phoneLabel: 'Phone Number',
      phonePlaceholder: '+7 (700) 000-00-00',
      messageLabel: 'Message / Inquiry',
      messagePlaceholder: 'Hi, I would like to learn more about pre-ordering SuGuard...',
      submitBtn: 'Send Request',
      submittedMsg: 'Thank you! Your inquiry has been submitted. Our team will contact you shortly.',
    },
    footer: {
      rights: 'All rights reserved.',
      desc: 'Innovative non-invasive glucose monitoring & diabetes prevention platform.',
    },
  },
  kk: {
    nav: {
      ecosystem: 'Экожүйе',
      achievements: 'Жетістіктер',
      experts: 'Сарапшылар',
      partners: 'Серіктестер',
      features: 'Мүмкіндіктер',
      app: 'Қосымша',
      pricing: 'Тарифтер',
      faq: 'FAQ',
      contactUs: 'Байланысу',
    },
    hero: {
      badge: 'Денсаулықты Бақылаудың Жаңа Буын ИИ-Экожүйесі',
      title: 'Глюкозаны инвазивті емес ақылды бақылау және ИИ талдау',
      subtitle: 'Глюкозаны, SpO2, тамыр соғысын үзіліссіз бақылауға және диабеттің алдын алуға арналған инновациялық тағылатын трекер мен мобильді қосымша.',
      watchDemo: 'Демо видеоны қарау',
      orderDevice: 'Құрылғыға тапсырыс беру',
      statAccuracy: '94%',
      statAccuracySub: 'Өлшеу Дәлдігі',
      statTests: '50+',
      statTestsSub: 'Сәтті Тесттер',
      statInvestment: '$13K',
      statInvestmentSub: 'Гранттық Инвестициялар',
      statSync: '< 1 сек',
      statSyncSub: 'Синхрондау Жылдамдығы',
    },
    ecosystem: {
      badge: 'Екі Компонентті Экожүйе',
      title: 'Тағылатын Құрылғы + Мобильді Платформа',
      subtitle: 'Саусақты ауыртып тесуді ұмытыңыз. Білегіңізден глюкозаның дәл көрсеткіштерін алып, нақты уақытта денсаулық тәуекелдерін талдаңыз.',
      hardwareTitle: 'SuGuard Тағылатын Сенсоры',
      hardwareBadge: 'HARDWARE',
      hardwareDesc: 'Қанды инвазивті емес талдауға арналған спектроскопиялық датчиктері бар ақылды білезік.',
      hardwareFeat1Title: 'Оптикалық PPG-сенсорлар',
      hardwareFeat1Desc: 'Инесіз және тест-жолақсыз сахар мен оттегіні өлшеу.',
      hardwareFeat2Title: 'Bluetooth 5.3 Low Energy',
      hardwareFeat2Desc: 'Деректерді смартфонға лезде жіберу.',
      hardwareFeat3Title: '7 күнге дейін автономды',
      hardwareFeat3Desc: 'Жылдам қуаттау және IP67 судан қорғалған корпус.',
      appTitle: 'SuGuard Мобильді Қосымшасы',
      appBadge: 'SOFTWARE & AI',
      appDesc: 'Диабет тәуекелін бағалайтын ИИ-моделі мен тамақтану трекері бар жеке сандық ассистент.',
      appFeat1Title: 'Диабет Тәуекелін ИИ-Бағалау',
      appFeat1Desc: 'Глюкоза, пульс және SpO2 негізінде ықтималдықты % түрде есептеу.',
      appFeat2Title: 'Сурет Бойынша Тамақ Трекері',
      appFeat2Desc: 'Тамақтың суреті арқылы АБЖУ мен калорияны автоматты есептеу.',
      appFeat3Title: '24/7 Жеке ИИ-Кеңесші',
      appFeat3Desc: 'Сұрақтарға жауап беру және сахар ауытқуының алдын алу бойынша кеңестер.',
    },
    achievements: {
      badge: 'Жетістіктер мен Нәтижелер',
      title: 'Біздің Негізгі Көрсеткіштеріміз',
      subtitle: 'Негізгі тиімділік көрсеткіштері, тартылған гранттық инвестициялар, расталған құрылғы дәлдігі және CustDev тестілеуі.',
      invTitle: 'Тартылған Инвестициялар',
      invDesc: 'Стартап конкурстары мен гранттық бағдарламалар арқылы тартылды.',
      accTitle: 'Өлшеу Дәлдігі',
      accDesc: 'Нейрожелі негізіндегі инвазивті емес глюкометрдің расталған дәлдігі.',
      testsTitle: 'Пайдаланушылық Тесттер',
      testsDesc: 'CustDev аясында нақты пациенттерде сәтті жүргізілген тестілеулер.',
      partnersTitle: 'Ресми Серіктестер',
      partnersDesc: 'Медициналық орталықтармен, ауруханалармен ресми серіктестік.',
    },
    experts: {
      badge: 'CustDev & Сарапшылар Кеңесі',
      title: 'Ғылыми Сарапшылар Кеңесі',
      subtitle: 'CustDev, құрылғы дәлдігін 94%-ға дейін арттыру және прототип жасау аясында кәсіби қолдау көрсеткен жетекші сарапшылар.',
      jerryRole: 'Scientific Advisor',
      jerryAff: 'University of Southern California',
      jerryDesc: 'AI-driven recommendations developed by bio-engineers and PhD researchers at University of Southern California. ИИ алгоритмдері бойынша кеңестер.',
      aidarRole: 'AI & Accuracy Expert',
      aidarAff: 'PhD Student at MBZUAI • AI Researcher',
      aidarDesc: 'Provided recommendations on improving device accuracy and implementing AI for glucose data analysis. Дәлдікті 94%-ға жеткізуге көмектескен ИИ зерттеушісі.',
      rustamRole: 'Hardware Prototyping Specialist',
      rustamAff: 'Fab Lab NURIS Digital Prototyping Engineer',
      rustamDesc: 'Prototyping specialist. Participated in the development of the first device prototype. Алғашқы физикалық прототипті жасаған маман.',
    },
    partners: {
      badge: 'Серіктестік пен Ынтымақтастық',
      title: 'Ресми Ынтымақтастық',
      subtitle: 'Біз жетекші медициналық орталықтармен, ауруханалармен және қоғамдық ұйымдармен белсенді жұмыс істейміз.',
      brbTitle: '«БРБ» ШЖҚ МКК',
      brbDesc: 'Қалалық клиникалық аурухана (Ақсай ауруханасы) - практикалық ынтымақтастық және құрылғыны сынақтан өткізу.',
      avicennaTitle: '«Авиценна» Медициналық Орталығы',
      avicennaDesc: 'Клиникалық консультациялар, деректер жинау және бақылау методологиясын тестілеу.',
      presidentialTitle: 'ҚР Президенті Іс Басқармасының Медорталығы',
      presidentialDesc: 'Білікті дәрігерлер тарапынан консультациялық қолдау және технологияларға эксперттік баға.',
      amanatTitle: '«Аманат» Партиясы',
      amanatDesc: 'Жобаны әлеуметтік-инновациялық қолдау және халық денсаулығын нығайту бағдарламалары.',
      academicTitle: 'Ғылыми Бастамалар мен Серіктестік Ұсыныстары',
      nncrzTitle: 'С. Қайырбекова атындағы ҰҒДРӨО',
      nncrzDesc: 'Денсаулық сақтауды дамыту ұлттық ғылыми орталығы - технологиялық шешімдерді енгізу ұсыныстары.',
      nuTitle: 'Назарбаев Университеті',
      nuDesc: 'Nazarbayev University - ғылыми-технологиялық CustDev және Fab Lab NURIS базасында прототип жасау.',
      amuTitle: 'Астана Медицина Университеті',
      amuDesc: 'Профильді кафедралардың сарапшыларымен және диабетологтарымен академикалық кеңестер.',
    },
    features: {
      badge: 'Мүмкіндіктер',
      title: 'Денсаулықты Бақылауға Арналған Барлық Құралдар',
      subtitle: 'Диабеттің алдын алу үшін тағылатын сенсор мен жасанды интеллектті біріктіретін кешенді жүйе.',
      f1Title: 'Глюкозаны Бақылау',
      f1Desc: 'Оптикалық сенсорлар негізінде қандағы сахар деңгейін инвазивті емес талдау.',
      f2Title: 'Диабет Тәуекелін Бағалау',
      f2Desc: 'Глюкоза, SpO2 және пульс көрсеткіштері бойынша тәуекел пайызын есептеу.',
      f3Title: 'Тамақтану Трекері',
      f3Desc: 'Сурет бойынша немесе қолмен тамақ күнделігін жүргізу (белок, май, көмірсу, калория).',
      f4Title: 'SpO2 және Пульсометр',
      f4Desc: 'Қандағы оттегі деңгейін және жүрек соғысы жиілігін үздіксіз өлшеу.',
      f5Title: 'ИИ-Кеңесші',
      f5Desc: 'Деректеріңізді талдап, денсаулыққа қатысты барлық сұрақтарға жауап беретін ИИ-ассистент.',
      f6Title: 'Бульттік Синхрондау',
      f6Desc: 'Bluetooth 5.3 арқылы нәтижелерді қорғалған бұлтқа лезде сақтау.',
    },
    device: {
      badge: 'Құрылғы Сипаттамасы',
      title: 'Сенсордың Инженерлік Дәлдігі',
      subtitle: 'Ыңғайлы эрогономикалық корпустағы жоғары дәлдікті оптикалық датчиктер.',
      spec1Title: 'PPG Оптикалық Модулі',
      spec1Desc: 'Жоғары дәлдіктегі екі толқынды оптикалық талдағыш.',
      spec2Title: 'Авиациялық Алюминий Корпусы',
      spec2Desc: 'Жеңіл, берік және IP67 стандарты бойынша судан қорғалған.',
      spec3Title: 'Энергия Тимді Процессор',
      spec3Desc: 'Төмен энергия тұтынатын және сигналдарды жылдам өңдейтін микроконтроллер.',
      spec4Title: 'Гипоаллергенді Бау',
      spec4Desc: 'Теріні тітіркендірмей 24/7 ыңғайлы тағуға арналған.',
    },
    appSection: {
      badge: 'Қосымша Интерфейсі',
      title: 'Ыңғайлы Мобильді Интерфейс',
      subtitle: 'Көрнекі аналитика, динамикалық графиктер және лездік хабарландырулар.',
      screen1Title: 'Негізгі Дашборд',
      screen1Desc: 'Ағымдағы сахар деңгейі, пульс, SpO2 және құрылғы қосылу статусы.',
      screen2Title: 'Диабет Тәуекел Картасы',
      screen2Desc: 'Тәуекел факторларын егжей-тегжейлі талдау және жеке ұсыныстар.',
      screen3Title: 'Тамақтану Күнделігі',
      screen3Desc: 'Сурет арқылы тамақты тану және тәуліктік калория балансы.',
      screen4Title: 'ИИ-Кеңесшімен Чат',
      screen4Desc: 'Денсаулығыңыз бойынша тәулік бойы қолдау және кеңестер.',
    },
    pricing: {
      badge: 'Тарифтер мен Бағалар',
      title: 'Өзіңізге Ыңғайлы Тарифті Таңдаңыз',
      subtitle: 'Жеке пайдалануға және жақындарыңызға қамқорлық жасауға арналған ашық бағалар.',
      plan1Name: 'Базалық Бастау',
      plan1Price: 'Тегін',
      plan1Desc: 'Мобильді қосымша және базалық тамақтану трекері.',
      plan1Feat1: 'SuGuard Мобильді Қосымшасы',
      plan1Feat2: 'Қолмен тамақтану күнделігі',
      plan1Feat3: 'Сахардың базалық аналитикасы',
      plan1Feat4: 'Email арқылы қолдау',
      plan1Btn: 'Тегін бастау',
      plan2Name: 'Құрылғы + Қосымша',
      plan2Price: '$149',
      plan2Desc: 'Толық жиынтық: инвазивті емес білезік + ИИ-қосымшаға мерзімсіз рұқсат.',
      plan2Feat1: 'SuGuard Сенсорлы Білезігі',
      plan2Feat2: 'Диабет тәуекелін ИИ-бағалау',
      plan2Feat3: 'Сурет бойынша тамақ сканері',
      plan2Feat4: 'Шексіз ИИ-Кеңесші',
      plan2Btn: 'Жиынтыққа тапсырыс беру',
      plan3Name: 'Отбасылық Тариф',
      plan3Price: '$269',
      plan3Desc: '2 SuGuard құрылғысы + кеңейтілген отбасылық аналитика.',
      plan3Feat1: '2x SuGuard Сенсорлы Білезігі',
      plan3Feat2: 'Отбасылық дашборд және ескертулер',
      plan3Feat3: 'Басымдықты ИИ-Кеңесші',
      plan3Feat4: 'Жеке менеджер',
      plan3Btn: 'Отбасылық тарифті алу',
      popularBadge: 'Ең Танымал',
    },
    faq: {
      badge: 'Жиі Қойылатын Сұрақтар',
      title: 'Жиі Қойылатын Сұрақтар',
      subtitle: 'SuGuard құрылғысы мен қосымшасының жұмысы туралы танымал сұрақтарға жауаптар.',
      q1: 'SuGuard деген не?',
      a1: 'SuGuard — бұл тағылатын оптикалық құрылғыдан және ИИ мобильді қосымшасынан тұратын денсаулықты бақылау экожүйесі.',
      q2: 'Инвазивті емес өлшеу қалай жұмыс істейді?',
      a2: 'Білезіктегі сенсор оптико-спектроскопияны (PPG) қолданып, инесіз қандағы глюкоза деңгейін анықтайды.',
      q3: 'Сахар көрсеткіштері қаншалықты дәл?',
      a3: 'Зерттеулер аясында алгоритм дәлдігі зертханалық глюкометрлермен салыстырғанда 94%-ға жетеді.',
      q4: 'Сурет бойынша тамақ сканері қалай жұмыс істейді?',
      a4: 'Тамақты суретке түсіресіз, ал ИИ тағамды анықтап, калориясы мен белок, май, көмірсу мөлшерін есептейді.',
      q5: 'Менің медициналық деректерім қауіпсіз бе?',
      a5: 'Барлық деректер AES-256 стандарты бойынша шифрланады және құпиялылық талаптарына сай қорғалған бұлтта сақталады.',
    },
    contact: {
      badge: 'Байланысу',
      title: 'Сұрақтарыңыз Бар ма? Бізбен Хабарласыңыз',
      subtitle: 'Алдын ала тапсырыс беру немесе кеңес алу үшін өтінім қалдырыңыз.',
      nameLabel: 'Сіздің атыңыз',
      namePlaceholder: 'Арман Сериков',
      emailLabel: 'Email мекенжайы',
      emailPlaceholder: 'arman@example.com',
      phoneLabel: 'Телефон нөмірі',
      phonePlaceholder: '+7 (707) 000-00-00',
      messageLabel: 'Хабарлама / Сұрақ',
      messagePlaceholder: 'Саламатсыз ба, алдын ала тапсырыс туралы білгім келеді...',
      submitBtn: 'Өтінімді жіберу',
      submittedMsg: 'Рахмет! Өтінішіңіз сәтті жіберілді. Мамандарымыз жақын арада хабарласады.',
    },
    footer: {
      rights: 'Барлық құқықтар қорғалған.',
      desc: 'Глюкозаны инвазивті емес бақылау және диабеттің алдын алу инновациялық платформасы.',
    },
  },
};
