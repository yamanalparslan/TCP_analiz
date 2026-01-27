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
    'alarm_registers': [
        # Adres 189: 32-bit (2 Register) okunmalı
        {'addr': 189, 'key': 'hata_kodu', 'count': 2},
        
        # Adres 193: 16-bit (1 Register) okunmalı (Senin ayarın)
        {'addr': 193, 'key': 'hata_kodu_193', 'count': 1} 
    ]
}

def read_device(client, slave_id):
    try:
        if not client.connected: 
            client.connect()
            time.sleep(0.1)
        
        # 1. STANDART VERİLERİ OKU (Güç, Voltaj, Akım, Isı)
        rr = client.read_holding_registers(CONFIG['start_addr'], count=4, slave=slave_id)
        if rr.isError(): return None

        veriler = {
            "guc": rr.registers[0] * 1.0,
            "voltaj": rr.registers[1] * 0.1,
            "akim": rr.registers[2] * 0.1,
            "sicaklik": rr.registers[3] * 1.0
        }

        # 2. ALARM REGİSTERLARINI OKU (Esnek Yapı: 189 ve 193)
        for reg in CONFIG['alarm_registers']:
            addr = reg['addr']
            key = reg['key']
            cnt = reg.get('count', 2) # Varsayılan 2, ama config'den 1 gelirse onu kullanır
            
            try:
                time.sleep(0.05) # Hızlı sorgu çakışmasını önle
                
                # Dinamik count ile okuma
                r_hata = client.read_holding_registers(addr, count=cnt, slave=slave_id)
                
                if not r_hata.isError():
                    if cnt == 2:
                        # 32-bit (2 Register) ise birleştir
                        veriler[key] = (r_hata.registers[0] << 16) | r_hata.registers[1]
                    else:
                        # 16-bit (1 Register) ise direkt al
                        veriler[key] = r_hata.registers[0]
                else:
                    veriler[key] = 0 # Okunamazsa 0 kabul et
            except:
                veriler[key] = 0 # Hata durumunda 0 kabul et

        return veriler

    except Exception as e:
        logging.error(f"ID {slave_id} Hata: {e}")
        client.close()
        return None

def start_collector():
    veritabani.init_db()
    # Timeout süresini biraz uzun tutuyoruz (2.0 sn)
    client = ModbusTcpClient(TARGET_IP, port=TARGET_PORT, timeout=2.0)
    
    print("-" * 50)
    print("🚀 COLLECTOR BAŞLATILDI (Dual Alarm Modu: 189[32bit] & 193[16bit])")
    print("-" * 50)

    while True:
        start_time = time.time()
        for dev_id in SLAVE_IDS:
            print(f"📡 ID {dev_id}...", end=" ")
            time.sleep(0.5) # Cihazlar arası kısa bekleme
            
            data = read_device(client, dev_id)
            if data:
                veritabani.veri_ekle(dev_id, data)
                
                # Durum Mesajı Oluşturma
                h189 = data.get('hata_kodu', 0)
                h193 = data.get('hata_kodu_193', 0)
                
                if h189 == 0 and h193 == 0:
                    durum = "TEMİZ"
                else:
                    durum = f"⚠️ HATA (189:{h189}, 193:{h193})"
                
                print(f"✅ [OK] {durum}")
            else:
                print(f"❌ [YOK]")
        
        elapsed = time.time() - start_time
        time.sleep(max(0, REFRESH_RATE - elapsed))

if __name__ == "__main__":
    logging.basicConfig(level=logging.ERROR)
    start_collector()