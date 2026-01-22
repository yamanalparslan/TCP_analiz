from pymodbus.client import ModbusTcpClient
import time

GATEWAY_IP = '10.35.14.10'  

GATEWAY_PORT = 502  

SLAVE_ID = 1 

def baglanti_testi():
    print("-" * 40)
    print(f"Hedef IP: {GATEWAY_IP}")
    print(f"Hedef Port: {GATEWAY_PORT}")
    print("Baglanti deneniyor...")
    print("-" * 40)

    # İstemciyi (Client) oluştur
    client = ModbusTcpClient(GATEWAY_IP, port=GATEWAY_PORT)

    # Bağlanmayı dene
    baglanti_durumu = client.connect()

    if baglanti_durumu:
        print("✅ BASARILI: Cihaza (WaveShare) bağlantı sağlandı!")
        
        # Test okuması yapalım (Adres 0'dan 10 adet register okuyalım)
        try:
            print("Veri okunuyor...")
            okunan = client.read_holding_registers(address=0, count=10, slave=SLAVE_ID)
            
            if not okunan.isError():
                print(f"📡 OKUNAN DEĞERLER: {okunan.registers}")
                print("Haberleşme zinciri (PC -> WaveShare -> Inverter) tamamen çalışıyor.")
            else:
                print("⚠️ UYARI: WaveShare'e bağlandık ama Inverter cevap vermedi.")
                print("Olası Sebepler:")
                print("1. Slave ID yanlış olabilir (SLAVE_ID değişkenini değiştir).")
                print("2. RS485 kabloları (A ve B) ters bağlanmış olabilir.")
                print(f"Hata Kodu: {okunan}")

        except Exception as e:
            print(f"Okuma sırasında hata oluştu: {e}")
            
        finally:
            client.close()
            print("Bağlantı kapatıldı.")
    else:
        print("❌ BAŞARISIZ: IP adresine ulaşılamadı.")
        print("Lütfen IP adresini ve bilgisayarının aynı ağda olduğunu kontrol et.")

if __name__ == "__main__":
    baglanti_testi()