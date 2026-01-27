import time
import logging
from datetime import datetime
from pymodbus.client import ModbusTcpClient
import veritabani

# --- YAPILANDIRMA ---
TARGET_IP = "10.35.14.10"
TARGET_PORT = 502
REFRESH_RATE = 2  # Döngü bitince kaç saniye beklesin
SLAVE_IDS = [1, 2, 3]  # Tüm cihazlar

# Okuma Ayarları
CONFIG = {
    'start_addr': 70, 
    'hata_addr': 189
}

def read_device(client, slave_id):
    try:
        # Bağlantı kontrolü
        if not client.connected: 
            client.connect()
            time.sleep(0.1)
        
        # 1. ADIM: STANDART VERİLERİ OKU (Güç, Voltaj, Akım, Isı)
        # Bu kısım ZORUNLUDUR. Burası hata verirse cihaz kapalı demektir.
        rr = client.read_holding_registers(CONFIG['start_addr'], count=4, slave=slave_id)
        
        if rr.isError():
            logging.warning(f"ID {slave_id} -> Temel Veri Okunamadı")
            return None

        val_guc = rr.registers[0] * 1.0
        val_volt = rr.registers[1] * 0.1
        val_akim = rr.registers[2] * 0.1
        val_isi = rr.registers[3] * 1.0

        # 2. ADIM: HATA KODUNU (189) OKUMAYI DENE (OPSİYONEL)
        # Burası hata verirse sistemi durdurmayacağız, sadece hata_kodu=0 diyeceğiz.
        hata_kodu = 0
        try:
            # Çok kısa bir bekleme (Hattı rahatlatmak için)
            time.sleep(0.05) 
            
            r_hata = client.read_holding_registers(CONFIG['hata_addr'], count=2, slave=slave_id)
            
            if not r_hata.isError():
                # Eğer cihaz destekliyorsa ve cevap verdiyse işle
                hata_kodu = (r_hata.registers[0] << 16) | r_hata.registers[1]
            else:
                # Cihaz cevap vermedi ama temel verileri aldığımız için sorun yok
                # Log kirliliği yapmaması için burayı sessiz geçebiliriz veya debug log basabiliriz
                pass 
                
        except Exception:
            # Hata kodu okurken ne olursa olsun ana akışı bozma
            hata_kodu = 0

        # Başarıyla toplanan verileri döndür
        return {
            "guc": val_guc,
            "voltaj": val_volt,
            "akim": val_akim,
            "sicaklik": val_isi,
            "hata_kodu": hata_kodu
        }

    except Exception as e:
        logging.error(f"ID {slave_id} -> Kritik Bağlantı Hatası: {e}")
        # Bağlantıda ciddi sorun varsa soketi kapatıp yenilemek iyidir
        client.close()
        return None

def start_collector():
    veritabani.init_db()
    # Timeout'u biraz artırdık, yavaş cihazlar için
    client = ModbusTcpClient(TARGET_IP, port=TARGET_PORT, timeout=2.0)
    
    logging.info(f"Collector Başlatıldı: {TARGET_IP}:{TARGET_PORT}")
    print("-" * 50)
    print("🚀 SİSTEM AKTİF - HİBRİT OKUMA MODU")
    print("-" * 50)

    while True:
        start_time = time.time()
        
        for dev_id in SLAVE_IDS:
            print(f"📡 Sorgulanıyor: ID {dev_id}...", end=" ")
            
            # Cihazlar arası geçişte kısa bekleme (Çarpışma önleyici)
            time.sleep(0.5) 
            
            data = read_device(client, dev_id)
            
            if data:
                veritabani.veri_ekle(dev_id, data)
                # Ekrana basarken hata kodu 0 ise 'OK', değilse kodu gösterelim
                durum_msg = "TEMİZ" if data['hata_kodu'] == 0 else f"HATA KODU: {data['hata_kodu']}"
                print(f"✅ [OK] {data['guc']} W | {durum_msg}")
            else:
                print(f"❌ [BAŞARISIZ]")
        
        # Döngü bitince bekle
        elapsed = time.time() - start_time
        wait = max(0, REFRESH_RATE - elapsed)
        time.sleep(wait)

if __name__ == "__main__":
    logging.basicConfig(level=logging.ERROR)
    start_collector()