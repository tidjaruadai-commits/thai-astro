import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from flask import Flask, render_template, request, jsonify
from engine.suriyayat import (
    compute_chart, gregorian_to_jd,
    compute_dasha, compute_yogas, get_chart_ruler,
)
from engine.data_lookup import annotate_chart

app = Flask(__name__)

SIGN_NAMES = ["","เมษ","พฤษภ","เมถุน","กรกฎ","สิงห์","กันย์",
              "ตุล","พิจิก","ธนู","มังกร","กุมภ์","มีน"]

PLANET_TH = {
    1:"อาทิตย์",2:"จันทร์",3:"อังคาร",4:"พุธ",5:"พฤหัส",
    6:"ศุกร์",7:"เสาร์",8:"ราหู",9:"เกตุ"
}
PLANET_SYM = {1:"☉",2:"☽",3:"♂",4:"☿",5:"♃",6:"♀",7:"♄",8:"ร",9:"ก"}

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/chart", methods=["POST"])
def api_chart():
    d = request.json
    try:
        year  = int(d["year"])
        month = int(d["month"])
        day   = int(d["day"])
        hour  = float(d["hour"]) + float(d.get("minute", 0)) / 60
        lat   = float(d.get("lat", 13.75))
        lon   = float(d.get("lon", 100.5))
        tz    = float(d.get("tz", 7.0))
    except (KeyError, ValueError) as e:
        return jsonify({"error": str(e)}), 400

    chart  = compute_chart(year, month, day, hour, lat, lon, tz_hours=tz)
    result = annotate_chart(chart)

    # ── sign map สำหรับตาราง
    sign_map = {i: [] for i in range(1, 13)}
    for p in result["planets"]:
        sign_map[p["sign_no"]].append(p)
    lagna_sign = result["lagna"]["sign_no"]
    sign_house = {s: ((s - lagna_sign) % 12) + 1 for s in range(1, 13)}
    result["sign_map"] = {
        str(s): {
            "planets": sign_map[s],
            "house_no": sign_house[s],
            "is_lagna": (s == lagna_sign),
            "sign_th": SIGN_NAMES[s],
        }
        for s in range(1, 13)
    }

    # ── ดาวเจ้าชะตา
    ruler_id = get_chart_ruler(lagna_sign)
    result["chart_ruler"] = {
        "planet_id": ruler_id,
        "planet_th": PLANET_TH.get(ruler_id, ""),
        "symbol": PLANET_SYM.get(ruler_id, ""),
    }

    # ── โยค
    yogas = compute_yogas(chart.planets, lagna_sign)
    for y in yogas:
        y["planets_th"] = [PLANET_TH.get(p,"") for p in y["planets"]]
    result["yogas"] = yogas

    # ── มหาทศา
    birth_jd = gregorian_to_jd(year, month, day) + (hour - tz) / 24.0
    moon = chart.planets.get(2)
    if moon:
        periods = compute_dasha(moon.longitude, birth_jd)
        import time as _time
        today_jd = gregorian_to_jd(2026, 6, 20)  # วันนี้
        current_idx = next(
            (i for i, p in enumerate(periods)
             if p["start_jd"] <= today_jd < p["end_jd"]), None
        )
        for i, p in enumerate(periods):
            p["is_current"] = (i == current_idx)
            p["planet_th"] = PLANET_TH.get(p["planet_id"], "")
            p["symbol"] = PLANET_SYM.get(p["planet_id"], "")
            del p["start_jd"], p["end_jd"]  # ไม่ส่ง JD ดิบ
        result["dasha"] = {
            "periods": periods,
            "current_idx": current_idx,
        }

    # ── ดาวย้าย (Transits วันนี้)
    birth_moon_sign = moon.sign_no if moon else lagna_sign
    today_chart = compute_chart(2026, 6, 20, 12.0, lat, lon, tz_hours=tz)
    transit_planets = []
    for pid, tpos in sorted(today_chart.planets.items()):
        house_from_lagna = ((tpos.sign_no - lagna_sign) % 12) + 1
        house_from_moon  = ((tpos.sign_no - birth_moon_sign) % 12) + 1
        tags = []
        if pid == 7 and house_from_moon in [12, 1, 2]:
            tags.append("เสาร์คร่อมจันทร์")
        if pid == 5 and house_from_moon in [1, 5, 9, 11]:
            tags.append("พฤหัสเมตตา")
        if pid == 8 and birth_moon_sign == tpos.sign_no:
            tags.append("ราหูคร่อมจันทร์")
        if pid == 9 and birth_moon_sign == tpos.sign_no:
            tags.append("เกตุคร่อมจันทร์")
        transit_planets.append({
            "planet_id":        pid,
            "planet_th":        PLANET_TH.get(pid, ""),
            "symbol":           PLANET_SYM.get(pid, ""),
            "sign_no":          tpos.sign_no,
            "sign_th":          SIGN_NAMES[tpos.sign_no],
            "degree":           round(tpos.degree_in_sign, 2),
            "house_from_lagna": house_from_lagna,
            "house_from_moon":  house_from_moon,
            "tags":             tags,
        })
    result["transits"] = {
        "date": "20 มิ.ย. 2569",
        "planets": transit_planets,
    }

    return jsonify(result)

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5050))
    app.run(host="0.0.0.0", port=port, debug=False)
