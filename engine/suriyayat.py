"""
Thai Astronomical Engine — สุริยยาตร์ (Suriyayat / Surya Siddhanta variant)

อ้างอิง:
  - Surya Siddhanta (translated Burgess, 1860)
  - Vernotte & Kichenassamy (2018), arxiv:1709.09620 — Khmer ephemeris constants
  - La Loubère (1693), Siamese system documentation
  - pythaidate (hmmbug/pythaidate) — Chulasakarat calendar

การคำนวณ:
  วัน/เวลา/พิกัด → หรคุณ → มัธยม → สมผุส → ราศี+องศา + ลัคนา

CALIBRATION NOTE:
  ค่าเริ่มต้น (beta_epoch) คำนวณจาก Surya Siddhanta ที่จุด Kali Yuga → CS epoch
  อาจคลาดเคลื่อน ±1–2° จากตำราไทยสำนักต่างๆ
  ควร cross-check กับ payakorn.com หรือ 4ZSuriya ด้วยวันเกิดที่รู้ผลแน่ชัด
"""

import math
from dataclasses import dataclass
from datetime import date, time


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Julian Day ของจุด CS epoch (จุลศักราช ปี 0 = March 21, 638 CE เที่ยงคืน)
CS_EPOCH_JD = 1_954_167.5

# Julian Day ของจุด Kali Yuga (KY epoch = Feb 18, 3102 BCE เที่ยงคืน)
KY_EPOCH_JD = 588_465.5

# วันใน Mahayuga (4,320,000 ปีสุริยะ) ตาม Surya Siddhanta
MAHAYUGA_DAYS = 1_577_917_828

# จำนวนรอบใน Mahayuga ต่อดาวแต่ละดวง (Surya Siddhanta บทที่ 1)
REVOLUTIONS = {
    "sun":           4_320_000,
    "moon":         57_753_336,
    "moon_apogee":     488_203,   # อุจจพล (ตำแหน่ง apogee จันทร์)
    "mars":          2_296_832,
    "mercury_sc":   17_937_060,   # sighroccha (mean synodic cycle)
    "jupiter":         364_220,
    "venus_sc":      7_022_376,   # sighroccha
    "saturn":          146_568,
    "rahu":           -232_238,   # ลบ = retrograde
}

# Mean daily motion (°/day) = revolutions × 360° / MAHAYUGA_DAYS
DAILY_MOTION = {k: v * 360.0 / MAHAYUGA_DAYS for k, v in REVOLUTIONS.items()}

# ตำแหน่งเริ่มต้น (mean longitude) ที่ CS epoch (°)
# คำนวณ: motion × (CS_EPOCH_JD - KY_EPOCH_JD) % 360
# ค่าเหล่านี้อาจต้องปรับ (calibration) ด้วย Beeja correction จากต้นฉบับไทย
_ky_to_cs = CS_EPOCH_JD - KY_EPOCH_JD  # 1,365,702 days
EPOCH_POSITION = {
    k: (DAILY_MOTION[k] * _ky_to_cs) % 360.0
    for k in DAILY_MOTION
}

# Manda epicycle sizes (° of periphery) — odd/even quadrant average
MANDA_EPICYCLE = {
    "sun":     13.667,
    "moon":    31.667,
    "mars":    75.0,
    "mercury": 28.0,
    "jupiter": 35.0,
    "venus":   12.0,
    "saturn":  49.0,
}

# Sighra epicycle sizes
SIGHRA_EPICYCLE = {
    "mars":     235.0,
    "mercury":  133.0,
    "jupiter":   70.0,
    "venus":    262.0,
    "saturn":    39.0,
}

# Surya Siddhanta sine radius
SS_RADIUS = 3438.0

# แมปดาว id (ระบบของ user) → key ใน constants นี้
PLANET_KEYS = {
    1: "sun",
    2: "moon",
    3: "mars",
    4: "mercury",
    5: "jupiter",
    6: "venus",
    7: "saturn",
    8: "rahu",
}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class PlanetPosition:
    planet_id: int
    longitude: float    # สมผุส longitude (0–360°, sidereal)
    sign_no: int         # ราศี 1–12
    degree_in_sign: float  # องศาในราศี 0–30°

    @property
    def retrograde(self) -> bool:
        return self.planet_id == 8  # ราหู always retrograde


@dataclass
class Chart:
    lagna: PlanetPosition
    planets: dict[int, PlanetPosition]  # planet_id → position


# ---------------------------------------------------------------------------
# Calendar helpers
# ---------------------------------------------------------------------------

def gregorian_to_jd(year: int, month: int, day: int) -> float:
    """Gregorian calendar → Julian Day Number (noon = integer)."""
    if month <= 2:
        year -= 1
        month += 12
    A = year // 100
    B = 2 - A + A // 4
    return int(365.25 * (year + 4716)) + int(30.6001 * (month + 1)) + day + B - 1524.5


def harakun(year: int, month: int, day: int) -> int:
    """คืนค่า หรคุณ = จำนวนวันนับจาก CS epoch จนถึงวันที่ระบุ"""
    jd = gregorian_to_jd(year, month, day)
    return int(jd - CS_EPOCH_JD)


# ---------------------------------------------------------------------------
# Mean position (มัธยม)
# ---------------------------------------------------------------------------

def mean_longitude(planet_key: str, t: int) -> float:
    """
    คำนวณ มัธยมราศี = ตำแหน่งเฉลี่ย ณ หรคุณ t
    ผลลัพธ์ 0–360°
    """
    pos = (EPOCH_POSITION[planet_key] + DAILY_MOTION[planet_key] * t) % 360.0
    if pos < 0:
        pos += 360.0
    return pos


# ---------------------------------------------------------------------------
# Equation of center (สมผุส — มันทะ correction)
# ---------------------------------------------------------------------------

def _ss_sin(angle_deg: float) -> float:
    """Sine ใน unit ของ Surya Siddhanta (ผล × SS_RADIUS)."""
    return math.sin(math.radians(angle_deg)) * SS_RADIUS


def manda_correction(planet_key: str, madhyama: float, apogee: float) -> float:
    """
    แก้ค่า equation of center (มันทะ) ให้กับ madhyama longitude
    คืนค่า longitude ที่แก้แล้ว (sphuta บางส่วน)

    planet_key: ชื่อดาว (sun, moon, mars, mercury, jupiter, venus, saturn)
    madhyama: mean longitude (°)
    apogee: apogee longitude (°) — สำหรับ sun/moon ใช้ sun's apogee ≈ 77.5° (fixed)
    """
    ep = MANDA_EPICYCLE.get(planet_key)
    if ep is None:
        return madhyama

    anomaly = (madhyama - apogee) % 360.0

    doh = (ep / 360.0) * _ss_sin(anomaly)
    correction_rad = math.asin(doh / SS_RADIUS)
    correction_deg = math.degrees(correction_rad)

    if 0 <= anomaly < 180:
        return (madhyama + correction_deg) % 360.0
    else:
        return (madhyama - correction_deg) % 360.0


def sighra_correction(planet_key: str, after_manda: float, sighroccha: float) -> float:
    """
    แก้ค่า sighra (synodic correction) สำหรับดาวเคราะห์ที่ต้องการ
    superior planets: mars, jupiter, saturn
    inferior planets: mercury, venus (ใช้ sighroccha โดยตรง)
    """
    ep = SIGHRA_EPICYCLE.get(planet_key)
    if ep is None:
        return after_manda

    anomaly = (sighroccha - after_manda) % 360.0

    doh = (ep / 360.0) * _ss_sin(anomaly)
    koti = (ep / 360.0) * _ss_sin(90 - anomaly)

    if 0 < anomaly < 90 or 270 < anomaly <= 360:
        sphuta_koti = SS_RADIUS + koti
    else:
        sphuta_koti = SS_RADIUS - koti

    karna = math.sqrt(doh ** 2 + sphuta_koti ** 2)
    correction_rad = math.asin(doh / karna)
    correction_deg = math.degrees(correction_rad)

    if 0 <= anomaly < 180:
        return (after_manda + correction_deg) % 360.0
    else:
        return (after_manda - correction_deg) % 360.0


# ---------------------------------------------------------------------------
# สมผุส (True longitude) per planet
# ---------------------------------------------------------------------------

# Sun's apogee (mandoccha) — nearly fixed ≈ 77.5° in modern epoch
# ค่าแท้คือ 77° + drift เล็กน้อย ใช้ค่า fixed ก่อน
SUN_APOGEE = 77.5


def sphuta(planet_id: int, t: int) -> float:
    """คำนวณ สมผุส longitude (°) สำหรับ planet_id ณ หรคุณ t"""
    if planet_id == 8:
        # ราหู: retrograde เท่านั้น ไม่มี equation of center
        return mean_longitude("rahu", t)

    if planet_id == 9:
        # เกตุ = ราหู + 180°
        return (sphuta(8, t) + 180.0) % 360.0

    key = PLANET_KEYS.get(planet_id)
    if key is None:
        raise ValueError(f"Unknown planet_id: {planet_id}")

    if planet_id == 1:
        # Sun: manda only
        mad = mean_longitude("sun", t)
        return manda_correction("sun", mad, SUN_APOGEE)

    if planet_id == 2:
        # Moon: manda only (sighra not applied to Moon in SS)
        apogee = mean_longitude("moon_apogee", t)
        mad = mean_longitude("moon", t)
        return manda_correction("moon", mad, apogee)

    # Superior planets: Mars(3), Jupiter(5), Saturn(7)
    # 4-pass: ½sighra → manda → manda again → full sighra
    if planet_id in (3, 5, 7):
        sun_true = sphuta(1, t)
        mad = mean_longitude(key, t)

        half_sig = sighra_correction(key, mad, sun_true)
        half_sig = ((mad + half_sig) / 2.0) % 360.0  # ½ correction

        after_manda = manda_correction(key, half_sig, SUN_APOGEE)
        after_manda2 = manda_correction(key, after_manda, SUN_APOGEE)
        return sighra_correction(key, after_manda2, sun_true)

    # Inferior planets: Mercury(4), Venus(6)
    # sighroccha IS the mean longitude for inferior planets
    if planet_id in (4, 6):
        sc_key = "mercury_sc" if planet_id == 4 else "venus_sc"
        sighroccha = mean_longitude(sc_key, t)
        sun_true = sphuta(1, t)

        after_manda = manda_correction(key, sun_true, sighroccha)
        return sighra_correction(key, after_manda, sighroccha)

    raise ValueError(f"No sphuta rule for planet_id: {planet_id}")


# ---------------------------------------------------------------------------
# Longitude → ราศี + องศา
# ---------------------------------------------------------------------------

def longitude_to_sign(lon: float) -> tuple[int, float]:
    """
    แปลง sidereal longitude (0–360°) → (sign_no 1–12, degree_in_sign 0–30°)
    sign 1 = เมษ starts at 0°
    """
    lon = lon % 360.0
    sign_no = int(lon / 30) + 1
    degree = lon % 30.0
    return sign_no, degree


# ---------------------------------------------------------------------------
# ลัคนา (Ascendant) — RAMC-based formula
# ---------------------------------------------------------------------------

# Obliquity of ecliptic (ค่าเฉลี่ย ณ J2000; drift น้อยมากในช่วง 200 ปี)
OBLIQUITY = 23.4393


def _gmst_degrees(jd: float) -> float:
    """Greenwich Mean Sidereal Time ณ Julian Day jd (°)."""
    JD_J2000 = 2451545.0
    d = jd - JD_J2000
    gmst = (280.46061837
            + 360.98564736629 * d
            + 0.000387933 * (d / 36525.0) ** 2) % 360.0
    return gmst


def lahiri_ayanamsa(jd: float) -> float:
    """
    Lahiri ayanamsa (°) — ใช้กับ sidereal Thai/Vedic astrology
    Reference epoch: Jan 1, 1900 = 22.46056°
    Precession: ~50.27"/year
    """
    JD_1900 = 2415020.0
    years = (jd - JD_1900) / 365.25
    return (22.46056 + years * 50.27 / 3600.0) % 360.0


def lagna(t: float, birth_hour: float, lat_deg: float, lon_deg: float,
          tz_hours: float = 7.0) -> float:
    """
    คำนวณ ลัคนา (Ascendant) สุริยยาตร์ ด้วย RAMC formula

    t         : หรคุณ (float, รวม fraction ของวันแล้ว)
    birth_hour: เวลาเกิด Local Standard Time (decimal hours)
    lat_deg   : ละติจูด (+ = เหนือ)
    lon_deg   : ลองจิจูด (+ = ตะวันออก)
    tz_hours  : UTC offset ของสถานที่เกิด (default 7.0 = ไทย UTC+7)

    Returns: sidereal longitude ของลัคนา (0–360°)
    """
    jd = CS_EPOCH_JD + t

    # GMST ณ เที่ยงคืน UT ของวันเกิด
    jd_midnight = math.floor(jd - 0.5) + 0.5
    gmst_midnight = _gmst_degrees(jd_midnight)

    # แปลง Local Standard Time → UT ด้วย timezone จริง (ไม่ใช่ lon/15)
    ut_hour = birth_hour - tz_hours

    # Local Mean Sidereal Time = GMST(UT) + geographic longitude
    last_deg = (gmst_midnight + ut_hour * 15.0 + lon_deg) % 360.0

    # Ascendant (tropical) จาก RAMC = LAST
    lat_r = math.radians(lat_deg)
    obl_r = math.radians(OBLIQUITY)
    ramc_r = math.radians(last_deg)

    y = -math.cos(ramc_r)
    x = math.sin(ramc_r) * math.cos(obl_r) + math.tan(lat_r) * math.sin(obl_r)
    asc_tropical = math.degrees(math.atan2(y, x)) % 360.0

    # Tropical → Sidereal (ลบ Lahiri ayanamsa)
    asc_sidereal = (asc_tropical - lahiri_ayanamsa(jd)) % 360.0
    return asc_sidereal


# ---------------------------------------------------------------------------
# Swiss Ephemeris planet calculation (แม่นยำ arc-second)
# ---------------------------------------------------------------------------

# แมป planet_id → swisseph planet constant
_SWE_IDS = {
    1: 0,   # Sun
    2: 1,   # Moon
    3: 4,   # Mars
    4: 2,   # Mercury
    5: 5,   # Jupiter
    6: 3,   # Venus
    7: 6,   # Saturn
    8: 10,  # Mean Node (Rahu)
    0: 7,   # Uranus
}


def _planets_swe(jd_ut: float, planet_ids):
    """
    คำนวณตำแหน่งดาวด้วย Swiss Ephemeris + Lahiri ayanamsa
    คืน dict: {planet_id: PlanetPosition}
    """
    import swisseph as swe
    swe.set_sid_mode(swe.SIDM_LAHIRI)
    FLAGS = swe.FLG_SIDEREAL | swe.FLG_SPEED

    result = {}
    for pid in planet_ids:
        if pid == 9:
            continue  # คำนวณเกตุจากราหูทีหลัง
        swe_id = _SWE_IDS.get(pid)
        if swe_id is None:
            continue
        ret, err = swe.calc_ut(jd_ut, swe_id, FLAGS)
        lon_deg = ret[0] % 360.0
        sign, deg = longitude_to_sign(lon_deg)
        result[pid] = PlanetPosition(planet_id=pid, longitude=lon_deg,
                                     sign_no=sign, degree_in_sign=deg)

    # เกตุ = ราหู + 180°
    if 9 in planet_ids and 8 in result:
        ketu_lon = (result[8].longitude + 180.0) % 360.0
        sign, deg = longitude_to_sign(ketu_lon)
        result[9] = PlanetPosition(planet_id=9, longitude=ketu_lon,
                                   sign_no=sign, degree_in_sign=deg)
    return result


# ---------------------------------------------------------------------------
# Main entry: คำนวณ chart ทั้งหมด
# ---------------------------------------------------------------------------

def compute_chart(
    birth_year: int,
    birth_month: int,
    birth_day: int,
    birth_hour: float,    # decimal hours (e.g. 14.5 = 14:30)
    lat: float,
    lon: float,
    planet_ids=None,  # list[int] | None
    tz_hours: float = 7.0,  # UTC offset; default 7 = ไทย (UTC+7)
    engine: str = "auto"   # "auto" | "swisseph" | "suriyayat"
) -> Chart:
    """
    รับ: วัน-เวลา-พิกัดเกิด (Gregorian, Local Standard Time)
    คืน: Chart object พร้อม PlanetPosition ของทุกดาว + ลัคนา

    engine:
      "auto"      — ใช้ swisseph ถ้ามี ไม่งั้นใช้ suriyayat
      "swisseph"  — Swiss Ephemeris (แม่นยำ, ต้องติดตั้ง pyswisseph)
      "suriyayat" — สุริยยาตร์ (ดั้งเดิม ±2–5°)
    """
    if planet_ids is None:
        planet_ids = [1, 2, 3, 4, 5, 6, 7, 8, 9]

    # ── เลือก engine
    use_swe = False
    if engine in ("auto", "swisseph"):
        try:
            import swisseph
            use_swe = True
        except ImportError:
            if engine == "swisseph":
                raise RuntimeError("pyswisseph ไม่ได้ติดตั้ง — pip install pyswisseph")

    # ── คำนวณดาว
    if use_swe:
        jd_ut = gregorian_to_jd(birth_year, birth_month, birth_day) + \
                (birth_hour - tz_hours) / 24.0
        result = _planets_swe(jd_ut, planet_ids)
    else:
        t = harakun(birth_year, birth_month, birth_day)
        t_frac = t + birth_hour / 24.0
        result = {}
        for pid in planet_ids:
            try:
                lon_deg = sphuta(pid, t_frac)
            except ValueError:
                continue
            sign, deg = longitude_to_sign(lon_deg)
            result[pid] = PlanetPosition(planet_id=pid, longitude=lon_deg,
                                         sign_no=sign, degree_in_sign=deg)

    # ── คำนวณลัคนา (วิธีดั้งเดิม: ราศีอาทิตย์ = ลัคนาตอนอาทิตย์ขึ้น, เดิน 2h/ราศี)
    sunrise_hour = 6.0
    sun_sign = result[1].sign_no
    hours_from_sunrise = birth_hour - sunrise_hour
    signs_elapsed = math.floor(hours_from_sunrise / 2.0)
    frac = (hours_from_sunrise / 2.0) - signs_elapsed
    lagna_sign_no = ((sun_sign - 1 + signs_elapsed) % 12) + 1
    lagna_deg_in_sign = frac * 30.0
    lagna_lon = ((lagna_sign_no - 1) * 30.0 + lagna_deg_in_sign) % 360.0
    lagna_sign, lagna_deg = longitude_to_sign(lagna_lon)
    lagna_pos = PlanetPosition(planet_id=0, longitude=lagna_lon,
                               sign_no=lagna_sign, degree_in_sign=lagna_deg)

    return Chart(lagna=lagna_pos, planets=result)


# ---------------------------------------------------------------------------
# House assignment (ภพ) นับจากลัคนา
# ---------------------------------------------------------------------------

def house_from_lagna(planet_sign: int, lagna_sign: int) -> int:
    return ((planet_sign - lagna_sign) % 12) + 1


# ---------------------------------------------------------------------------
# JD ↔ Gregorian helpers
# ---------------------------------------------------------------------------

def jd_to_greg(jd: float):
    """Julian Day → (year, month, day) Gregorian"""
    z = int(jd + 0.5)
    f = (jd + 0.5) - z
    if z < 2299161:
        a = z
    else:
        alpha = int((z - 1867216.25) / 36524.25)
        a = z + 1 + alpha - alpha // 4
    b = a + 1524
    c = int((b - 122.1) / 365.25)
    d = int(365.25 * c)
    e = int((b - d) / 30.6001)
    day = b - d - int(30.6001 * e)
    month = e - 1 if e < 14 else e - 13
    year = c - 4716 if month > 2 else c - 4715
    return year, month, day


def greg_to_thai_year(ce_year: int) -> int:
    return ce_year + 543


# ---------------------------------------------------------------------------
# มหาทศา — Vimshottari Dasha (120 ปี)
# ---------------------------------------------------------------------------

# เจ้าของนักษัตรทั้ง 27 (วนซ้ำ 3 รอบ × 9 ดาว)
# เกตุ=9, ศุกร์=6, อาทิตย์=1, จันทร์=2, อังคาร=3, ราหู=8, พฤหัส=5, เสาร์=7, พุธ=4
_NAK_LORDS = [9, 6, 1, 2, 3, 8, 5, 7, 4] * 3

# ระยะเวลาทศา (ปี Julian = 365.25 วัน)
_DASHA_YEARS = {1: 6, 2: 10, 3: 7, 4: 17, 5: 16, 6: 20, 7: 19, 8: 18, 9: 7}
_DASHA_ORDER = [9, 6, 1, 2, 3, 8, 5, 7, 4]
_DAYS_PER_YEAR = 365.25


def compute_dasha(moon_lon: float, birth_jd: float):
    """
    คำนวณมหาทศา Vimshottari จาก longitude จันทร์ (sidereal) และ JD วันเกิด
    คืน list ของ period dict — ครอบคลุม 120 ปีหลังเกิด
    """
    nak_size = 360.0 / 27
    nak_num = int(moon_lon / nak_size) % 27
    pos_in_nak = moon_lon % nak_size
    balance = 1.0 - pos_in_nak / nak_size

    lord = _NAK_LORDS[nak_num]
    start_idx = _DASHA_ORDER.index(lord)

    first_dur = balance * _DASHA_YEARS[lord] * _DAYS_PER_YEAR
    jd = birth_jd - first_dur  # ทศาแรกเริ่มก่อนวันเกิด

    periods = []
    for cycle in range(15):
        for step in range(9):
            idx = (start_idx + cycle * 9 + step) % 9
            planet = _DASHA_ORDER[idx]
            dur = first_dur if (cycle == 0 and step == 0) else _DASHA_YEARS[planet] * _DAYS_PER_YEAR
            end_jd = jd + dur
            y_start, m_start, _ = jd_to_greg(jd)
            y_end, m_end, _ = jd_to_greg(end_jd)
            periods.append({
                "planet_id": planet,
                "start_jd": jd,
                "end_jd": end_jd,
                "years": dur / _DAYS_PER_YEAR,
                "start_thai": greg_to_thai_year(y_start),
                "end_thai": greg_to_thai_year(y_end),
            })
            jd = end_jd
            if jd > birth_jd + 122 * _DAYS_PER_YEAR:
                return periods
    return periods


# ---------------------------------------------------------------------------
# ดาวเจ้าชะตา (Chart Ruler)
# ---------------------------------------------------------------------------

_SIGN_RULERS = {
    1: 3, 2: 6, 3: 4, 4: 2, 5: 1, 6: 4,
    7: 6, 8: 3, 9: 5, 10: 7, 11: 7, 12: 5,
}

def get_chart_ruler(lagna_sign: int) -> int:
    """คืน planet_id ของดาวเจ้าชะตา (เจ้าของราศีลัคนา)"""
    return _SIGN_RULERS.get(lagna_sign, 1)


# ---------------------------------------------------------------------------
# โยค (Yoga) — การรวมดาวพิเศษ
# ---------------------------------------------------------------------------

def compute_yogas(planets: dict, lagna_sign: int):
    """
    ตรวจหาโยคสำคัญ คืน list[dict] ของโยคที่พบ
    planets: {planet_id: PlanetPosition}
    """
    yogas = []

    def house(sign):
        return ((sign - lagna_sign) % 12) + 1

    def is_kendra(sign):
        return house(sign) in (1, 4, 7, 10)

    def is_trikona(sign):
        return house(sign) in (1, 5, 9)

    # ── กาลสรปโยค: ดาวทั้งหมดอยู่ระหว่าง ราหู–เกตุ (ฝั่งเดียว)
    rahu_lon = planets.get(8, None)
    ketu_lon = planets.get(9, None)
    if rahu_lon and ketu_lon:
        r, k = rahu_lon.longitude, ketu_lon.longitude
        classic = [planets[p].longitude for p in [1,2,3,4,5,6,7] if p in planets]
        if classic:
            # ตรวจว่าดาวทุกดวงอยู่ในส่วนโค้ง r→k (ตามเข็ม) หรือ k→r
            def arc_contains(start, end, point):
                if start <= end:
                    return start <= point <= end
                return point >= start or point <= end
            arc_rk = [(r - k) % 360]
            side1 = all(arc_contains(k, r, lon) for lon in classic)
            side2 = all(arc_contains(r, k, lon) for lon in classic)
            if side1 or side2:
                yogas.append({
                    "name": "กาลสรปโยค",
                    "name_en": "Kala Sarpa Yoga",
                    "desc": "ดาวทั้งหมดอยู่ระหว่างราหู–เกตุ มีพลังอำนาจและความสำเร็จสูง แต่ชีวิตมีความท้าทายพิเศษ",
                    "planets": [8, 9],
                    "level": "warning",
                })

    # ── ปัญจมหาปุรุษโยค: ดาวในเกษตร/อุจจ อยู่ใน kendra
    mahapurusha = [
        (3, {1,8}, 10, "รุจกโยค", "อังคารในอุจจ/เกษตรใน kendra — ความกล้า ผู้นำ"),
        (4, {3,6}, 6,  "ภัทรโยค", "พุธในอุจจ/เกษตรใน kendra — ปัญญา ธุรกิจ วาทศิลป์"),
        (5, {9,12},4,  "หังสโยค", "พฤหัสในอุจจ/เกษตรใน kendra — ปัญญา ศาสนา โชคลาภ"),
        (6, {2,7}, 12, "มาลวยโยค","ศุกร์ในอุจจ/เกษตรใน kendra — ความงาม ความรัก ความสุข"),
        (7, {10,11},7, "สาศโยค",  "เสาร์ในอุจจ/เกษตรใน kendra — ความพากเพียร อายุยืน"),
    ]
    for pid, own_signs, ucca_sign, name, desc in mahapurusha:
        p = planets.get(pid)
        if p and is_kendra(p.sign_no) and (p.sign_no in own_signs or p.sign_no == ucca_sign):
            yogas.append({
                "name": name,
                "name_en": "",
                "desc": desc,
                "planets": [pid],
                "level": "good",
            })

    # ── คชเกสริโยค: พฤหัส–จันทร์ ใน kendra ต่อกัน
    moon = planets.get(2)
    jup  = planets.get(5)
    if moon and jup:
        diff = abs(house(jup.sign_no) - house(moon.sign_no))
        if diff in (0, 3, 6, 9):
            yogas.append({
                "name": "คชเกสริโยค",
                "name_en": "Gajakesari Yoga",
                "desc": "พฤหัสบดีใน kendra จากจันทร์ — ชื่อเสียง ปัญญา ความมั่งคั่ง",
                "planets": [2, 5],
                "level": "good",
            })

    # ── ราชโยค: เจ้าตรีโกณ + เจ้า kendra ร่วมราศี
    trikona_lords = {_SIGN_RULERS[((lagna_sign - 1 + (h-1)) % 12) + 1]
                     for h in (1, 5, 9)}
    kendra_lords  = {_SIGN_RULERS[((lagna_sign - 1 + (h-1)) % 12) + 1]
                     for h in (4, 7, 10)}
    raja_planets = trikona_lords & kendra_lords
    if not raja_planets:
        # ดูจากตำแหน่งดาว: เจ้า trikona อยู่ใน kendra หรือกลับกัน
        for pid, p in planets.items():
            if pid in (8, 9): continue
            if _SIGN_RULERS.get(p.sign_no) == pid:  # อยู่บ้านตัวเอง
                if is_kendra(p.sign_no) and pid in trikona_lords:
                    raja_planets.add(pid)
    if raja_planets:
        yogas.append({
            "name": "ราชโยค",
            "name_en": "Raja Yoga",
            "desc": "เจ้าราศีตรีโกณและ kendra รวมกัน — ยศถาบรรดาศักดิ์ ความสำเร็จ",
            "planets": list(raja_planets),
            "level": "good",
        })

    # ── ธนโยค: เจ้าภพ 2 และเจ้าภพ 11 ร่วมราศี หรืออยู่ใน 2/11
    h2_sign = ((lagna_sign - 1 + 1) % 12) + 1
    h11_sign = ((lagna_sign - 1 + 10) % 12) + 1
    lord2  = _SIGN_RULERS[h2_sign]
    lord11 = _SIGN_RULERS[h11_sign]
    p2  = planets.get(lord2)
    p11 = planets.get(lord11)
    if p2 and p11 and p2.sign_no == p11.sign_no:
        yogas.append({
            "name": "ธนโยค",
            "name_en": "Dhana Yoga",
            "desc": "เจ้าภพ 2 และเจ้าภพ 11 ร่วมราศี — โชคลาภ รายได้ ทรัพย์สินงอกเงย",
            "planets": [lord2, lord11],
            "level": "good",
        })

    return yogas


# ---------------------------------------------------------------------------
# Quick test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # ตัวอย่าง: วันเกิดสมมติ 1 มกราคม 2533 (1990) เวลา 10:00 กรุงเทพฯ (13.75°N, 100.5°E)
    chart = compute_chart(1990, 1, 1, 10.0, lat=13.75, lon=100.5)

    planet_names = {1:"อาทิตย์",2:"จันทร์",3:"อังคาร",4:"พุธ",5:"พฤหัสบดี",
                    6:"ศุกร์",7:"เสาร์",8:"ราหู",9:"เกตุ"}
    sign_names = ["","เมษ","พฤษภ","เมถุน","กรกฎ","สิงห์","กันย์",
                  "ตุล","พิจิก","ธนู","มังกร","กุมภ์","มีน"]

    print(f"ลัคนา: ราศี{sign_names[chart.lagna.sign_no]} {chart.lagna.degree_in_sign:.2f}°")
    for pid, pos in sorted(chart.planets.items()):
        house = house_from_lagna(pos.sign_no, chart.lagna.sign_no)
        print(f"  {planet_names.get(pid,'?'):10s}  ราศี{sign_names[pos.sign_no]:5s}"
              f"  {pos.degree_in_sign:5.2f}°  ภพ{house:2d}")
