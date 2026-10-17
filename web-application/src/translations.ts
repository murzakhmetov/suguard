export type Language = 'ru' | 'en' | 'kk';

export interface TranslationSchema {
  nav: {
    opticalAi: string;
    ecosystem: string;
    hardware3d: string;
    app: string;
    experts: string;
    partners: string;
    pricing: string;
    faq: string;
    contactUs: string;
    orderCta: string;
    menuTitle: string;
  };
  hero: {
    badge: string;
    eyebrowTech: string;
    title: string;
    subtitle: string;
    btnLaser: string;
    btnLaserBadge: string;
    btn3d: string;
    btn3dBadge: string;
    btnDownload: string;
    btnDownloadBadge: string;
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
  cinema: {
    kicker: string;
    title: string;
    tabWrist: string;
    tabStudio: string;
    badgeWrist: string;
    badgeStudio: string;
    soundOn: string;
    soundOff: string;
    step1Title: string;
    step1Desc: string;
    step2Title: string;
    step2Desc: string;
    step3Title: string;
    step3Desc: string;
    metricGlucose: string;
    valGlucose: string;
    metricOxygen: string;
    valOxygen: string;
    metricPulse: string;
    valPulse: string;
  };
  deck: {
    counterLabel: string;
    mod1Tag: string;
    mod1Sub: string;
    mod1Wavelengths: string;
    mod1ValWavelengths: string;
    mod1Adc: string;
    mod1NonInvasive: string;
    mod1Caption: string;
    mod2Tag: string;
    mod2Sub: string;
    mod2Accuracy: string;
    mod2Continuous: string;
    mod2Latency: string;
    mod2ValLatency: string;
    mod2Caption: string;
    mod3Tag: string;
    mod3Sub: string;
    mod3Weight: string;
    mod3ValWeight: string;
    mod3Battery: string;
    mod3ValBattery: string;
    mod3Mcu: string;
    mod3Caption: string;
    mod4Tag: string;
    mod4Sub: string;
    mod4Macros: string;
    mod4ValMacros: string;
    mod4Consultant: string;
    mod4Export: string;
    mod4Caption: string;
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
    syncTitle: string;
    syncDesc: string;
  };
  experts: {
    badge: string;
    title: string;
    subtitle: string;
    jerryName: string;
    jerryRole: string;
    jerryAff: string;
    jerryDesc: string;
    aidarName: string;
    aidarRole: string;
    aidarAff: string;
    aidarDesc: string;
    rustamName: string;
    rustamRole: string;
    rustamAff: string;
    rustamDesc: string;
  };
  partners: {
    badge: string;
    title: string;
    subtitle: string;
    catClinical: string;
    catMedCenter: string;
    catPresidential: string;
    catPublic: string;
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
    counterLabel: string;
    screen1Tag: string;
    screen1Title: string;
    screen1Desc: string;
    screen1Specs: string[];
    screen2Tag: string;
    screen2Title: string;
    screen2Desc: string;
    screen2Specs: string[];
    screen3Tag: string;
    screen3Title: string;
    screen3Desc: string;
    screen3Specs: string[];
    screen4Tag: string;
    screen4Title: string;
    screen4Desc: string;
    screen4Specs: string[];
  };
  order: {
    kitTitle: string;
    kitSub: string;
    kitPriceUsd: string;
    bullet1: string;
    bullet2: string;
    bullet3: string;
    bullet4: string;
    bullet5: string;
    btnApp: string;
    btnAppBadge: string;
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
    navTitle: string;
    contactsTitle: string;
    downloadsTitle: string;
    preorderLink: string;
    androidApp: string;
    rights: string;
    desc: string;
    designedIn: string;
  };
}

export const translations: Record<Language, TranslationSchema> = {
  ru: {
    nav: {
      opticalAi: 'Оптический ИИ',
      ecosystem: 'Экосистема',
      hardware3d: '3D Инженерия',
      app: 'Приложение',
      experts: 'Эксперты',
      partners: 'Партнеры',
      pricing: 'Тарифы',
      faq: 'FAQ',
      contactUs: 'Связаться',
      orderCta: 'Заказать',
      menuTitle: 'НАВИГАЦИЯ',
    },
    hero: {
      badge: 'ИИ-Экосистема Мониторинга Здоровья',
      eyebrowTech: 'ОПТИЧЕСКИЙ PPG 660 / 880 НМ',
      title: 'Умный неинвазивный мониторинг сахара и риск-анализ',
      subtitle: 'Инновационный носимый трекер и мобильное приложение для непрерывного отслеживания глюкозы, SpO2, пульса и предотвращения диабета.',
      btnLaser: 'Как работает лазер (Видео)',
      btnLaserBadge: 'PPG 660 нм',
      btn3d: '3D Инженерия',
      btn3dBadge: '5 слоёв',
      btnDownload: 'Скачать приложение',
      btnDownloadBadge: 'Android .APK',
      watchDemo: 'Смотреть демо видео',
      orderDevice: 'Приобрести устройство',
      statAccuracy: '94%',
      statAccuracySub: 'Точность измерения',
      statTests: '300+',
      statTestsSub: 'Успешных тестов',
      statInvestment: '$10K+',
      statInvestmentSub: 'Инвестиции и гранты',
      statSync: '< 1 сек',
      statSyncSub: 'Скорость синхронизации',
    },
    cinema: {
      kicker: 'ОПТИЧЕСКАЯ СПЕКТРОСКОПИЯ В ДЕЙСТВИИ',
      title: 'Точность в каждом импульсе.',
      tabWrist: '01. Сканирование на руке (Лазер + Пульс)',
      tabStudio: '02. Обзор браслета 360° в студии',
      badgeWrist: 'ЛАЗЕРНАЯ СПЕКТРОСКОПИЯ MAX30102 • АКТИВНОЕ СКАНИРОВАНИЕ',
      badgeStudio: 'КОРПУС SUGUARD • 360° ОБЗОР В СТУДИИ',
      soundOn: '🔊 Звук включен',
      soundOff: '🔇 Включить звук диктора',
      step1Title: 'Контакт с кожей',
      step1Desc: 'Калибровка базовой линии и отсечение внешнего света',
      step2Title: 'Импульс 660 / 880 нм',
      step2Desc: 'Красный и ИК-лазер просвечивают капилляры запястья',
      step3Title: 'ИИ-спектральный анализ',
      step3Desc: 'Расчёт уровня глюкозы, SpO2 и волны пульса в реальном времени',
      metricGlucose: 'ГЛЮКОЗА',
      valGlucose: '5.8 ммоль/л',
      metricOxygen: 'КИСЛОРОД',
      valOxygen: '98% SpO2',
      metricPulse: 'ПУЛЬС',
      valPulse: '72 уд/мин',
    },
    deck: {
      counterLabel: 'МОДУЛЬ',
      mod1Tag: 'ОПТИЧЕСКАЯ PPG СПЕКТРОСКОПИЯ',
      mod1Sub: 'Двухволновое лазерное зондирование капилляров 660 / 880 нм',
      mod1Wavelengths: 'Длины волн',
      mod1ValWavelengths: '660 / 880 нм',
      mod1Adc: 'АЦП сенсора',
      mod1NonInvasive: 'Неинвазивно',
      mod1Caption: 'Оптический биосенсор MAX30102 сканирует спектр поглощения крови',
      mod2Tag: 'ПРЕДИКТИВНЫЙ ИИ-ДВИЖОК',
      mod2Sub: 'Нейросетевой расчёт вероятности диабета в реальном времени',
      mod2Accuracy: 'Точность ИИ',
      mod2Continuous: 'Непрерывный анализ',
      mod2Latency: 'Отклик модели',
      mod2ValLatency: '< 1 сек',
      mod2Caption: 'Многофакторная оценка гликемического профиля, пульса покоя и SpO2',
      mod3Tag: 'НОСИМОЕ УСТРОЙСТВО',
      mod3Sub: 'Кастомная плата SuGuard.Health и до 7 дней автономности',
      mod3Weight: 'Масса корпуса',
      mod3ValWeight: '38 г',
      mod3Battery: 'Автономность Li-Po',
      mod3ValBattery: '7 дней',
      mod3Mcu: 'Радиомодуль ESP32',
      mod3Caption: 'Ударопрочный матовый корпус на гипоаллергенном ремешке Pin-and-Tuck',
      mod4Tag: 'КОМПЬЮТЕРНОЕ ЗРЕНИЕ И ИИ-ВРАЧ',
      mod4Sub: 'Распознавание блюд по фотографии и персональный ИИ-эндокринолог',
      mod4Macros: 'Расчёт БЖУ и Ккал',
      mod4ValMacros: 'Фото-ИИ',
      mod4Consultant: 'ИИ-Консультант',
      mod4Export: 'Экспорт для врача',
      mod4Caption: 'Автоматический подсчёт углеводной нагрузки по одному снимку тарелки',
    },
    ecosystem: {
      badge: 'Двухкомпонентная экосистема',
      title: 'Носимое устройство + Мобильное приложение',
      subtitle: 'Забудьте о болезненном проколе пальцев. Получайте точные показания глюкозы на запястье и анализируйте риски в реальном времени.',
      hardwareTitle: 'Носимый сенсор SuGuard',
      hardwareBadge: 'АППАРАТНАЯ ЧАСТЬ',
      hardwareDesc: 'Умный смарт-браслет со встроенными спектроскопическими датчиками для неинвазивного анализа крови.',
      hardwareFeat1Title: 'Оптические PPG-сенсоры',
      hardwareFeat1Desc: 'Измерение сахара и кислорода без иголок и тест-полосок.',
      hardwareFeat2Title: 'Связь Bluetooth 5.3 Low Energy',
      hardwareFeat2Desc: 'Мгновенная передача данных на смарт-устройство.',
      hardwareFeat3Title: 'Автономность до 7 дней',
      hardwareFeat3Desc: 'Быстрая зарядка и влагозащищенный корпус.',
      appTitle: 'Мобильное приложение SuGuard',
      appBadge: 'СОФТ И ИИ',
      appDesc: 'Персональный цифровой ассистент с ИИ-моделью оценки риска диабета и трекером питания.',
      appFeat1Title: 'ИИ-оценка риска диабета',
      appFeat1Desc: 'Расчет вероятности в % на базе глюкозы, пульса и SpO2.',
      appFeat2Title: 'Трекер питания по фото',
      appFeat2Desc: 'Автоматический подсчет БЖУ и калорий по фотографии блюда.',
      appFeat3Title: 'Персональный ИИ-Консультант',
      appFeat3Desc: 'Ответы на вопросы и рекомендации по предотвращению скачков сахара.',
    },
    achievements: {
      badge: 'Достижения и результаты',
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
      syncTitle: 'Скорость синхронизации',
      syncDesc: 'Мгновенный обмен данными между трекером и приложением по Bluetooth 5.3.',
    },
    experts: {
      badge: 'Экспертный совет и CustDev',
      title: 'Экспертный совет и CustDev',
      subtitle: 'Ведущие международные и национальные эксперты, оказавшие профессиональную поддержку в рамках CustDev, повышении точности прибора и создании прототипа.',
      jerryName: 'Проф. Джерри Лоеб',
      jerryRole: 'Научный советник',
      jerryAff: 'Университет Южной Калифорнии (USC)',
      jerryDesc: 'Рекомендации по биосенсорике и алгоритмам ИИ от биоинженеров и докторантов Университета Южной Калифорнии.',
      aidarName: 'Айдар Алимбаев',
      aidarRole: 'Эксперт по ИИ и точности данных',
      aidarAff: 'Докторант MBZUAI • Исследователь ИИ',
      aidarDesc: 'Рекомендации по повышению точности сенсора и внедрению нейросетей для анализа биомаркеров (достигнута точность 94%).',
      rustamName: 'Рустам Аскарулы',
      rustamRole: 'Специалист по аппаратному прототипированию',
      rustamAff: 'Инженер цифрового прототипирования Fab Lab NURIS',
      rustamDesc: 'Специалист по прототипированию. Руководил разработкой и сборкой первого физического прототипа устройства.',
    },
    partners: {
      badge: 'Партнерство и сотрудничество',
      title: 'Официальное сотрудничество',
      subtitle: 'Мы активно сотрудничаем с ведущими медицинскими центрами, больницами и общественными организациями.',
      catClinical: '01 / КЛИНИЧЕСКАЯ АПРОБАЦИЯ',
      catMedCenter: '02 / МЕДИЦИНСКИЙ ЦЕНТР',
      catPresidential: '03 / ПРЕЗИДЕНТСКАЯ КЛИНИКА',
      catPublic: '04 / ОБЩЕСТВЕННАЯ ИНИЦИАТИВА',
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
      nncrzDesc: 'Национальный научный центр развития здравоохранения - предложения о внедрении решений.',
      nuTitle: 'Назарбаев Университет',
      nuDesc: 'Научно-технический CustDev и аппаратное прототипирование на базе лаборатории Fab Lab NURIS.',
      amuTitle: 'Медицинский университет Астана',
      amuDesc: 'Академические консультации с профильными кафедрами и диабетологами.',
    },
    features: {
      badge: 'Возможности',
      title: 'Все необходимое для контроля здоровья',
      subtitle: 'Комплексная система, объединяющая носимый датчик и искусственный интеллект для профилактики диабета.',
      f1Title: 'Мониторинг глюкозы',
      f1Desc: 'Неинвазивное оптическое измерение сахара в крови с мгновенной синхронизацией.',
      f2Title: 'Оценка риска диабета',
      f2Desc: 'Расчет вероятности развития диабета на базе непрерывного анализа биомаркеров.',
      f3Title: 'Трекер питания',
      f3Desc: 'Распознавание блюд по фото и автоматический подсчет белков, жиров, углеводов и калорий.',
      f4Title: 'SpO2 и Пульс',
      f4Desc: 'Непрерывное отслеживание уровня насыщения крови кислородом и частоты сердечных сокращений.',
      f5Title: 'ИИ-Консультант',
      f5Desc: 'Умный ассистент, готовый ответить на любые вопросы о вашем здоровье и показателях 24/7.',
      f6Title: 'Облачная синхронизация',
      f6Desc: 'Безопасная передача и шифрование данных по Bluetooth 5.3 в облачное хранилище.',
    },
    device: {
      badge: 'Характеристики',
      title: 'Инженерная точность в каждой детали',
      subtitle: 'Высокоточные оптические сенсоры в эргономичном алюминиевом корпусе.',
      spec1Title: 'Оптический модуль PPG',
      spec1Desc: 'Двухволновой спектроскопический датчик высокой чувствительности.',
      spec2Title: 'Корпус из авиационного алюминия',
      spec2Desc: 'Легкий, прочный и влагозащищенный корпус по стандарту IP67.',
      spec3Title: 'Энергоэффективный микроконтроллер',
      spec3Desc: 'Процессор с низким энергопотреблением для бесперебойной обработки сигналов.',
      spec4Title: 'Гипоаллергенный ремешок',
      spec4Desc: 'Мягкий силиконовый ремешок для комфортного круглосуточного ношения.',
    },
    appSection: {
      badge: 'Интерфейс приложения',
      title: 'Интуитивный и мощный дашборд',
      subtitle: 'Наглядная аналитика, графики в реальном времени и мгновенные уведомления о рисках.',
      counterLabel: 'ЭКРАН',
      screen1Tag: 'ОБЗОР ЗДОРОВЬЯ В РЕАЛЬНОМ ВРЕМЕНИ',
      screen1Title: 'Главный экран мониторинга',
      screen1Desc: 'Текущий уровень глюкозы, пульс, SpO2 и статус подключения датчика в реальном времени.',
      screen1Specs: ['Индекс риска диабета в %', 'Текущая глюкоза (ммоль/л)', 'SpO2 и ЧСС в реальном времени'],
      screen2Tag: 'БИОМЕТРИЧЕСКИЕ ФАКТОРЫ РИСКА',
      screen2Title: 'Оценка факторов риска',
      screen2Desc: 'Детальный анализ факторов риска развития диабета и персональные рекомендации.',
      screen2Specs: ['Декомпозиция факторов риска', 'Динамика среднего сахара', 'Раннее предупреждение скачков'],
      screen3Tag: 'ГРАФИКИ ГЛЮКОЗЫ В РЕАЛЬНОМ ВРЕМЕНИ',
      screen3Title: 'Дневник питания и калорий',
      screen3Desc: 'Распознавание еды по фото и автоматический подсчет баланса нутриентов.',
      screen3Specs: ['Суточные, недельные и месячные графики', 'Минимум, максимум и среднее', 'Распознавание еды по фото (БЖУ)'],
      screen4Tag: 'ЧАТ С ИИ-ЭНДОКРИНОЛОГОМ',
      screen4Title: 'ИИ-Консультант в чате',
      screen4Desc: 'Круглосуточные персональные консультации на основе ваших биометрических показателей.',
      screen4Specs: ['Анализ ваших графиков и рациона', 'Персональные медицинские советы', 'Мгновенные ответы 24/7'],
    },
    order: {
      kitTitle: 'Комплект SuGuard Complete Kit',
      kitSub: 'Носимый оптический биосенсор SuGuard + бессрочный доступ к ИИ-экосистеме мониторинга глюкозы, SpO2 и питания.',
      kitPriceUsd: '≈ $70 USD • Единоразовая покупка без скрытых платежей',
      bullet1: 'Смарт-браслет SuGuard (MAX30102 + SuGuard.Health PCB)',
      bullet2: 'Неинвазивный мониторинг глюкозы, SpO2 и ЧСС 24/7',
      bullet3: 'ИИ-оценка риска диабета и компьютерное зрение для еды',
      bullet4: 'Персональный ИИ-эндокринолог и облачная синхронизация',
      bullet5: 'Кабель быстрой зарядки USB Type-C и гарантия 12 месяцев',
      btnApp: 'Скачать мобильное приложение',
      btnAppBadge: 'Android .APK',
    },
    pricing: {
      badge: 'Тарифы и планы',
      title: 'Выберите подходящий вариант',
      subtitle: 'Прозрачные условия для индивидуального контроля здоровья и заботы о близких.',
      plan1Name: 'Базовый',
      plan1Price: 'Бесплатно',
      plan1Desc: 'Мобильное приложение и ручной трекинг питания.',
      plan1Feat1: 'Мобильное приложение SuGuard',
      plan1Feat2: 'Ручной дневник питания',
      plan1Feat3: 'Базовая аналитика сахара',
      plan1Feat4: 'Поддержка по email',
      plan1Btn: 'Начать бесплатно',
      plan2Name: 'Комплект с устройством',
      plan2Price: '$149',
      plan2Desc: 'Полный комплект: смарт-браслет + пожизненный доступ к приложению.',
      plan2Feat1: 'Носимый сенсор SuGuard',
      plan2Feat2: 'ИИ-оценка риска диабета',
      plan2Feat3: 'Трекер питания по фото',
      plan2Feat4: 'Неограниченный ИИ-Консультант',
      plan2Btn: 'Заказать комплект',
      plan3Name: 'Семейный комплект',
      plan3Price: '$269',
      plan3Desc: '2 устройства SuGuard + семейный доступ к мониторингу здоровья.',
      plan3Feat1: '2x носимых сенсора SuGuard',
      plan3Feat2: 'Семейный дашборд и алерты',
      plan3Feat3: 'Приоритетный ИИ-Консультант',
      plan3Feat4: 'Персональный менеджер',
      plan3Btn: 'Оформить семейный',
      popularBadge: 'Популярный выбор',
    },
    faq: {
      badge: 'Вопросы и ответы',
      title: 'Часто задаваемые вопросы',
      subtitle: 'Ответы на популярные вопросы о работе устройства SuGuard и мобильного приложения.',
      q1: 'Что такое SuGuard?',
      a1: 'SuGuard - это комплексная экосистема для мониторинга здоровья, состоящая из носимого оптического браслета и мобильного приложения с искусственным интеллектом.',
      q2: 'Как работает неинвазивное измерение сахара?',
      a2: 'Браслет использует оптическую PPG-спектроскопию: датчик сканирует капиллярный кровоток и определяет уровень глюкозы по коэффициенту поглощения света без уколов.',
      q3: 'Насколько точны измерения?',
      a3: 'В ходе испытаний алгоритмы нейросети SuGuard продемонстрировали точность до 94% по сравнению с традиционными инвазивными глюкометрами.',
      q4: 'Как работает распознавание еды по фото?',
      a4: 'Вы делаете фотографию блюда, а нейросеть приложения определяет состав, оценивает объем порции и рассчитывает калории, белки, жиры и углеводы.',
      q5: 'Безопасны ли мои медицинские данные?',
      a5: 'Да, все данные шифруются по протоколу AES-256 и передаются по защищенному каналу в соответствии со стандартами медицинской тайны.',
    },
    contact: {
      badge: 'Контакты',
      title: 'Остались вопросы? Свяжитесь с нами',
      subtitle: 'Оставьте заявку на предзаказ или задайте интересующий вопрос нашей команде.',
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
      navTitle: 'Навигация',
      contactsTitle: 'Контакты',
      downloadsTitle: 'Загрузки',
      preorderLink: 'Предзаказ устройства',
      androidApp: 'Приложение Android (.APK)',
      rights: 'Все права защищены.',
      desc: 'Инновационная система неинвазивного мониторинга глюкозы и профилактики диабета.',
      designedIn: 'Разработано и спроектировано в Казахстане',
    },
  },
  en: {
    nav: {
      opticalAi: 'Optical AI',
      ecosystem: 'Ecosystem',
      hardware3d: '3D Hardware',
      app: 'App',
      experts: 'Experts',
      partners: 'Partners',
      pricing: 'Pricing',
      faq: 'FAQ',
      contactUs: 'Contact Us',
      orderCta: 'Order',
      menuTitle: 'NAVIGATION',
    },
    hero: {
      badge: 'Next-Gen AI Health Ecosystem',
      eyebrowTech: 'OPTICAL PPG 660 / 880 NM',
      title: 'Non-Invasive Glucose Monitoring & AI Risk Analytics',
      subtitle: 'Innovative wearable tracker and companion mobile app for continuous glucose, SpO2, pulse monitoring, and diabetes prevention.',
      btnLaser: 'How Optical Sensor Works',
      btnLaserBadge: 'PPG 660 nm',
      btn3d: '3D Hardware Stack',
      btn3dBadge: '5 Layers',
      btnDownload: 'Download App',
      btnDownloadBadge: 'Android .APK',
      watchDemo: 'Watch Demo Video',
      orderDevice: 'Order Device',
      statAccuracy: '94%',
      statAccuracySub: 'Sensor Accuracy',
      statTests: '300+',
      statTestsSub: 'Real Patient Tests',
      statInvestment: '$10K+',
      statInvestmentSub: 'Grant Funding',
      statSync: '< 1 sec',
      statSyncSub: 'Sync Speed',
    },
    cinema: {
      kicker: 'OPTICAL PPG BIO-SENSING IN ACTION',
      title: 'Precision in every pulse.',
      tabWrist: '01. Wrist Scanning (Laser + Pulse)',
      tabStudio: '02. 360° Studio Hardware Orbit',
      badgeWrist: 'MAX30102 LASER SPECTROSCOPY • ACTIVE SCAN',
      badgeStudio: 'SUGUARD UNIBODY • 360° STUDIO ORBIT',
      soundOn: '🔊 Sound enabled',
      soundOff: '🔇 Enable voiceover',
      step1Title: 'Skin Contact',
      step1Desc: 'Baseline calibration and ambient light filtering',
      step2Title: '660 / 880 nm Pulse',
      step2Desc: 'Red and IR laser illuminate wrist capillaries',
      step3Title: 'AI Spectral Analysis',
      step3Desc: 'Real-time calculation of glucose, SpO2, and pulse wave',
      metricGlucose: 'GLUCOSE',
      valGlucose: '5.8 mmol/L',
      metricOxygen: 'OXYGEN',
      valOxygen: '98% SpO2',
      metricPulse: 'PULSE',
      valPulse: '72 BPM',
    },
    deck: {
      counterLabel: 'MODULE',
      mod1Tag: 'OPTICAL PPG SPECTROSCOPY',
      mod1Sub: 'Dual-wavelength optical capillary probing at 660 / 880 nm',
      mod1Wavelengths: 'Wavelengths',
      mod1ValWavelengths: '660 / 880 nm',
      mod1Adc: 'Sensor ADC',
      mod1NonInvasive: 'Non-invasive',
      mod1Caption: 'MAX30102 optical biosensor scanning blood absorption spectra',
      mod2Tag: 'PREDICTIVE AI ENGINE',
      mod2Sub: 'Real-time neural network diabetic risk probability engine',
      mod2Accuracy: 'AI Accuracy',
      mod2Continuous: 'Continuous Analysis',
      mod2Latency: 'Model Latency',
      mod2ValLatency: '< 1 sec',
      mod2Caption: 'Multifactor assessment of glycemic trends, resting HR, and SpO2',
      mod3Tag: 'WEARABLE HARDWARE',
      mod3Sub: 'Custom SuGuard.Health motherboard and up to 7-day battery life',
      mod3Weight: 'Chassis Weight',
      mod3ValWeight: '38 g',
      mod3Battery: 'Li-Po Battery Life',
      mod3ValBattery: '7 d',
      mod3Mcu: 'ESP32 Wireless MCU',
      mod3Caption: 'Impact-resistant matte enclosure with hypoallergenic Pin-and-Tuck strap',
      mod4Tag: 'COMPUTER VISION & AI DOCTOR',
      mod4Sub: 'Meal recognition by camera snapshot & personalized AI endocrinologist',
      mod4Macros: 'Macros & Calories',
      mod4ValMacros: 'Photo-AI',
      mod4Consultant: 'AI Consultant',
      mod4Export: 'Doctor PDF Export',
      mod4Caption: 'Automated glycemic and carbohydrate analysis from a single plate photo',
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
      syncTitle: 'Sync Speed',
      syncDesc: 'Instant data transmission between smart wearable and phone via Bluetooth 5.3.',
    },
    experts: {
      badge: 'CustDev & Advisory Board',
      title: 'Scientific & Expert Advisory Board',
      subtitle: 'Leading international and national experts who supported our CustDev, accuracy enhancements, and prototyping.',
      jerryName: 'Prof. Jerry Loeb',
      jerryRole: 'Scientific Advisor',
      jerryAff: 'University of Southern California',
      jerryDesc: 'AI-driven bio-sensing recommendations and algorithmic guidance developed by bio-engineers and PhD researchers at USC.',
      aidarName: 'Aidar Alimbayev',
      aidarRole: 'AI & Accuracy Expert',
      aidarAff: 'PhD Student at MBZUAI • AI Researcher',
      aidarDesc: 'Provided technical guidance on maximizing sensor accuracy and implementing machine learning for non-invasive glucose estimation (achieved 94%).',
      rustamName: 'Askaruly Rustam',
      rustamRole: 'Hardware Prototyping Specialist',
      rustamAff: 'Fab Lab NURIS Digital Prototyping Engineer',
      rustamDesc: 'Digital fabrication and hardware prototyping engineer. Led the development of the first physical device prototype.',
    },
    partners: {
      badge: 'Partnerships & Collaborations',
      title: 'Official Institutional Collaborations',
      subtitle: 'We actively partner with leading medical centers, hospitals, and national organizations.',
      catClinical: '01 / CLINICAL',
      catMedCenter: '02 / MEDICAL CENTER',
      catPresidential: '03 / PRESIDENTIAL CLINIC',
      catPublic: '04 / PUBLIC INITIATIVE',
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
      nuDesc: 'R&D CustDev, research, and hardware digital prototyping at Fab Lab NURIS.',
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
      counterLabel: 'SCREEN',
      screen1Tag: 'LIVE HEALTH OVERVIEW',
      screen1Title: 'Live Dashboard',
      screen1Desc: 'Real-time glucose, heart rate, SpO2, and sensor connection status.',
      screen1Specs: ['Diabetes risk index %', 'Real-time glucose (mmol/L)', 'SpO2 & HR live stream'],
      screen2Tag: 'BIOMETRIC RISK FACTORS',
      screen2Title: 'Diabetes Risk Breakdown',
      screen2Desc: 'Detailed analysis of health risk factors and personalized advice.',
      screen2Specs: ['Risk factor breakdown', 'Average glucose trends', 'Early spike warnings'],
      screen3Tag: 'CONTINUOUS GLUCOSE CHARTS',
      screen3Title: 'Food & Calorie Journal',
      screen3Desc: 'Photo meal recognition and daily macronutrient breakdown.',
      screen3Specs: ['Daily, weekly & monthly charts', 'Min, max & average values', 'Photo meal recognition (Macros)'],
      screen4Tag: 'AI ENDOCRINOLOGIST CHAT',
      screen4Title: 'AI Health Chat',
      screen4Desc: 'Around-the-clock AI guidance tailored to your health profile.',
      screen4Specs: ['Analysis of your trends & diet', 'Personalized medical guidance', 'Instant 24/7 responses'],
    },
    order: {
      kitTitle: 'SuGuard Complete Kit',
      kitSub: 'Wearable SuGuard optical biosensor + lifetime access to the AI health monitoring ecosystem (glucose, SpO2 & nutrition).',
      kitPriceUsd: '≈ $70 USD • One-time purchase with no subscription fees',
      bullet1: 'SuGuard Smart Wearable (MAX30102 + SuGuard.Health PCB)',
      bullet2: 'Non-invasive 24/7 glucose, SpO2, and heart rate monitoring',
      bullet3: 'AI diabetes risk assessment and computer vision food logging',
      bullet4: 'Personalized AI endocrinologist & secure cloud sync',
      bullet5: 'USB Type-C fast charging cable & 12-month full warranty',
      btnApp: 'Download Mobile App',
      btnAppBadge: 'Android .APK',
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
      popularBadge: 'Popular Choice',
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
      navTitle: 'Navigation',
      contactsTitle: 'Contacts',
      downloadsTitle: 'Downloads',
      preorderLink: 'Pre-order Device',
      androidApp: 'Android App (.APK)',
      rights: 'All rights reserved.',
      desc: 'Innovative non-invasive glucose monitoring & diabetes prevention platform.',
      designedIn: 'Designed & Engineered in Kazakhstan',
    },
  },
  kk: {
    nav: {
      opticalAi: 'Оптикалық ИИ',
      ecosystem: 'Экожүйе',
      hardware3d: '3D Құрылымы',
      app: 'Қосымша',
      experts: 'Сарапшылар',
      partners: 'Серіктестер',
      pricing: 'Тарифтер',
      faq: 'FAQ',
      contactUs: 'Байланысу',
      orderCta: 'Тапсырыс',
      menuTitle: 'НАВИГАЦИЯ',
    },
    hero: {
      badge: 'Денсаулықты Бақылаудың Жаңа Буын ИИ-Экожүйесі',
      eyebrowTech: 'ОПТИКАЛЫҚ PPG 660 / 880 НМ',
      title: 'Глюкозаны инвазивті емес ақылды бақылау және ИИ талдау',
      subtitle: 'Глюкозаны, SpO2, тамыр соғысын үзіліссіз бақылауға және диабеттің алдын алуға арналған инновациялық тағылатын трекер мен мобильді қосымша.',
      btnLaser: 'Лазер қалай жұмыс істейді',
      btnLaserBadge: 'PPG 660 нм',
      btn3d: '3D Құрылымы',
      btn3dBadge: '5 қабат',
      btnDownload: 'Қосымшаны жүктеу',
      btnDownloadBadge: 'Android .APK',
      watchDemo: 'Демо видеоны қарау',
      orderDevice: 'Құрылғыға тапсырыс беру',
      statAccuracy: '94%',
      statAccuracySub: 'Өлшеу Дәлдігі',
      statTests: '300+',
      statTestsSub: 'Сәтті Тесттер',
      statInvestment: '$10K+',
      statInvestmentSub: 'Гранттық Инвестициялар',
      statSync: '< 1 сек',
      statSyncSub: 'Синхрондау Жылдамдығы',
    },
    cinema: {
      kicker: 'ОПТИКАЛЫҚ БИО-СЕНСОР ЖҰМЫС ҮСТІНДЕ',
      title: 'Әр импульстегі дәлдік.',
      tabWrist: '01. Білекте сканерлеу (Лазер + Тамыр соғысы)',
      tabStudio: '02. Студияда 360° білезік шолуы',
      badgeWrist: 'MAX30102 ЛАЗЕРЛІК СПЕКТРОСКОПИЯСЫ • БЕЛСЕНДІ СКАНЕРЛЕУ',
      badgeStudio: 'SUGUARD КОРПУСЫ • 360° СТУДИЯЛЫҚ ШОЛУ',
      soundOn: '🔊 Дыбыс қосылды',
      soundOff: '🔇 Диктор дауысын қосу',
      step1Title: 'Терімен байланыс',
      step1Desc: 'Базалық сызықты калибрлеу және сыртқы жарықты сүзу',
      step2Title: '660 / 880 нм импульс',
      step2Desc: 'Қызыл және ИҚ-лазер білек капиллярларын жарқыратады',
      step3Title: 'ИИ-спектрлік талдау',
      step3Desc: 'Глюкоза, SpO2 және тамыр соғысын нақты уақытта есептеу',
      metricGlucose: 'ГЛЮКОЗА',
      valGlucose: '5.8 ммоль/л',
      metricOxygen: 'ОТТЕГІ',
      valOxygen: '98% SpO2',
      metricPulse: 'ТАМЫР СОҒЫСЫ',
      valPulse: '72 соғ/мин',
    },
    deck: {
      counterLabel: 'МОДУЛЬ',
      mod1Tag: 'ОПТИКАЛЫҚ PPG СПЕКТРОСКОПИЯ',
      mod1Sub: '660 / 880 нм екі толқынды капиллярларды зондтау',
      mod1Wavelengths: 'Толқын ұзындығы',
      mod1ValWavelengths: '660 / 880 нм',
      mod1Adc: 'Сенсор АЦП',
      mod1NonInvasive: 'Инвазивті емес',
      mod1Caption: 'MAX30102 оптикалық биосенсоры қанның сіңіру спектрін сканерлейді',
      mod2Tag: 'БОЛЖАМДЫ ЖИ ҚОЗҒАЛТҚЫШЫ',
      mod2Sub: 'Диабет қаупін нақты уақытта есептейтін нейрожелі',
      mod2Accuracy: 'ИИ дәлдігі',
      mod2Continuous: 'Үздіксіз талдау',
      mod2Latency: 'Жауап уақыты',
      mod2ValLatency: '< 1 сек',
      mod2Caption: 'Гликемиялық профиль, тыныштық тамыр соғысы және SpO2 кешенді бағасы',
      mod3Tag: 'ТАҒЫЛАТЫН ЭЛЕКТРОНИКА',
      mod3Sub: 'SuGuard.Health аналық тақтасы және 7 күнге дейінгі автономдылық',
      mod3Weight: 'Корпус салмағы',
      mod3ValWeight: '38 г',
      mod3Battery: 'Li-Po автономдылығы',
      mod3ValBattery: '7 күн',
      mod3Mcu: 'ESP32 радиомодулі',
      mod3Caption: 'Pin-and-Tuck бауы бар соққыға төзімді матты корпус',
      mod4Tag: 'КОМПЬЮТЕРЛІК КӨРУ ЖӘНЕ ЖИ-ДӘРІГЕР',
      mod4Sub: 'Тағамдарды фотомен тану және жеке ИИ-эндокринолог',
      mod4Macros: 'Ақуыз-май-көмірсу',
      mod4ValMacros: 'Фото-ЖИ',
      mod4Consultant: 'ИИ-Кеңесші',
      mod4Export: 'Дәрігерге экспорт',
      mod4Caption: 'Бір тәрелке фотосынан көмірсу жүктемесін автоматты есептеу',
    },
    ecosystem: {
      badge: 'Екі Компонентті Экожүйе',
      title: 'Тағылатын Құрылғы + Мобильді Платформа',
      subtitle: 'Саусақты ауыртып тесуді ұмытыңыз. Білегіңізден глюкозаның дәл көрсеткіштерін алып, нақты уақытта денсаулық тәуекелдерін талдаңыз.',
      hardwareTitle: 'SuGuard Тағылатын Сенсоры',
      hardwareBadge: 'АППАРАТТЫҚ ҚҰРЫЛҒЫ',
      hardwareDesc: 'Қанды инвазивті емес талдауға арналған спектроскопиялық датчиктері бар ақылды білезік.',
      hardwareFeat1Title: 'Оптикалық PPG-сенсорлар',
      hardwareFeat1Desc: 'Инесіз және тест-жолақсыз сахар мен оттегіні өлшеу.',
      hardwareFeat2Title: 'Bluetooth 5.3 Low Energy байланысы',
      hardwareFeat2Desc: 'Деректерді смартфонға лезде жіберу.',
      hardwareFeat3Title: '7 күнге дейін автономды',
      hardwareFeat3Desc: 'Жылдам қуаттау және IP67 судан қорғалған корпус.',
      appTitle: 'SuGuard Мобильді Қосымшасы',
      appBadge: 'БАҒДАРЛАМА ЖӘНЕ ЖИ',
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
      syncTitle: 'Синхрондау Жылдамдығы',
      syncDesc: 'Bluetooth 5.3 арқылы трекер мен мобильді қосымша арасындағы лездік дерек алмасу.',
    },
    experts: {
      badge: 'CustDev & Сарапшылар Кеңесі',
      title: 'Ғылыми Сарапшылар Кеңесі',
      subtitle: 'CustDev, құрылғы дәлдігін 94%-ға дейін арттыру және прототип жасау аясында кәсіби қолдау көрсеткен жетекші сарапшылар.',
      jerryName: 'Проф. Джерри Лоеб',
      jerryRole: 'Ғылыми кеңесші',
      jerryAff: 'Оңтүстік Калифорния Университеті (USC)',
      jerryDesc: 'Оңтүстік Калифорния Университетінің биоинженерлері мен PhD зерттеушілері әзірлеген биосенсорика және ЖИ ұсыныстары.',
      aidarName: 'Айдар Әлімбаев',
      aidarRole: 'ЖИ және деректер дәлдігі сарапшысы',
      aidarAff: 'MBZUAI докторанты • ЖИ зерттеушісі',
      aidarDesc: 'Сенсор дәлдігін арттыру және глюкоза деректерін талдауға жасанды интеллект енгізу бойынша кеңестер (94% дәлдікке қол жеткізді).',
      rustamName: 'Рүстем Асқарұлы',
      rustamRole: 'Аппараттық прототиптеу маманы',
      rustamAff: 'Fab Lab NURIS цифрлық прототиптеу инженері',
      rustamDesc: 'Сандық прототиптеу маманы. Құрылғының алғашқы физикалық үлгісін әзірлеуге және құрастыруға жетекшілік етті.',
    },
    partners: {
      badge: 'Серіктестік пен Ынтымақтастық',
      title: 'Ресми Ынтымақтастық',
      subtitle: 'Біз жетекші медициналық орталықтармен, ауруханалармен және қоғамдық ұйымдармен белсенді жұмыс істейміз.',
      catClinical: '01 / КЛИНИКАЛЫҚ СЫНАҚ',
      catMedCenter: '02 / МЕДИЦИНАЛЫҚ ОРТАЛЫҚ',
      catPresidential: '03 / ПРЕЗИДЕНТТІК КЛИНИКА',
      catPublic: '04 / ҚОҒАМДЫҚ БАСТАМА',
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
      nuDesc: 'Ғылыми-технологиялық CustDev және Fab Lab NURIS зертханасында аппараттық прототип жасау.',
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
      f6Title: 'Бұлттық Синхрондау',
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
      spec3Title: 'Энергия Тиімді Процессор',
      spec3Desc: 'Төмен энергия тұтынатын және сигналдарды жылдам өңдейтін микроконтроллер.',
      spec4Title: 'Гипоаллергенді Бау',
      spec4Desc: 'Теріні тітіркендірмей 24/7 ыңғайлы тағуға арналған.',
    },
    appSection: {
      badge: 'Қосымша Интерфейсі',
      title: 'Ыңғайлы Мобильді Интерфейс',
      subtitle: 'Көрнекі аналитика, динамикалық графиктер және лездік хабарландырулар.',
      counterLabel: 'ЭКРАН',
      screen1Tag: 'LIVE ДЕНСАУЛЫҚ ШОЛУЫ',
      screen1Title: 'Негізгі Дашборд',
      screen1Desc: 'Ағымдағы сахар деңгейі, пульс, SpO2 және құрылғы қосылу статусы.',
      screen1Specs: ['Диабет қаупінің % индексі', 'Ағымдағы глюкоза (ммоль/л)', 'SpO2 және тамыр соғысы'],
      screen2Tag: 'БИОМЕТРИЯЛЫҚ ҚАУІП ФАКТОРЛАРЫ',
      screen2Title: 'Диабет Тәуекел Картасы',
      screen2Desc: 'Тәуекел факторларын егжей-тегжейлі талдау және жеке ұсыныстар.',
      screen2Specs: ['Қауіп факторларын талдау', 'Орташа қант динамикасы', 'Қант көтерілуін алдын ала ескерту'],
      screen3Tag: 'ҮЗДІКСІЗ ГЛЮКОЗА ГРАФИКТЕРІ',
      screen3Title: 'Тамақтану Күнделігі',
      screen3Desc: 'Сурет арқылы тамақты тану және тәуліктік калория балансы.',
      screen3Specs: ['Тәуліктік, апталық және айлық графиктер', 'Мин, макс және орташа мән', 'Фото бойынша тағамды тану (АМК)'],
      screen4Tag: 'ЖИ-ЭНДОКРИНОЛОГПЕН ЧАТ',
      screen4Title: 'ИИ-Кеңесшімен Чат',
      screen4Desc: 'Денсаулығыңыз бойынша тәулік бойы қолдау және кеңестер.',
      screen4Specs: ['График пен рационды талдау', 'Жеке медициналық кеңестер', '24/7 лезде жауаптар'],
    },
    order: {
      kitTitle: 'SuGuard Complete Kit жиынтығы',
      kitSub: 'SuGuard тағылатын оптикалық биосенсоры + глюкоза, SpO2 және тамақтануды бақылайтын ИИ-экожүйесіне өмірлік қолжетімділік.',
      kitPriceUsd: '≈ $70 USD • Жасырын төлемсіз бір реттік сатып алу',
      bullet1: 'SuGuard смарт-білезігі (MAX30102 + SuGuard.Health PCB)',
      bullet2: 'Глюкоза, SpO2 және тамыр соғысын 24/7 инвазивті емес бақылау',
      bullet3: 'Диабет қаупін ИИ арқылы бағалау және тағамдарды компьютерлік көру',
      bullet4: 'Жеке ИИ-эндокринолог және бұлтты синхрондау',
      bullet5: 'USB Type-C жылдам қуаттау кабелі және 12 айлық кепілдік',
      btnApp: 'Мобильді қосымшаны жүктеу',
      btnAppBadge: 'Android .APK',
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
      a1: 'SuGuard - бұл тағылатын оптикалық құрылғыдан және ИИ мобильді қосымшасынан тұратын денсаулықты бақылау экожүйесі.',
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
      navTitle: 'Навигация',
      contactsTitle: 'Байланыс',
      downloadsTitle: 'Жүктеулер',
      preorderLink: 'Құрылғыға алдын ала тапсырыс',
      androidApp: 'Android қосымшасы (.APK)',
      rights: 'Барлық құқықтар қорғалған.',
      desc: 'Глюкозаны инвазивті емес бақылау және диабеттің алдын алу инновациялық платформасы.',
      designedIn: 'Қазақстанда әзірленген және жобаланған',
    },
  },
};
