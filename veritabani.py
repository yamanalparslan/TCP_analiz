import sqlite3
from datetime import datetime

DB_NAME = "solar_log.db"

def init_db():
    """Veritabanı tablosunu ve gerekli sütunları oluşturur."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # 1. Tabloyu Oluştur (Eğer hiç yoksa)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS olcumler (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slave_id INTEGER, 
            zaman TIMESTAMP,
            guc REAL,
            voltaj REAL,
            akim REAL,
            sicaklik REAL,
            hata_kodu INTEGER DEFAULT 0
        )
    ''')

    # 2. Ayarlar Tablosu (Limitler vb. için)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ayarlar (
            anahtar TEXT PRIMARY KEY,
            deger TEXT
        )
    ''')

    # 3. MIGRATION (GÖÇ) MANTIĞI:
    # Eğer eski veritabanı kullanılıyorsa 'hata_kodu' sütunu eksik olabilir.
    # Bunu kontrol edip yoksa ekliyoruz.
    try:
        cursor.execute("SELECT hata_kodu FROM olcumler LIMIT 1")
    except sqlite3.OperationalError:
        print("⚠️ Eski tablo yapısı tespit edildi. 'hata_kodu' sütunu ekleniyor...")
        cursor.execute("ALTER TABLE olcumler ADD COLUMN hata_kodu INTEGER DEFAULT 0")
        conn.commit()
        print("✅ Veritabanı başarıyla güncellendi.")

    conn.commit()
    conn.close()

def veri_ekle(slave_id, veri_sozlugu):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    simdi = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')
    
    # Eğer veri sözlüğünde hata kodu yoksa 0 (Hatasız) kabul et
    gelen_hata_kodu = veri_sozlugu.get('hata_kodu', 0)

    cursor.execute('''
        INSERT INTO olcumler (slave_id, zaman, guc, voltaj, akim, sicaklik, hata_kodu)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (
        slave_id,
        simdi, 
        veri_sozlugu['guc'],
        veri_sozlugu['voltaj'],
        veri_sozlugu['akim'],
        veri_sozlugu['sicaklik'],
        gelen_hata_kodu
    ))
    conn.commit()
    conn.close()

def son_verileri_getir(slave_id, limit=100):
    """
    SADECE panelde seçilen cihazın geçmiş verilerini getirir.
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Hata kodunu da çekelim (Grafiklerde kullanılmasa bile veri bütünlüğü için)
    cursor.execute(f'''
        SELECT zaman, guc, voltaj, akim, sicaklik, hata_kodu
        FROM olcumler 
        WHERE slave_id = {slave_id}
        ORDER BY zaman DESC 
        LIMIT {limit}
    ''')
    
    rows = cursor.fetchall()
    conn.close()
    
    return rows[::-1]

def tum_cihazlarin_son_durumu():
    """
    Ana ekrandaki 'Canlı Filo Durumu' ve 'Alarm Sistemi' için 
    son durumu (Hata Kodu dahil) çeker.
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # DİKKAT: row[6] artık hata_kodu olacak
    cursor.execute('''
        SELECT slave_id, MAX(zaman) as son_zaman, guc, voltaj, akim, sicaklik, hata_kodu
        FROM olcumler
        GROUP BY slave_id
        ORDER BY slave_id ASC
    ''')
    
    rows = cursor.fetchall()
    conn.close()
    return rows

def db_temizle():
    """Tüm ölçüm verilerini siler."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute('DELETE FROM olcumler')
        conn.commit()
        return True
    except Exception as e:
        print(f"Silme hatası: {e}")
        return False
    finally:
        conn.close()

# --- ESKİ ALARM FONKSİYONLARI (Geriye Dönük Uyumluluk İçin Kalsın) ---
def alarm_limitlerini_getir():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT anahtar, deger FROM ayarlar")
    ayarlar = dict(cursor.fetchall())
    conn.close()
    
    return {
        "max_isi": float(ayarlar.get('max_isi', 60.0)),
        "max_volt": float(ayarlar.get('max_volt', 250.0)),
        "max_akim": float(ayarlar.get('max_akim', 15.0))
    }

def alarm_limit_guncelle(anahtar, deger):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO ayarlar (anahtar, deger) VALUES (?, ?)", (anahtar, str(deger)))
    conn.commit()
    conn.close()