// 梦眠阁 — 设计令牌 (HarmonyOS)
export class Colors {
  static readonly BG = '#0A0A12';
  static readonly BG2 = '#0E0E18';
  static readonly CARD = '#161622';
  static readonly PRIMARY = '#5B6ABF';
  static readonly PRIMARY_SOFT = 'rgba(91,106,191,0.15)';
  static readonly TEAL = '#3DAAA0';
  static readonly TEAL_SOFT = 'rgba(61,170,160,0.12)';
  static readonly WARN = '#C8923A';
  static readonly WARN_SOFT = 'rgba(200,146,58,0.12)';
  static readonly DANGER = '#C4544A';
  static readonly SUCCESS = '#4CAF50';
  static readonly TX = '#E4E4EC';
  static readonly TX2 = '#A0A0C0';
  static readonly TX3 = '#6A6A8A';
  static readonly BORDER = 'rgba(255,255,255,0.06)';
}

export class Spacing {
  static readonly XS = 4;
  static readonly SM = 8;
  static readonly MD = 12;
  static readonly LG = 16;
  static readonly XL = 20;
  static readonly XXL = 24;
}

export class Radius {
  static readonly SM = 8;
  static readonly MD = 10;
  static readonly LG = 16;
  static readonly XL = 20;
  static readonly FULL = 50;
}

export class FontSize {
  static readonly XS = 10;
  static readonly SM = 12;
  static readonly BASE = 14;
  static readonly MD = 16;
  static readonly LG = 18;
  static readonly XL = 22;
  static readonly XXL = 26;
  static readonly XXXL = 32;
}

export const API_BASE = 'http://192.168.3.64:8000';
