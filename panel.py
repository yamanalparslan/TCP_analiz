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
    page_title="Solar TCP Monitor Pro",
    layout="wide",
    page_icon="⚡",
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
        padding: 15px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.3);
    }
    .chart-title {
        font-size: 1.1rem; font-weight: 700; margin-bottom: 0px;
        padding: 5px 10px; border-radius: 5px 5px 0 0; display: inline-block; width: 100%;
    }
</style>
""", unsafe_allow_html=True)

# --- YARDIMCI FONKSİYONLAR ---
def validate_inputs(ip, port):
    ip_pattern = r"^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$"
    if not re.match(ip_pattern, ip): return False, "Geçersiz IP"
    if not (1 <= port <= 65535): return False, "Geçersiz Port"
    return True, None

@st.cache_resource
def get_modbus_client(ip, port):
    return ModbusTcpClient(ip, port=port, timeout=2)

# --- DINAMIK OKUMA FONKSİYONU ---
def read_dynamic_modbus(ip, port, slave, config):
    """
    Belirtilen IP'den, kullanıcının girdiği adresleri tek tek okur.
    config: {'guc_addr': 0, 'guc_scale': 1.0, ...}
    """
    client = get_modbus_client(ip, port)
    if not client.connected: client.connect()
    if not client.connected: return None, "Bağlantı Hatası"

    try:
        # 1. GÜÇ OKUMA
        r_guc = client.read_holding_registers(config['guc_addr'], 1, slave=slave)
        if r_guc.isError(): raise Exception(f"Güç Hatası: {r_guc} (Adr: {config['guc_addr']})")
        val_guc = r_guc.registers[0] * config['guc_scale']

        # 2. VOLTAJ OKUMA
        r_volt = client.read_holding_registers(config['volt_addr'], 1, slave=slave)
        if r_volt.isError(): raise Exception(f"Voltaj Okunamadı (Adr: {config['volt_addr']})")
        val_volt = r_volt.registers[0] * config['volt_scale']

        # 3. AKIM OKUMA
        r_akim = client.read_holding_registers(config['akim_addr'], 1, slave=slave)
        if r_akim.isError(): raise Exception(f"Akım Okunamadı (Adr: {config['akim_addr']})")
        val_akim = r_akim.registers[0] * config['akim_scale']

        # 4. SICAKLIK OKUMA
        r_isi = client.read_holding_registers(config['isi_addr'], 1, slave=slave)
        if r_isi.isError(): raise Exception(f"Isı Okunamadı (Adr: {config['isi_addr']})")
        val_isi = r_isi.registers[0] * config['isi_scale']

        return {
            "guc": val_guc,
            "voltaj": val_volt,
            "akim": val_akim,
            "sicaklik": val_isi,
            "timestamp": datetime.now()
        }, None

    except Exception as e:
        client.close()
        return None, str(e)

# --- STATE ---
if 'monitoring' not in st.session_state:
    st.session_state.monitoring = False

# --- YAN MENÜ (KONFIGURASYON MERKEZİ) ---
with st.sidebar:
    st.header("⚙️ Bağlantı Ayarları")
    target_ip = st.text_input("IP Adresi", value="127.0.0.1")
    target_port = st.number_input("Port", value=5020, step=1)
    slave_id = st.number_input("Slave ID", value=1, min_value=1)
    
    st.markdown("---")
    st.header("🗺️ Adres Haritası (Register Map)")
    st.info("İnverter PDF'indeki Decimal adresleri giriniz.")
    
    with st.expander("☀️ GÜÇ Ayarları", expanded=True):
        conf_guc_adr = st.number_input("Güç Adresi", value=2, min_value=0)
        conf_guc_carpan = st.number_input("Güç Çarpanı", value=1.0, step=0.1, format="%.2f")

    with st.expander("⚡ VOLTAJ Ayarları", expanded=False):
        conf_volt_adr = st.number_input("Voltaj Adresi", value=0, min_value=0)
        conf_volt_carpan = st.number_input("Voltaj Çarpanı", value=1.0, step=0.1, format="%.2f")

    with st.expander("ww AKIM Ayarları", expanded=False):
        conf_akim_adr = st.number_input("Akım Adresi", value=1, min_value=0)
        conf_akim_carpan = st.number_input("Akım Çarpanı", value=0.1, step=0.01, format="%.2f") # Örn: 125 gelir, 0.1 ile çarpıp 12.5 yaparız

    with st.expander("🌡️ SICAKLIK Ayarları", expanded=False):
        conf_isi_adr = st.number_input("Sıcaklık Adresi", value=4, min_value=0)
        conf_isi_carpan = st.number_input("Sıcaklık Çarpanı", value=1.0, step=0.1, format="%.2f")

    # Konfigürasyon Paketi
    user_config = {
        'guc_addr': conf_guc_adr, 'guc_scale': conf_guc_carpan,
        'volt_addr': conf_volt_adr, 'volt_scale': conf_volt_carpan,
        'akim_addr': conf_akim_adr, 'akim_scale': conf_akim_carpan,
        'isi_addr': conf_isi_adr, 'isi_scale': conf_isi_carpan
    }

    st.divider()
    c1, c2 = st.columns(2)
    if c1.button("▶️ BAŞLAT", type="primary"):
        v, m = validate_inputs(target_ip, target_port)
        if v: st.session_state.monitoring = True
        else: st.error(m)
    if c2.button("⏹️ DURDUR"):
        st.session_state.monitoring = False
        st.rerun()

# --- ANA EKRAN ---
safe_ip = html.escape(target_ip)
st.markdown(f"## ⚡ Solar Dashboard: <code style='color:#4FC3F7'>{safe_ip}:{target_port}</code>", unsafe_allow_html=True)

status_box = st.empty()
st.markdown("---")
kpi1, kpi2, kpi3, kpi4 = st.columns(4)
metric_guc = kpi1.empty()
metric_volt = kpi2.empty()
metric_akim = kpi3.empty()
metric_isi = kpi4.empty()

row1_col1, row1_col2 = st.columns(2)
row2_col1, row2_col2 = st.columns(2)

with row1_col1:
    st.markdown('<div class="chart-title" style="background:#332a00; color:#FFD700; border-left:4px solid #FFD700;">☀️ Anlık Güç (Watt)</div>', unsafe_allow_html=True)
    chart_guc_spot = st.empty()

with row1_col2:
    st.markdown('<div class="chart-title" style="background:#001e33; color:#29B6F6; border-left:4px solid #29B6F6;">⚡ Voltaj (Volt)</div>', unsafe_allow_html=True)
    chart_volt_spot = st.empty()

with row2_col1:
    st.markdown('<div class="chart-title" style="background:#0a260e; color:#66BB6A; border-left:4px solid #66BB6A;">ww Akım (Amper)</div>', unsafe_allow_html=True)
    chart_akim_spot = st.empty()

with row2_col2:
    st.markdown('<div class="chart-title" style="background:#2e0a0a; color:#EF5350; border-left:4px solid #EF5350;">🌡️ Sıcaklık (°C)</div>', unsafe_allow_html=True)
    chart_isi_spot = st.empty()

def ui_guncelle():
    rows = veritabani.son_verileri_getir(limit=100)
    if rows:
        df = pd.DataFrame(rows, columns=["timestamp", "guc", "voltaj", "akim", "sicaklik"])
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.set_index("timestamp")
        chart_guc_spot.area_chart(df["guc"], color="#FFD700")
        chart_volt_spot.line_chart(df["voltaj"], color="#29B6F6")
        chart_akim_spot.area_chart(df["akim"], color="#66BB6A")
        chart_isi_spot.line_chart(df["sicaklik"], color="#EF5350")

# --- ANA DÖNGÜ ---
if st.session_state.monitoring:
    status_box.success(f"✅ Canlı İzleme Aktif (Slave ID: {slave_id})")
    
    while True:
        # Config'i her döngüde parametre olarak gönderiyoruz
        data, err = read_dynamic_modbus(target_ip, target_port, slave_id, user_config)
        
        if err:
            status_box.error(f"⚠️ {err}")
            time.sleep(2)
        else:
            metric_guc.metric("Güç", f"{data['guc']:.1f} W")
            metric_volt.metric("Voltaj", f"{data['voltaj']:.1f} V")
            metric_akim.metric("Akım", f"{data['akim']:.2f} A")
            metric_isi.metric("Sıcaklık", f"{data['sicaklik']:.1f} °C")
            
            veritabani.veri_ekle(data)
            ui_guncelle()
            time.sleep(1)

else:
    status_box.info("Sistem Beklemede... Lütfen Sol Menüden Adresleri Ayarlayıp Başlatın.")
    ui_guncelle()