import sqlite3
from datetime import datetime
import json
import time

DB_NAME = "solar_log.db"

# --- YARDIMCI: GÜVENLİ BAĞLANTI ---
def get_connection():
    """
    Veritabanı kilitlenme hatalarını önlemek için timeout süresini uzatır.
    Backend ve Frontend aynı anda eriştiğinde biri diğerini 30 saniye bekler.
    """
    return sqlite3.connect(DB_NAME, timeout=30, check_same_thread=False)

def init_db():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # 1. Ölçüm Tablosu
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS olcumler (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slave_id INTEGER, 
                zaman TIMESTAMP,
                guc REAL,
                voltaj REAL,
                akim REAL,
                sicaklik REAL
            )
        ''')
        
        # Endeksleme (Sorguları hızlandırır)
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_slave_zaman ON olcumler(slave_id, zaman)')

        # 2. Ayarlar Tablosu
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ayarlar (
                anahtar TEXT PRIMARY KEY,
                deger TEXT
            )
        ''')
        
        # Varsayılan ayarları yükle
        default_config = {
            "ip": "10.35.14.10",
            "port": 502,
            "ids": "1",
            "refresh": 30,
            "modbus_config": json.dumps({
                'guc_addr': 16, 'guc_scale': 1.0,
                'volt_addr': 0, 'volt_scale': 0.1,
                'akim_addr': 1, 'akim_scale': 0.1,
                'isi_addr': 4, 'isi_scale': 1.0
            })
        }
        
        for k, v in default_config.items():
            cursor.execute("INSERT OR IGNORE INTO ayarlar (anahtar, deger) VALUES (?, ?)", (k, str(v)))

        conn.commit()
        conn.close()
    except Exception as e:
        print(f"DB Init Hatası: {e}")

def veri_ekle(slave_id, veri_sozlugu):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO olcumler (slave_id, zaman, guc, voltaj, akim, sicaklik)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (slave_id, datetime.now(), veri_sozlugu['guc'], veri_sozlugu['voltaj'], veri_sozlugu['akim'], veri_sozlugu['sicaklik']))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Veri Ekleme Hatası: {e}")

def son_verileri_getir(slave_id, limit=100):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        # SQL Injection koruması için f-string yerine ? parametresi kullanıldı
        cursor.execute('SELECT zaman, guc, voltaj, akim, sicaklik FROM olcumler WHERE slave_id = ? ORDER BY zaman DESC LIMIT ?', (slave_id, limit))
        rows = cursor.fetchall()
        conn.close()
        return rows[::-1] # Grafikler için tersten (eskiden yeniye) sırala
    except:
        return []

def tum_cihazlarin_son_durumu():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        # Her cihazın en son eklenen kaydını getirir
        # NOT: SQLite'da MAX(zaman) ile gruplamak, o satıra ait diğer verileri de getirir.
        query = """
            SELECT slave_id, MAX(zaman) as son_zaman, guc, voltaj, akim, sicaklik 
            FROM olcumler 
            GROUP BY slave_id 
            ORDER BY slave_id ASC
        """
        cursor.execute(query)
        rows = cursor.fetchall()
        conn.close()
        return rows
    except:
        return []

# --- AYAR YÖNETİMİ ---
def get_ayar(anahtar):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT deger FROM ayarlar WHERE anahtar=?", (anahtar,))
        res = cursor.fetchone()
        conn.close()
        return res[0] if res else None
    except:
        return None

def set_ayar(anahtar, deger):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO ayarlar (anahtar, deger) VALUES (?, ?)", (anahtar, str(deger)))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Ayar Kayıt Hatası: {e}")