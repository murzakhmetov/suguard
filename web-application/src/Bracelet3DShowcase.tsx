import React, { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import gsap from 'gsap';
import { type Language } from './translations';

interface PartInfo {
  id: string;
  num: string;
  shortName: string;
  overline: string;
  title: string;
  subtitle: string;
  description: string;
  specs: { label: string; value: string }[];
  pins: { title: string; sub: string }[];
  color: string;
}

const contentByLang: Record<
  Language,
  {
    headerTag: string;
    headerTitle: string;
    dragHint: string;
    xrayLabel: string;
    parts: PartInfo[];
  }
> = {
  ru: {
    headerTag: 'ИНЖЕНЕРНАЯ АРХИТЕКТУРА SUGUARD',
    headerTitle: 'Создан для точности.',
    dragHint: 'Зажмите мышь для вращения 360°',
    xrayLabel: 'Показать все слои (Рентген)',
    parts: [
      {
        id: 'assembled',
        num: '01',
        shortName: 'Смарт-браслет',
        overline: 'МОНОЛИТНЫЙ КОРПУС • ЭРГОНОМИКА 24/7',
        title: 'Смарт-браслет SuGuard',
        subtitle: 'Ударопрочный матовый корпус и гипоаллергенный ремешок',
        description:
          'В собранном виде вся электроника и разъёмы полностью скрыты внутри защитного прямоугольного корпуса с рельефной гравировкой SuGuard. Мягкий силиконовый ремешок с системой фиксации Pin-and-Tuck обеспечивает плотный контакт сенсора с запястьем 24/7.',
        specs: [
          { label: 'Масса трекера', value: '38 г' },
          { label: 'Защита корпуса', value: 'IP67' },
          { label: 'Фиксация', value: 'Pin-Lock 316L' },
        ],
        pins: [
          { title: 'Корпус SuGuard', sub: 'Ударопрочный матовый полимер' },
          { title: 'Замок Pin-and-Tuck', sub: 'Стальной пин + сквозной паз' },
          { title: 'Перфорированный ремешок', sub: '7 уровней регулировки обхвата' },
        ],
        color: '#00d4aa',
      },
      {
        id: 'stack',
        num: '02',
        shortName: 'Взрыв-схема',
        overline: 'МНОГОСЛОЙНАЯ КОМПОНОВКА • 5 УРОВНЕЙ',
        title: 'Внутренняя компоновка модулей',
        subtitle: 'Идеальная вертикальная центровка внутри шасси',
        description:
          'При раскрытии корпуса видна четырёхъярусная архитектура: верхняя крышка, литий-полимерный аккумулятор, кастомная материнская плата SuGuard.Health и оптический сенсор MAX30102, направленный в окно на дне корпуса.',
        specs: [
          { label: 'Архитектура', value: '5 уровней' },
          { label: 'Оптическое окно', value: 'ИК-линза' },
          { label: 'Толщина корпуса', value: '11.4 мм' },
        ],
        pins: [
          { title: 'Верхняя крышка', sub: 'Рельефный логотип SuGuard' },
          { title: 'Модуль электроники', sub: 'Аккумулятор + PCB + MAX30102' },
          { title: 'Нижняя чаша шасси', sub: 'Светоизолированное окно к коже' },
        ],
        color: '#38bdf8',
      },
      {
        id: 'battery',
        num: '03',
        shortName: 'Аккумулятор',
        overline: 'АВТОНОМНОЕ ПИТАНИЕ • ЗАЩИТА BMS',
        title: 'Литий-полимерный аккумулятор',
        subtitle: 'До 7 суток непрерывного мониторинга на одном заряде',
        description:
          'Высокоплотная Li-Po ячейка в алюминиевой ламинированной оболочке. Под янтарной термостойкой каптоновой лентой интегрирована плата защиты BMS (чипы DW01 и сдвоенные MOSFET), гарантирующая стабильное питание без просадок напряжения.',
        specs: [
          { label: 'Автономность', value: '7 дней' },
          { label: 'Номинал ячейки', value: '3.7V Li-Po' },
          { label: 'Быстрая зарядка', value: '45 мин' },
        ],
        pins: [
          { title: 'Ячейка Li-Po 3.7V', sub: 'Ламинированный алюминиевый корпус' },
          { title: 'Контроллер BMS + Каптон', sub: 'Защита от перезаряда и КЗ' },
          { title: 'Силовые линии', sub: 'Гибкие медные провода в силиконе' },
        ],
        color: '#facc15',
      },
      {
        id: 'pcb',
        num: '04',
        shortName: 'Плата PCB',
        overline: 'МАТЕРИНСКАЯ ПЛАТА • SUGUARD.HEALTH',
        title: 'Кастомная плата SuGuard.Health',
        subtitle: 'Модуль ESP32, фильтрация биосигналов и порт USB Type-C',
        description:
          'Фирменная зелёная плата SuGuard.Health объединяет экранированный радиомодуль ESP32 (Bluetooth 5.3 / Wi-Fi) с позолоченными торцевыми контактами, микросхему U1 (SOIC-8), малошумящие стабилизаторы U2 и U9, индикаторы D1/D2, кнопки RESET/BOOT и разъём USB Type-C.',
        specs: [
          { label: 'Микроконтроллер', value: 'ESP32 BLE 5.3' },
          { label: 'Каскад питания', value: 'U1 / U2 / U9' },
          { label: 'Интерфейс', value: 'USB Type-C' },
        ],
        pins: [
          { title: 'Радиомодуль ESP32', sub: '32-bit Dual-Core + антенна 2.4 ГГц' },
          { title: 'Микросхемы U1 / U2 / U9', sub: 'Обработка сигнала и LDO питание' },
          { title: 'Порт USB-C + BOOT / RESET', sub: 'Внутренний интерфейс зарядки и прошивки' },
        ],
        color: '#22c55e',
      },
      {
        id: 'sensor',
        num: '05',
        shortName: 'MAX30102',
        overline: 'ОПТИЧЕСКАЯ СПЕКТРОСКОПИЯ • PPG БИОСЕНСОР',
        title: 'Оптический датчик MAX30102',
        subtitle: 'Измерение пульса, SpO2 и глюкозы без прокола кожи',
        description:
          'Оптический модуль MAX30102 излучает сфокусированный красный (660 нм) и инфракрасный (880 нм) свет в капилляры запястья. Сверхчувствительный 18-битный фотодетектор фиксирует спектр поглощения крови, а нейросеть SuGuard вычисляет уровень глюкозы, сатурацию кислорода (SpO2) и пульс.',
        specs: [
          { label: 'Длины волн', value: '660 / 880 нм' },
          { label: 'Разрядность АЦП', value: '18-бит I2C' },
          { label: 'Точность ИИ', value: '94.2%' },
        ],
        pins: [
          { title: 'Излучатели 660 / 880 нм', sub: 'Красный + инфракрасный светодиоды PPG' },
          { title: 'Кремниевый фотодетектор', sub: '18-битный АЦП с фильтрацией засветки' },
          { title: 'Позолоченная шина I2C', sub: 'Контактные площадки VIN, SCL, SDA, INT' },
        ],
        color: '#f43f5e',
      },
    ],
  },
  en: {
    headerTag: 'SUGUARD HARDWARE ENGINEERING',
    headerTitle: 'Engineered for precision.',
    dragHint: 'Drag to rotate 360°',
    xrayLabel: 'Show All Layers (X-Ray)',
    parts: [
      {
        id: 'assembled',
        num: '01',
        shortName: 'Wearable',
        overline: 'MONOLITHIC UNIBODY • 24/7 ERGONOMICS',
        title: 'SuGuard Smart Wearable',
        subtitle: 'Impact-resistant matte enclosure & medical silicone strap',
        description:
          'Fully assembled, all electronics and ports are completely enclosed inside the matte black housing with raised SuGuard lettering. The soft fluoroelastomer band with a steel pin-and-tuck clasp ensures snug optical contact 24/7.',
        specs: [
          { label: 'Total Weight', value: '38 g' },
          { label: 'Protection', value: 'IP67' },
          { label: 'Clasp System', value: 'Pin-Lock 316L' },
        ],
        pins: [
          { title: 'SuGuard Unibody', sub: 'Matte impact-resistant polymer' },
          { title: 'Pin-and-Tuck Clasp', sub: '316L steel stud + pass-through slot' },
          { title: 'Perforated Wristband', sub: '7 precision sizing holes' },
        ],
        color: '#00d4aa',
      },
      {
        id: 'stack',
        num: '02',
        shortName: 'Exploded View',
        overline: 'MULTI-LAYER ARCHITECTURE • 5 TIERS',
        title: 'Internal Hardware Stack',
        subtitle: 'Precision vertical alignment inside the chassis',
        description:
          'Opening the enclosure reveals a five-tier architecture: top protective cover, high-density Li-Po cell, custom SuGuard.Health motherboard, and the MAX30102 optical biosensor aligned with the bottom aperture.',
        specs: [
          { label: 'Architecture', value: '5 Tiers' },
          { label: 'Optical Window', value: 'IR-Lens' },
          { label: 'Case Profile', value: '11.4 mm' },
        ],
        pins: [
          { title: 'Top Shield Cover', sub: 'Raised SuGuard emblem' },
          { title: 'Electronics Core', sub: 'Li-Po + PCB + MAX30102' },
          { title: 'Lower Chassis Tray', sub: 'Light-shielded skin aperture' },
        ],
        color: '#38bdf8',
      },
      {
        id: 'battery',
        num: '03',
        shortName: 'Battery',
        overline: 'AUTONOMOUS POWER • BMS PROTECTION',
        title: 'Lithium-Polymer Power Cell',
        subtitle: 'Up to 7 days of continuous monitoring on a single charge',
        description:
          'High-density pouch cell in brushed aluminum laminate. Sealed beneath amber Kapton tape is the BMS protection module (DW01 + dual MOSFETs) ensuring stable current delivery.',
        specs: [
          { label: 'Battery Life', value: '7 Days' },
          { label: 'Cell Rating', value: '3.7V Li-Po' },
          { label: 'Fast Charge', value: '45 min' },
        ],
        pins: [
          { title: '3.7V Li-Po Cell', sub: 'Brushed aluminum pouch' },
          { title: 'BMS + Kapton Seal', sub: 'Overcharge & short-circuit guard' },
          { title: 'Power Leads', sub: 'Silicone-insulated copper wires' },
        ],
        color: '#facc15',
      },
      {
        id: 'pcb',
        num: '04',
        shortName: 'Custom PCB',
        overline: 'MOTHERBOARD • SUGUARD.HEALTH',
        title: 'Custom SuGuard.Health PCB',
        subtitle: 'ESP32 MCU, signal conditioning & USB Type-C',
        description:
          'Our custom green SuGuard.Health PCB integrates a shielded ESP32 module (Bluetooth 5.3 / Wi-Fi) with gold castellated pads, U1 SOIC-8 IC, low-noise U2/U9 LDO regulators, D1/D2 LEDs, RESET/BOOT switches, and USB Type-C.',
        specs: [
          { label: 'Wireless MCU', value: 'ESP32 BLE 5.3' },
          { label: 'Power Rail', value: 'U1 / U2 / U9' },
          { label: 'Interface', value: 'USB Type-C' },
        ],
        pins: [
          { title: 'ESP32 RF Module', sub: '32-bit Dual-Core + 2.4GHz antenna' },
          { title: 'U1 / U2 / U9 ICs', sub: 'Signal conditioning & LDO regulation' },
          { title: 'USB-C + BOOT / RESET', sub: 'Internal charging & firmware flashing' },
        ],
        color: '#22c55e',
      },
      {
        id: 'sensor',
        num: '05',
        shortName: 'MAX30102',
        overline: 'OPTICAL SPECTROSCOPY • PPG BIOSENSOR',
        title: 'MAX30102 Optical Biosensor',
        subtitle: 'Painless Pulse, SpO2 & Glucose estimation',
        description:
          'The MAX30102 module emits 660nm Red and 880nm Infrared light into wrist capillaries. Its 18-bit photodetector captures blood absorption spectra, translated by SuGuard AI into glucose, SpO2, and heart rate.',
        specs: [
          { label: 'Wavelengths', value: '660 / 880 nm' },
          { label: 'ADC Resolution', value: '18-bit I2C' },
          { label: 'AI Accuracy', value: '94.2%' },
        ],
        pins: [
          { title: '660 / 880nm Emitters', sub: 'Dual Red + Infrared PPG LEDs' },
          { title: 'Silicon Photodetector', sub: '18-bit ADC ambient light rejection' },
          { title: 'Gold I2C Pads', sub: 'VIN, SCL, SDA, INT interface' },
        ],
        color: '#f43f5e',
      },
    ],
  },
  kk: {
    headerTag: 'SUGUARD ИНЖЕНЕРЛІК АРХИТЕКТУРАСЫ',
    headerTitle: 'Дәлдік үшін жасалған.',
    dragHint: '360° айналдыру үшін тінтуірді басыңыз',
    xrayLabel: 'Барлық қабаттар (Рентген)',
    parts: [
      {
        id: 'assembled',
        num: '01',
        shortName: 'Білезік',
        overline: 'МОНОЛИТТІ КОРПУС • 24/7 ЭРГОНОМИКА',
        title: 'SuGuard Смарт-білезігі',
        subtitle: 'Соққыға төзімді корпус және гипоаллергенді бау',
        description:
          'Толық жиналған күйінде барлық электроника мен порттар SuGuard корпусының ішінде толық жасырылған. Pin-and-Tuck бекіткіші бар жұмсақ силикон бау тәулік бойы терімен тығыз байланысты қамтамасыз етеді.',
        specs: [
          { label: 'Салмағы', value: '38 г' },
          { label: 'Қорғаныс', value: 'IP67' },
          { label: 'Бекіткіш', value: 'Pin-Lock 316L' },
        ],
        pins: [
          { title: 'SuGuard Корпусы', sub: 'Матты соққыға төзімді полимер' },
          { title: 'Pin-and-Tuck Құлпы', sub: 'Болат пин + өтпелі ойық' },
          { title: 'Перфорацияланған бау', sub: '7 өлшемді реттеу тесігі' },
        ],
        color: '#00d4aa',
      },
      {
        id: 'stack',
        num: '02',
        shortName: 'Жарылыс-схема',
        overline: 'КӨПҚАБАТТЫ ҚҰРЫЛЫМ • 5 ДЕҢГЕЙ',
        title: 'Ішкі модульдердің орналасуы',
        subtitle: 'Шасси ішіндегі вертикалды дәлдік',
        description:
          'Корпусты ашқанда бес деңгейлі архитектура көрінеді: үстіңгі қақпақ, Li-Po аккумуляторы, SuGuard.Health аналық тақтасы және MAX30102 оптикалық сенсоры.',
        specs: [
          { label: 'Құрылымы', value: '5 деңгей' },
          { label: 'Оптикалық терезе', value: 'ИҚ-линза' },
          { label: 'Қалыңдығы', value: '11.4 мм' },
        ],
        pins: [
          { title: 'Үстіңгі қақпақ', sub: 'Бедерлі SuGuard логотипі' },
          { title: 'Электроника ядросы', sub: 'Li-Po + PCB + MAX30102' },
          { title: 'Төменгі шасси', sub: 'Жарықтан қорғалған терезе' },
        ],
        color: '#38bdf8',
      },
      {
        id: 'battery',
        num: '03',
        shortName: 'Аккумулятор',
        overline: 'АВТОНОМДЫ ҚУАТ • BMS ҚОРҒАНЫСЫ',
        title: 'Литий-полимерлі аккумулятор',
        subtitle: 'Бір зарядпен 7 тәулікке дейін үздіксіз жұмыс',
        description:
          'Алюминий корпустағы жоғары тығыздықты Li-Po ұяшығы. Каптон таспасының астында қысқа тұйықталудан қорғайтын BMS модулі орналасқан.',
        specs: [
          { label: 'Автономдылық', value: '7 күн' },
          { label: 'Кернеуі', value: '3.7V Li-Po' },
          { label: 'Жылдам заряд', value: '45 мин' },
        ],
        pins: [
          { title: 'Li-Po 3.7V Ұяшығы', sub: 'Алюминий ламинатталған корпус' },
          { title: 'BMS + Каптон', sub: 'Қысқа тұйықталудан қорғаныс' },
          { title: 'Қуат желісі', sub: 'Силиконды мыс сымдар' },
        ],
        color: '#facc15',
      },
      {
        id: 'pcb',
        num: '04',
        shortName: 'Плата PCB',
        overline: 'АНАЛЫҚ ТАҚТА • SUGUARD.HEALTH',
        title: 'Арнайы SuGuard.Health Платасы',
        subtitle: 'ESP32 модулі, сигналды сүзу және USB Type-C',
        description:
          'Алтын жалатылған контактілері бар SuGuard.Health тақтасы ESP32 радиомодулін (Bluetooth 5.3 / Wi-Fi), U1/U2/U9 микросхемаларын, RESET/BOOT батырмаларын және USB-C портын біріктіреді.',
        specs: [
          { label: 'Процессор', value: 'ESP32 BLE 5.3' },
          { label: 'Микросхемалар', value: 'U1 / U2 / U9' },
          { label: 'Интерфейс', value: 'USB Type-C' },
        ],
        pins: [
          { title: 'ESP32 Радиомодулі', sub: '32-bit Dual-Core + 2.4 ГГц антенна' },
          { title: 'U1 / U2 / U9 Каскады', sub: 'Сигналды өңдеу және LDO' },
          { title: 'USB-C + BOOT / RESET', sub: 'Қуаттау және бағдарламалау' },
        ],
        color: '#22c55e',
      },
      {
        id: 'sensor',
        num: '05',
        shortName: 'MAX30102',
        overline: 'ОПТИКАЛЫҚ СПЕКТРОСКОПИЯ • PPG БИОСЕНСОР',
        title: 'MAX30102 Оптикалық Сенсоры',
        subtitle: 'Пульс, SpO2 және глюкозаны инесіз өлшеу',
        description:
          'MAX30102 модулі білек капиллярларына 660 нм (қызыл) және 880 нм (инфрақызыл) сәуле бағыттайды. 18-биттік фотодетектор мен SuGuard ЖИ алгоритмі қант деңгейін, SpO2 және пульсті есептейді.',
        specs: [
          { label: 'Толқындар', value: '660 / 880 нм' },
          { label: 'АЦП дәлдігі', value: '18-бит I2C' },
          { label: 'ЖИ дәлдігі', value: '94.2%' },
        ],
        pins: [
          { title: '660 / 880 нм Кристалл', sub: 'Қызыл + инфрақызыл PPG диодтары' },
          { title: 'Кремний фотодетекторы', sub: '18-биттік АЦП спектр талдағышы' },
          { title: 'Алтын I2C Шинасы', sub: 'VIN, SCL, SDA, INT контактілері' },
        ],
        color: '#f43f5e',
      },
    ],
  },
};

function createDarkStudioEnvMap(renderer: THREE.WebGLRenderer): THREE.Texture {
  const canvas = document.createElement('canvas');
  canvas.width = 1024;
  canvas.height = 512;
  const ctx = canvas.getContext('2d')!;

  ctx.fillStyle = '#040508';
  ctx.fillRect(0, 0, 1024, 512);

  const g1 = ctx.createRadialGradient(512, 85, 10, 512, 85, 240);
  g1.addColorStop(0, '#ffffff');
  g1.addColorStop(0.3, 'rgba(220, 235, 255, 0.78)');
  g1.addColorStop(1, 'rgba(0, 0, 0, 0)');
  ctx.fillStyle = g1;
  ctx.fillRect(0, 0, 1024, 512);

  const g2 = ctx.createRadialGradient(170, 240, 10, 170, 240, 190);
  g2.addColorStop(0, '#00ffd5');
  g2.addColorStop(0.35, 'rgba(0, 212, 170, 0.4)');
  g2.addColorStop(1, 'rgba(0, 0, 0, 0)');
  ctx.fillStyle = g2;
  ctx.fillRect(0, 0, 1024, 512);

  const g3 = ctx.createRadialGradient(850, 210, 10, 850, 210, 190);
  g3.addColorStop(0, '#ffffff');
  g3.addColorStop(0.3, 'rgba(56, 189, 248, 0.45)');
  g3.addColorStop(1, 'rgba(0, 0, 0, 0)');
  ctx.fillStyle = g3;
  ctx.fillRect(0, 0, 1024, 512);

  ctx.fillStyle = 'rgba(255, 255, 255, 0.85)';
  ctx.fillRect(100, 50, 820, 14);

  const envTex = new THREE.CanvasTexture(canvas);
  envTex.mapping = THREE.EquirectangularReflectionMapping;

  const pmrem = new THREE.PMREMGenerator(renderer);
  const target = pmrem.fromEquirectangular(envTex);
  envTex.dispose();
  pmrem.dispose();
  return target.texture;
}

function createMicroBumpTexture(): THREE.CanvasTexture {
  const canvas = document.createElement('canvas');
  canvas.width = 512;
  canvas.height = 512;
  const ctx = canvas.getContext('2d')!;
  ctx.fillStyle = '#808080';
  ctx.fillRect(0, 0, 512, 512);

  ctx.strokeStyle = '#929292';
  ctx.lineWidth = 1.4;
  for (let i = -512; i < 512; i += 4) {
    ctx.beginPath();
    ctx.moveTo(i, 0);
    ctx.lineTo(i + 512, 512);
    ctx.stroke();
  }
  const tex = new THREE.CanvasTexture(canvas);
  tex.wrapS = THREE.RepeatWrapping;
  tex.wrapT = THREE.RepeatWrapping;
  tex.repeat.set(4, 4);
  return tex;
}

function createRoundedPlateGeometry(
  width: number,
  depth: number,
  thickness: number,
  radius: number,
  bevel = 0.02
): THREE.ExtrudeGeometry {
  const shape = new THREE.Shape();
  const w = width / 2;
  const d = depth / 2;
  const r = Math.min(radius, w, d);

  shape.moveTo(-w + r, -d);
  shape.lineTo(w - r, -d);
  shape.quadraticCurveTo(w, -d, w, -d + r);
  shape.lineTo(w, d - r);
  shape.quadraticCurveTo(w, d, w - r, d);
  shape.lineTo(-w + r, d);
  shape.quadraticCurveTo(-w, d, -w, d - r);
  shape.lineTo(-w, -d + r);
  shape.quadraticCurveTo(-w, -d, -w + r, -d);

  const geo = new THREE.ExtrudeGeometry(shape, {
    depth: thickness,
    bevelEnabled: true,
    bevelSegments: 4,
    steps: 1,
    bevelSize: bevel,
    bevelThickness: bevel,
  });
  geo.rotateX(-Math.PI / 2);
  geo.center();
  return geo;
}

function createHollowCaseGeometry(
  width: number,
  depth: number,
  height: number,
  wall: number,
  radius: number
): THREE.ExtrudeGeometry {
  const shape = new THREE.Shape();
  const w = width / 2;
  const d = depth / 2;
  const r = radius;

  shape.moveTo(-w + r, -d);
  shape.lineTo(w - r, -d);
  shape.quadraticCurveTo(w, -d, w, -d + r);
  shape.lineTo(w, d - r);
  shape.quadraticCurveTo(w, d, w - r, d);
  shape.lineTo(-w + r, d);
  shape.quadraticCurveTo(-w, d, -w, d - r);
  shape.lineTo(-w, -d + r);
  shape.quadraticCurveTo(-w, -d, -w + r, -d);

  const hole = new THREE.Path();
  const iw = w - wall;
  const id = d - wall;
  const ir = Math.max(0.03, r - wall * 0.5);

  hole.moveTo(-iw + ir, -id);
  hole.lineTo(iw - ir, -id);
  hole.quadraticCurveTo(iw, -id, iw, -id + ir);
  hole.lineTo(iw, id - ir);
  hole.quadraticCurveTo(iw, id, iw - ir, id);
  hole.lineTo(-iw + ir, id);
  hole.quadraticCurveTo(-iw, id, -iw, id - ir);
  hole.lineTo(-iw, -id + ir);
  hole.quadraticCurveTo(-iw, -id, -iw + ir, -id);
  shape.holes.push(hole);

  const geo = new THREE.ExtrudeGeometry(shape, {
    depth: height,
    bevelEnabled: true,
    bevelSegments: 4,
    steps: 1,
    bevelSize: 0.018,
    bevelThickness: 0.018,
  });
  geo.rotateX(-Math.PI / 2);
  geo.center();
  return geo;
}

function createUpperStrapGeometry(): THREE.ExtrudeGeometry {
  const shape = new THREE.Shape();
  shape.moveTo(-0.5, 0);
  shape.lineTo(0.5, 0);
  shape.lineTo(0.5, 1.45);
  shape.bezierCurveTo(0.5, 1.85, 0.68, 2.0, 0.68, 2.38);
  shape.bezierCurveTo(0.68, 2.75, 0.52, 3.35, 0.0, 3.35);
  shape.bezierCurveTo(-0.52, 3.35, -0.68, 2.75, -0.68, 2.38);
  shape.bezierCurveTo(-0.68, 2.0, -0.5, 1.85, -0.5, 1.45);
  shape.closePath();

  const slot = new THREE.Path();
  const sw = 0.34;
  const sh = 0.095;
  const sy = 2.25;
  slot.moveTo(-sw + sh, sy - sh);
  slot.lineTo(sw - sh, sy - sh);
  slot.absarc(sw - sh, sy, sh, -Math.PI / 2, Math.PI / 2, false);
  slot.lineTo(-sw + sh, sy + sh);
  slot.absarc(-sw + sh, sy, sh, Math.PI / 2, (3 * Math.PI) / 2, false);
  shape.holes.push(slot);

  const geo = new THREE.ExtrudeGeometry(shape, {
    depth: 0.1,
    bevelEnabled: true,
    bevelSegments: 3,
    steps: 1,
    bevelSize: 0.018,
    bevelThickness: 0.018,
  });
  geo.rotateX(-Math.PI / 2);
  return geo;
}

function createLowerStrapGeometry(): THREE.ExtrudeGeometry {
  const shape = new THREE.Shape();
  shape.moveTo(-0.5, 0);
  shape.lineTo(0.5, 0);
  shape.lineTo(0.46, -3.7);
  shape.absarc(0, -3.7, 0.46, 0, Math.PI, true);
  shape.lineTo(-0.5, 0);

  for (let i = 0; i < 7; i++) {
    const hy = -1.15 - i * 0.36;
    const hole = new THREE.Path();
    hole.absarc(0, hy, 0.068, 0, Math.PI * 2, false);
    shape.holes.push(hole);
  }

  const geo = new THREE.ExtrudeGeometry(shape, {
    depth: 0.1,
    bevelEnabled: true,
    bevelSegments: 3,
    steps: 1,
    bevelSize: 0.018,
    bevelThickness: 0.018,
  });
  geo.rotateX(-Math.PI / 2);
  return geo;
}

function createSMDPart(
  length: number,
  width: number,
  height: number,
  bodyMat: THREE.Material,
  solderMat: THREE.Material,
  padMat: THREE.Material
): THREE.Group {
  const g = new THREE.Group();
  const termLen = length * 0.24;
  const bodyLen = length - termLen * 2;

  const padGeo = new THREE.BoxGeometry(termLen * 1.35, 0.008, width * 1.15);
  const leftPad = new THREE.Mesh(padGeo, padMat);
  leftPad.position.set(-(bodyLen / 2 + termLen / 2), -height / 2 + 0.004, 0);
  const rightPad = new THREE.Mesh(padGeo, padMat);
  rightPad.position.set(bodyLen / 2 + termLen / 2, -height / 2 + 0.004, 0);

  const leftTerm = new THREE.Mesh(new THREE.BoxGeometry(termLen, height, width), solderMat);
  leftTerm.position.x = -(bodyLen / 2 + termLen / 2);

  const centerBody = new THREE.Mesh(
    new THREE.BoxGeometry(bodyLen, height * 0.96, width * 0.96),
    bodyMat
  );

  const rightTerm = new THREE.Mesh(new THREE.BoxGeometry(termLen, height, width), solderMat);
  rightTerm.position.x = bodyLen / 2 + termLen / 2;

  g.add(leftPad, rightPad, leftTerm, centerBody, rightTerm);
  return g;
}

function createICPackage(
  bodyW: number,
  bodyD: number,
  bodyH: number,
  pinsLeft: number,
  pinsRight: number,
  icMat: THREE.Material,
  pinMat: THREE.Material,
  goldMat: THREE.Material
): THREE.Group {
  const g = new THREE.Group();
  const body = new THREE.Mesh(
    createRoundedPlateGeometry(bodyW, bodyD, bodyH, 0.02, 0.008),
    icMat
  );
  body.position.y = bodyH / 2 + 0.02;
  g.add(body);

  const dot = new THREE.Mesh(
    new THREE.CylinderGeometry(0.022, 0.022, 0.006, 16),
    new THREE.MeshBasicMaterial({ color: 0xcbd5e1 })
  );
  dot.position.set(-bodyW * 0.3, bodyH + 0.03, -bodyD * 0.3);
  g.add(dot);

  const addPins = (count: number, side: number) => {
    for (let i = 0; i < count; i++) {
      const zOffset =
        count === 1 ? 0 : -bodyD * 0.35 + (i / (count - 1)) * (bodyD * 0.7);
      const pin = new THREE.Mesh(new THREE.BoxGeometry(0.085, 0.028, 0.032), pinMat);
      pin.position.set(side * (bodyW / 2 + 0.035), 0.022, zOffset);
      const pad = new THREE.Mesh(new THREE.BoxGeometry(0.11, 0.006, 0.046), goldMat);
      pad.position.set(side * (bodyW / 2 + 0.045), 0.004, zOffset);
      g.add(pin, pad);
    }
  };

  addPins(pinsLeft, -1);
  addPins(pinsRight, 1);
  return g;
}

function createExactSuGuardTopLogo(): THREE.CanvasTexture {
  const canvas = document.createElement('canvas');
  canvas.width = 1024;
  canvas.height = 600;
  const ctx = canvas.getContext('2d')!;
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  ctx.save();
  ctx.translate(canvas.width / 2, 175);

  const drawLogoPaths = (strokeColor: string, width: number) => {
    ctx.strokeStyle = strokeColor;
    ctx.lineWidth = width;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';

    const r = 44;
    ctx.beginPath();
    ctx.arc(0, -42, r, Math.PI * 0.84, Math.PI * 0.16, false);
    ctx.stroke();

    ctx.beginPath();
    ctx.arc(0, 42, r, -Math.PI * 0.16, -Math.PI * 0.84, false);
    ctx.stroke();

    ctx.beginPath();
    ctx.arc(-42, 0, r, Math.PI * 0.34, -Math.PI * 0.34, false);
    ctx.stroke();

    ctx.beginPath();
    ctx.arc(42, 0, r, -Math.PI * 0.66, Math.PI * 0.66, false);
    ctx.stroke();

    ctx.beginPath();
    ctx.moveTo(-25, -10);
    ctx.bezierCurveTo(-8, -34, 14, 34, 25, 10);
    ctx.stroke();
  };

  drawLogoPaths('rgba(5, 6, 8, 0.9)', 26);
  drawLogoPaths('#dde3ea', 16);
  ctx.restore();

  ctx.font = '600 172px Inter, Arial, sans-serif';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.lineWidth = 14;
  ctx.strokeStyle = 'rgba(5, 6, 8, 0.9)';
  ctx.strokeText('SuGuard', canvas.width / 2, 435);
  ctx.fillStyle = '#dde3ea';
  ctx.fillText('SuGuard', canvas.width / 2, 435);

  const tex = new THREE.CanvasTexture(canvas);
  tex.anisotropy = 16;
  return tex;
}

function createRealisticPCBTexture(): THREE.CanvasTexture {
  const canvas = document.createElement('canvas');
  canvas.width = 1024;
  canvas.height = 1024;
  const ctx = canvas.getContext('2d')!;

  ctx.fillStyle = '#0a3d1e';
  ctx.fillRect(0, 0, 1024, 1024);

  ctx.strokeStyle = '#126332';
  ctx.lineWidth = 9;
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';

  const traces = [
    [[165, 560], [275, 560], [335, 620]],
    [[165, 720], [275, 720], [335, 680]],
    [[390, 520], [390, 430], [480, 430]],
    [[512, 580], [512, 850]],
    [[470, 700], [470, 860]],
    [[615, 560], [725, 560], [725, 740]],
    [[235, 255], [320, 255]],
    [[235, 345], [320, 345]],
    [[680, 220], [790, 220], [790, 490]],
    [[720, 300], [835, 300], [835, 530]],
  ];
  traces.forEach((t) => {
    ctx.beginPath();
    t.forEach(([x, y], i) => (i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y)));
    ctx.stroke();
  });

  const vias = [
    [290, 470], [670, 490], [730, 250], [775, 310],
    [430, 780], [640, 760], [260, 820], [700, 820],
    [760, 390], [810, 450], [310, 520], [540, 510],
  ];
  vias.forEach(([vx, vy]) => {
    ctx.beginPath();
    ctx.arc(vx, vy, 9, 0, Math.PI * 2);
    ctx.fillStyle = '#fbbf24';
    ctx.fill();
    ctx.beginPath();
    ctx.arc(vx, vy, 4, 0, Math.PI * 2);
    ctx.fillStyle = '#041e0e';
    ctx.fill();
  });

  ctx.save();
  ctx.translate(888, 795);
  ctx.rotate(-Math.PI / 2);
  ctx.fillStyle = '#ffffff';
  ctx.fillRect(0, -28, 336, 48);
  ctx.fillStyle = '#0a3d1e';
  ctx.font = 'bold 36px monospace';
  ctx.fillText('SuGuard.Health', 12, 8);
  ctx.restore();

  ctx.fillStyle = '#f8fafc';
  ctx.font = 'bold 21px monospace';
  ctx.fillText('R16', 248, 205);
  ctx.fillText('C1', 258, 312);
  ctx.fillText('C2 R6', 230, 420);
  ctx.fillText('D1', 120, 575);
  ctx.fillText('D2', 120, 735);
  ctx.fillText('R4', 252, 590);
  ctx.fillText('R3', 252, 692);
  ctx.fillText('R11 R13', 280, 640);
  ctx.fillText('C11', 482, 545);
  ctx.fillText('U9', 540, 615);
  ctx.fillText('U2', 525, 685);
  ctx.fillText('C17', 625, 505);
  ctx.fillText('R8 R9', 645, 615);
  ctx.fillText('C18', 615, 725);
  ctx.fillText('R1', 350, 725);
  ctx.fillText('R5', 345, 775);
  ctx.fillText('C4', 400, 765);
  ctx.fillText('C5', 535, 765);
  ctx.fillText('R2', 600, 790);
  ctx.fillText('RESET', 208, 912);
  ctx.fillText('BOOT', 742, 912);

  const tex = new THREE.CanvasTexture(canvas);
  tex.anisotropy = 16;
  return tex;
}

function createESP32ShieldTexture(): THREE.CanvasTexture {
  const canvas = document.createElement('canvas');
  canvas.width = 512;
  canvas.height = 512;
  const ctx = canvas.getContext('2d')!;

  ctx.fillStyle = '#cbd5e1';
  ctx.fillRect(0, 0, 512, 512);

  ctx.strokeStyle = 'rgba(255,255,255,0.25)';
  ctx.lineWidth = 1;
  for (let y = 0; y < 512; y += 3) {
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(512, y);
    ctx.stroke();
  }

  ctx.strokeStyle = 'rgba(30, 41, 59, 0.45)';
  ctx.lineWidth = 4;
  ctx.strokeRect(28, 28, 456, 456);

  ctx.fillStyle = 'rgba(15, 23, 42, 0.6)';
  ctx.beginPath();
  ctx.arc(72, 440, 12, 0, Math.PI * 2);
  ctx.fill();

  ctx.font = 'bold 34px monospace';
  ctx.fillText('ESP32-S3-WROOM', 65, 190);
  ctx.font = '600 24px monospace';
  ctx.fillText('SuGuard AI Core', 65, 240);
  ctx.font = '20px monospace';
  ctx.fillText('2.4GHz Wi-Fi / BLE 5.3', 65, 290);
  ctx.fillText('FCC ID: 2AC7Z-ESP32', 65, 330);

  const tex = new THREE.CanvasTexture(canvas);
  tex.anisotropy = 8;
  return tex;
}

function sampleKeyframes(values: number[], tNorm: number): number {
  const n = values.length - 1;
  const scaled = THREE.MathUtils.clamp(tNorm, 0, 1) * n;
  const idx = Math.min(Math.floor(scaled), n - 1);
  const frac = scaled - idx;
  const smooth = frac * frac * (3 - 2 * frac);
  return THREE.MathUtils.lerp(values[idx], values[idx + 1], smooth);
}

export const Bracelet3DShowcase: React.FC<{ lang: Language }> = ({ lang }) => {
  const sectionRef = useRef<HTMLDivElement>(null);
  const canvasWrapperRef = useRef<HTMLDivElement>(null);
  const textContentRef = useRef<HTMLDivElement>(null);

  const [activeStage, setActiveStage] = useState<number>(0);
  const [xrayMode, setXrayMode] = useState<boolean>(false);

  const smoothScrollRef = useRef<{ value: number }>({ value: 0 });
  const activeStageRef = useRef<number>(0);
  const xrayModeRef = useRef<boolean>(false);

  const t = contentByLang[lang];

  useEffect(() => {
    xrayModeRef.current = xrayMode;
  }, [xrayMode]);

  useEffect(() => {
    if (!textContentRef.current) return;
    const elems = textContentRef.current.querySelectorAll('.gsap-reveal-item');
    gsap.killTweensOf(elems);
    gsap.fromTo(
      elems,
      { y: 28, opacity: 0, filter: 'blur(6px)' },
      {
        y: 0,
        opacity: 1,
        filter: 'blur(0px)',
        duration: 0.65,
        stagger: 0.07,
        ease: 'power3.out',
      }
    );
  }, [activeStage, lang]);

  useEffect(() => {
    const onScroll = () => {
      if (!sectionRef.current) return;
      const rect = sectionRef.current.getBoundingClientRect();
      const totalScrollable = sectionRef.current.offsetHeight - window.innerHeight;
      if (totalScrollable <= 0) return;

      const rawProgress = THREE.MathUtils.clamp(-rect.top / totalScrollable, 0, 1);

      gsap.to(smoothScrollRef.current, {
        value: rawProgress,
        duration: 0.42,
        ease: 'power2.out',
        overwrite: true,
      });

      const nextStage = Math.min(4, Math.floor(rawProgress * 4.99));
      if (nextStage !== activeStageRef.current) {
        activeStageRef.current = nextStage;
        setActiveStage(nextStage);
      }
    };

    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  useEffect(() => {
    const mount = canvasWrapperRef.current;
    if (!mount) return;

    const scene = new THREE.Scene();

    const camera = new THREE.PerspectiveCamera(
      32,
      mount.clientWidth / mount.clientHeight,
      0.1,
      100
    );

    const updateCameraOffset = () => {
      if (!mount) return;
      const w = mount.clientWidth;
      const h = mount.clientHeight;
      camera.aspect = w / h;
      if (w > 1024) {
        camera.setViewOffset(w, h, w * 0.21, 0, w, h);
      } else {
        camera.clearViewOffset();
      }
      camera.updateProjectionMatrix();
    };
    updateCameraOffset();

    const renderer = new THREE.WebGLRenderer({
      antialias: true,
      alpha: true,
      powerPreference: 'high-performance',
    });
    renderer.setSize(mount.clientWidth, mount.clientHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.2;
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    mount.innerHTML = '';
    mount.appendChild(renderer.domElement);

    const envTexture = createDarkStudioEnvMap(renderer);
    scene.environment = envTexture;
    const microBump = createMicroBumpTexture();

    const keyLight = new THREE.DirectionalLight(0xffffff, 2.4);
    keyLight.position.set(5, 10, 7);
    keyLight.castShadow = true;
    scene.add(keyLight);

    const tealRim = new THREE.SpotLight(0x00d4aa, 5.0, 24, Math.PI / 3, 0.6);
    tealRim.position.set(-6, 5, -5);
    scene.add(tealRim);

    const blueFill = new THREE.PointLight(0x38bdf8, 2.0, 18);
    blueFill.position.set(5, -4, 4);
    scene.add(blueFill);

    const topCaseMat = new THREE.MeshPhysicalMaterial({
      color: 0x101216,
      roughness: 0.34,
      metalness: 0.14,
      bumpMap: microBump,
      bumpScale: 0.004,
      clearcoat: 0.22,
      clearcoatRoughness: 0.3,
      envMapIntensity: 1.5,
      transparent: true,
      opacity: 1,
    });

    const bottomCaseMat = new THREE.MeshPhysicalMaterial({
      color: 0x101216,
      roughness: 0.36,
      metalness: 0.14,
      bumpMap: microBump,
      bumpScale: 0.004,
      clearcoat: 0.2,
      envMapIntensity: 1.4,
      transparent: true,
      opacity: 1,
    });

    const strapMat = new THREE.MeshPhysicalMaterial({
      color: 0x0c0d10,
      roughness: 0.72,
      metalness: 0.04,
      bumpMap: microBump,
      bumpScale: 0.0015,
      clearcoat: 0.08,
      transparent: true,
      opacity: 1,
    });

    const goldMat = new THREE.MeshStandardMaterial({
      color: 0xffc72c,
      metalness: 1.0,
      roughness: 0.11,
      envMapIntensity: 2.3,
    });

    const solderMat = new THREE.MeshStandardMaterial({
      color: 0xe2e8f0,
      metalness: 0.92,
      roughness: 0.18,
      envMapIntensity: 1.8,
    });

    const chromeMat = new THREE.MeshStandardMaterial({
      color: 0xf8fafc,
      metalness: 0.98,
      roughness: 0.08,
      envMapIntensity: 2.3,
    });

    const lipoFoilMat = new THREE.MeshPhysicalMaterial({
      color: 0xdbe2ea,
      metalness: 0.9,
      roughness: 0.2,
      bumpMap: microBump,
      bumpScale: 0.002,
      clearcoat: 0.4,
      envMapIntensity: 1.9,
      transparent: true,
      opacity: 1,
    });

    const pcbSolderMaskMat = new THREE.MeshPhysicalMaterial({
      color: 0x0a3d1e,
      roughness: 0.22,
      metalness: 0.12,
      clearcoat: 0.8,
      clearcoatRoughness: 0.14,
      envMapIntensity: 1.6,
      transparent: true,
      opacity: 1,
    });

    const rootGroup = new THREE.Group();
    scene.add(rootGroup);

    const topCoverGroup = new THREE.Group();

    const topShellMesh = new THREE.Mesh(
      createRoundedPlateGeometry(3.3, 1.96, 0.34, 0.11, 0.028),
      topCaseMat
    );
    topShellMesh.castShadow = true;
    topShellMesh.receiveShadow = true;
    topCoverGroup.add(topShellMesh);

    const logoOverlayMat = new THREE.MeshStandardMaterial({
      map: createExactSuGuardTopLogo(),
      transparent: true,
      metalness: 0.45,
      roughness: 0.28,
      envMapIntensity: 1.6,
      depthWrite: false,
      polygonOffset: true,
      polygonOffsetFactor: -2,
    });
    const logoOverlayPlane = new THREE.Mesh(
      new THREE.PlaneGeometry(3.12, 1.82),
      logoOverlayMat
    );
    logoOverlayPlane.rotation.x = -Math.PI / 2;
    logoOverlayPlane.position.y = 0.2;
    topCoverGroup.add(logoOverlayPlane);

    rootGroup.add(topCoverGroup);

    const batteryGroup = new THREE.Group();

    const lipoCell = new THREE.Mesh(
      createRoundedPlateGeometry(2.1, 1.48, 0.24, 0.12, 0.04),
      lipoFoilMat
    );
    lipoCell.position.set(-0.22, 0, 0);
    lipoCell.castShadow = true;
    batteryGroup.add(lipoCell);

    const bmsPcb = new THREE.Mesh(
      new THREE.BoxGeometry(0.34, 0.06, 1.38),
      new THREE.MeshStandardMaterial({ color: 0x064e24, roughness: 0.3 })
    );
    bmsPcb.position.set(0.68, 0.02, 0);
    batteryGroup.add(bmsPcb);

    const icBlackMat = new THREE.MeshStandardMaterial({ color: 0x0f1319, roughness: 0.25 });
    const dw01Chip = createICPackage(0.12, 0.18, 0.055, 3, 3, icBlackMat, solderMat, goldMat);
    dw01Chip.position.set(0.68, 0.05, -0.26);
    const mosfetChip = createICPackage(0.14, 0.22, 0.055, 4, 4, icBlackMat, solderMat, goldMat);
    mosfetChip.position.set(0.68, 0.05, 0.22);
    batteryGroup.add(dw01Chip, mosfetChip);

    const kaptonMat = new THREE.MeshPhysicalMaterial({
      color: 0xf59e0b,
      transparent: true,
      opacity: 0.72,
      roughness: 0.12,
      metalness: 0.05,
      clearcoat: 1.0,
      envMapIntensity: 1.6,
    });
    const kaptonMesh = new THREE.Mesh(
      createRoundedPlateGeometry(0.54, 1.52, 0.27, 0.08, 0.02),
      kaptonMat
    );
    kaptonMesh.position.set(0.62, 0, 0);
    batteryGroup.add(kaptonMesh);

    const redWireCurve = new THREE.CatmullRomCurve3([
      new THREE.Vector3(0.84, 0.03, 0.42),
      new THREE.Vector3(1.15, 0.06, 0.52),
      new THREE.Vector3(1.1, -0.12, 0.28),
      new THREE.Vector3(0.78, -0.22, 0.16),
    ]);
    const blkWireCurve = new THREE.CatmullRomCurve3([
      new THREE.Vector3(0.84, 0.03, -0.42),
      new THREE.Vector3(1.15, 0.06, -0.52),
      new THREE.Vector3(1.1, -0.12, -0.28),
      new THREE.Vector3(0.78, -0.22, -0.16),
    ]);
    batteryGroup.add(
      new THREE.Mesh(
        new THREE.TubeGeometry(redWireCurve, 32, 0.035, 12, false),
        new THREE.MeshStandardMaterial({ color: 0xdc2626, roughness: 0.3 })
      ),
      new THREE.Mesh(
        new THREE.TubeGeometry(blkWireCurve, 32, 0.035, 12, false),
        new THREE.MeshStandardMaterial({ color: 0x18181b, roughness: 0.3 })
      )
    );

    rootGroup.add(batteryGroup);

    const pcbGroup = new THREE.Group();

    const pcbBoardMesh = new THREE.Mesh(
      createRoundedPlateGeometry(2.26, 2.26, 0.08, 0.16, 0.015),
      pcbSolderMaskMat
    );
    pcbBoardMesh.castShadow = true;
    pcbBoardMesh.receiveShadow = true;
    pcbGroup.add(pcbBoardMesh);

    const pcbTopMat = new THREE.MeshPhysicalMaterial({
      map: createRealisticPCBTexture(),
      roughness: 0.22,
      metalness: 0.15,
      clearcoat: 0.65,
      clearcoatRoughness: 0.15,
      polygonOffset: true,
      polygonOffsetFactor: -2,
    });
    const pcbTopSurface = new THREE.Mesh(new THREE.PlaneGeometry(2.18, 2.18), pcbTopMat);
    pcbTopSurface.rotation.x = -Math.PI / 2;
    pcbTopSurface.position.y = 0.058;
    pcbGroup.add(pcbTopSurface);

    [
      [-0.92, -0.92],
      [0.92, -0.92],
      [-0.92, 0.92],
      [0.92, 0.92],
    ].forEach(([cx, cz]) => {
      const pad = new THREE.Mesh(new THREE.CylinderGeometry(0.11, 0.11, 0.118, 28), goldMat);
      pad.position.set(cx, 0, cz);
      const hole = new THREE.Mesh(
        new THREE.CylinderGeometry(0.072, 0.072, 0.124, 24),
        new THREE.MeshBasicMaterial({ color: 0x050608 })
      );
      hole.position.set(cx, 0, cz);
      pcbGroup.add(pad, hole);
    });

    [0.12, 0.34].forEach((cz) => {
      const pad = new THREE.Mesh(new THREE.CylinderGeometry(0.072, 0.072, 0.118, 24), goldMat);
      pad.position.set(0.68, 0, cz);
      const hole = new THREE.Mesh(
        new THREE.CylinderGeometry(0.036, 0.036, 0.124, 16),
        new THREE.MeshBasicMaterial({ color: 0x050608 })
      );
      hole.position.set(0.68, 0, cz);
      pcbGroup.add(pad, hole);
    });

    const espSubstrate = new THREE.Mesh(
      createRoundedPlateGeometry(1.26, 1.45, 0.05, 0.04, 0.008),
      new THREE.MeshStandardMaterial({ color: 0x14161c, roughness: 0.4 })
    );
    espSubstrate.position.set(-0.04, 0.085, -0.62);
    pcbGroup.add(espSubstrate);

    const espShieldMat = new THREE.MeshStandardMaterial({
      map: createESP32ShieldTexture(),
      metalness: 0.9,
      roughness: 0.2,
      envMapIntensity: 1.9,
    });
    const espShieldMesh = new THREE.Mesh(
      createRoundedPlateGeometry(1.14, 1.02, 0.16, 0.05, 0.015),
      espShieldMat
    );
    espShieldMesh.position.set(-0.04, 0.185, -0.42);
    espShieldMesh.castShadow = true;
    pcbGroup.add(espShieldMesh);

    const antTracePositions = [
      [-0.38, -1.18, 0.04, 0.22],
      [-0.22, -1.18, 0.04, 0.22],
      [-0.06, -1.18, 0.04, 0.22],
      [0.1, -1.18, 0.04, 0.22],
      [0.26, -1.18, 0.04, 0.22],
      [-0.06, -1.28, 0.68, 0.04],
    ];
    antTracePositions.forEach(([ax, az, aw, ad]) => {
      const tr = new THREE.Mesh(new THREE.BoxGeometry(aw, 0.008, ad), goldMat);
      tr.position.set(ax, 0.12, az);
      pcbGroup.add(tr);
    });

    for (let i = 0; i < 9; i++) {
      const zPos = -0.86 + i * 0.105;
      [-0.67, 0.59].forEach((xSide) => {
        const castPad = new THREE.Mesh(new THREE.BoxGeometry(0.065, 0.07, 0.055), goldMat);
        castPad.position.set(xSide, 0.085, zPos);
        pcbGroup.add(castPad);
      });
    }
    for (let i = 0; i < 8; i++) {
      const xPos = -0.46 + i * 0.12;
      const castPad = new THREE.Mesh(new THREE.BoxGeometry(0.055, 0.07, 0.065), goldMat);
      castPad.position.set(xPos, 0.085, 0.11);
      pcbGroup.add(castPad);
    }

    const usbGroup = new THREE.Group();
    const usbOuterShell = new THREE.Mesh(
      createHollowCaseGeometry(0.68, 0.22, 0.52, 0.045, 0.08),
      chromeMat
    );
    usbOuterShell.rotation.x = Math.PI / 2;
    usbOuterShell.position.set(0, 0.165, 0.96);
    usbGroup.add(usbOuterShell);

    const usbInnerDark = new THREE.Mesh(
      new THREE.BoxGeometry(0.56, 0.12, 0.44),
      new THREE.MeshBasicMaterial({ color: 0x050608 })
    );
    usbInnerDark.position.set(0, 0.165, 0.94);
    usbGroup.add(usbInnerDark);

    const usbTongue = new THREE.Mesh(
      new THREE.BoxGeometry(0.44, 0.035, 0.38),
      new THREE.MeshStandardMaterial({ color: 0x1e293b, roughness: 0.3 })
    );
    usbTongue.position.set(0, 0.165, 0.97);
    usbGroup.add(usbTongue);

    for (let i = 0; i < 12; i++) {
      const px = -0.25 + i * 0.045;
      const pin = new THREE.Mesh(new THREE.BoxGeometry(0.022, 0.03, 0.095), goldMat);
      pin.position.set(px, 0.075, 0.68);
      usbGroup.add(pin);
    }
    pcbGroup.add(usbGroup);

    [-0.56, 0.56].forEach((bx) => {
      const swGroup = new THREE.Group();
      const swBody = new THREE.Mesh(
        createRoundedPlateGeometry(0.28, 0.32, 0.08, 0.03, 0.008),
        new THREE.MeshStandardMaterial({ color: 0xf8fafc, roughness: 0.25 })
      );
      swBody.position.y = 0.095;
      const swShield = new THREE.Mesh(new THREE.BoxGeometry(0.25, 0.09, 0.25), chromeMat);
      swShield.position.y = 0.102;
      const swActuator = new THREE.Mesh(
        new THREE.CylinderGeometry(0.072, 0.072, 0.145, 24),
        new THREE.MeshStandardMaterial({ color: 0x334155, metalness: 0.5, roughness: 0.25 })
      );
      swActuator.position.y = 0.14;

      [
        [-0.14, -0.1],
        [0.14, -0.1],
        [-0.14, 0.1],
        [0.14, 0.1],
      ].forEach(([px, pz]) => {
        const leg = new THREE.Mesh(new THREE.BoxGeometry(0.05, 0.03, 0.04), solderMat);
        leg.position.set(px, 0.072, pz);
        swGroup.add(leg);
      });

      swGroup.add(swBody, swShield, swActuator);
      swGroup.position.set(bx, 0, 0.85);
      pcbGroup.add(swGroup);
    });

    const u1Soic = createICPackage(0.32, 0.36, 0.11, 4, 4, icBlackMat, solderMat, goldMat);
    u1Soic.position.set(-0.22, 0.06, 0.25);
    pcbGroup.add(u1Soic);

    const u9Chip = createICPackage(0.18, 0.2, 0.08, 3, 2, icBlackMat, solderMat, goldMat);
    u9Chip.position.set(0.32, 0.06, 0.22);
    pcbGroup.add(u9Chip);

    const u2Chip = createICPackage(0.18, 0.2, 0.08, 3, 3, icBlackMat, solderMat, goldMat);
    u2Chip.position.set(-0.02, 0.06, 0.44);
    pcbGroup.add(u2Chip);

    [
      [0.22, 0x00ffaa],
      [0.54, 0x38bdf8],
    ].forEach(([lz, lcol]) => {
      const ledPart = createSMDPart(
        0.18,
        0.09,
        0.075,
        new THREE.MeshBasicMaterial({ color: lcol }),
        solderMat,
        goldMat
      );
      ledPart.position.set(-0.86, 0.092, lz);
      ledPart.rotation.y = Math.PI / 2;
      pcbGroup.add(ledPart);
    });

    const smdCapMat = new THREE.MeshStandardMaterial({ color: 0xc27803, roughness: 0.3 });
    const smdResMat = new THREE.MeshStandardMaterial({ color: 0x0f172a, roughness: 0.25 });

    const smdCoords: [number, number, number, number, boolean, number][] = [
      [-0.82, -0.45, 0.18, 0.09, true, Math.PI / 2],
      [-0.82, -0.25, 0.14, 0.07, true, Math.PI / 2],
      [-0.72, -0.62, 0.12, 0.06, false, 0],
      [0.02, 0.18, 0.18, 0.09, true, 0],
      [0.34, 0.04, 0.18, 0.09, true, 0],
      [0.24, 0.48, 0.18, 0.09, true, Math.PI / 2],
      [-0.24, 0.54, 0.16, 0.08, true, Math.PI / 2],
      [0.12, 0.56, 0.14, 0.07, true, Math.PI / 2],
      [-0.48, 0.22, 0.12, 0.06, false, Math.PI / 2],
      [-0.48, 0.36, 0.12, 0.06, false, Math.PI / 2],
      [-0.64, 0.26, 0.12, 0.06, false, Math.PI / 2],
      [-0.64, 0.48, 0.12, 0.06, false, Math.PI / 2],
      [0.5, 0.18, 0.12, 0.06, false, Math.PI / 2],
      [0.5, 0.32, 0.12, 0.06, false, Math.PI / 2],
      [-0.42, 0.58, 0.12, 0.06, false, Math.PI / 2],
      [0.28, 0.64, 0.12, 0.06, false, Math.PI / 2],
    ];
    smdCoords.forEach(([sx, sz, l, w, isCap, ry]) => {
      const part = createSMDPart(
        l,
        w,
        0.07,
        isCap ? smdCapMat : smdResMat,
        solderMat,
        goldMat
      );
      part.position.set(sx, 0.092, sz);
      part.rotation.y = ry;
      pcbGroup.add(part);
    });

    rootGroup.add(pcbGroup);

    const sensorGroup = new THREE.Group();

    const maxPcbMesh = new THREE.Mesh(
      createRoundedPlateGeometry(1.85, 1.32, 0.075, 0.1, 0.012),
      new THREE.MeshPhysicalMaterial({
        color: 0x0b0d12,
        roughness: 0.24,
        metalness: 0.2,
        clearcoat: 0.7,
      })
    );
    maxPcbMesh.castShadow = true;
    sensorGroup.add(maxPcbMesh);

    for (let i = 0; i < 7; i++) {
      const px = -0.6 + i * 0.2;
      [-0.52, 0.52].forEach((pz) => {
        const ring = new THREE.Mesh(new THREE.CylinderGeometry(0.058, 0.058, 0.102, 24), goldMat);
        ring.position.set(px, 0, pz);
        const hole = new THREE.Mesh(
          new THREE.CylinderGeometry(0.03, 0.03, 0.108, 16),
          new THREE.MeshBasicMaterial({ color: 0x040507 })
        );
        hole.position.set(px, 0, pz);
        sensorGroup.add(ring, hole);
      });
    }

    [-0.78, 0.78].forEach((sx) => {
      const bar = new THREE.Mesh(new THREE.BoxGeometry(0.06, 0.1, 0.88), goldMat);
      bar.position.set(sx, 0, 0);
      sensorGroup.add(bar);
    });

    const maxHousing = new THREE.Mesh(
      createRoundedPlateGeometry(0.64, 0.44, 0.14, 0.04, 0.01),
      new THREE.MeshStandardMaterial({ color: 0x161922, roughness: 0.22, metalness: 0.45 })
    );
    maxHousing.position.y = 0.085;
    sensorGroup.add(maxHousing);

    for (let i = 0; i < 7; i++) {
      const px = -0.24 + i * 0.08;
      [-0.23, 0.23].forEach((pz) => {
        const p = new THREE.Mesh(new THREE.BoxGeometry(0.036, 0.04, 0.05), goldMat);
        p.position.set(px, 0.055, pz);
        sensorGroup.add(p);
      });
    }

    const emitterWell = new THREE.Mesh(
      new THREE.BoxGeometry(0.22, 0.02, 0.32),
      new THREE.MeshBasicMaterial({ color: 0x050609 })
    );
    emitterWell.position.set(-0.15, 0.158, 0);

    const detectorWell = new THREE.Mesh(
      new THREE.BoxGeometry(0.24, 0.02, 0.32),
      new THREE.MeshBasicMaterial({ color: 0x050609 })
    );
    detectorWell.position.set(0.13, 0.158, 0);
    sensorGroup.add(emitterWell, detectorWell);

    const redLedDie = new THREE.Mesh(
      new THREE.BoxGeometry(0.08, 0.025, 0.08),
      new THREE.MeshBasicMaterial({ color: 0xff1e42 })
    );
    redLedDie.position.set(-0.15, 0.168, -0.07);

    const irLedDie = new THREE.Mesh(
      new THREE.BoxGeometry(0.08, 0.025, 0.08),
      new THREE.MeshBasicMaterial({ color: 0xff5252 })
    );
    irLedDie.position.set(-0.15, 0.168, 0.07);

    const photoDetectorDie = new THREE.Mesh(
      new THREE.BoxGeometry(0.18, 0.022, 0.26),
      new THREE.MeshPhysicalMaterial({
        color: 0x0284c7,
        metalness: 0.9,
        roughness: 0.08,
        clearcoat: 1.0,
      })
    );
    photoDetectorDie.position.set(0.13, 0.168, 0);
    sensorGroup.add(redLedDie, irLedDie, photoDetectorDie);

    const glassCover = new THREE.Mesh(
      new THREE.BoxGeometry(0.58, 0.018, 0.38),
      new THREE.MeshPhysicalMaterial({
        color: 0xffffff,
        transparent: true,
        opacity: 0.28,
        roughness: 0.05,
        metalness: 0.1,
        clearcoat: 1,
      })
    );
    glassCover.position.y = 0.182;
    sensorGroup.add(glassCover);

    [
      [-0.48, -0.2],
      [-0.48, 0.0],
      [-0.48, 0.2],
      [0.48, -0.2],
      [0.48, 0.0],
      [0.48, 0.2],
    ].forEach(([mx, mz], idx) => {
      const smd = createSMDPart(
        0.14,
        0.07,
        0.06,
        idx % 2 === 0 ? smdCapMat : smdResMat,
        solderMat,
        goldMat
      );
      smd.position.set(mx, 0.072, mz);
      sensorGroup.add(smd);
    });

    const maxRegulator = createICPackage(0.2, 0.2, 0.07, 3, 2, icBlackMat, solderMat, goldMat);
    maxRegulator.position.set(0.48, 0.048, -0.32);
    sensorGroup.add(maxRegulator);

    const sensorGlowLight = new THREE.PointLight(0xff1744, 2.2, 3.2);
    sensorGlowLight.position.set(-0.15, 0.28, 0);
    sensorGroup.add(sensorGlowLight);

    rootGroup.add(sensorGroup);

    const bottomCaseGroup = new THREE.Group();

    const lowerWalls = new THREE.Mesh(
      createHollowCaseGeometry(3.3, 1.96, 0.56, 0.15, 0.11),
      bottomCaseMat
    );
    lowerWalls.position.y = 0.06;
    lowerWalls.castShadow = true;
    lowerWalls.receiveShadow = true;
    bottomCaseGroup.add(lowerWalls);

    const lowerFloor = new THREE.Mesh(
      createRoundedPlateGeometry(3.3, 1.96, 0.08, 0.11, 0.02),
      bottomCaseMat
    );
    lowerFloor.position.y = -0.22;
    bottomCaseGroup.add(lowerFloor);

    const upperStrapMesh = new THREE.Mesh(createUpperStrapGeometry(), strapMat);
    upperStrapMesh.position.set(0, -0.12, -0.92);
    bottomCaseGroup.add(upperStrapMesh);

    const pinFlange = new THREE.Mesh(
      new THREE.CylinderGeometry(0.18, 0.18, 0.06, 32),
      chromeMat
    );
    pinFlange.position.set(0, -0.02, -3.72);
    const pinHead = new THREE.Mesh(
      new THREE.CylinderGeometry(0.09, 0.09, 0.14, 24),
      chromeMat
    );
    pinHead.position.set(0, 0.03, -3.72);
    bottomCaseGroup.add(pinFlange, pinHead);

    const lowerStrapMesh = new THREE.Mesh(createLowerStrapGeometry(), strapMat);
    lowerStrapMesh.position.set(0, -0.12, 0.92);
    bottomCaseGroup.add(lowerStrapMesh);

    rootGroup.add(bottomCaseGroup);

    let isDragging = false;
    let prevX = 0;
    let prevY = 0;
    let userRotY = 0;
    let userRotX = 0;

    const onPointerDown = (e: PointerEvent) => {
      isDragging = true;
      prevX = e.clientX;
      prevY = e.clientY;
    };
    const onPointerMove = (e: PointerEvent) => {
      if (!isDragging) return;
      userRotY += (e.clientX - prevX) * 0.008;
      userRotX = Math.max(-0.55, Math.min(0.55, userRotX + (e.clientY - prevY) * 0.006));
      prevX = e.clientX;
      prevY = e.clientY;
    };
    const onPointerUp = () => {
      isDragging = false;
    };

    const domElem = renderer.domElement;
    domElem.addEventListener('pointerdown', onPointerDown);
    window.addEventListener('pointermove', onPointerMove);
    window.addEventListener('pointerup', onPointerUp);

    let animFrameId: number;
    const clock = new THREE.Clock();

    const animate = () => {
      animFrameId = requestAnimationFrame(animate);
      const elapsed = clock.getElapsedTime();
      const p = smoothScrollRef.current.value; 

      const batScale = sampleKeyframes([0.74, 0.92, 1.32, 0.85, 0.8], p);
      const pcbScale = sampleKeyframes([0.68, 0.86, 0.82, 1.25, 0.8], p);
      const senScale = sampleKeyframes([0.72, 0.9, 0.85, 0.85, 1.42], p);

      batteryGroup.scale.setScalar(batScale);
      pcbGroup.scale.setScalar(pcbScale);
      sensorGroup.scale.setScalar(senScale);

      topCoverGroup.position.y = sampleKeyframes([0.22, 2.2, 3.6, 3.8, 3.8], p);
      topCoverGroup.position.z = sampleKeyframes([0.0, -0.2, -1.5, -1.8, -1.8], p);

      batteryGroup.position.y = sampleKeyframes([0.06, 1.05, 0.15, 2.8, 3.0], p);
      batteryGroup.position.z = sampleKeyframes([0.0, -0.05, 0.3, -1.5, -1.6], p);

      pcbGroup.position.y = sampleKeyframes([-0.03, 0.0, -1.6, 0.1, 2.2], p);
      pcbGroup.position.z = sampleKeyframes([0.0, 0.1, -0.8, 0.35, -1.4], p);

      sensorGroup.position.y = sampleKeyframes([-0.12, -1.0, -2.4, -1.8, 0.05], p);
      sensorGroup.position.z = sampleKeyframes([0.0, 0.2, -1.0, -0.9, 0.45], p);

      bottomCaseGroup.position.y = sampleKeyframes([-0.16, -2.15, -3.4, -3.4, -3.2], p);
      bottomCaseGroup.position.z = sampleKeyframes([0.0, -0.1, -1.2, -1.2, -1.1], p);

      const minGhost = xrayModeRef.current ? 0.16 : 0.0;
      const caseAlpha = Math.max(
        minGhost,
        sampleKeyframes([1.0, 1.0, 0.0, 0.0, 0.0], p)
      );
      const batAlpha = Math.max(
        minGhost,
        sampleKeyframes([0.0, 1.0, 1.0, 0.0, 0.0], p)
      );
      const pcbAlpha = Math.max(
        minGhost,
        sampleKeyframes([0.0, 1.0, 0.0, 1.0, 0.0], p)
      );
      const senAlpha = Math.max(
        minGhost,
        sampleKeyframes([0.0, 1.0, 0.0, 0.0, 1.0], p)
      );

      topCaseMat.opacity = xrayModeRef.current && p < 0.15 ? 0.22 : caseAlpha;
      logoOverlayMat.opacity = topCaseMat.opacity;
      bottomCaseMat.opacity = caseAlpha;
      strapMat.opacity = caseAlpha;
      lipoFoilMat.opacity = xrayModeRef.current && p < 0.15 ? 1.0 : batAlpha;
      pcbSolderMaskMat.opacity = xrayModeRef.current && p < 0.15 ? 1.0 : pcbAlpha;
      pcbTopMat.opacity = pcbSolderMaskMat.opacity;

      topCoverGroup.visible = topCaseMat.opacity > 0.01;
      bottomCaseGroup.visible = bottomCaseMat.opacity > 0.01;
      batteryGroup.visible = lipoFoilMat.opacity > 0.01;
      pcbGroup.visible = pcbSolderMaskMat.opacity > 0.01;
      sensorGroup.visible = (xrayModeRef.current && p < 0.15 ? 1.0 : senAlpha) > 0.01;

      const camY = sampleKeyframes([6.8, 3.8, 3.2, 3.4, 2.9], p);
      const camZ = sampleKeyframes([9.6, 10.6, 6.4, 6.2, 5.6], p);
      const lookY = sampleKeyframes([-0.2, 0.0, 0.15, 0.1, 0.05], p);

      camera.position.set(0, camY, camZ);
      camera.lookAt(0, lookY, 0);

      const baseRotX = sampleKeyframes([0.48, 0.32, 0.52, 0.62, 0.58], p);
      const baseRotY =
        sampleKeyframes([-0.18, 0.36, -0.22, 0.14, -0.18], p) +
        Math.sin(elapsed * 0.45) * 0.06;

      rootGroup.rotation.x = THREE.MathUtils.lerp(
        rootGroup.rotation.x,
        baseRotX + userRotX,
        0.08
      );
      rootGroup.rotation.y = THREE.MathUtils.lerp(
        rootGroup.rotation.y,
        baseRotY + userRotY,
        0.08
      );

      const heartBeat = Math.pow(Math.sin(elapsed * 3.6), 4);
      sensorGlowLight.intensity = 1.6 + heartBeat * 2.2;

      renderer.render(scene, camera);
    };

    animate();

    const handleResize = () => {
      if (!mount) return;
      updateCameraOffset();
      renderer.setSize(mount.clientWidth, mount.clientHeight);
    };
    window.addEventListener('resize', handleResize);

    return () => {
      cancelAnimationFrame(animFrameId);
      domElem.removeEventListener('pointerdown', onPointerDown);
      window.removeEventListener('pointermove', onPointerMove);
      window.removeEventListener('pointerup', onPointerUp);
      window.removeEventListener('resize', handleResize);
      envTexture.dispose();
      microBump.dispose();
      renderer.dispose();
    };
  }, [lang]);

  const currentPart = t.parts[activeStage];

  const jumpToStage = (index: number) => {
    if (!sectionRef.current) return;
    const rect = sectionRef.current.getBoundingClientRect();
    const absoluteTop = window.scrollY + rect.top;
    const scrollableDistance = sectionRef.current.offsetHeight - window.innerHeight;
    const targetProgress = index / 4;
    window.scrollTo({
      top: absoluteTop + scrollableDistance * targetProgress,
      behavior: 'smooth',
    });
  };

  return (
    <section ref={sectionRef} className="suguard-3d-fullbleed" id="hardware-3d">
      <div className="suguard-3d-sticky">
        <div ref={canvasWrapperRef} className="suguard-3d-canvas-full" />

        <div className="suguard-3d-topbar container">
          <div className="suguard-3d-brand-head">
            <span className="suguard-3d-kicker">{t.headerTag}</span>
            <h2 className="suguard-3d-headline">{t.headerTitle}</h2>
          </div>

          <div className="suguard-3d-nav-steps">
            {t.parts.map((part, idx) => (
              <button
                key={part.id}
                onClick={() => jumpToStage(idx)}
                className={`suguard-step-btn ${activeStage === idx ? 'active' : ''}`}
              >
                <span
                  className="step-btn-num"
                  style={activeStage === idx ? { color: part.color } : undefined}
                >
                  {part.num}
                </span>
                <span className="step-btn-name">{part.shortName}</span>
                {activeStage === idx && (
                  <span
                    className="step-btn-bar"
                    style={{ background: part.color }}
                  />
                )}
              </button>
            ))}
          </div>
        </div>

        <div className="suguard-3d-editorial-wrap container">
          <div ref={textContentRef} className="suguard-editorial-content">
            <div className="editorial-index-row gsap-reveal-item">
              <span
                className="editorial-index-num"
                style={{ color: currentPart.color }}
              >
                {currentPart.num}
              </span>
              <span
                className="editorial-index-line"
                style={{ background: currentPart.color }}
              />
              <span
                className="editorial-overline"
                style={{ color: currentPart.color }}
              >
                {currentPart.overline}
              </span>
            </div>

            <h3 className="editorial-title gsap-reveal-item">{currentPart.title}</h3>

            <p className="editorial-subtitle gsap-reveal-item">{currentPart.subtitle}</p>

            <p className="editorial-description gsap-reveal-item">
              {currentPart.description}
            </p>

            <div className="editorial-pins-list gsap-reveal-item">
              {currentPart.pins.map((pin, idx) => (
                <div key={idx} className="editorial-pin-item">
                  <span
                    className="editorial-pin-dot"
                    style={{
                      background: currentPart.color,
                      boxShadow: `0 0 10px ${currentPart.color}`,
                    }}
                  />
                  <div>
                    <div className="editorial-pin-title">{pin.title}</div>
                    <div className="editorial-pin-sub">{pin.sub}</div>
                  </div>
                </div>
              ))}
            </div>

            <div className="editorial-metrics-row gsap-reveal-item">
              {currentPart.specs.map((spec, i) => (
                <div key={i} className="editorial-metric-item">
                  <div
                    className="editorial-metric-value"
                    style={i === 0 ? { color: currentPart.color } : undefined}
                  >
                    {spec.value}
                  </div>
                  <div className="editorial-metric-label">{spec.label}</div>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="suguard-3d-bottombar container">
          <button
            type="button"
            onClick={() => setXrayMode(!xrayMode)}
            className={`suguard-xray-pill ${xrayMode ? 'active' : ''}`}
          >
            <span className="xray-dot" />
            {t.xrayLabel}
          </button>

          <div className="suguard-drag-hint">{t.dragHint}</div>
        </div>
      </div>
    </section>
  );
};