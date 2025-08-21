import json
import random
import time
import threading
from datetime import datetime, timedelta

import requests
import os

print("\033[91m" + """
███████╗██████╗ ██╗   ██╗██╗███╗   ██╗██╗   ██╗     
██╔════╝██╔══██╗██║   ██║██║████╗  ██║╚██╗██╔╝     
███████╗██████╔╝███████║██║██╔██╗ ██║ ╚███╔╝      
╚════██║██╔═══╝ ██╔══██║██║██║╚██╗██║ ██╔██╗      
███████║██║     ██║  ██║██║██║ ╚████║██╔╝ ██╗     
╚══════╝╚═╝     ╚═╝  ╚═╝╚═╝╚═╝  ╚═══╝╚═╝  ╚═╝     
                                                 
   ⚡ SCRIPT PUPARTY ⚡
   🎯 Auto Spin | 🏗️ Auto Upgrade | 💰 Auto Collect | 🌐 Proxy Support
         Telegram : @Nobodyxore
""" + "\033[0m")

API_BASE = "https://tg-puparty-h5-api.puparty.com/api/v1"

# --- Membaca Data Akun ---
INIT_DATA_LIST = []
if os.path.exists("pupat.txt"):
    with open("pupat.txt", "r", encoding="utf-8") as f:
        INIT_DATA_LIST = [line.strip() for line in f if line.strip()]
else:
    print("File pupat.txt tidak ditemukan. Harap buat file dan isi dengan initData akun-akunmu.")

# --- FITUR PROXY: Membaca Data Proxy ---
PROXY_LIST = []
if os.path.exists("proxy.txt"):
    with open("proxy.txt", "r", encoding="utf-8") as f:
        PROXY_LIST = [line.strip() for line in f if line.strip()]
    if PROXY_LIST:
        print(f"✅ Berhasil memuat {len(PROXY_LIST)} proxy dari proxy.txt")
else:
    print("⚠️ File proxy.txt tidak ditemukan, skrip akan berjalan tanpa proxy.")


ENABLE_UPGRADE = True
BUILDING_INDEXES_TO_TRY = [1, 2, 3, 4, 5]

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

def post_json(url: str, headers: dict, payload: dict, akun_idx: int, tag: str, proxy_dict: dict | None = None):
    for attempt in range(1, MAX_RETRY + 1):
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=20, proxies=proxy_dict)
            if 200 <= resp.status_code < 300:
                return safe_json(resp)
            else:
                log(akun_idx, f"{tag} HTTP {resp.status_code}: {resp.text[:200]}")
        except requests.exceptions.ProxyError as e:
            log(akun_idx, f"Proxy error on attempt {attempt}: {e}")
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
    for key in ["times", "freeSpins", "spins", "leftSpins", "spinCount", "availableSpins"]:
        if isinstance(d.get(key), int):
            return d.get(key)
    for key in ["slot", "profile", "extra"]:
        sub = d.get(key, {})
        for k in ["times", "freeSpins", "spins", "leftSpins", "spinCount", "availableSpins"]:
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
    prize = (bet_data.get("data") or {}).get("prize")
    if isinstance(prize, str) and trigger_name in prize.lower():
        return True
    return False

def get_trigger_id_from_bet(bet_data: dict) -> str | None:
    try:
        data = bet_data.get("data", {})
        prize = data.get("prize")
        slots = data.get("slots")
        if prize and isinstance(slots, list):
            count = slots.count(prize)
            if count > 0:
                return str(count)
    except Exception:
        return None
    return None

def api_daily_sign(akun_idx: int, headers: dict, proxy_dict: dict | None):
    url = f"{API_BASE}/slot/sign/trigger"
    return post_json(url, headers, {}, akun_idx, "daily_sign", proxy_dict)

def api_attack_trigger(akun_idx: int, headers: dict, bet_data: dict, proxy_dict: dict | None) -> dict | None:
    url = f"{API_BASE}/slot/attack/trigger"
    trigger_id = get_trigger_id_from_bet(bet_data)
    if trigger_id is None:
        log(akun_idx, "ATTACK trigger gagal: Tidak dapat menghitung ID dari respons bet.")
        return None
    payload = {"id": trigger_id}
    return post_json(url, headers, payload, akun_idx, "attack/trigger", proxy_dict)

def api_steal(akun_idx: int, headers: dict, bet_data: dict, proxy_dict: dict | None):
    url = f"{API_BASE}/slot/steal"
    trigger_id = get_trigger_id_from_bet(bet_data)
    if trigger_id is None:
        log(akun_idx, "STEAL trigger gagal: Tidak dapat menghitung ID dari respons bet.")
        return None
    payload = {"id": trigger_id}
    return post_json(url, headers, payload, akun_idx, "steal", proxy_dict)

def api_login(akun_idx: int, init_data: str, proxy_dict: dict | None) -> str | None:
    url = f"{API_BASE}/member/login"
    payload = rand_device_payload(init_data)
    res = post_json(url, BASE_HEADERS, payload, akun_idx, "login", proxy_dict)
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

def api_index(akun_idx: int, headers: dict, proxy_dict: dict | None):
    url = f"{API_BASE}/slot/index"
    return post_json(url, headers, {}, akun_idx, "index", proxy_dict)

def api_bet(akun_idx: int, headers: dict, proxy_dict: dict | None):
    url = f"{API_BASE}/slot/bet"
    payload = {"bet": 1}
    return post_json(url, headers, payload, akun_idx, "bet", proxy_dict)

def api_collect_get(akun_idx: int, headers: dict, proxy_dict: dict | None):
    url = f"{API_BASE}/member/asset/collect/get"
    return post_json(url, headers, {}, akun_idx, "collect/get", proxy_dict)

def api_collect_receive(akun_idx: int, headers: dict, collect_id, proxy_dict: dict | None):
    url = f"{API_BASE}/member/asset/collect/receive"
    payload = {"id": collect_id}
    return post_json(url, headers, payload, akun_idx, "collect/receive", proxy_dict)

def api_upgrade_building(akun_idx: int, headers: dict, building_index: int, proxy_dict: dict | None):
    url = f"{API_BASE}/farm/building/upgrade"
    payload = {"buildingIndex": building_index}
    return post_json(url, headers, payload, akun_idx, "building/upgrade", proxy_dict)

def do_collect_all(akun_idx: int, headers: dict, proxy_dict: dict | None):
    data = api_collect_get(akun_idx, headers, proxy_dict)
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
        res = api_collect_receive(akun_idx, headers, cid, proxy_dict)
        if res and response_ok(res):
            cnt += 1
            log(akun_idx, f"Collect receive OK (id={cid})")
        sleep_jitter()
    if cnt: log(akun_idx, f"Collected {cnt} item(s).")

# --- FUNGSI UTAMA TRIGGER TELAH DIPERBAIKI SECARA TOTAL ---
def maybe_triggers(akun_idx: int, headers: dict, bet_res: dict, proxy_dict: dict | None):
    # ---- Steal ----
    if has_trigger(bet_res, "steal"):
        log(akun_idx, "Memicu STEAL... Melakukan 3x percobaan pencurian.")
        total_gold_stolen = 0
        successful_steals = 0
        
        # Melakukan loop untuk mencuri sebanyak 3 kali
        for i in range(1, 4):
            log(akun_idx, f"Percobaan mencuri ke-{i}...")
            res = api_steal(akun_idx, headers, bet_res, proxy_dict)
            if res and response_ok(res):
                gold = int((res.get("data") or {}).get("gold", 0))
                total_gold_stolen += gold
                successful_steals += 1
                log(akun_idx, f"  -> Berhasil mencuri {gold} emas.")
            else:
                log(akun_idx, f"  -> Gagal mencuri: {get_error_message(res)}")
            sleep_jitter()
        
        if successful_steals > 0:
            log(akun_idx, f"✅ STEAL selesai. Total emas dicuri: {total_gold_stolen}")
        else:
            log(akun_idx, "❌ STEAL gagal di semua percobaan.")
        sleep_jitter()

    # ---- Attack ----
    if has_trigger(bet_res, "attack"):
        log(akun_idx, "Memicu ATTACK...")
        res = api_attack_trigger(akun_idx, headers, bet_res, proxy_dict)
        if res and response_ok(res):
            hasil = res.get('data', {})
            koin_didapat = hasil.get('coin', '0')
            target_kena_shield = hasil.get('shield', False)
            if target_kena_shield:
                log(akun_idx, f"✅ ATTACK berhasil! Target punya perisai. Hadiah: {koin_didapat} emas.")
            else:
                log(akun_idx, f"✅ ATTACK berhasil! Koin didapat: {koin_didapat} emas.")
        else:
            log(akun_idx, f"❌ ATTACK gagal: {get_error_message(res)}")
        sleep_jitter()


def do_upgrade_sequence(akun_idx: int, headers: dict, proxy_dict: dict | None):
    if not ENABLE_UPGRADE: return
    total_upgraded = 0
    log(akun_idx, "Memulai proses upgrade bangunan hingga koin habis...")
    while True:
        upgraded_in_pass = 0
        random.shuffle(BUILDING_INDEXES_TO_TRY)
        for idx in BUILDING_INDEXES_TO_TRY:
            res = api_upgrade_building(akun_idx, headers, idx, proxy_dict)
            if res and response_ok(res):
                total_upgraded += 1
                upgraded_in_pass += 1
                log(akun_idx, f"✅ Upgrade bangunan index {idx} berhasil!")
                sleep_jitter()
        if upgraded_in_pass == 0:
            log(akun_idx, "Tidak ada upgrade yang bisa dilakukan lagi (koin habis).")
            break
    if total_upgraded > 0:
        log(akun_idx, f"🎉 Total {total_upgraded} upgrade berhasil dilakukan.")

def run_account(akun_idx: int, init_data: str):
    log(akun_idx, "Memulai proses untuk akun ini...")

    proxy_dict = None
    if PROXY_LIST:
        proxy_string = PROXY_LIST[(akun_idx - 1) % len(PROXY_LIST)]
        try:
            parts = proxy_string.split(':')
            if len(parts) == 4:
                host, port, user, pw = parts
                proxy_url = f"http://{user}:{pw}@{host}:{port}"
                proxy_dict = {"http": proxy_url, "https": proxy_url}
                log(akun_idx, f"Menggunakan proxy: {host}:{port}")
            else:
                log(akun_idx, f"Format proxy salah di baris '{proxy_string}', berjalan tanpa proxy.")
        except Exception as e:
            log(akun_idx, f"Gagal memproses proxy: {e}, berjalan tanpa proxy.")

    token = api_login(akun_idx, init_data, proxy_dict)
    if not token:
        log(akun_idx, "Login gagal. Skip akun ini.")
        return

    headers = BASE_HEADERS.copy()
    headers["token"] = token
    sleep_jitter()

    log(akun_idx, "Mencoba daily sign-in...")
    res_daily = api_daily_sign(akun_idx, headers, proxy_dict)
    if res_daily and response_ok(res_daily):
        log(akun_idx, "✅ Daily sign-in berhasil.")
    else:
        log(akun_idx, f"⚠️ Daily sign-in gagal atau sudah dilakukan: {get_error_message(res_daily)}")
    sleep_jitter()

    idx_data = api_index(akun_idx, headers, proxy_dict)
    
    spins = get_spins_from_index(akun_idx, idx_data)
    log(akun_idx, f"Spin tersedia: {spins}")

    for i in range(max(0, spins)):
        log(akun_idx, f"Spin {i + 1}/{spins}")
        bet_res = api_bet(akun_idx, headers, proxy_dict)
        if bet_res:
            maybe_triggers(akun_idx, headers, bet_res, proxy_dict)
        sleep_jitter()

    log(akun_idx, "Semua spin selesai. Sekarang collect & upgrade…")
    do_collect_all(akun_idx, headers, proxy_dict)
    do_upgrade_sequence(akun_idx, headers, proxy_dict)
    log(akun_idx, "Akun selesai ✅")

def main():
    if not INIT_DATA_LIST:
        print("Harap isi pupat.txt dengan initData akun-akunmu.", flush=True)
        return
    while True:
        try:
            print("\n" + "="*50)
            print(f"🚀 Memulai siklus baru pada {datetime.now().strftime('%H:%M:%S')}")
            print("="*50)
            for idx, init_data in enumerate(INIT_DATA_LIST, start=1):
                try:
                    run_account(idx, init_data)
                    print("-" * 30)
                except Exception as e:
                    log(idx, f"Terjadi error fatal: {e}")
            print("\n" + "="*60)
            print("✅ Semua akun telah selesai diproses.")
            wait_hours = 4
            wait_seconds = wait_hours * 3600
            next_run_time = datetime.now() + timedelta(seconds=wait_seconds)
            print(f"🔁 Siklus berikutnya dalam {wait_hours} jam.")
            print(f"🕒 Waktu eksekusi berikutnya: {next_run_time.strftime('%H:%M:%S')} (WIB)")
            print("="*60)
            print("(Tekan Ctrl+C untuk stop)")
            time.sleep(wait_seconds)
        except KeyboardInterrupt:
            print("\n🛑 Skrip dihentikan oleh pengguna. Sampai jumpa!")
            break
        except Exception as e:
            print(f"\n🔥 Terjadi error tak terduga di loop utama: {e}")
            print("Mencoba lagi dalam 5 menit...")
            time.sleep(300)

if __name__ == "__main__":
    main()
