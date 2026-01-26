import time
import logging
from datetime import datetime
from pymodbus.client import ModbusTcpClient
import veritabani

# Yapılandırma (Arayüzden bağımsız çalıştığı için buraya sabitliyoruz veya bir config dosyasından çekebilirsin)
TARGET_IP = "10.35.14.10"
TARGET_PORT = 502
REFRESH_RATE = 10  # Kaç saniyede bir veri çekilsin?
SLAVE_IDS = [1, 2 ,3] # İzlenecek cihazlar

# Modbus Adres Haritası (panel.py ile aynı)
CONFIG = {
    'guc_addr': 70, 'guc_scale': 1.0,
    'volt_addr': 71, 'volt_scale': 0.1,
    'akim_addr': 72, 'akim_scale': 0.1,
    'isi_addr': 73, 'isi_scale': 1.0
}

def read_device(client, slave_id):
    try:
        if not client.connected: 
            client.connect()
        
        # GÜNCEL PYMODBUS v3.x Yazımı:
        # İlk argüman adres, ikinci argüman adet (count), slave ise keyword olarak verilmelidir.
        r_guc = client.read_holding_registers(CONFIG['guc_addr'], count=1, slave=slave_id)
        r_volt = client.read_holding_registers(CONFIG['volt_addr'], count=1, slave=slave_id)
        r_akim = client.read_holding_registers(CONFIG['akim_addr'], count=1, slave=slave_id)
        r_isi = client.read_holding_registers(CONFIG['isi_addr'], count=1, slave=slave_id)

        # Hata kontrolü (Pymodbus hata nesnesi dönerse)
        if r_guc.isError(): 
            return None

        return {
            "guc": r_guc.registers[0] * CONFIG['guc_scale'],
            "voltaj": r_volt.registers[0] * CONFIG['volt_scale'],
            "akim": r_akim.registers[0] * CONFIG['akim_scale'],
            "sicaklik": r_isi.registers[0] * CONFIG['isi_scale']
        }
    except Exception as e:
        logging.error(f"ID {slave_id} okuma hatası: {e}")
        return None

        return {
            "guc": r_guc.registers[0] * CONFIG['guc_scale'],
            "voltaj": r_volt.registers[0] * CONFIG['volt_scale'],
            "akim": r_akim.registers[0] * CONFIG['akim_scale'],
            "sicaklik": r_isi.registers[0] * CONFIG['isi_scale']
        }
    except Exception as e:
        logging.error(f"ID {slave_id} okuma hatası: {e}")
        return None

def start_collector():
    veritabani.init_db()
    client = ModbusTcpClient(TARGET_IP, port=TARGET_PORT)
    logging.info(f"Collector başlatıldı: {TARGET_IP}:{TARGET_PORT}")

    while True:
        start_time = time.time()
        for dev_id in SLAVE_IDS:
            data = read_device(client, dev_id)
            if data:
                veritabani.veri_ekle(dev_id, data)
                print(f"[{datetime.now().strftime('%H:%M:%S')}] ID {dev_id} verisi kaydedildi.")
        
        # Refresh rate'den geçen süreyi çıkararak hassas bekleme yap
        elapsed = time.time() - start_time
        wait = max(0, REFRESH_RATE - elapsed)
        time.sleep(wait)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    start_collector()
