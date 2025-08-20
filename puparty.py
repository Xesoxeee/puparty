import json
import random
import time
import threading
from datetime import datetime, timedelta

import requests
import os

print("\033[91m" + """
███████╗██████╗ ██╗  ██╗██╗███╗   ██╗██╗  ██╗    
██╔════╝██╔══██╗██║  ██║██║████╗  ██║╚██╗██╔╝    
███████╗██████╔╝███████║██║██╔██╗ ██║ ╚███╔╝     
╚════██║██╔═══╝ ██╔══██║██║██║╚██╗██║ ██╔██╗     
███████║██║     ██║  ██║██║██║ ╚████║██╔╝ ██╗    
╚══════╝╚═╝     ╚═╝  ╚═╝╚═╝╚═╝  ╚═══╝╚═╝  ╚═╝    
                                                 
    ⚡ SCRIPT PUPARTY ⚡
    🎯 Auto Spin | 🏗️ Auto Upgrade | 💰 Auto Collect
            Telegram : @Nobodyxore
""" + "\033[0m")

API_BASE = "https://tg-puparty-h5-api.puparty.com/api/v1"

INIT_DATA_LIST = []
if os.path.exists("pupat.txt"):
    with open("pupat.txt", "r", encoding="utf-8") as f:
        INIT_DATA_LIST = [line.strip() for line in f if line.strip()]
else:
    print("File pupat.txt tidak ditemukan. Harap buat file dan isi dengan initData akun-akunmu.")

ENABLE_UPGRADE = True
BUILDING_INDEXES_TO_TRY = [1, 2, 3, 4, 5]

ENABLE_WATCH_ADS = False
AD_TRIGGER_ENDPOINT = "/slot/ad/trigger"
AD_CLAIM_ENDPOINT = "/support/ad/upload"
ADS_TO_WATCH = 5
AD_TRIGGER_PAYLOAD = {"type": 1}

DEFAULT_SPINS_IF_NOT_FOUND = 100

SLEEP_MIN = 0.6
SLEEP_MAX = 1.4

MAX_RETRY = 3
BACKOFF_BASE = 0.9
BACKOFF_JITTER = (0.3, 0.7)

BASE_HEADERS = {
    "accept": "*/*",
    "accept-encoding": "gzip, deflate, br, zstd",
    "accept-language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
    "cache-control": "no-cache",
    "content-type": "application/json",
    "device": "game",
    "gameversion": "2.4.5",
    "lang": "in_ID",
    "origin": "https://h5.puparty.com",
    "pragma": "no-cache",
    "referer": "https://h5.puparty.com/",
    "source": "android",
    "company-code": "7",
    "user-agent": (
        "Mozilla/5.0 (Linux; Android 15; K) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/139.0.7258.94 Mobile Safari/537.36 "
        "Telegram-Android/11.14.1 (Infinix Infinix X6728; Android 15; SDK 35; AVERAGE)"
    ),
    "x-requested-with": "org.telegram.messenger",
}

MANUFACTURERS = [
    "Infinix Infinix X6728", "Samsung SM-A536E", "Xiaomi Redmi Note 10",
    "OPPO CPH2015", "Vivo V2141A", "Realme RMX3360", "POCO F3", "Nothing A065"
]
PERF_CLASSES = ["LOW", "AVERAGE", "HIGH"]
ANDROID_VERSIONS = ["13", "14", "15"]
SDK_VERSIONS = ["33", "34", "35"]
TG_VERSION = "11.14.1"

def rand_device_payload(init_data: str) -> dict:
    return {
        "androidVersion": random.choice(ANDROID_VERSIONS),
        "initData": init_data,
        "manufacturer": random.choice(MANUFACTURERS),
        "performanceClass": random.choice(PERF_CLASSES),
        "pid": None,
        "sdkVersion": random.choice(SDK_VERSIONS),
        "source": "android",
        "tgVersion": TG_VERSION,
    }


print_lock = threading.Lock()

def log(akun_idx: int, *args):
    with print_lock:
        prefix = f"[Akun {akun_idx:02d}]"
        print(prefix, *args, flush=True)

def sleep_jitter():
    time.sleep(random.uniform(SLEEP_MIN, SLEEP_MAX))

def backoff_sleep(attempt: int):
    base = BACKOFF_BASE * (2 ** (attempt - 1))
    jitter = random.uniform(*BACKOFF_JITTER)
    time.sleep(base + jitter)

def safe_json(resp: requests.Response):
    try:
        return resp.json()
    except Exception:
        return {"raw": resp.text, "status_code": resp.status_code}

def post_json(url: str, headers: dict, payload: dict, akun_idx: int, tag: str):
    for attempt in range(1, MAX_RETRY + 1):
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=20)
            if 200 <= resp.status_code < 300:
                return safe_json(resp)
            else:
                log(akun_idx, f"{tag} HTTP {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            log(akun_idx, f"{tag} error attempt {attempt}: {e}")
        if attempt < MAX_RETRY:
            backoff_sleep(attempt)
    return None

def get_error_message(res: dict | None) -> str:
    if not isinstance(res, dict):
        return str(res)[:180]

    if 'msg' in res and res['msg']:
        return str(res['msg'])
    if 'message' in res and res['message']:
        return str(res['message'])
    
    if 'code' in res:
        return f"Kode Error: {res['code']}"

    return json.dumps(res)


def get_spins_from_index(akun_idx: int, index_data: dict) -> int:
    d = (index_data or {}).get("data", {})
    for key in ["freeSpins", "spins", "leftSpins", "spinCount", "availableSpins"]:
        if isinstance(d.get(key), int):
            return d.get(key)
    for key in ["slot", "profile", "extra"]:
        sub = d.get(key, {})
        for k in ["freeSpins", "spins", "leftSpins", "spinCount", "availableSpins"]:
            val = sub.get(k)
            if isinstance(val, int):
                return val
    log(akun_idx, f"Tidak bisa menemukan jumlah spin dari API, menggunakan default: {DEFAULT_SPINS_IF_NOT_FOUND}")
    return DEFAULT_SPINS_IF_NOT_FOUND

def response_ok(data: dict) -> bool:
    if not isinstance(data, dict):
        return False
    d = data
    if d.get("success") is True:
        return True
    if isinstance(d.get("code"), int) and d.get("code") in (0, 200):
        return True
    if str(d.get("status")).lower() in ("ok", "success", "200"):
        return True
    return False

def has_trigger(bet_data: dict, trigger_name: str) -> bool:
    if not isinstance(bet_data, dict):
        return False
    s = json.dumps(bet_data).lower()
    return trigger_name in s

def api_login(akun_idx: int, init_data: str) -> str | None:
    url = f"{API_BASE}/member/login"
    payload = rand_device_payload(init_data)
    res = post_json(url, BASE_HEADERS, payload, akun_idx, "login")
    if not res:
        return None
    token = (res.get("data") or {}).get("token")
    if not token:
        for k in ["auth", "session", "result", "payload"]:
            maybe = (res.get("data") or {}).get(k, {})
            if isinstance(maybe, dict) and "token" in maybe:
                token = maybe["token"]
                break
    if not token:
        log(akun_idx, "Login gagal: token tidak ditemukan.", get_error_message(res))
        return None
    return token

def api_index(akun_idx: int, headers: dict):
    url = f"{API_BASE}/slot/index"
    return post_json(url, headers, {}, akun_idx, "index")

def api_bet(akun_idx: int, headers: dict):
    url = f"{API_BASE}/slot/bet"
    payload = {"bet": 1}
    return post_json(url, headers, payload, akun_idx, "bet")

def api_steal(akun_idx: int, headers: dict):
    url = f"{API_BASE}/slot/steal"
    return post_json(url, headers, {}, akun_idx, "steal")

def api_attack_trigger(akun_idx: int, headers: dict, target_id=None):
    url = f"{API_BASE}/slot/attack/trigger"
    payload = {"id": target_id} if target_id is not None else {}
    return post_json(url, headers, payload, akun_idx, "attack/trigger")

def api_collect_get(akun_idx: int, headers: dict):
    url = f"{API_BASE}/member/asset/collect/get"
    return post_json(url, headers, {}, akun_idx, "collect/get")

def api_collect_receive(akun_idx: int, headers: dict, collect_id):
    url = f"{API_BASE}/member/asset/collect/receive"
    payload = {"id": collect_id}
    return post_json(url, headers, payload, akun_idx, "collect/receive")

def api_upgrade_building(akun_idx: int, headers: dict, building_index: int):
    url = f"{API_BASE}/farm/building/upgrade"
    payload = {"buildingIndex": building_index}
    return post_json(url, headers, payload, akun_idx, "building/upgrade")

def do_collect_all(akun_idx: int, headers: dict):
    data = api_collect_get(akun_idx, headers)
    if not data: return
    items = []
    if isinstance(data.get("data"), list): items = data["data"]
    elif isinstance(data.get("data"), dict):
        for v in data["data"].values():
            if isinstance(v, list):
                items = v
                break
    cnt = 0
    for it in items:
        if not isinstance(it, dict): continue
        cid = it.get("id") or it.get("collectId") or it.get("cid")
        if cid is None: continue
        res = api_collect_receive(akun_idx, headers, cid)
        if res and response_ok(res):
            cnt += 1
            log(akun_idx, f"Collect receive OK (id={cid})")
        sleep_jitter()
    if cnt: log(akun_idx, f"Collected {cnt} item(s).")

def maybe_triggers(akun_idx: int, headers: dict, bet_res: dict):
    did_any = False
    want_steal = has_trigger(bet_res, "steal")
    want_attack = has_trigger(bet_res, "attack") or has_trigger(bet_res, "hammer") or has_trigger(bet_res, "palu")
    if want_steal:
        res = api_steal(akun_idx, headers)
        if res and response_ok(res):
            log(akun_idx, "STEAL sukses.")
            did_any = True
        else:
            error_msg = get_error_message(res)
            log(akun_idx, f"STEAL gagal: {error_msg}")
        sleep_jitter()
    if want_attack:
        res = api_attack_trigger(akun_idx, headers, target_id=None)
        if res and response_ok(res):
            log(akun_idx, "ATTACK trigger sukses.")
            did_any = True
        else:
            error_msg = get_error_message(res)
            log(akun_idx, f"ATTACK gagal: {error_msg}")
        sleep_jitter()
    return did_any

def do_upgrade_sequence(akun_idx: int, headers: dict):
    if not ENABLE_UPGRADE: return
    upgraded = 0
    for idx in BUILDING_INDEXES_TO_TRY:
        res = api_upgrade_building(akun_idx, headers, idx)
        if not res: continue
        if response_ok(res):
            upgraded += 1
            log(akun_idx, f"Upgrade building index {idx} OK.")
        else:
            error_msg = get_error_message(res)
            log(akun_idx, f"Upgrade building index {idx} gagal/skip: {error_msg}")
        sleep_jitter()
    if upgraded: log(akun_idx, f"Total upgrade OK: {upgraded}")

def run_account(akun_idx: int, init_data: str):
    log(akun_idx, "Memulai proses untuk akun ini...")
    token = api_login(akun_idx, init_data)
    if not token:
        log(akun_idx, "Login gagal. Skip akun ini.")
        return

    headers = BASE_HEADERS.copy()
    headers["token"] = token
    sleep_jitter()

    idx = api_index(akun_idx, headers)
    spins = get_spins_from_index(akun_idx, idx)
    log(akun_idx, f"Spin tersedia: {spins}")

    for i in range(max(0, spins)):
        log(akun_idx, f"Spin {i + 1}/{spins}")
        bet_res = api_bet(akun_idx, headers)
        if bet_res: maybe_triggers(akun_idx, headers, bet_res)
        sleep_jitter()

    log(akun_idx, "Semua spin selesai. Sekarang collect & upgrade…")
    do_collect_all(akun_idx, headers)
    do_upgrade_sequence(akun_idx, headers)
    log(akun_idx, "Akun selesai ✅")


def main():
    if not INIT_DATA_LIST:
        print("Harap isi pupat.txt dengan initData akun-akunmu.", flush=True)
        return

    # Loop utama yang akan berjalan selamanya
    while True:
        try:
            print("\n" + "="*50)
            print(f"🚀 Memulai siklus baru pada {datetime.now().strftime('%H:%M:%S')}")
            print("="*50)

            # Memproses setiap akun secara berurutan
            for idx, init_data in enumerate(INIT_DATA_LIST, start=1):
                try:
                    run_account(idx, init_data)
                    print("-" * 30) # Pemisah antar akun
                except Exception as e:
                    log(idx, f"Terjadi error fatal: {e}")
            
            # Setelah semua akun selesai, tunggu 4 jam
            print("\n" + "="*60)
            print("✅ Semua akun telah selesai diproses.")
            
            wait_hours = 4
            wait_seconds = wait_hours * 3600
            next_run_time = datetime.now() + timedelta(seconds=wait_seconds)
            
            print(f"🔁 Siklus berikutnya akan dimulai dalam {wait_hours} jam.")
            print(f"🕒 Waktu eksekusi berikutnya: {next_run_time.strftime('%H:%M:%S')} (WIB)")
            print("="*60)
            print("(Tekan Ctrl + C untuk menghentikan skrip)")
            
            time.sleep(wait_seconds)

        except KeyboardInterrupt:
            print("\n🛑 Skrip dihentikan oleh pengguna. Sampai jumpa!")
            break # Keluar dari loop while True
        except Exception as e:
            print(f"\n🔥 Terjadi error tak terduga di loop utama: {e}")
            print("Mencoba lagi dalam 5 menit...")
            time.sleep(300)


if __name__ == "__main__":
    # Menghapus import yang tidak perlu lagi
    from concurrent.futures import ThreadPoolExecutor, as_completed
    main()