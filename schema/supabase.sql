-- ============================================================
-- Thai Astrology — Supabase Schema
-- 3 layers: Reference (seed once) / Chart (per reading) / Content
-- ============================================================

-- ------------------------------------------------------------
-- LAYER 1: Reference tables (seed once, read-only in app)
-- ------------------------------------------------------------

CREATE TABLE planets (
  id         smallint PRIMARY KEY,
  th         text NOT NULL,
  en         text NOT NULL,
  swe_id     smallint,           -- Swiss Ephemeris body ID (null สำหรับ Ketu)
  note       text
);

CREATE TABLE signs (
  no         smallint PRIMARY KEY CHECK (no BETWEEN 1 AND 12),
  th         text NOT NULL,
  en         text NOT NULL,
  element    text NOT NULL,
  ruler      smallint REFERENCES planets(id),
  co_ruler   smallint REFERENCES planets(id)  -- e.g. Rahu co-rules Aquarius
);

CREATE TABLE houses (
  no         smallint PRIMARY KEY CHECK (no BETWEEN 1 AND 12),
  th         text NOT NULL,
  en         text NOT NULL,
  meaning    text
);

CREATE TABLE ucha_nicha (
  planet     smallint REFERENCES planets(id),
  ucha_sign  smallint REFERENCES signs(no),
  ucha_deg   smallint,
  nicha_sign smallint REFERENCES signs(no),
  nicha_deg  smallint,
  note       text,
  PRIMARY KEY (planet)
);

-- ตาราง planet × sign → ตำแหน่ง (1 planet+sign อาจมีหลาย position)
CREATE TABLE planet_sign_positions (
  planet      smallint REFERENCES planets(id),
  sign        smallint REFERENCES signs(no),
  position    text NOT NULL,             -- เกษตร / ราชาโชค / อุจจาวิลาส / ...
  note        text,
  PRIMARY KEY (planet, sign, position)
);

-- ลำดับความแกร่งของตำแหน่ง
CREATE TABLE position_ranks (
  position   text PRIMARY KEY,
  rank       smallint NOT NULL,          -- 1 = แกร่งที่สุด (อุจจ)
  label_th   text,
  label_en   text,
  strength   text,
  note       text
);

-- ------------------------------------------------------------
-- LAYER 2: Chart data (per reading)
-- ------------------------------------------------------------

CREATE TABLE charts (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id      uuid REFERENCES auth.users ON DELETE CASCADE,
  name         text,                  -- ชื่อเจ้าชะตา
  birth_date   date NOT NULL,
  birth_time   time,
  birth_lat    double precision,
  birth_lon    double precision,
  birth_place  text,
  engine       text NOT NULL DEFAULT 'suriyayat',
  created_at   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE chart_planets (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  chart_id     uuid NOT NULL REFERENCES charts(id) ON DELETE CASCADE,
  planet_id    smallint NOT NULL REFERENCES planets(id),
  longitude    double precision NOT NULL,   -- 0–360° sidereal
  sign_no      smallint NOT NULL REFERENCES signs(no),
  degree_in_sign double precision NOT NULL, -- 0–30°
  house_no     smallint,                   -- ภพนับจากลัคนา (null ถ้า is_lagna)
  is_lagna     boolean DEFAULT false,
  retrograde   boolean DEFAULT false,
  UNIQUE (chart_id, planet_id)
);

-- ตำแหน่งดาวที่คำนวณได้สำหรับแต่ละดาวในชาร์ต (derived)
CREATE TABLE chart_planet_positions (
  chart_id    uuid REFERENCES charts(id) ON DELETE CASCADE,
  planet_id   smallint REFERENCES planets(id),
  position    text REFERENCES position_ranks(position),
  PRIMARY KEY (chart_id, planet_id, position)
);

-- ------------------------------------------------------------
-- LAYER 3: Content (คำทำนาย)
-- ------------------------------------------------------------

-- คำทำนาย: ดาว × ตำแหน่ง → ข้อความ
CREATE TABLE interpretations_planet_position (
  planet      smallint REFERENCES planets(id),
  position    text REFERENCES position_ranks(position),
  tradition   text NOT NULL DEFAULT 'default',  -- ระบุสำนัก/ตำรา
  text_short  text,   -- 1–2 ประโยค (ใช้ใน UI สรุป)
  text_full   text,   -- คำทำนายเต็ม
  PRIMARY KEY (planet, position, tradition)
);

-- คำทำนาย: ดาว × ราศี → ข้อความ
CREATE TABLE interpretations_planet_sign (
  planet      smallint REFERENCES planets(id),
  sign        smallint REFERENCES signs(no),
  tradition   text NOT NULL DEFAULT 'default',
  text_short  text,
  text_full   text,
  PRIMARY KEY (planet, sign, tradition)
);

-- คำทำนาย: ดาว × ภพ → ข้อความ
CREATE TABLE interpretations_planet_house (
  planet      smallint REFERENCES planets(id),
  house_no    smallint CHECK (house_no BETWEEN 1 AND 12),
  tradition   text NOT NULL DEFAULT 'default',
  text_short  text,
  text_full   text,
  PRIMARY KEY (planet, house_no, tradition)
);

-- ------------------------------------------------------------
-- Indexes
-- ------------------------------------------------------------

CREATE INDEX ON chart_planets (chart_id);
CREATE INDEX ON chart_planet_positions (chart_id);
CREATE INDEX ON interpretations_planet_sign (planet, sign);
CREATE INDEX ON interpretations_planet_house (planet, house_no);

-- ------------------------------------------------------------
-- RLS (Row Level Security) — เปิดใช้กับ auth.users
-- ------------------------------------------------------------

ALTER TABLE charts ENABLE ROW LEVEL SECURITY;
ALTER TABLE chart_planets ENABLE ROW LEVEL SECURITY;
ALTER TABLE chart_planet_positions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "users see own charts"
  ON charts FOR ALL
  USING (auth.uid() = user_id);

CREATE POLICY "users see own chart_planets"
  ON chart_planets FOR ALL
  USING (chart_id IN (SELECT id FROM charts WHERE user_id = auth.uid()));

CREATE POLICY "users see own positions"
  ON chart_planet_positions FOR ALL
  USING (chart_id IN (SELECT id FROM charts WHERE user_id = auth.uid()));

-- Reference tables: อ่านได้ทุกคน
CREATE POLICY "public read planets"      ON planets      FOR SELECT USING (true);
CREATE POLICY "public read signs"        ON signs        FOR SELECT USING (true);
CREATE POLICY "public read houses"       ON houses       FOR SELECT USING (true);
CREATE POLICY "public read pos_ranks"    ON position_ranks FOR SELECT USING (true);
CREATE POLICY "public read psp"          ON planet_sign_positions FOR SELECT USING (true);
CREATE POLICY "public read interp_ps"    ON interpretations_planet_sign FOR SELECT USING (true);
CREATE POLICY "public read interp_ph"    ON interpretations_planet_house FOR SELECT USING (true);
CREATE POLICY "public read interp_pp"    ON interpretations_planet_position FOR SELECT USING (true);
