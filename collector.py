import time
import logging
from pymodbus.client import ModbusTcpClient
import veritabani

# --- AYARLAR ---
TARGET_IP = "10.35.14.10"
TARGET_PORT = 502
REFRESH_RATE = 2  
SLAVE_IDS = [1, 2, 3] 

# Okuma Ayarları
CONFIG = {
    'start_addr': 70, 
    # BURAYA DİKKAT: Okunacak Alarm Adresleri Listesi
    'alarm_registers': [
        {'addr': 189, 'key': 'hata_kodu'},     # Mevcut
        {'addr': 193, 'key': 'hata_kodu_193'}  # Yeni
    ]
}

def read_device(client, slave_id):
    try:
        if not client.connected: 
            client.connect()
            time.sleep(0.1)
        
        # 1. STANDART VERİLERİ OKU
        rr = client.read_holding_registers(CONFIG['start_addr'], count=4, slave=slave_id)
        if rr.isError(): return None

        veriler = {
            "guc": rr.registers[0] * 1.0,
            "voltaj": rr.registers[1] * 0.1,
            "akim": rr.registers[2] * 0.1,
            "sicaklik": rr.registers[3] * 1.0
        }

        # 2. ALARM REGİSTERLARINI OKU (189 ve 193)
        # Her bir adres için ayrı try-except kuruyoruz ki biri bozuksa diğeri çalışsın.
        for reg in CONFIG['alarm_registers']:
            addr = reg['addr']
            key = reg['key']
            
            try:
                time.sleep(0.05) # Kısa bekleme
                r_hata = client.read_holding_registers(addr, count=2, slave=slave_id)
                
                if not r_hata.isError():
                    # 32-bit birleştirme
                    veriler[key] = (r_hata.registers[0] << 16) | r_hata.registers[1]
                else:
                    veriler[key] = 0 # Okunamazsa 0
            except:
                veriler[key] = 0 # Hata verirse 0

        return veriler

    except Exception as e:
        logging.error(f"ID {slave_id} Hata: {e}")
        client.close()
        return None

def start_collector():
    veritabani.init_db()
    client = ModbusTcpClient(TARGET_IP, port=TARGET_PORT, timeout=2.0)
    
    print("-" * 50)
    print("🚀 COLLECTOR BAŞLATILDI (Dual Alarm Modu: 189 & 193)")
    print("-" * 50)

    while True:
        start_time = time.time()
        for dev_id in SLAVE_IDS:
            print(f"📡 ID {dev_id}...", end=" ")
            time.sleep(0.5)
            
            data = read_device(client, dev_id)
            if data:
                veritabani.veri_ekle(dev_id, data)
                # Ekrana 189 ve 193 durumunu yazalım
                h189 = data['hata_kodu']
                h193 = data['hata_kodu_193']
                durum = "TEMİZ" if (h189 == 0 and h193 == 0) else f"⚠️ HATA (189:{h189}, 193:{h193})"
                print(f"✅ [OK] {durum}")
            else:
                print(f"❌ [YOK]")
        
        elapsed = time.time() - start_time
        time.sleep(max(0, REFRESH_RATE - elapsed))

if __name__ == "__main__":
    logging.basicConfig(level=logging.ERROR)
    start_collector()