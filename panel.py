import streamlit as st
import time
import pandas as pd
import json
import veritabani
import plotly.graph_objects as go
import plotly.express as px

# --- 1. SAYFA AYARLARI ---
st.set_page_config(page_title="Solar Master", layout="wide", page_icon="☀️", initial_sidebar_state="collapsed")

# Veritabanı başlat
try: veritabani.init_db()
except: pass

# --- 2. CSS ---
st.markdown("""
<style>
    .stApp { background-color: #0E1117; }
    div[data-testid="stMetric"] {
        background-color: #1a1c24; border: 1px solid #30333d; border-radius: 10px; padding: 10px;
    }
    [data-testid="stMetricValue"] { color: #fbbf24 !important; font-size: 26px !important; }
    [data-testid="stMetricLabel"] { color: #9ca3af !important; }
    [data-testid="stSidebar"] { background-color: #11131b; border-right: 1px solid #30333d; }
    [data-testid="stDataFrame"] { border-radius: 10px; overflow: hidden; }
</style>
""", unsafe_allow_html=True)

# --- 3. HEADER ---
c1, c2 = st.columns([1, 15])
with c1: st.header("☀️")
with c2: st.header("Solar Master SCADA")

# --- 4. SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Ayarlar")
    curr_conf = json.loads(veritabani.get_ayar("modbus_config"))
    
    with st.form("settings"):
        # KEY EKLENDİ (Benzersizlik için)
        nip = st.text_input("IP", value=veritabani.get_ayar("ip"), key="k_ip")
        npt = st.number_input("Port", value=int(veritabani.get_ayar("port")), key="k_port")
        nid = st.text_input("ID Listesi", value=veritabani.get_ayar("ids"), key="k_ids")
        nrf = st.number_input("Hız", value=max(int(veritabani.get_ayar("refresh")), 5), min_value=5, key="k_rf")
        
        with st.expander("Kalibrasyon"):
            c_a, c_b = st.columns(2)
            ga = c_a.number_input("Güç Adr", value=curr_conf['guc_addr'], key="k_ga")
            gs = c_b.number_input("Çarpan", value=curr_conf['guc_scale'], key="k_gs")
            va = c_a.number_input("Volt Adr", value=curr_conf['volt_addr'], key="k_va")
            vs = c_b.number_input("Çarpan", value=curr_conf['volt_scale'], key="k_vs")
            aa = c_a.number_input("Akım Adr", value=curr_conf['akim_addr'], key="k_aa")
            as_ = c_b.number_input("Çarpan", value=curr_conf['akim_scale'], key="k_as")
            ia = c_a.number_input("Isı Adr", value=curr_conf['isi_addr'], key="k_ia")
            is_ = c_b.number_input("Çarpan", value=curr_conf['isi_scale'], key="k_is")

        if st.form_submit_button("💾 Kaydet"):
            veritabani.set_ayar("ip", nip); veritabani.set_ayar("port", npt)
            veritabani.set_ayar("ids", nid); veritabani.set_ayar("refresh", nrf)
            veritabani.set_ayar("modbus_config", json.dumps({
                'guc_addr': ga, 'guc_scale': gs, 'volt_addr': va, 'volt_scale': vs,
                'akim_addr': aa, 'akim_scale': as_, 'isi_addr': ia, 'isi_scale': is_
            }))
            st.toast("Ayarlar Kaydedildi!", icon="✅"); time.sleep(1); st.rerun()

# --- 5. ANA İŞLEYİŞ (DÖNGÜ YOK, RERUN VAR) ---

# Veri Çekme
raw = veritabani.tum_cihazlarin_son_durumu()
if not raw:
    st.info("📡 Veri bekleniyor... (Lütfen bekleyin)")
    time.sleep(3)
    st.rerun() # Veri yoksa 3sn bekle ve tekrar dene

df = pd.DataFrame(raw, columns=["ID", "Zaman", "Güç", "Voltaj", "Akım", "Isı"])

# KPI Kartları
k1, k2, k3, k4 = st.columns(4)
k1.metric("Toplam Güç", f"{df['Güç'].sum()/1000:.2f} kW")
k2.metric("Ort. Voltaj", f"{df['Voltaj'].mean():.1f} V")
k3.metric("Max Sıcaklık", f"{df['Isı'].max():.1f} °C")
k4.metric("Aktif Cihaz", len(df))
st.divider()

# Sekmeler
tab_list, tab_graph = st.tabs(["📋 Liste", "📈 Grafik Analiz"])

with tab_list:
    st.dataframe(
        df.set_index("ID"), use_container_width=True,
        column_config={
            "Zaman": st.column_config.DatetimeColumn(format="HH:mm:ss"),
            "Güç": st.column_config.ProgressColumn("Güç", format="%d W", min_value=0, max_value=max(int(df["Güç"].max()), 100)),
            "Voltaj": st.column_config.NumberColumn("Voltaj", format="%.1f V"),
            "Isı": st.column_config.NumberColumn("Sıcaklık", format="%.1f °C")
        }
    )

with tab_graph:
    ids = sorted(df["ID"].unique())
    # ARTIK HATA VERMEZ, ÇÜNKÜ LOOP YOK
    selected_id = st.selectbox("🔍 Cihaz Seçin:", ids, key="graph_select_box")
    
    if selected_id:
        row = df[df["ID"] == selected_id].iloc[0]
        
        # İbreler
        def gauge(val, title, mx, col):
            fig = go.Figure(go.Indicator(mode="gauge+number", value=val, title={'text':title},
                gauge={'axis':{'range':[None, mx]}, 'bar':{'color':col}, 'bgcolor':"#222"}))
            fig.update_layout(height=180, margin=dict(t=30,b=10,l=20,r=20), paper_bgcolor="rgba(0,0,0,0)", font={'color':"white"})
            return fig

        g1, g2, g3 = st.columns(3)
        with g1: st.plotly_chart(gauge(row["Güç"], "Güç (W)", 3000, "#FBBF24"), use_container_width=True)
        with g2: st.plotly_chart(gauge(row["Voltaj"], "Voltaj (V)", 300, "#60A5FA"), use_container_width=True)
        with g3: st.plotly_chart(gauge(row["Isı"], "Sıcaklık (°C)", 75, "#F87171"), use_container_width=True)
        
        # Çizgi Grafik (Line Chart)
        hist = veritabani.son_verileri_getir(selected_id, limit=60)
        if hist:
            hdf = pd.DataFrame(hist, columns=["zaman", "guc", "voltaj", "akim", "sicaklik"])
            hdf["zaman"] = pd.to_datetime(hdf["zaman"])
            
            # Area değil Line (Çizgi) Grafik
            fig = px.line(hdf, x="zaman", y="guc", title="Güç Trendi", markers=True)
            fig.update_traces(line_color="#FBBF24", line_width=3)
            fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font_color="white", height=300)
            st.plotly_chart(fig, use_container_width=True)
            
            c_v, c_t = st.columns(2)
            with c_v:
                fig_v = px.line(hdf, x="zaman", y="voltaj", title="Voltaj", markers=False)
                fig_v.update_traces(line_color="#60A5FA")
                fig_v.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font_color="white", height=250)
                st.plotly_chart(fig_v, use_container_width=True)
            with c_t:
                fig_t = px.line(hdf, x="zaman", y="sicaklik", title="Sıcaklık", markers=False)
                fig_t.update_traces(line_color="#F87171")
                fig_t.add_hline(y=60, line_dash="dot", line_color="red")
                fig_t.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font_color="white", height=250)
                st.plotly_chart(fig_t, use_container_width=True)

# --- 6. OTOMATİK YENİLEME ---
time.sleep(2)  # 2 saniye bekle
st.rerun()     # Sayfayı baştan yükle (Bu komut döngüyü sağlar)