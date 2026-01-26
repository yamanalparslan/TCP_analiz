import sqlite3
from datetime import datetime, timedelta
import json
import time

DB_NAME = "solar_log.db"

# --- GÜVENLİ BAĞLANTI (Timeout Korumalı) ---
def get_connection():
    return sqlite3.connect(DB_NAME, timeout=30, check_same_thread=False)

def init_db():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Tabloları oluştur
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS olcumler (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slave_id INTEGER, 
                zaman TIMESTAMP,
                guc REAL, voltaj REAL, akim REAL, sicaklik REAL
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_zaman ON olcumler(zaman)')
        
        cursor.execute('CREATE TABLE IF NOT EXISTS ayarlar (anahtar TEXT PRIMARY KEY, deger TEXT)')
        
        # Varsayılan ayarlar
        default_config = {
            "ip": "10.35.14.10", "port": 502, "ids": "1", "refresh": 30,
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
    except: pass

def veri_ekle(slave_id, data):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO olcumler (slave_id, zaman, guc, voltaj, akim, sicaklik)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (slave_id, datetime.now(), data['guc'], data['voltaj'], data['akim'], data['sicaklik']))
        conn.commit()
        conn.close()
    except: pass

def tum_cihazlarin_son_durumu():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT slave_id, MAX(zaman), guc, voltaj, akim, sicaklik FROM olcumler GROUP BY slave_id ORDER BY slave_id ASC")
        rows = cursor.fetchall()
        conn.close()
        return rows
    except: return []

# --- YENİ EKLENEN FONKSİYON: GEÇMİŞ VERİ ANALİZİ ---
def gecmis_verileri_getir(slave_id, saat=1):
    """
    Belirtilen saat kadar geriye gidip verileri çeker.
    Örn: saat=24 ise son 1 günü getirir.
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Başlangıç zamanını hesapla
        baslangic = datetime.now() - timedelta(hours=saat)
        
        # O tarihten bu yana olan tüm verileri çek (Eskiden yeniye sıralı)
        cursor.execute('''
            SELECT zaman, guc, voltaj, akim, sicaklik 
            FROM olcumler 
            WHERE slave_id = ? AND zaman >= ? 
            ORDER BY zaman ASC
        ''', (slave_id, baslangic))
        
        rows = cursor.fetchall()
        conn.close()
        return rows
    except Exception as e:
        print(f"DB Hatası: {e}")
        return []

def get_ayar(k):
    try:
        conn = get_connection()
        res = conn.execute("SELECT deger FROM ayarlar WHERE anahtar=?", (k,)).fetchone()
        conn.close()
        return res[0] if res else None
    except: return None

def set_ayar(k, v):
    try:
        conn = get_connection()
        conn.execute("INSERT OR REPLACE INTO ayarlar (anahtar, deger) VALUES (?, ?)", (k, str(v)))
        conn.commit()
        conn.close()
    except: pass