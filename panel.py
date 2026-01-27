import streamlit as st
import time
import pandas as pd
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

# --- YENİ ALARM HARİTASI (BIT-MAP) ---
FAULT_MAP = {
    0:  "DC Overcurrent Fault [1-1]",
    1:  "DC Overcurrent Fault [1-2]",
    2:  "DC Overcurrent Fault [2-1]",
    3:  "DC Overcurrent Fault [2-2]",
    4:  "DC Overcurrent Fault [3-1]",
    5:  "DC Overcurrent Fault [3-2]",
    6:  "DC Overcurrent Fault [4-1]",
    7:  "DC Overcurrent Fault [4-2]",
    8:  "DC Overcurrent Fault [5-1]",
    9:  "DC Overcurrent Fault [5-2]",
    10: "DC Overcurrent Fault [6-1]",
    11: "DC Overcurrent Fault [6-2]",
    12: "DC Overcurrent Fault [7-1]",
    13: "DC Overcurrent Fault [7-2]",
    14: "DC Overcurrent Fault [8-1]",
    15: "DC Overcurrent Fault [8-2]",
    16: "DC Overcurrent Fault [9-1]",
    17: "DC Overcurrent Fault [9-2]",
    18: "DC Overcurrent Fault [10-1]",
    19: "DC Overcurrent Fault [10-2]",
    20: "DC Overcurrent Fault [11-1]",
    21: "DC Overcurrent Fault [11-2]",
    22: "DC Overcurrent Fault [12-1]",
    23: "DC Overcurrent Fault [12-2]"
}

# --- YARDIMCI FONKSİYONLAR ---
def parse_id_list(id_string):
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

def active_fault_checker(hata_kodu):
    active_faults = []
    for bit_index in range(24):
        if (hata_kodu >> bit_index) & 1:
            mesaj = FAULT_MAP.get(bit_index, f"Bilinmeyen Hata (Bit {bit_index})")
            active_faults.append(mesaj)
    return active_faults

@st.cache_resource
def get_modbus_client(ip, port):
    return ModbusTcpClient(ip, port=port, timeout=1) 

def read_device(client, slave_id, config):
    try:
        if not client.connected: client.connect()
        
        r_guc = client.read_holding_registers(config['guc_addr'], 1, slave=slave_id)
        if r_guc.isError(): return None, "No Response"
        val_guc = r_guc.registers[0] * config['guc_scale']

        r_volt = client.read_holding_registers(config['volt_addr'], 1, slave=slave_id)
        val_volt = 0 if r_volt.isError() else r_volt.registers[0] * config['volt_scale']

        r_akim = client.read_holding_registers(config['akim_addr'], 1, slave=slave_id)
        val_akim = 0 if r_akim.isError() else r_akim.registers[0] * config['akim_scale']

        r_isi = client.read_holding_registers(config['isi_addr'], 1, slave=slave_id)
        val_isi = 0 if r_isi.isError() else r_isi.registers[0] * config['isi_scale']

        hata_addr = config.get('hata_addr', 189)
        r_hata = client.read_holding_registers(hata_addr, 2, slave=slave_id)
        
        hata_kodu = 0
        if not r_hata.isError():
            hata_kodu = (r_hata.registers[0] << 16) | r_hata.registers[1]

        return {
            "slave_id": slave_id,
            "guc": val_guc,
            "voltaj": val_volt,
            "akim": val_akim,
            "sicaklik": val_isi,
            "hata_kodu": hata_kodu,
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
    id_input = st.text_input("İnverter ID Listesi", value="1, 2, 3")
    target_ids = parse_id_list(id_input)
    st.write(f"📡 İzlenecek ID'ler: {target_ids}")
    
    st.divider()
    
    st.header("⏳ Zamanlayıcı")
    refresh_rate = st.number_input("Veri Çekme Sıklığı (Saniye)", value=30, min_value=1, step=1)
    
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
        c_hata_adr = st.number_input("Hata Adresi (DC Faults)", value=189, help="Dokümanda 40190 ise buraya 189 yazın.")
    
    config = {
        'guc_addr': c_guc_adr, 'guc_scale': c_guc_sc,
        'volt_addr': c_volt_adr, 'volt_scale': c_volt_sc,
        'akim_addr': c_akim_adr, 'akim_scale': c_akim_sc,
        'isi_addr': c_isi_adr, 'isi_scale': c_isi_sc,
        'hata_addr': c_hata_adr
    }

    if st.button("▶️ SİSTEMİ BAŞLAT", type="primary"):
        st.session_state.monitoring = True
        st.rerun()
    if st.button("⏹️ DURDUR"):
        st.session_state.monitoring = False
        st.rerun()

    st.markdown("---")
    st.header("🗑️ Veri Yönetimi")
    if st.button("Tüm Verileri Sil", help="Veritabanındaki tüm ölçüm geçmişini temizler."):
        if veritabani.db_temizle():
            st.success("Veritabanı başarıyla temizlendi!")
            time.sleep(1)
            st.rerun()
        else:
            st.error("Silme işlemi başarısız oldu.")

# --- ANA EKRAN ---
st.title("⚡ Güneş Enerjisi Santrali İzleme")

st.subheader("📋 Canlı Filo Durumu")
table_spot = st.empty()

st.markdown("---")
st.markdown("### 🚨 Aktif Donanım Arızaları")
alarm_spot = st.container()

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
    st.markdown(f'<div class="chart-title" style="background:#0a260e; color:#66BB6A;">📈 ID:{selected_id} - Akım</div>', unsafe_allow_html=True)
    chart_akim = st.empty()
with row2_c2:
    st.markdown(f'<div class="chart-title" style="background:#2e0a0a; color:#EF5350;">🌡️ ID:{selected_id} - Sıcaklık</div>', unsafe_allow_html=True)
    chart_isi = st.empty()

# --- DURUM ÇUBUĞU ---
status_bar = st.empty()

def ui_refresh():
    # 1. TABLO GÜNCELLEME
    summary_data = veritabani.tum_cihazlarin_son_durumu()
    if summary_data:
        # Tabloyu oluştururken Hata Kodu (index 6) hariç ilk 6 sütunu alıyoruz
        # summary_data satır yapısı: [slave_id, zaman, guc, voltaj, akim, sicaklik, hata_kodu]
        df_sum = pd.DataFrame([row[:6] for row in summary_data], columns=["ID", "Son Zaman", "Güç (W)", "Voltaj (V)", "Akım (A)", "Isı (C)"])
        df_sum["Son Zaman"] = pd.to_datetime(df_sum["Son Zaman"]).dt.strftime('%H:%M:%S')
        table_spot.dataframe(df_sum.set_index("ID"), use_container_width=True)

        # 2. HATA KODU ANALİZİ (YENİ SİSTEM)
        with alarm_spot:
            active_alarms = 0
            for row in summary_data:
                # row yapısı: (0:id, 1:zaman, 2:guc, 3:voltaj, 4:akim, 5:isi, 6:hata_kodu)
                if len(row) > 6:
                    hata_kodu = row[6]
                    if hata_kodu > 0: 
                        hatalar = active_fault_checker(hata_kodu)
                        for hata_mesaji in hatalar:
                            st.error(f"🛑 KRİTİK ARIZA [ID: {row[0]}]: {hata_mesaji}")
                            active_alarms += 1
                
            if active_alarms == 0:
                st.success("✅ Sistem Stabil - Aktif Donanım Arızası Yok")

    # 3. GRAFİK GÜNCELLEME
    detail_data = veritabani.son_verileri_getir(selected_id, limit=100)
    if detail_data:
        # DÜZELTME BURADA YAPILDI: "hata_kodu" sütunu listeye eklendi
        df_det = pd.DataFrame(detail_data, columns=["timestamp", "guc", "voltaj", "akim", "sicaklik", "hata_kodu"])
        df_det["timestamp"] = pd.to_datetime(df_det["timestamp"])
        df_det = df_det.set_index("timestamp")
        
        chart_guc.line_chart(df_det["guc"], color="#FFD700")
        chart_volt.line_chart(df_det["voltaj"], color="#29B6F6")
        chart_akim.line_chart(df_det["akim"], color="#66BB6A")
        chart_isi.line_chart(df_det["sicaklik"], color="#EF5350")

# --- ANA DÖNGÜ ---
if st.session_state.monitoring:
    client = get_modbus_client(target_ip, target_port)
    status_bar.success(f"✅ Sistem Aktif - Hata Registerları İzleniyor.")
    
    while st.session_state.monitoring:
        for dev_id in target_ids:
            data, err = read_device(client, dev_id, config)
            if data:
                veritabani.veri_ekle(dev_id, data)
        
        ui_refresh()
        time.sleep(2) 
        st.rerun()
else:
    ui_refresh()
    status_bar.info("Sistem Beklemede. Grafikleri görmek için BAŞLAT'a basın.")