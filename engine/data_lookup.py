"""
Data Lookup — bridge ระหว่าง Engine กับ Data layer

โหลด JSON ทุกไฟล์ครั้งเดียวตอน import แล้ว cache ไว้
ฟังก์ชันหลัก:
  get_positions(planet_id, sign_no)         → list[str]  ตำแหน่งดาว
  get_house(planet_sign, lagna_sign)        → int        ภพที่
  get_interp_planet_house(planet, house)    → dict       คำทำนาย
  get_interp_planet_position(planet, pos)   → dict       คำทำนาย
  get_interp_planet_sign(planet, sign)      → dict       คำทำนาย
  annotate_chart(chart, tradition)          → dict       ข้อมูลครบชุด
"""

import json
import os

_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


def _load(filename: str) -> list:
    path = os.path.join(_DATA_DIR, filename)
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    # strip _comment entries
    return [r for r in raw if not any(k.startswith("_") for k in r)]


# ---------------------------------------------------------------------------
# One-time load at module import
# ---------------------------------------------------------------------------

_PLANETS          = {p["id"]: p for p in _load("planets.json")}
_SIGNS            = {s["no"]: s for s in _load("signs.json")}
_HOUSES           = {h["no"]: h for h in _load("houses.json")}
_UCHA_NICHA       = {u["planet"]: u for u in _load("ucha_nicha.json")}
_POSITION_RANKS   = {r["key"]: r for r in _load("position_ranks.json")}

# Build position lookup: (planet, sign) → [position_key, ...]
_PSP_RAW = _load("planet_sign_positions.json")
_PSP = {}
for row in _PSP_RAW:
    key = (row["planet"], row["sign"])
    _PSP.setdefault(key, [])
    _PSP[key].append(row["position"])

# Interpretations (optional files — return empty dict if missing)
def _load_interp(filename: str) -> dict:
    try:
        rows = _load(filename)
    except FileNotFoundError:
        return {}
    out = {}
    for r in rows:
        tradition = r.get("tradition", "มาตรฐาน")
        out[(r.get("planet"), r.get("sign"), r.get("house_no"),
             r.get("position"), tradition)] = r
    return out


_INTERP_PLANET_HOUSE     = _load_interp("interpretations_planet_house.json")
_INTERP_PLANET_SIGN      = _load_interp("interpretations_planet_sign.json")
_INTERP_PLANET_POSITION  = _load_interp("interpretations_planet_position.json")


# ---------------------------------------------------------------------------
# Public lookup functions
# ---------------------------------------------------------------------------

def get_planet(planet_id: int) -> dict:
    return _PLANETS.get(planet_id, {})


def get_sign(sign_no: int) -> dict:
    return _SIGNS.get(sign_no, {})


def get_house_info(house_no: int) -> dict:
    return _HOUSES.get(house_no, {})


def get_positions(planet_id: int, sign_no: int) -> list:
    """คืน list ของ position keys ที่ดาวนี้มีในราศีนี้ เช่น ['เกษตร', 'มหาจักร']"""
    return _PSP.get((planet_id, sign_no), [])


def get_position_rank(position_key: str) -> int:
    """คืน rank ของตำแหน่ง (1 = แกร่งสุด, 10 = อ่อนสุด)"""
    return _POSITION_RANKS.get(position_key, {}).get("rank", 99)


def get_best_position(planet_id: int, sign_no: int) -> str:
    """คืน position ที่แกร่งที่สุด (rank ต่ำสุด) สำหรับ planet×sign นี้"""
    positions = get_positions(planet_id, sign_no)
    if not positions:
        return ""
    return min(positions, key=lambda p: get_position_rank(p))


def get_house(planet_sign: int, lagna_sign: int) -> int:
    """ภพที่ของดาว นับจาก lagna_sign เป็นภพ 1"""
    return ((planet_sign - lagna_sign) % 12) + 1


def get_interp_planet_house(
    planet_id: int,
    house_no: int,
    tradition: str = "มาตรฐาน"
) -> dict:
    """คืน interpretation dict สำหรับ planet อยู่ใน house"""
    key = (planet_id, None, house_no, None, tradition)
    return _INTERP_PLANET_HOUSE.get(key, {})


def get_interp_planet_sign(
    planet_id: int,
    sign_no: int,
    tradition: str = "มาตรฐาน"
) -> dict:
    """คืน interpretation dict สำหรับ planet อยู่ใน sign"""
    key = (planet_id, sign_no, None, None, tradition)
    return _INTERP_PLANET_SIGN.get(key, {})


def get_interp_planet_position(
    planet_id: int,
    position_key: str,
    tradition: str = "มาตรฐาน"
) -> dict:
    """คืน interpretation dict สำหรับ planet มีตำแหน่งนี้"""
    key = (planet_id, None, None, position_key, tradition)
    return _INTERP_PLANET_POSITION.get(key, {})


# ---------------------------------------------------------------------------
# Annotate chart: เพิ่ม positions, house_no, interpretation เข้าไปใน chart
# ---------------------------------------------------------------------------

def annotate_chart(chart, tradition: str = "มาตรฐาน") -> dict:
    """
    รับ Chart object จาก suriyayat.compute_chart()
    คืน dict ที่พร้อมใช้ใน API / UI:
    {
      "lagna": {...},
      "planets": [
        {
          "planet_id": 1,
          "planet_th": "อาทิตย์",
          "sign_no": 9,
          "sign_th": "ธนู",
          "degree": 16.63,
          "house_no": 5,
          "house_th": "ปุตตะ",
          "positions": ["..."],
          "best_position": "...",
          "interp_house": {...},
          "interp_position": {...},
        },
        ...
      ]
    }
    """
    lagna_sign = chart.lagna.sign_no
    lagna_info = get_sign(lagna_sign)

    planets_out = []
    for pid, pos in sorted(chart.planets.items()):
        planet_info   = get_planet(pid)
        sign_info     = get_sign(pos.sign_no)
        house_no      = get_house(pos.sign_no, lagna_sign)
        house_info    = get_house_info(house_no)
        positions     = get_positions(pid, pos.sign_no)
        best_pos      = get_best_position(pid, pos.sign_no)

        interp_house  = get_interp_planet_house(pid, house_no, tradition)
        interp_pos    = (get_interp_planet_position(pid, best_pos, tradition)
                         if best_pos else {})
        interp_sign   = get_interp_planet_sign(pid, pos.sign_no, tradition)

        planets_out.append({
            "planet_id":      pid,
            "planet_th":      planet_info.get("th", ""),
            "sign_no":        pos.sign_no,
            "sign_th":        sign_info.get("th", ""),
            "degree":         round(pos.degree_in_sign, 2),
            "longitude":      round(pos.longitude, 4),
            "house_no":       house_no,
            "house_th":       house_info.get("th", ""),
            "house_meaning":  house_info.get("meaning", ""),
            "positions":      positions,
            "best_position":  best_pos,
            "interp_house":   {
                "short": interp_house.get("text_short", ""),
                "full":  interp_house.get("text_full", ""),
            },
            "interp_position": {
                "short": interp_pos.get("text_short", ""),
                "full":  interp_pos.get("text_full", ""),
            },
            "interp_sign": {
                "short": interp_sign.get("text_short", ""),
                "full":  interp_sign.get("text_full", ""),
            },
        })

    return {
        "lagna": {
            "sign_no":   lagna_sign,
            "sign_th":   lagna_info.get("th", ""),
            "degree":    round(chart.lagna.degree_in_sign, 2),
            "element":   lagna_info.get("element", ""),
            "ruler":     lagna_info.get("ruler"),
        },
        "planets": planets_out,
    }


# ---------------------------------------------------------------------------
# Optional: Uranus via pyswisseph
# ---------------------------------------------------------------------------

def get_uranus_position(jd: float, ayanamsa_deg: float = 24.0):
    """
    คำนวณตำแหน่งมฤตยู (Uranus) ด้วย pyswisseph
    คืน (sign_no, degree_in_sign) หรือ None ถ้าไม่มี pyswisseph
    """
    try:
        import swisseph as swe
        swe.set_sid_mode(swe.SIDM_LAHIRI)
        xx, _ = swe.calc_ut(jd, swe.URANUS, swe.FLG_SIDEREAL)
        lon = xx[0] % 360.0
        sign_no = int(lon / 30) + 1
        degree  = lon % 30.0
        return sign_no, degree
    except ImportError:
        return None
