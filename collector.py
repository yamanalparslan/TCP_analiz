import time
import logging
from datetime import datetime
from pymodbus.client import ModbusTcpClient
import veritabani

# --- YAPILANDIRMA ---
TARGET_IP = "10.35.14.10"
TARGET_PORT = 502
REFRESH_RATE = 2 # Döngü bitince kaç saniye beklesin
SLAVE_IDS = [1, 2, 3] # Sorgulanacak ID'ler

# Okuma Ayarları
CONFIG = {
    'start_addr': 70, 
    'hata_addr': 189
}

def read_device(client, slave_id):
    try:
        # Bağlantı koptuysa tekrar bağlan
        if not client.connected: 
            logging.info("Bağlantı yenileniyor...")
            client.connect()
            time.sleep(0.1) # Bağlantı oturması için minik bekleme
        
        # 1. STANDART VERİLERİ OKU (Blok Halinde)
        rr = client.read_holding_registers(CONFIG['start_addr'], count=4, slave=slave_id)
        
        if rr.isError():
            logging.warning(f"ID {slave_id} -> Standart Veri Okunamadı (Modbus Error)")
            return None

        # Verileri ayrıştır
        val_guc = rr.registers[0] * 1.0
        val_volt = rr.registers[1] * 0.1
        val_akim = rr.registers[2] * 0.1
        val_isi = rr.registers[3] * 1.0

        # 2. HATA KODUNU OKU
        # Arka arkaya sorgu gönderirken araya yine minik bir nefes koyalım
        time.sleep(0.05) 
        r_hata = client.read_holding_registers(CONFIG['hata_addr'], count=2, slave=slave_id)

        hata_kodu = 0
        if not r_hata.isError():
            hata_kodu = (r_hata.registers[0] << 16) | r_hata.registers[1]

        return {
            "guc": val_guc,
            "voltaj": val_volt,
            "akim": val_akim,
            "sicaklik": val_isi,
            "hata_kodu": hata_kodu
        }

    except Exception as e:
        logging.error(f"ID {slave_id} -> Sistem Hatası: {e}")
        # Hata durumunda bağlantıyı kapatıp açmak gateway'i kendine getirebilir
        client.close()
        return None

def start_collector():
    veritabani.init_db()
    
    # Timeout süresini biraz artıralım (Varsayılan bazen yetmez)
    client = ModbusTcpClient(TARGET_IP, port=TARGET_PORT, timeout=2)
    
    logging.info(f"🚀 Collector Başlatıldı: {TARGET_IP}:{TARGET_PORT}")
    print("-" * 50)

    while True:
        start_time = time.time()
        
        for dev_id in SLAVE_IDS:
            print(f"📡 Sorgulanıyor: ID {dev_id}...", end=" ")
            
            # --- KRİTİK DÜZELTME: İki cihaz sorgusu arasına bekleme koyuyoruz ---
            # Bu, RS485 hattının 'traffic jam' olmasını engeller.
            time.sleep(0.3) 
            
            data = read_device(client, dev_id)
            
            if data:
                veritabani.veri_ekle(dev_id, data)
                print(f"✅ OK: Güç {data['guc']}W | Hata: {data['hata_kodu']}")
            else:
                print(f"❌ BAŞARISIZ")
        
        # Döngü bitince bekle
        elapsed = time.time() - start_time
        wait = max(0, REFRESH_RATE - elapsed)
        print(f"💤 Döngü bitti. {wait:.1f}sn bekleniyor...")
        time.sleep(wait)

if __name__ == "__main__":
    logging.basicConfig(level=logging.ERROR) # Sadece kritik hataları logla
    start_collector()