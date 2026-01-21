import streamlit as st
import time
import pandas as pd
from datetime import datetime
from pymodbus.client import ModbusTcpClient

# --- SAYFA AYARLARI ---
st.set_page_config(
    page_title="Solar TCP İzleme", 
    layout="wide", 
    page_icon="⚡",
    initial_sidebar_state="expanded"
)

# --- DARK MODE CSS TASARIMI ---
st.markdown("""
<style>
    /* Ana Arka Plan Ayarı (Streamlit varsayılanı koyu değilse zorlar) */
    .stApp {
        background-color: #0E1117;
        color: #FAFAFA;
    }

    /* Üst Başlık - Cyberpunk Gradyan */
    .main-header {
        background: linear-gradient(90deg, #000428 0%, #004e92 100%);
        padding: 20px; 
        border-radius: 15px; 
        color: white; 
        text-align: center; 
        margin-bottom: 25px;
        box-shadow: 0 4px 15px rgba(0, 200, 255, 0.2);
        border: 1px solid #1e3a8a;
    }

    /* Metrik Kutuları - Koyu Gri Kartlar */
    div[data-testid="stMetric"] {
        background-color: #262730;
        border: 1px solid #414452;
        padding: 20px;
        border-radius: 10px;
        color: white;
        transition: transform 0.2s;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
    }
    
    div[data-testid="stMetric"]:hover {
        transform: scale(1.02);
        border-color: #004e92;
    }

    /* Metrik Etiket Rengi */
    div[data-testid="stMetricLabel"] {
        color: #B0B0B0 !important;
        font-size: 0.9rem;
    }

    /* Metrik Değer Rengi */
    div[data-testid="stMetricValue"] {
        color: #FFFFFF !important;
        font-weight: 700;
        text-shadow: 0 0 10px rgba(255,255,255,0.1);
    }

    /* Durum Kutuları */
    .status-box {
        padding: 15px; 
        border-radius: 8px; 
        text-align: center; 
        font-weight: bold; 
        color: white; 
        margin-bottom: 20px;
        box-shadow: 0 4px 10px rgba(0,0,0,0.4);
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    
    /* Expander (Debug) Arka Planı */
    .streamlit-expanderHeader {
        background-color: #262730;
        color: white;
    }
</style>
""", unsafe_allow_html=True)

# --- SESSION STATE İLKLENDİRME ---
if 'gecmis_veriler' not in st.session_state:
    st.session_state.gecmis_veriler = pd.DataFrame(columns=['Zaman', 'Güç', 'Sıcaklık'])
if 'bagli' not in st.session_state:
    st.session_state.bagli = False
if 'son_okuma' not in st.session_state:
    st.session_state.son_okuma = None

# --- YAN MENÜ: BAĞLANTI AYARLARI ---
with st.sidebar:
    st.header("🌑 Sistem Ayarları")
    
    with st.expander("📡 Bağlantı", expanded=True):
        ip_adresi = st.text_input("IP Adresi", value="10.35.14.10")
        port = st.number_input("Port", value=502, step=1)
        slave_id = st.number_input("Slave ID", value=1, min_value=1, max_value=247)
    
    with st.expander("📍 Adres Haritası", expanded=False):
        st.info("İnverter PDF'indeki Decimal adresler:")
        reg_voltaj = st.number_input("Voltaj Adresi", value=0, min_value=0)
        reg_akim = st.number_input("Akım Adresi", value=1, min_value=0)
        reg_guc = st.number_input("Güç Adresi", value=2, min_value=0) 
        reg_sicaklik = st.number_input("Sıcaklık Adresi", value=4, min_value=0)
    
    with st.expander("🔧 Çarpanlar (Scaling)", expanded=False):
        scale_voltaj = st.number_input("Voltaj Çarpanı", value=1.0, format="%.3f")
        scale_akim = st.number_input("Akım Çarpanı", value=1.0, format="%.3f")
        scale_guc = st.number_input("Güç Çarpanı", value=0.1, format="%.3f")
        scale_sicaklik = st.number_input("Sıcaklık Çarpanı", value=1.0, format="%.3f")
    
    st.divider()
    
    col1, col2 = st.columns(2)
    if col1.button("🚀 BAŞLAT", use_container_width=True, type="primary"):
        st.session_state.bagli = True
        st.rerun()
    
    if col2.button("🛑 DURDUR", use_container_width=True):
        st.session_state.bagli = False
        st.rerun()
    
    if st.button("🗑️ Verileri Sıfırla", use_container_width=True):
        st.session_state.gecmis_veriler = pd.DataFrame(columns=['Zaman', 'Güç', 'Sıcaklık'])
        st.rerun()

# --- ANA EKRAN ---
st.markdown(
    f'<div class="main-header"><h1>⚡ Solar İnverter Takip</h1><p style="color:#a0a0a0;">Hedef Cihaz: {ip_adresi}:{port}</p></div>', 
    unsafe_allow_html=True
)

# Durum Göstergesi
durum_alani = st.empty()

# Metrik Kutuları
c1, c2, c3, c4 = st.columns(4)
m_guc = c1.empty()
m_voltaj = c2.empty()
m_akim = c3.empty()
m_sicaklik = c4.empty()

st.divider()

# Grafikler
st.markdown("### 📈 Performans Grafikleri")
g1, g2 = st.columns([2, 1])
grafik_guc = g1.empty()
grafik_sicaklik = g2.empty()

# Debug Bilgisi
debug_area = st.empty()

# --- MODBUS OKUMA FONKSİYONU ---
def modbus_oku():
    """Modbus TCP üzerinden veri okur"""
    client = ModbusTcpClient(ip_adresi, port=port, timeout=3)
    
    try:
        if not client.connect():
            return None, "Bağlantı kurulamadı (Timeout)"
        
        try:
            # Önce 'slave' parametresiyle dene
            r_volt = client.read_holding_registers(reg_voltaj, 1, slave=slave_id)
        except TypeError:
            # Eğer 'slave' çalışmazsa 'unit' kullan
            r_volt = client.read_holding_registers(reg_voltaj, 1, unit=slave_id)
            r_akim = client.read_holding_registers(reg_akim, 1, unit=slave_id)
            r_guc = client.read_holding_registers(reg_guc, 1, unit=slave_id)
            r_sic = client.read_holding_registers(reg_sicaklik, 1, unit=slave_id)
        else:
            r_akim = client.read_holding_registers(reg_akim, 1, slave=slave_id)
            r_guc = client.read_holding_registers(reg_guc, 1, slave=slave_id)
            r_sic = client.read_holding_registers(reg_sicaklik, 1, slave=slave_id)
        
        # Hata kontrolü
        if r_volt.isError(): return None, f"Voltaj Hatası: {r_volt}"
        if r_akim.isError(): return None, f"Akım Hatası: {r_akim}"
        if r_guc.isError(): return None, f"Güç Hatası: {r_guc}"
        if r_sic.isError(): return None, f"Sıcaklık Hatası: {r_sic}"
        
        # Değerleri ölçeklendir
        veri = {
            'voltaj': r_volt.registers[0] * scale_voltaj,
            'akim': r_akim.registers[0] * scale_akim,
            'guc': r_guc.registers[0] * scale_guc,
            'sicaklik': r_sic.registers[0] * scale_sicaklik,
            'ham_voltaj': r_volt.registers[0],
            'ham_akim': r_akim.registers[0],
            'ham_guc': r_guc.registers[0],
            'ham_sicaklik': r_sic.registers[0]
        }
        return veri, None
        
    except Exception as e:
        return None, f"Sistem Hatası: {str(e)}"
    finally:
        client.close()

# --- ANA LOJİK ---
if st.session_state.bagli:
    durum_alani.markdown(
        f'<div class="status-box" style="background: linear-gradient(45deg, #FF8008, #FFC837);">⏳ Bağlanılıyor: {ip_adresi}...</div>', 
        unsafe_allow_html=True
    )
    
    veri, hata = modbus_oku()
    
    if hata:
        durum_alani.markdown(
            f'<div class="status-box" style="background: linear-gradient(45deg, #cb2d3e, #ef473a);">❌ HATA: {hata}</div>', 
            unsafe_allow_html=True
        )
        with debug_area.container():
            st.error(f"Hata Detayı: {hata}")
            st.warning("Kontrol: IP Adresi, Firewall, WaveShare Ayarları")
        
        st.session_state.bagli = False
    else:
        durum_alani.markdown(
            '<div class="status-box" style="background: linear-gradient(45deg, #11998e, #38ef7d);">✅ SİSTEM AKTİF</div>', 
            unsafe_allow_html=True
        )
        
        # Metrikleri göster
        m_guc.metric("Anlık Güç", f"{veri['guc']:.1f} W", delta=f"{veri['guc']/1000:.2f} kW")
        m_voltaj.metric("Voltaj", f"{veri['voltaj']:.1f} V")
        m_akim.metric("Akım", f"{veri['akim']:.2f} A")
        m_sicaklik.metric("Sıcaklık", f"{veri['sicaklik']:.1f} °C")
        
        # Geçmişe ekle
        now = datetime.now().strftime("%H:%M:%S")
        new_data = pd.DataFrame({
            'Zaman': [now], 
            'Güç': [veri['guc']], 
            'Sıcaklık': [veri['sicaklik']]
        })
        st.session_state.gecmis_veriler = pd.concat(
            [st.session_state.gecmis_veriler, new_data], 
            ignore_index=True
        )
        
        if len(st.session_state.gecmis_veriler) > 100:
            st.session_state.gecmis_veriler = st.session_state.gecmis_veriler.iloc[-100:]
        
        # Grafikleri güncelle (Renkler Dark Mode'a uyarlandı)
        if len(st.session_state.gecmis_veriler) > 0:
            grafik_guc.area_chart(
                st.session_state.gecmis_veriler, 
                x='Zaman', 
                y='Güç', 
                color='#FFD700'  # Altın sarısı (Güç için)
            )
            grafik_sicaklik.line_chart(
                st.session_state.gecmis_veriler, 
                x='Zaman', 
                y='Sıcaklık', 
                color='#FF4B4B'  # Parlak Kırmızı (Sıcaklık için)
            )
        
        # Debug bilgisi (Gizlenebilir)
        with debug_area.expander("🛠️ Ham Veri Detayları"):
            st.code(f"""
            Ham Değerler (Register'dan okunan):
            -----------------------------------
            Voltaj:   {veri['ham_voltaj']}
            Akım:     {veri['ham_akim']}
            Güç:      {veri['ham_guc']}
            Sıcaklık: {veri['ham_sicaklik']}
            """)
        
        st.session_state.son_okuma = datetime.now()
        
        time.sleep(1)
        st.rerun()
else:
    durum_alani.info("▶️ İzlemeyi başlatmak için sol menüden 'BAŞLAT' butonuna basın.")
    if st.session_state.son_okuma:
        st.caption(f"🕒 Son başarılı okuma: {st.session_state.son_okuma.strftime('%H:%M:%S')}")