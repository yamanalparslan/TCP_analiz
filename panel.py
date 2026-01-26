import streamlit as st
import time
import pandas as pd
import re
import html
from datetime import datetime
from pymodbus.client import ModbusTcpClient
import veritabani 

# --- SAYFA AYARLARI ---
st.set_page_config(
    page_title="Solar Multi-Monitor",
    layout="wide",
    page_icon="🏭",
    initial_sidebar_state="expanded"
)

# DB Başlat
veritabani.init_db()

# --- CSS TASARIMI ---
st.markdown("""
<style>
    .stApp { background-color: #0E1117; color: #E0E0E0; }
    div[data-testid="stMetric"] {
        background-color: #1E1E1E; border: 1px solid #333;
        padding: 10px; border-radius: 8px;
    }
    .chart-title {
        font-size: 1rem; font-weight: 700; margin-bottom: 0px;
        padding: 5px 10px; border-radius: 5px 5px 0 0; display: inline-block; width: 100%;
    }
</style>
""", unsafe_allow_html=True)

# --- YARDIMCI FONKSİYONLAR ---
def parse_id_list(id_string):
    """ '1, 2, 3-5' şeklindeki stringi [1, 2, 3, 4, 5] listesine çevirir. """
    ids = set()
    parts = id_string.split(',')
    for part in parts:
        part = part.strip()
        if '-' in part:
            try:
                start, end = map(int, part.split('-'))
                for i in range(start, end + 1):
                    ids.add(i)
            except: pass
        else:
            try:
                ids.add(int(part))
            except: pass
    return sorted(list(ids))

@st.cache_resource
def get_modbus_client(ip, port):
    return ModbusTcpClient(ip, port=port, timeout=1) 

def read_device(client, slave_id, config):
    """Tek bir cihazdan veri okur"""
    try:
        if not client.connected: client.connect()
        
        # GÜÇ
        r_guc = client.read_holding_registers(config['guc_addr'], 1, slave=slave_id)
        if r_guc.isError(): return None, "No Response"
        val_guc = r_guc.registers[0] * config['guc_scale']

        # VOLTAJ
        r_volt = client.read_holding_registers(config['volt_addr'], 1, slave=slave_id)
        val_volt = 0 if r_volt.isError() else r_volt.registers[0] * config['volt_scale']

        # AKIM
        r_akim = client.read_holding_registers(config['akim_addr'], 1, slave=slave_id)
        val_akim = 0 if r_akim.isError() else r_akim.registers[0] * config['akim_scale']

        # SICAKLIK
        r_isi = client.read_holding_registers(config['isi_addr'], 1, slave=slave_id)
        val_isi = 0 if r_isi.isError() else r_isi.registers[0] * config['isi_scale']

        return {
            "slave_id": slave_id,
            "guc": val_guc,
            "voltaj": val_volt,
            "akim": val_akim,
            "sicaklik": val_isi,
            "timestamp": datetime.now()
        }, None

    except Exception as e:
        return None, str(e)

# --- STATE ---
if 'monitoring' not in st.session_state: st.session_state.monitoring = False

# --- YAN MENÜ ---
with st.sidebar:
    st.header("🏭 PULSAR Ayarları")
    target_ip = st.text_input("IP Adresi", value="10.35.14.10")
    target_port = st.number_input("Port", value=502, step=1)
    
    st.info("Virgül veya tire ile ayırın (Örn: 1, 2, 5-8)")
    id_input = st.text_input("İnverter ID Listesi", value="1, 2")
    target_ids = parse_id_list(id_input)
    st.write(f"📡 İzlenecek ID'ler: {target_ids}")
    
    st.divider()
    
    # --- YENİ EKLENEN KISIM: ZAMANLAYICI AYARI ---
    st.header("⏳ Zamanlayıcı")
    refresh_rate = st.number_input("Veri Çekme Sıklığı (Saniye)", value=30, min_value=1, step=1, help="Sistem bu süre kadar bekleyip sonra tekrar veri çeker.")
    
    st.markdown("---")
    st.header("🗺️ Adres Haritası")
    with st.expander("Detaylı Adres Ayarları"):
        c_guc_adr = st.number_input("Güç Adresi", value=70)
        c_guc_sc = st.number_input("Güç Çarpan", value=1.0)
        c_volt_adr = st.number_input("Voltaj Adresi", value=71)
        c_volt_sc = st.number_input("Voltaj Çarpan", value=0.1)
        c_akim_adr = st.number_input("Akım Adresi", value=72)
        c_akim_sc = st.number_input("Akım Çarpan", value=0.1)
        c_isi_adr = st.number_input("Isı Adresi", value=73)
        c_isi_sc = st.number_input("Isı Çarpan", value=1.0)
    
    config = {
        'guc_addr': c_guc_adr, 'guc_scale': c_guc_sc,
        'volt_addr': c_volt_adr, 'volt_scale': c_volt_sc,
        'akim_addr': c_akim_adr, 'akim_scale': c_akim_sc,
        'isi_addr': c_isi_adr, 'isi_scale': c_isi_sc
    }

    if st.button("▶️ SİSTEMİ BAŞLAT", type="primary"):
        st.session_state.monitoring = True
        st.rerun()
    if st.button("⏹️ DURDUR"):
        st.session_state.monitoring = False
        st.rerun()

# --- ANA EKRAN ---
st.title("⚡ Güneş Enerjisi Santrali İzleme")

st.subheader("📋 Canlı Filo Durumu")
table_spot = st.empty()

st.markdown("---")
col_sel, col_info = st.columns([1, 3])
with col_sel:
    selected_id = st.selectbox("📊 Detaylı Grafik İçin Cihaz Seç:", target_ids)

# Grafik Yer Tutucuları
row1_c1, row1_c2 = st.columns(2)
row2_c1, row2_c2 = st.columns(2)

with row1_c1:
    st.markdown(f'<div class="chart-title" style="background:#332a00; color:#FFD700;">☀️ ID:{selected_id} - Güç</div>', unsafe_allow_html=True)
    chart_guc = st.empty()
with row1_c2:
    st.markdown(f'<div class="chart-title" style="background:#001e33; color:#29B6F6;">⚡ ID:{selected_id} - Voltaj</div>', unsafe_allow_html=True)
    chart_volt = st.empty()
with row2_c1:
    st.markdown(f'<div class="chart-title" style="background:#0a260e; color:#66BB6A;">ww ID:{selected_id} - Akım</div>', unsafe_allow_html=True)
    chart_akim = st.empty()
with row2_c2:
    st.markdown(f'<div class="chart-title" style="background:#2e0a0a; color:#EF5350;">🌡️ ID:{selected_id} - Sıcaklık</div>', unsafe_allow_html=True)
    chart_isi = st.empty()

# --- DURUM ÇUBUĞU ---
status_bar = st.empty()

def ui_refresh():
    summary_data = veritabani.tum_cihazlarin_son_durumu()
    if summary_data:
        df_sum = pd.DataFrame(summary_data, columns=["ID", "Son Zaman", "Güç (W)", "Voltaj (V)", "Akım (A)", "Isı (C)"])
        df_sum["Son Zaman"] = pd.to_datetime(df_sum["Son Zaman"]).dt.strftime('%H:%M:%S')
        table_spot.dataframe(df_sum.set_index("ID"), use_container_width=True)

    detail_data = veritabani.son_verileri_getir(selected_id, limit=100)
    if detail_data:
        df_det = pd.DataFrame(detail_data, columns=["timestamp", "guc", "voltaj", "akim", "sicaklik"])
        df_det["timestamp"] = pd.to_datetime(df_det["timestamp"])
        df_det = df_det.set_index("timestamp")
        
        chart_guc.line_chart(df_det["guc"], color="#FFD700")
        chart_volt.line_chart(df_det["voltaj"], color="#29B6F6")
        chart_akim.line_chart(df_det["akim"], color="#66BB6A")
        chart_isi.line_chart(df_det["sicaklik"], color="#EF5350")

# --- ANA DÖNGÜ ---
if st.session_state.monitoring:
    client = get_modbus_client(target_ip, target_port)
    status_bar.success(f"✅ Sistem Aktif - {refresh_rate} saniyede bir güncelleniyor.")
    
    while True:
        # 1. TÜM CİHAZLARI TARA
        for dev_id in target_ids:
            data, err = read_device(client, dev_id, config)
            if data:
                veritabani.veri_ekle(dev_id, data)
            else:
                print(f"Hata ID {dev_id}: {err}")
        
        # 2. EKRANI GÜNCELLE
        ui_refresh()
        
        # 3. BELİRLENEN SÜRE KADAR BEKLE
        # Kullanıcı arayüzünde takılma olmasın diye küçük parçalar halinde bekle
        for i in range(refresh_rate):
            # Eğer bekleme sırasında kullanıcı "Durdur"a basarsa anında çık
            if not st.session_state.monitoring:
                break
            time.sleep(1)
            

            # --- VERİTABANI YÖNETİMİ ---
st.sidebar.markdown("### Veri Yönetimi")
if st.sidebar.button("🗑️ Tüm Verileri Sil", help="Veritabanındaki tüm ölçüm geçmişini temizler."):
    if veritabani.db_temizle():
        st.sidebar.success("Veritabanı başarıyla temizlendi!")
        time.sleep(1)
        st.rerun()
    else:
        st.sidebar.error("Silme işlemi başarısız oldu.")


        # --- ANA DÖNGÜ (Collector artık dışarıda çalıştığı için burası sadece UI yeniler) ---
if st.session_state.monitoring:
    status_bar.success(f"✅ İzleme Modu Aktif - Veritabanı güncellendikçe grafikler yenilenir.")
    
    # Döngü içinde artık veri okumuyoruz, sadece veritabanından çekip UI güncelliyoruz
    while st.session_state.monitoring:
        ui_refresh()
        time.sleep(2) # UI yenileme hızı (Veritabanını yormamak için ideal)
        st.rerun() # Streamlit'in ekranı tazelemesi için

else:
    ui_refresh()
    status_bar.info("Sistem Beklemede. Grafikleri görmek için BAŞLAT'a basın.")