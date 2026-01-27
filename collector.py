import time
import logging
from datetime import datetime
from pymodbus.client import ModbusTcpClient
import veritabani

# Yapılandırma
TARGET_IP = "10.35.14.10"
TARGET_PORT = 502
REFRESH_RATE = 1  
SLAVE_IDS = [1, 2, 3] # Dikkat: Cevap vermeyen cihazlar sistemi yavaşlatır!

CONFIG = {
    'start_addr': 70, # Okumaya başlayacağımız adres (Guc)
    'hata_addr': 189  # Hata Register Adresi
}

def read_device(client, slave_id):
    try:
        if not client.connected: 
            client.connect()
        
        # --- OPTİMİZASYON ---
        # 70, 71, 72, 73 adreslerini TEK SEFERDE okuyoruz (Count=4)
        # Bu işlem hem daha hızlıdır hem de kopukluk riskini azaltır.
        rr = client.read_holding_registers(CONFIG['start_addr'], count=4, slave=slave_id)
        
        if rr.isError():
            logging.warning(f"ID {slave_id} standart veri okuma hatası.")
            return None

        # Gelen 4 veriyi parçalayalım
        # [0]=Guc, [1]=Voltaj, [2]=Akim, [3]=Isi
        val_guc = rr.registers[0] * 1.0
        val_volt = rr.registers[1] * 0.1
        val_akim = rr.registers[2] * 0.1
        val_isi = rr.registers[3] * 1.0

        # --- HATA KODU OKUMA ---
        # Adres 189'dan 2 adet (32-bit) okuyoruz
        r_hata = client.read_holding_registers(CONFIG['hata_addr'], count=2, slave=slave_id)

        hata_kodu = 0
        if not r_hata.isError():
            # Big-endian: İlk register yüksek bit, ikinci register düşük bit
            hata_kodu = (r_hata.registers[0] << 16) | r_hata.registers[1]
        else:
            # Hata kodu okunamadıysa log düşelim ama diğer verileri kaybetmeyelim
            logging.warning(f"ID {slave_id} hata kodu okunamadı, 0 varsayılıyor.")

        return {
            "guc": val_guc,
            "voltaj": val_volt,
            "akim": val_akim,
            "sicaklik": val_isi,
            "hata_kodu": hata_kodu
        }

    except Exception as e:
        logging.error(f"ID {slave_id} genel okuma hatası: {e}")
        return None

def start_collector():
    veritabani.init_db()
    client = ModbusTcpClient(TARGET_IP, port=TARGET_PORT)
    logging.info(f"Collector başlatıldı (Hata Takibi Aktif): {TARGET_IP}:{TARGET_PORT}")

    while True:
        start_time = time.time()
        for dev_id in SLAVE_IDS:
            data = read_device(client, dev_id)
            if data:
                veritabani.veri_ekle(dev_id, data)
                print(f"[{datetime.now().strftime('%H:%M:%S')}] ID {dev_id} | Güç: {data['guc']}W | Hata Kodu: {data['hata_kodu']}")
            else:
                # Veri alınamazsa terminale bilgi verelim
                print(f"[{datetime.now().strftime('%H:%M:%S')}] ID {dev_id} -- Bağlantı Yok --")
        
        elapsed = time.time() - start_time
        wait = max(0, REFRESH_RATE - elapsed)
        time.sleep(wait)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    start_collector()