import sqlite3
from datetime import datetime

DB_NAME = "solar_log.db"

def init_db():
    """Veritabanı tablosunu ve gerekli sütunları oluşturur."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # DİKKAT: 'slave_id' sütunu eklendi. Artık her verinin kime ait olduğunu biliyoruz.
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
    conn.commit()
    conn.close()

def veri_ekle(slave_id, veri_sozlugu):
    """
    Belirtilen Slave ID (Inverter) için gelen veriyi kaydeder.
    Örn: veri_ekle(1, {...}) -> 1 numaralı inverterin verisi kaydedilir.
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO olcumler (slave_id, zaman, guc, voltaj, akim, sicaklik)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (
        slave_id,
        datetime.now(), 
        veri_sozlugu['guc'],
        veri_sozlugu['voltaj'],
        veri_sozlugu['akim'],
        veri_sozlugu['sicaklik']
    ))
    conn.commit()
    conn.close()

def son_verileri_getir(slave_id, limit=100):
    """
    SADECE panelde seçilen (Dropdown'dan seçilen) cihazın geçmiş verilerini getirir.
    Grafiklerin birbirine karışmasını engeller.
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute(f'''
        SELECT zaman, guc, voltaj, akim, sicaklik 
        FROM olcumler 
        WHERE slave_id = {slave_id}
        ORDER BY zaman DESC 
        LIMIT {limit}
    ''')
    
    rows = cursor.fetchall()
    conn.close()
    
    # Grafiğin soldan sağa akması için veriyi ters çeviriyoruz
    return rows[::-1]

def tum_cihazlarin_son_durumu():
    """
    Ana ekrandaki 'Canlı Filo Durumu' tablosu için 
    her bir inverterin gönderdiği EN SON veriyi çeker.
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # SQL Group By ile her slave_id'nin MAX(zaman) yani son kaydını alıyoruz
    cursor.execute('''
        SELECT slave_id, MAX(zaman) as son_zaman, guc, voltaj, akim, sicaklik
        FROM olcumler
        GROUP BY slave_id
        ORDER BY slave_id ASC
    ''')
    
    rows = cursor.fetchall()
    conn.close()
    return rows