import sqlite3
from datetime import datetime

DB_NAME = "solar_log.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # 1. Tabloyu Oluştur (Temel Sütunlar)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS olcumler (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slave_id INTEGER, 
            zaman TIMESTAMP,
            guc REAL,
            voltaj REAL,
            akim REAL,
            sicaklik REAL,
            hata_kodu INTEGER DEFAULT 0,      -- Register 189 (Eski Adı Koruduk)
            hata_kodu_193 INTEGER DEFAULT 0   -- Register 193 (YENİ)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ayarlar (
            anahtar TEXT PRIMARY KEY,
            deger TEXT
        )
    ''')

    # 2. MIGRATION (Eski veritabanına yeni sütunu ekle)
    mevcut_sutunlar = [row[1] for row in cursor.execute("PRAGMA table_info(olcumler)")]
    
    if 'hata_kodu_193' not in mevcut_sutunlar:
        print("⚠️ Tablo güncelleniyor: 'hata_kodu_193' sütunu ekleniyor...")
        cursor.execute("ALTER TABLE olcumler ADD COLUMN hata_kodu_193 INTEGER DEFAULT 0")
        
    conn.commit()
    conn.close()

def veri_ekle(slave_id, data):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    simdi = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')
    
    # Verileri sözlükten al (Yoksa 0 yaz)
    hk_189 = data.get('hata_kodu', 0)
    hk_193 = data.get('hata_kodu_193', 0)

    cursor.execute('''
        INSERT INTO olcumler (slave_id, zaman, guc, voltaj, akim, sicaklik, hata_kodu, hata_kodu_193)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (slave_id, simdi, data['guc'], data['voltaj'], data['akim'], data['sicaklik'], hk_189, hk_193))
    
    conn.commit()
    conn.close()

def son_verileri_getir(slave_id, limit=100):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(f'''
        SELECT zaman, guc, voltaj, akim, sicaklik, hata_kodu, hata_kodu_193
        FROM olcumler 
        WHERE slave_id = {slave_id}
        ORDER BY zaman DESC 
        LIMIT {limit}
    ''')
    rows = cursor.fetchall()
    conn.close()
    return rows[::-1]

def tum_cihazlarin_son_durumu():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    # Hata kodlarını (189 ve 193) çekiyoruz
    cursor.execute('''
        SELECT slave_id, MAX(zaman) as son_zaman, guc, voltaj, akim, sicaklik, hata_kodu, hata_kodu_193
        FROM olcumler
        GROUP BY slave_id
        ORDER BY slave_id ASC
    ''')
    rows = cursor.fetchall()
    conn.close()
    return rows

def db_temizle():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute('DELETE FROM olcumler')
        conn.commit()
        return True
    except: return False
    finally: conn.close()