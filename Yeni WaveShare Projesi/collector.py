import time
import json
import sys
from pymodbus.client import ModbusTcpClient
import veritabani

# Veritabanı bağlantı kontrolü
try:
    veritabani.init_db()
    print("✅ Collector: Veritabanı Hazır.")
except Exception as e:
    print(f"🔥 Collector Başlatılamadı: {e}")
    sys.exit(1)

def run_daemon():
    print("🚀 Solar Collector: Hassas Zamanlayıcı Modu Devrede...", flush=True)
    
    while True:
        # ⏱️ DÖNGÜ BAŞLANGIÇ ZAMANI (Kronometreye Bas)
        loop_start_time = time.time()
        
        try:
            # 1. AYARLARI VERİTABANINDAN AL (Her turda güncel ayarı okur)
            target_ip = veritabani.get_ayar("ip")
            target_port = int(veritabani.get_ayar("port"))
            
            # Panelden girilen saniyeyi al (En az 2 sn güvenlik limiti)
            raw_refresh = int(veritabani.get_ayar("refresh"))
            target_interval = max(raw_refresh, 2) 

            # ID Listesini Çöz
            id_str = veritabani.get_ayar("ids")
            ids = set()
            for part in str(id_str).split(','):
                part = part.strip()
                if '-' in part:
                    try:
                        s, e = map(int, part.split('-'))
                        ids.update(range(s, e + 1))
                    except: pass
                elif part:
                    try:
                        ids.add(int(part))
                    except: pass
            target_ids = sorted(list(ids))
            
            # Modbus Ayarları
            conf = json.loads(veritabani.get_ayar("modbus_config"))

            print(f"📡 Bağlanıyor: {target_ip}:{target_port} | Hedef Süre: {target_interval}sn", flush=True)

            # 2. CİHAZLARA BAĞLAN
            # Timeout süresini kısa tutuyoruz ki bir cihaz bozuksa diğerlerini bekletmesin
            client = ModbusTcpClient(target_ip, port=target_port, timeout=2)
            
            if client.connect():
                for slave_id in target_ids:
                    try:
                        # Önce Holding Register dene (Standart)
                        r_guc = client.read_holding_registers(address=conf['guc_addr'], count=1, slave=slave_id)
                        
                        # Holding hata verirse Input Register dene
                        read_func = client.read_holding_registers
                        if r_guc.isError():
                            read_func = client.read_input_registers
                            r_guc = read_func(address=conf['guc_addr'], count=1, slave=slave_id)

                        if not r_guc.isError():
                            # Değerleri Al ve Çarp
                            val_guc = r_guc.registers[0] * conf['guc_scale']
                            
                            r_volt = read_func(address=conf['volt_addr'], count=1, slave=slave_id)
                            val_volt = r_volt.registers[0] * conf['volt_scale'] if not r_volt.isError() else 0
                            
                            r_akim = read_func(address=conf['akim_addr'], count=1, slave=slave_id)
                            val_akim = r_akim.registers[0] * conf['akim_scale'] if not r_akim.isError() else 0
                            
                            r_isi = read_func(address=conf['isi_addr'], count=1, slave=slave_id)
                            val_isi = r_isi.registers[0] * conf['isi_scale'] if not r_isi.isError() else 0

                            # DB'ye Yaz
                            veritabani.veri_ekle(slave_id, {
                                "guc": val_guc, "voltaj": val_volt, "akim": val_akim, "sicaklik": val_isi
                            })
                            print(f"   ✅ ID {slave_id} OKUNDU -> Güç: {val_guc} W", flush=True)
                        else:
                            print(f"   ⚠️ ID {slave_id} Cevap Vermiyor.", flush=True)

                    except Exception as e:
                        print(f"   🔥 ID {slave_id} Okuma Hatası: {e}", flush=True)
                
                client.close()
            else:
                print(f"❌ Bağlantı Hatası: {target_ip} adresine ulaşılamıyor.", flush=True)

        except Exception as main_e:
            print(f"🔥 Genel Döngü Hatası: {main_e}", flush=True)

        # 3. HASSAS ZAMANLAMA (MATEMATİK)
        # İşlemlerin ne kadar sürdüğünü hesapla
        elapsed_time = time.time() - loop_start_time
        
        # Hedef süreden geçen süreyi çıkar
        sleep_time = target_interval - elapsed_time
        
        if sleep_time > 0:
            print(f"💤 İşlem {elapsed_time:.2f}sn sürdü. Tam zamanında olması için {sleep_time:.2f}sn uyunuyor...", flush=True)
            time.sleep(sleep_time)
        else:
            # Eğer işlem, hedef süreden daha uzun sürdüyse (örn: 5sn istedin ama okuma 7sn sürdü)
            print(f"⚠️ DİKKAT: Okuma işlemi ({elapsed_time:.2f}sn), hedef süreden ({target_interval}sn) uzun sürdü! Hiç beklemeden devam ediliyor.", flush=True)

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding='utf-8')
    run_daemon()