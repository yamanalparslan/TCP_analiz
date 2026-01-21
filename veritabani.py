import sqlite3
from datetime import datetime

DB_NAME = "solar_log.db"

def init_db():
    """Veritabanı tablosunu oluşturur (Eğer yoksa)"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    # Zaman, Güç, Voltaj, Akım, Sıcaklık
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS olcumler (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            zaman TIMESTAMP,
            guc REAL,
            voltaj REAL,
            akim REAL,
            sicaklik REAL
        )
    ''')
    conn.commit()
    conn.close()

def veri_ekle(veri_sozlugu):
    """Gelen veri paketini veritabanına yazar."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO olcumler (zaman, guc, voltaj, akim, sicaklik)
        VALUES (?, ?, ?, ?, ?)
    ''', (
        datetime.now(), 
        veri_sozlugu['guc'],
        veri_sozlugu['voltaj'],
        veri_sozlugu['akim'],
        veri_sozlugu['sicaklik']
    ))
    
    conn.commit()
    conn.close()

def son_verileri_getir(limit=100):
    """Grafik için son N kaydı çeker (Tüm parametreler dahil)."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # GÜNCELLEME: voltaj ve akim sütunlarını da SELECT sorgusuna ekledik
    cursor.execute(f'''
        SELECT zaman, guc, voltaj, akim, sicaklik 
        FROM olcumler 
        ORDER BY zaman DESC 
        LIMIT {limit}
    ''')
    
    rows = cursor.fetchall()
    conn.close()
    
    # Veriyi ters çevir (Eskiden yeniye grafik çizimi için)
    return rows[::-1]