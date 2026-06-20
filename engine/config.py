"""
Thai Astrology — Tradition Configuration

เก็บ flag ที่ขึ้นกับสำนัก/ตำรา แยกออกมาจาก Engine
เปลี่ยนค่าที่นี่โดยไม่ต้องแตะโค้ด Engine
"""

# ---------------------------------------------------------------------------
# Rahu / Ketu tradition
# ---------------------------------------------------------------------------

# ราหู เกษตร (own sign)
# "aquarius"  = กุมภ์  (นิยมในไทย/อินเดียสายเหนือ)
# "gemini"    = เมถุน  (บางสำนักไทย)
RAHU_KSHETRA = "aquarius"

# ราหู อุจจ (exaltation)
# "scorpio"  = พิจิก (นิยม)
# "taurus"   = พฤษภ
# "gemini"   = เมถุน
RAHU_UCHA = "scorpio"

# ราหู นิจ (debilitation) = ตรงข้ามกับ อุจจ
# "taurus"      (if RAHU_UCHA = scorpio)
# "sagittarius" (if RAHU_UCHA = gemini)
RAHU_NICHA = "taurus"

# ---------------------------------------------------------------------------
# Saturn co-ruler of Aquarius
# ---------------------------------------------------------------------------

# True  = ราหูเป็น co-ruler ของกุมภ์ด้วย (สำนักที่ใช้ outer planets)
# False = เสาร์เท่านั้นที่ปกครองกุมภ์
RAHU_CO_RULES_AQUARIUS = True

# ---------------------------------------------------------------------------
# Lagna calculation method
# ---------------------------------------------------------------------------

# "ramc"       = RAMC-based (Lahiri ayanamsa) — default, แม่นยำกว่า
# "suriyayat"  = Classical rising-time table จากสุริยยาตร์ (ต้องใส่ตาราง OA)
LAGNA_METHOD = "ramc"

# Ayanamsa to use when LAGNA_METHOD = "ramc"
# "lahiri" = Lahiri (IAU 1974 recommendation)
# "krishnamurti" = KP system
AYANAMSA = "lahiri"

# ---------------------------------------------------------------------------
# Uranus (มฤตยู) support
# ---------------------------------------------------------------------------

# True  = พยายาม import pyswisseph และคำนวณ Uranus
# False = ข้ามดาวมฤตยู (ไม่มี error)
INCLUDE_URANUS = True

# ---------------------------------------------------------------------------
# Position classification
# ---------------------------------------------------------------------------

# True  = รวม อุจจาวิลาส / อุจจาภิมุข ใน position list
# False = แสดงเฉพาะ เกษตร / อุจจ / นิจ / ราชาโชค / มหาจักร / ประเกษตร / เทวีโชค
INCLUDE_UCHA_TRANSITIONS = True
