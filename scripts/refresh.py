"""Read item level and combat power from lostark.bible roster pages and save them to the shared database.

One request per roster in roster.json, 20 seconds apart (the site has traffic detection).
A roster that fails to load keeps its previous numbers. Needs SUPABASE_URL and SUPABASE_SERVICE_KEY.
"""
import json, os, re, sys, time, urllib.error, urllib.parse, urllib.request

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"
PAUSE = 20
# lostark.bible class keys -> the class names the page uses (Warpbeaver = Dimensionalist)
CLASS = {"holyknight_female": "Valkyrie", "alchemist": "Wildsoul", "yinyangshi": "Artist", "bard": "Bard",
         "infighter_male": "Breaker", "infighter": "Scrapper", "dragon_knight": "Guardianknight",
         "dimension_master": "Warpbeaver", "berserker": "Berserker", "hawk_eye": "Sharpshooter",
         "demonic": "Shadowhunter", "battle_master": "Wardancer", "devil_hunter": "Deadeye",
         "devil_hunter_female": "Gunslinger", "elemental_master": "Sorceress", "scouter": "Scouter",
         "warlord": "Gunlancer", "blade": "Deathblade", "lance_master": "Glavier", "holyknight": "Paladin",
         "destroyer": "Destroyer", "summoner": "Summoner", "reaper": "Reaper", "arcana": "Arcana",
         "weather_artist": "Aeromancer", "berserker_female": "Slayer", "soul_eater": "Souleater",
         "soulfist": "Soulfist", "striker": "Striker", "gunslinger": "Gunslinger", "artillerist": "Artillerist"}

def fetch_roster(region, name):
    url = f"https://lostark.bible/character/{region}/{urllib.parse.quote(name)}/roster"
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html"})
    with urllib.request.urlopen(req, timeout=30) as r:
        s = r.read().decode("utf-8", "replace")
    m = re.search(r'data:\{roster:(\[.*?\])\},uses', s)
    if not m:
        raise ValueError("no roster data on the page")
    ro = json.loads(re.sub(r'([{,])([a-zA-Z_]+):', r'\1"\2":', m.group(1)))
    w = re.search(r'world:"([^"]+)"', s)
    chars = [{"name": c["name"], "cls": CLASS.get(c["class"], c["class"]), "il": round(float(c["ilvl"]), 2),
              "cp": round(float(c["combatPower"]["score"]), 2), "sup": c["combatPower"].get("id") == 2} for c in ro]
    return (w.group(1) if w else None), chars

def save(rows):
    url, key = os.environ["SUPABASE_URL"].rstrip("/"), os.environ["SUPABASE_SERVICE_KEY"]
    req = urllib.request.Request(url + "/rest/v1/docs", data=json.dumps(rows).encode(), method="POST",
                                 headers={"apikey": key, "Authorization": "Bearer " + key, "Content-Type": "application/json",
                                          "Prefer": "resolution=merge-duplicates,return=minimal"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status

def main():
    cfg = json.load(open(os.path.join(os.path.dirname(__file__), "..", "roster.json")))
    rows, failed = [], []
    for n, ro in enumerate(cfg["rosters"]):
        if n:
            time.sleep(PAUSE)
        try:
            world, chars = fetch_roster(cfg.get("region", "CE"), ro["main"])
        except (urllib.error.URLError, TimeoutError, ValueError, KeyError) as e:
            print(f"{ro['key']}: could not read ({e}); keeping previous numbers"); failed.append(ro["key"]); continue
        unknown = sorted({c["cls"] for c in chars if c["cls"][0].islower()})
        print(f"{ro['key']}: {len(chars)} characters on {world}" + (f"; unknown class keys {unknown}" if unknown else ""))
        rows.append({"coll": "stats", "id": ro["key"], "data": {"at": int(time.time() * 1000), "world": world,
                     "alt": bool(ro.get("alt")), "main": ro["main"], "chars": chars},
                     "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
    if rows:
        print("saved", len(rows), "rosters, status", save(rows))
    if failed and not rows:
        sys.exit("no roster could be read")

if __name__ == "__main__":
    main()
