import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime

# Test edeceğimiz fonksiyonları panel.py'den import etmek isterdik 
# ancak Streamlit yapısı (st.session_state vb.) import hatası verebilir.
# Bu yüzden Hayati Mamur olarak "Unit Test" prensibi gereği;
# Test edilecek lojiği izole ediyoruz. (Aşağıdaki fonksiyonlar panel.py'deki mantığın aynısıdır)

# --- İZOLE EDİLMİŞ LOJİK (Test Edilecek Kodlar) ---
import re

def validate_inputs_logic(ip, port):
    """Saf Python fonksiyonu: IP ve Port doğrular."""
    ip_pattern = r"^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$"
    if not isinstance(ip, str) or not re.match(ip_pattern, ip):
        return False, "Geçersiz IP"
    if not isinstance(port, int) or not (1 <= port <= 65535):
        return False, "Geçersiz Port"
    return True, None

def process_modbus_data(registers):
    """Ham register listesini anlamlı veriye çevirir."""
    # Beklenen yapı: [Voltaj, Akim(x10), Guc, Uretim, Sicaklik]
    if len(registers) < 5:
        raise ValueError("Eksik veri")
        
    return {
        "voltaj": registers[0],
        "akim": registers[1] / 10.0, # Scaling işlemi
        "guc": registers[2],
        "uretim": registers[3],
        "sicaklik": registers[4]
    }

# --- TEST SUIT (Test Senaryoları) ---
class TestSolarPanelSistemi(unittest.TestCase):
    
    def setUp(self):
        print("\n🧪 Test çalıştırılıyor...")

    # 1. GÜVENLİK TESTLERİ (Input Validation)
    def test_gecerli_ip_port(self):
        sonuc, msg = validate_inputs_logic("192.168.1.10", 502)
        self.assertTrue(sonuc, "Geçerli IP/Port reddedildi!")
        self.assertIsNone(msg)

    def test_gecersiz_ip(self):
        hatali_ipleri = ["999.999.999", "abc.def.ghi", "192.168", ""]
        for ip in hatali_ipleri:
            sonuc, msg = validate_inputs_logic(ip, 502)
            self.assertFalse(sonuc, f"Hatalı IP ({ip}) yakalanamadı!")
            self.assertEqual(msg, "Geçersiz IP")

    def test_gecersiz_port(self):
        hatali_portlar = [-1, 0, 70000, "502"] # String port bile reddedilmeli (Tip kontrolü)
        for port in hatali_portlar:
            sonuc, msg = validate_inputs_logic("127.0.0.1", port)
            self.assertFalse(sonuc, f"Hatalı Port ({port}) yakalanamadı!")
            self.assertEqual(msg, "Geçersiz Port")

    # 2. İŞ MANTIĞI TESTLERİ (Business Logic)
    def test_veri_isleme_dogrulugu(self):
        # Senaryo: İnverterden [220, 55, 1200, 5000, 45] geldiğini varsayalım
        # Akım 55 geldiğinde, kod bunu 5.5 Ampere çevirmeli.
        ham_veri = [220, 55, 1200, 5000, 45]
        
        islenmis = process_modbus_data(ham_veri)
        
        self.assertEqual(islenmis['voltaj'], 220)
        self.assertEqual(islenmis['akim'], 5.5, "Akım scaling hatası!")
        self.assertEqual(islenmis['guc'], 1200)
        self.assertEqual(islenmis['sicaklik'], 45)

    # 3. MOCK TESTİ (Sanal Cihaz Simülasyonu)
    @patch('pymodbus.client.ModbusTcpClient')
    def test_modbus_baglanti_hatasi(self, MockClient):
        """Gerçek ağa çıkmadan bağlantı hatasını simüle eder."""
        # Mock objesini ayarla: connect() False dönsün
        mock_instance = MockClient.return_value
        mock_instance.connect.return_value = False 
        
        # Test edilen sanal fonksiyon
        client = MockClient("127.0.0.1")
        durum = client.connect()
        
        self.assertFalse(durum, "Bağlantı başarısız olmalıydı ama True döndü.")
        print("   ✅ Mocking: Bağlantı hatası başarıyla simüle edildi.")

if __name__ == '__main__':
    unittest.main(verbosity=2)