"""Put the farm pack's design into a running Inspector Studio through its API (every part is checked by Inspector
when it is saved), in English or Traditional Chinese.

    python pack/build.py --lang en    --url http://127.0.0.1:8769 --design <the pack's design folder>
    python pack/build.py --lang zh-TW --url http://127.0.0.1:8770 --design <...>

What it makes (the ids are the same in both languages; only the words differ):
  sources       GH-CAM and COOP-CAM: the simulator's two camera streams (project.json "sources")
  states        pack/states.json - ten states, all judged by screen rules (no training needed), each for its own
                camera ("sources": GH-CAM or COOP-CAM); the references they need (the vents, the door, the
                thermometer's digits) come from pack/refs/
  output        "farm": the simulator's equipment (HTTP POST to its /api/command)
  settings      vents_open_above / vents_close_below: the greenhouse temperatures (the farmer sets them)
  variable      eggs_told: the farmer has been told about the eggs
  sub-scripts   one per piece of equipment (the panel's buttons use them)
  main scripts  Greenhouse keeper (GH-CAM only): too hot -> vents open, cooled down -> vents closed, a dry bed ->
                water that bed. Hen house keeper (COOP-CAM only): a fox -> the alarm; night and every hen in ->
                shut the door; day -> open it; eggs waiting -> tell the farmer once.
  panel         the farmer's page: both cameras and how they are, the greenhouse's buttons on the greenhouse
                camera's row only and the hen house's on its own, the temperatures, notifications"""
import argparse
import json
import os
import shutil
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
SIM = "http://127.0.0.1:8810"
GH, COOP = "GH-CAM", "COOP-CAM"

T = {
    "en": {
        "project": ("Small farm", "A greenhouse and a hen house, one camera each: roof vents, sprinklers, the hen house door and a fox alarm driven through an HTTP output.",
                    {"device": "camera", "item": "item"}),
        "states": {"temperature": ("Greenhouse temperature", "The red digits on the wall display, in °C.", {}, "Thermometer digits"),
                   "vents": ("Roof vents", "Open: the glass pane is lifted on its arm and a dark gap shows. Closed: the pane lies flat.", {"open": "Open", "closed": "Closed", "hidden": "Other camera"}, "Left roof vent"),
                   "bed1_dry": ("Bed 1 dry", "Pale, dry soil showing between the plants of bed 1.", {"dry": "Dry", "ok": "Fine", "hidden": "Other camera"}, "Bed 1 soil"),
                   "bed2_dry": ("Bed 2 dry", "Pale, dry soil showing between the plants of bed 2.", {"dry": "Dry", "ok": "Fine", "hidden": "Other camera"}, "Bed 2 soil"),
                   "bed3_dry": ("Bed 3 dry", "Pale, dry soil showing between the plants of bed 3.", {"dry": "Dry", "ok": "Fine", "hidden": "Other camera"}, "Bed 3 soil"),
                   "daylight": ("Day or night", "How bright the sky above the hills is.", {"day": "Day", "night": "Night", "hidden": "Other camera"}, "Sky"),
                   "door": ("Hen house door", "Open: the dark inside and the door swung back. Shut: planks with a Z brace.", {"open": "Open", "closed": "Shut", "hidden": "Other camera"}, "Door"),
                   "hens_out": ("Hens outside", "White hens anywhere in the fenced run or waiting at the door (by night too: the lamp lights the run a little).", {"yes": "Yes", "no": "No", "hidden": "Other camera"}, "The run"),
                   "eggs": ("Eggs to collect", "Pale eggs on the straw in the three nest boxes: 'time to collect' from four eggs.", {"many": "Time to collect", "few": "Not yet", "hidden": "Other camera"}, "Nest boxes"),
                   "fox": ("Fox", "An orange fox outside the fence on the right.", {"yes": "There", "no": "None", "hidden": "Other camera"}, "Outside the fence (right)")},
        "output": "Farm equipment",
        "cameras": {GH: "Greenhouse camera", COOP: "Hen house camera"},
        "settings": {"vents_open_above": ("Open the vents above", "The roof vents open when the greenhouse stays warmer than this (°C)."),
                     "vents_close_below": ("Close the vents below", "The roof vents close when it has cooled down below this (°C).")},
        "var": "Told about the eggs",
        "subs": {"vents_open": ("Open the roof vents", "Roof vents opened"), "vents_close": ("Close the roof vents", "Roof vents closed"),
                 "water_1": ("Water bed 1", "Watered bed 1"), "water_2": ("Water bed 2", "Watered bed 2"), "water_3": ("Water bed 3", "Watered bed 3"),
                 "door_open": ("Open the hen house door", "Hen house door opened"), "door_close": ("Shut the hen house door", "Hen house door shut"),
                 "sound_alarm": ("Sound the fox alarm", "Fox alarm sounded")},
        "sub_desc": 'Sends "{cmd}" to the farm equipment.',
        "greenhouse": ("Greenhouse keeper", "Keeps the greenhouse right: the temperature with the roof vents, each bed watered when it dries out.", "Watching the greenhouse", "Nothing to do"),
        "henhouse": ("Hen house keeper", "Keeps the hens safe: the door by day and night, the fox alarm, and the eggs.", "Watching the hen house", "Nothing to do"),
        "rules": {"too_hot": ("Too hot: open the vents", "The greenhouse is too hot ({temperature} °C): roof vents opened"),
                  "cooled": ("Cooled down: close the vents", "The greenhouse has cooled down ({temperature} °C): roof vents closed"),
                  "bed": ("Bed {n} dry: water it", "Bed {n} was dry: watered it"),
                  "fox": ("A fox: sound the alarm", "A fox came to the hen house: sounded the alarm"),
                  "door_shut": ("Night and every hen in: shut the door", "Night, every hen is in: hen house door shut"),
                  "door_open": ("Morning: open the door", "Morning: hen house door opened"),
                  "eggs": ("Eggs waiting: tell the farmer", "Eggs are waiting in the nest boxes: time to collect them"),
                  "eggs_gone": ("Eggs collected", "")},
        "panel": {"title": "Small farm", "pages": {"main": "Now", "settings": "Settings", "notify": "Notifications"},
                  "sources_help": "Start the simulator first (python sim/server.py), then add its cameras: http://127.0.0.1:8810/greenhouse/video.mjpg and http://127.0.0.1:8810/coop/video.mjpg",
                  "blocks": {"w_devices": ("How the farm is", ""),
                             "greenhouse": ("Greenhouse", "Open or close the roof vents and water a bed by hand. The greenhouse keeper also does it on its own when needed."),
                             "henhouse": ("Hen house", "Open or shut the door and sound the fox alarm by hand. The hen house keeper also does it on its own."),
                             "now": ("Stop / resume", "Stop: that camera's keeper does nothing on its own until you press Resume."),
                             "w_log": ("What happened lately", ""),
                             "temps": ("Greenhouse temperature", "The roof vents keep the greenhouse between these two temperatures."),
                             "w_chat": ("Notifications and commands", "Get the farm's news on your phone (a fox, eggs to collect), and give commands from the chat.")},
                  "controls": {"vents_open": "Open vents", "vents_close": "Close vents", "water_1": "Water bed 1", "water_2": "Water bed 2", "water_3": "Water bed 3",
                               "door_open": "Open door", "door_close": "Shut door", "alarm": "Fox alarm", "stop_now": "Stop",
                               "vents_open_above": "Open the vents above", "vents_close_below": "Close the vents below"}},
    },
    "zh-TW": {
        "project": ("小農場", "一間溫室和一間雞舍,各一台攝影機:屋頂通風窗、灑水器、雞舍門和驅狐警報透過 HTTP 輸出控制。", {"device": "攝影機", "item": "項目"}),
        "states": {"temperature": ("溫室溫度", "牆上顯示器的紅色數字,單位 °C。", {}, "溫度計數字"),
                   "vents": ("屋頂通風窗", "開:玻璃窗被支架撐起,露出暗色的縫。關:窗平貼在屋頂上。", {"open": "開著", "closed": "關著", "hidden": "另一台攝影機"}, "左邊的通風窗"),
                   "bed1_dry": ("第 1 畦乾了", "第 1 畦的菜之間露出淺色的乾土。", {"dry": "乾了", "ok": "正常", "hidden": "另一台攝影機"}, "第 1 畦的土"),
                   "bed2_dry": ("第 2 畦乾了", "第 2 畦的菜之間露出淺色的乾土。", {"dry": "乾了", "ok": "正常", "hidden": "另一台攝影機"}, "第 2 畦的土"),
                   "bed3_dry": ("第 3 畦乾了", "第 3 畦的菜之間露出淺色的乾土。", {"dry": "乾了", "ok": "正常", "hidden": "另一台攝影機"}, "第 3 畦的土"),
                   "daylight": ("白天晚上", "山上的天空有多亮。", {"day": "白天", "night": "晚上", "hidden": "另一台攝影機"}, "天空"),
                   "door": ("雞舍門", "開:看得到雞舍裡面暗暗的,門板往外打開。關:木板門上有 Z 字形橫木。", {"open": "開著", "closed": "關著", "hidden": "另一台攝影機"}, "門"),
                   "hens_out": ("雞在外面", "圍欄裡的運動場或門口有白色的雞(晚上也看得到:燈會照亮一點)。", {"yes": "有", "no": "沒有", "hidden": "另一台攝影機"}, "運動場"),
                   "eggs": ("該撿蛋了", "三個產蛋箱稻草上的淺色雞蛋:4 顆以上就是「該撿了」。", {"many": "該撿了", "few": "還不用", "hidden": "另一台攝影機"}, "產蛋箱"),
                   "fox": ("狐狸", "右邊圍籬外的橘色狐狸。", {"yes": "有", "no": "沒有", "hidden": "另一台攝影機"}, "圍籬外(右邊)")},
        "output": "農場設備",
        "cameras": {GH: "溫室攝影機", COOP: "雞舍攝影機"},
        "settings": {"vents_open_above": ("高於這個溫度就開窗", "溫室持續比這個熱,就打開屋頂通風窗(°C)。"),
                     "vents_close_below": ("低於這個溫度就關窗", "溫室降到這個以下,就關上屋頂通風窗(°C)。")},
        "var": "已經通知撿蛋",
        "subs": {"vents_open": ("打開屋頂通風窗", "屋頂通風窗已打開"), "vents_close": ("關上屋頂通風窗", "屋頂通風窗已關上"),
                 "water_1": ("澆第 1 畦", "第 1 畦已澆水"), "water_2": ("澆第 2 畦", "第 2 畦已澆水"), "water_3": ("澆第 3 畦", "第 3 畦已澆水"),
                 "door_open": ("打開雞舍門", "雞舍門已打開"), "door_close": ("關上雞舍門", "雞舍門已關上"),
                 "sound_alarm": ("響驅狐警報", "已響驅狐警報")},
        "sub_desc": "送「{cmd}」給農場設備。",
        "greenhouse": ("溫室管家", "顧好溫室:用屋頂通風窗控制溫度,哪一畦乾了就澆哪一畦。", "看著溫室", "不用做什麼"),
        "henhouse": ("雞舍管家", "顧好雞:白天晚上開關門、趕狐狸、提醒撿蛋。", "看著雞舍", "不用做什麼"),
        "rules": {"too_hot": ("太熱:開通風窗", "溫室太熱了({temperature} °C):已打開屋頂通風窗"),
                  "cooled": ("降溫了:關通風窗", "溫室降溫了({temperature} °C):已關上屋頂通風窗"),
                  "bed": ("第 {n} 畦乾了:澆水", "第 {n} 畦乾了:已經澆水"),
                  "fox": ("狐狸來了:響警報", "狐狸跑到雞舍來了:已響警報"),
                  "door_shut": ("晚上雞都進去了:關門", "天黑了,雞都進去了:雞舍門已關上"),
                  "door_open": ("早上:開門", "早上了:雞舍門已打開"),
                  "eggs": ("有蛋可以撿:通知", "產蛋箱裡有蛋了:可以去撿了"),
                  "eggs_gone": ("蛋撿走了", "")},
        "panel": {"title": "小農場", "pages": {"main": "現況", "settings": "設定", "notify": "通知"},
                  "sources_help": "先啟動模擬器(python sim/server.py),再加入它的攝影機:http://127.0.0.1:8810/greenhouse/video.mjpg 和 http://127.0.0.1:8810/coop/video.mjpg",
                  "blocks": {"w_devices": ("農場現況", ""),
                             "greenhouse": ("溫室", "手動開關屋頂通風窗、澆某一畦。需要時溫室管家也會自己處理。"),
                             "henhouse": ("雞舍", "手動開關雞舍門、響驅狐警報。需要時雞舍管家也會自己處理。"),
                             "now": ("停下來 / 繼續", "停下來:那台攝影機的管家不再自己做任何事,直到你按「繼續」。"),
                             "w_log": ("最近發生的事", ""),
                             "temps": ("溫室溫度", "屋頂通風窗會把溫室維持在這兩個溫度之間。"),
                             "w_chat": ("通知與指令", "農場的消息(狐狸來了、該撿蛋了)傳到手機,也可以從聊天下指令。")},
                  "controls": {"vents_open": "開通風窗", "vents_close": "關通風窗", "water_1": "澆第 1 畦", "water_2": "澆第 2 畦", "water_3": "澆第 3 畦",
                               "door_open": "開雞舍門", "door_close": "關雞舍門", "alarm": "驅狐警報", "stop_now": "停下來",
                               "vents_open_above": "高於這個溫度就開窗", "vents_close_below": "低於這個溫度就關窗"}},
    },
}


def call(base, method, path, body, lang):
    req = urllib.request.Request(base + path, method=method, data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                                 headers={"Content-Type": "application/json", "X-Lang": lang})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        sys.exit(f"{method} {path}: {e.code} {e.read().decode('utf-8', 'replace')}")


def state(sid, op, value, secs=None):
    c = {"state": sid, "op": op, "value": value}
    if secs:
        c["for"] = secs
    return c


def var(name, value):
    return {"kind": "var", "var": name, "op": "is", "value": value}


def out(command):
    return {"type": "output", "output": "farm", "command": command}


def note(text):
    return {"type": "notify", "text": text}


SUBS = [("vents_open", "vents_open"), ("vents_close", "vents_close"), ("water_1", "water_1"), ("water_2", "water_2"),
        ("water_3", "water_3"), ("door_open", "door_open"), ("door_close", "door_close"), ("sound_alarm", "alarm")]


def states(t):
    out_ = json.load(open(os.path.join(HERE, "states.json"), encoding="utf-8"))["states"]
    for s in out_:
        name, desc, classes, roi = t["states"][s["id"]]
        s["name"], s["description"] = name, desc
        for c in s.get("classes") or []:
            c["name"] = classes[c["value"]]
        s["rois"][0]["name"] = roi
    return out_


def rule(rid, name, when, do, **kw):
    return {"id": rid, "name": name, "enabled": True, "when": [when], "do": do, **kw}


def greenhouse(t):
    r = t["rules"]
    name, desc, sit, nothing = t["greenhouse"]
    rules = [rule("too_hot", r["too_hot"][0], [state("temperature", "gt", {"setting": "vents_open_above"}, 10), state("vents", "is", "closed", 5)],
                  [out("vents_open"), note(r["too_hot"][1])], cooldown=60),
             rule("cooled", r["cooled"][0], [state("temperature", "lt", {"setting": "vents_close_below"}, 20), state("vents", "is", "open", 5)],
                  [out("vents_close"), note(r["cooled"][1])], cooldown=60)]
    for n in (1, 2, 3):
        rules.append(rule(f"bed{n}", r["bed"][0].format(n=n), [state(f"bed{n}_dry", "is", "dry", 5)],
                          [out(f"water_{n}"), note(r["bed"][1].format(n=n))], cooldown=40))
    return {"id": "greenhouse_keeper", "name": name, "enabled": True, "devices": {"*": "off", GH: "live"}, "description": desc,
            "otherwise": {"type": "none", "text": nothing}, "initial": "watching",
            "situations": [{"id": "watching", "name": sit, "rules": rules}]}


def henhouse(t):
    r = t["rules"]
    name, desc, sit, nothing = t["henhouse"]
    rules = [rule("fox", r["fox"][0], [state("fox", "is", "yes", 2)], [out("alarm"), note(r["fox"][1])], urgent=True, cooldown=10),
             rule("door_shut", r["door_shut"][0], [state("daylight", "is", "night", 20), state("hens_out", "is", "no", 20), state("door", "is", "open", 5)],
                  [out("door_close"), note(r["door_shut"][1])], cooldown=60),
             rule("door_open", r["door_open"][0], [state("daylight", "is", "day", 20), state("door", "is", "closed", 10)],
                  [out("door_open"), note(r["door_open"][1])], cooldown=300),
             rule("eggs", r["eggs"][0], [state("eggs", "is", "many", 10), var("eggs_told", 0)],
                  [note(r["eggs"][1]), {"type": "set_var", "var": "eggs_told", "mode": "set", "value": 1}], cooldown=30),
             rule("eggs_gone", r["eggs_gone"][0], [state("eggs", "is", "few", 10), var("eggs_told", 1)],
                  [{"type": "set_var", "var": "eggs_told", "mode": "set", "value": 0}], cooldown=30)]
    return {"id": "henhouse_keeper", "name": name, "enabled": True, "devices": {"*": "off", COOP: "live"}, "description": desc,
            "otherwise": {"type": "none", "text": nothing}, "initial": "watching",
            "situations": [{"id": "watching", "name": sit, "rules": rules}]}


def panel(t):
    p = t["panel"]
    b, c = p["blocks"], p["controls"]

    def block(bid, page, items=(), widget=None):
        out_ = {"id": bid, "title": b[bid][0], "help": b[bid][1], "items": list(items), "page": page}
        if widget:
            out_["widget"] = widget
        return out_

    def act(cid, sub, cam):
        return {"id": cid, "label": c[cid], "type": "action", "scope": "device", "devices": [cam], "bind": {"kind": "act_sub", "sub": sub}}

    def temp(cid):
        return {"id": cid, "label": c[cid], "type": "number", "unit": "°C", "min": 15, "max": 40, "scope": "global",
                "bind": {"kind": "setting", "setting": cid}}

    return {
        "title": p["title"], "devices": [GH, COOP],
        "pages": [{"id": k, "title": v} for k, v in p["pages"].items()],
        "sources": {"kinds": ["stream/http"], "help": p["sources_help"], "new_mode": "live"},
        "blocks": [
            block("w_devices", "main", widget={"kind": "devices", "show_step": True, "show_alerts": True, "show_image": True}),
            block("greenhouse", "main", ["vents_open", "vents_close", "water_1", "water_2", "water_3"]),
            block("henhouse", "main", ["door_open", "door_close", "alarm"]),
            block("now", "main", ["stop_now"]),
            block("w_log", "main", widget={"kind": "log", "limit": 20, "panel_changes": True}),
            block("temps", "settings", ["vents_open_above", "vents_close_below"]),
            block("w_chat", "notify", widget={"kind": "chat", "setup": True, "pair": True}),
        ],
        "controls": [
            act("vents_open", "vents_open", GH), act("vents_close", "vents_close", GH),
            act("water_1", "water_1", GH), act("water_2", "water_2", GH), act("water_3", "water_3", GH),
            act("door_open", "door_open", COOP), act("door_close", "door_close", COOP), act("alarm", "sound_alarm", COOP),
            {"id": "stop_now", "label": c["stop_now"], "type": "action", "scope": "device", "bind": {"kind": "act_stop"}},
            temp("vents_open_above"), temp("vents_close_below"),
        ],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", choices=sorted(T), default="en")
    ap.add_argument("--url", default="http://127.0.0.1:8769")
    ap.add_argument("--design", help="the pack's design folder: the project's name, words and cameras (project.json), "
                                     "and the reference pictures the states need")
    a = ap.parse_args()
    t, lang, b = T[a.lang], a.lang, a.url.rstrip("/")
    if a.design:
        p = os.path.join(a.design, "project.json")
        pj = json.load(open(p, encoding="utf-8"))
        cam = lambda path: {"url": f"{SIM}/{path}/video.mjpg", "http_mode": "mjpeg", "fit": "contain"}
        pj.update({"name": t["project"][0], "description": t["project"][1], "words": t["project"][2],
                   "screen": {"width": 1280, "height": 720}, "plugins": [],
                   # the cameras this pack watches, made so on a new computer (Inspector: project.json "sources")
                   "sources": {GH: {"kind": "stream/http", "name": t["cameras"][GH], "params": cam("greenhouse")},
                               COOP: {"kind": "stream/http", "name": t["cameras"][COOP], "params": cam("coop")}}})
        with open(p, "w", encoding="utf-8") as f:
            json.dump(pj, f, ensure_ascii=False, indent=1)
        pk = os.path.join(os.path.dirname(os.path.abspath(a.design)), "pack.json")      # the pack's own name too
        if os.path.exists(pk):
            info = json.load(open(pk, encoding="utf-8"))
            info.update({"name": t["project"][0], "description": t["project"][1], "license": "Apache-2.0",
                         "homepage": "https://github.com/wrbyhaquc/inspector-demo-farm"})
            with open(pk, "w", encoding="utf-8") as f:
                json.dump(info, f, ensure_ascii=False, indent=1)
        dst = os.path.join(a.design, "meta", "rule_templates")         # the taught references (tools/teach_refs.py)
        shutil.rmtree(dst, ignore_errors=True)
        shutil.copytree(os.path.join(HERE, "refs", "meta", "rule_templates"), dst)
    call(b, "POST", "/api/states", {"states": states(t), "note": "farm"}, lang)
    call(b, "PUT", "/api/outputs", {"outputs": [{"id": "farm", "name": t["output"], "type": "http", "url": SIM + "/api/command", "method": "POST", "headers": {}}]}, lang)
    s = t["settings"]
    call(b, "POST", "/api/settings", {"settings": [
        {"id": "vents_open_above", "label": s["vents_open_above"][0], "description": s["vents_open_above"][1], "type": "number", "scope": "shared", "default": 30, "min": 15, "max": 40},
        {"id": "vents_close_below", "label": s["vents_close_below"][0], "description": s["vents_close_below"][1], "type": "number", "scope": "shared", "default": 24, "min": 15, "max": 40}]}, lang)
    call(b, "POST", "/api/variables", {"vars": [{"name": "eggs_told", "label": t["var"], "scope": "device", "reset": "never", "initial": 0}]}, lang)
    for sid, cmd in SUBS:
        name, text = t["subs"][sid]
        call(b, "POST", "/api/subscripts", {"sub": {"id": sid, "name": name, "description": t["sub_desc"].format(cmd=cmd), "timeout": 30,
                                                    "params": [], "say": name, "steps": [out(cmd), note(text)], "cleanup": []},
                                            "note": "farm"}, lang)
    call(b, "POST", "/api/scripts", {"script": greenhouse(t), "note": "farm"}, lang)
    call(b, "POST", "/api/scripts", {"script": henhouse(t), "note": "farm"}, lang)
    call(b, "POST", "/api/panel/definition", {"panel": panel(t)}, lang)
    print(f"done ({lang}): states, output, 2 settings, variable, {len(SUBS)} sub-scripts, 2 main scripts, panel")


if __name__ == "__main__":
    main()
