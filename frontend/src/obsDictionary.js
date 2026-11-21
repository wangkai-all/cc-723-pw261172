// RINEX 3.05 观测类型三字符编码解释（表 5-3 ~ 5-6）
// 第 1 字符：观测类型；第 2 字符：频段；第 3 字符：跟踪方式/通道代码
export const OBS_KIND = {
  C: '伪距（C/A 码等，单位米）',
  L: '载波相位（单位周）',
  D: '多普勒频率（单位 Hz）',
  S: '载噪比/信号强度（dB-Hz）',
  I: '电离层相位延迟（单位周）',
  X: '接收机信道号（仅电离层映射）',
}

export const BAND_GNSS = {
  // GPS (G) / QZSS (J)
  G: {
    '1': 'L1（1575.42 MHz）',
    '2': 'L2（1227.60 MHz）',
    '5': 'L5（1176.45 MHz）',
  },
  J: {
    '1': 'L1（1575.42 MHz）',
    '2': 'L2（1227.60 MHz）',
    '5': 'L5（1176.45 MHz）',
    '6': 'LEX（1278.75 MHz）',
  },
  // GLONASS (R)：频段号对应 FDMA 频道
  R: {
    '1': 'G1（~1602 MHz，FDMA）',
    '2': 'G2（~1246 MHz，FDMA）',
    '3': 'G3（1202.025 MHz，CDMA）',
    '4': 'G1a（1600.995 MHz，CDMA）',
    '6': 'G2a（1248.060 MHz，CDMA）',
  },
  // Galileo (E)
  E: {
    '1': 'E1（1575.42 MHz）',
    '5': 'E5a（1176.45 MHz）',
    '6': 'E6（1278.75 MHz）',
    '7': 'E5b（1207.14 MHz）',
    '8': 'E5ab（1191.795 MHz）',
  },
  // BDS (C)
  C: {
    '1': 'B1I（1561.098 MHz）',
    '2': 'B1-2（1589.742 MHz）',
    '5': 'B2a（1176.45 MHz）',
    '6': 'B3（1268.520 MHz）',
    '7': 'B2b/B2I（1207.14 MHz）',
    '8': 'B2ab（1191.795 MHz）',
  },
  // NavIC (I)
  I: {
    '5': 'L5（1176.45 MHz）',
    '9': 'S 频段（2492.028 MHz）',
  },
  // SBAS (S)
  S: {
    '1': 'L1（1575.42 MHz）',
    '5': 'L5（1176.45 MHz）',
  },
}

const SYSTEM_NAME = {
  G: 'GPS',
  R: 'GLONASS',
  E: 'Galileo',
  C: 'BDS 北斗',
  J: 'QZSS',
  I: 'NavIC',
  S: 'SBAS',
}

export function systemName(code) {
  return SYSTEM_NAME[code] || code
}

// 解释一个完整的三字符观测类型，如 C1C / L2W
export function explainObsType(obsType, system) {
  if (!obsType || obsType.length < 3) return { full: obsType || '' }
  const [kind, band, channel] = obsType
  const bandMeaning = BAND_GNSS[system]?.[band] || `频段 ${band}`
  return {
    full: obsType,
    kind,
    kindMeaning: OBS_KIND[kind] || `未知观测类型 ${kind}`,
    band,
    bandMeaning,
    channel,
    meaning: `${OBS_KIND[kind] || kind} · ${bandMeaning} · 通道码 ${channel}`,
  }
}

export const LLI_MEANING = {
  '1': '失锁/周跳（可能发生）',
  '2': '半周模糊度',
  '4': '站点无供电（天线悬空）',
}

export const SSI_MEANING = {
  '1': '极差',
  '2': '较差',
  '3': '一般',
  '4': '良好',
  '5': '优秀',
}
