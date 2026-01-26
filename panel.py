import streamlit as st
import time
import pandas as pd
import json
import veritabani
import plotly.express as px
import random

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Solar Master", layout="wide", page_icon="☀️", initial_sidebar_state="expanded")
try: veritabani.init_db()
except: pass

# --- CSS ---
st.markdown("""
<style>
    .stApp { background-color: #0E1117; }
    div[data-testid="stMetric"] { background-color: #1a1c24; border: 1px solid #30333d; border-radius: 10px; padding: 10px; }
    [data-testid="stMetricValue"] { color: #fbbf24 !important; }
    [data-testid="stSidebar"] { background-color: #11131b; border-right: 1px solid #30333d; }
    .chart-box { background-color: #161b22; padding: 15px; border-radius: 10px; border: 1px solid #30363d; margin-bottom: 20px; }
</style>
""", unsafe_allow_html=True)

# --- HEADER ---
c1, c2 = st.columns([1, 15])
with c1: st.header("☀️")
with c2: st.header("Solar Master SCADA")

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Kontrol Paneli")
    auto_refresh = st.checkbox("🔄 CANLI VERİ AKIŞI", value=True, key="main_ref")
    st.divider()
    
    # TEST ARACI
    if st.button("🧪 Test Verisi Ekle (Debugging)"):
        try:
            sid = int(veritabani.get_ayar("ids").split(',')[0])
        except: sid = 1
        veritabani.veri_ekle(sid, {"guc": random.randint(2000,4000), "voltaj": 220, "akim": 10, "sicaklik": 45})
        st.success(f"ID {sid} için veri eklendi!")
    st.divider()

    curr_conf = json.loads(veritabani.get_ayar("modbus_config"))
    with st.form("settings"):
        nip = st.text_input("IP", value=veritabani.get_ayar("ip"), key="k_ip")
        npt = st.number_input("Port", value=int(veritabani.get_ayar("port")), key="k_pt")
        nid = st.text_input("ID Listesi", value=veritabani.get_ayar("ids"), key="k_id")
        nrf = st.number_input("Hız (sn)", value=max(int(veritabani.get_ayar("refresh")), 5), min_value=5, key="k_rf")
        
        with st.expander("Kalibrasyon"):
            c1,c2=st.columns(2)
            # KEY PARAMETRELERİ EKLENDİ
            ga=c1.number_input("Güç Adr", value=curr_conf['guc_addr'], key="k_guc_addr")
            gs=c2.number_input("Çarpan", value=curr_conf['guc_scale'], key="k_guc_scale")
            
            va=c1.number_input("Volt Adr", value=curr_conf['volt_addr'], key="k_volt_addr")
            vs=c2.number_input("Çarpan", value=curr_conf['volt_scale'], key="k_volt_scale")
            
            aa=c1.number_input("Akim Adr", value=curr_conf['akim_addr'], key="k_akim_addr")
            as_=c2.number_input("Çarpan", value=curr_conf['akim_scale'], key="k_akim_scale")
            
            ia=c1.number_input("Isi Adr", value=curr_conf['isi_addr'], key="k_isi_addr")
            is_=c2.number_input("Çarpan", value=curr_conf['isi_scale'], key="k_isi_scale")

        if st.form_submit_button("💾 Kaydet"):
            veritabani.set_ayar("ip", nip); veritabani.set_ayar("port", npt)
            veritabani.set_ayar("ids", nid); veritabani.set_ayar("refresh", nrf)
            veritabani.set_ayar("modbus_config", json.dumps({'guc_addr':ga,'guc_scale':gs,'volt_addr':va,'volt_scale':vs,'akim_addr':aa,'akim_scale':as_,'isi_addr':ia,'isi_scale':is_}))
            st.success("Kaydedildi!"); time.sleep(1); st.rerun()

# --- VERİ ÇEKME ---
raw = veritabani.tum_cihazlarin_son_durumu()
if not raw:
    st.warning("📡 Veri Bekleniyor... (Veritabanı boş)"); 
    if auto_refresh: time.sleep(3); st.rerun()
    st.stop()

df = pd.DataFrame(raw, columns=["ID", "Zaman", "Güç", "Voltaj", "Akım", "Isı"])

# KPI
k1, k2, k3, k4 = st.columns(4)
k1.metric("Toplam Güç", f"{df['Güç'].sum()/1000:.2f} kW")
k2.metric("Ort. Voltaj", f"{df['Voltaj'].mean():.1f} V")
k3.metric("Max Sıcaklık", f"{df['Isı'].max():.1f} °C")
k4.metric("Aktif Cihaz", len(df))
st.divider()

# --- SEKMELER ---
tab_list, tab_graph, tab_multi = st.tabs(["📋 Liste", "📈 Detaylı Analiz (Geçmiş)", "⚔️ Karşılaştırma"])

# TAB 1: LİSTE
with tab_list:
    st.dataframe(df.set_index("ID"), use_container_width=True)

# TAB 2: DETAYLI GEÇMİŞ ANALİZİ
with tab_graph:
    c_sel, c_time = st.columns([1, 2])
    with c_sel:
        all_ids = sorted(df["ID"].unique())
        selected_id = st.selectbox("Cihaz Seçin:", all_ids, key="graph_id_sel")
    with c_time:
        # ZAMAN ARALIĞI SEÇİCİSİ
        time_period = st.select_slider(
            "⏳ Analiz Periyodu:", 
            options=["Son 1 Saat", "Son 6 Saat", "Son 24 Saat", "Son 1 Hafta", "Son 1 Ay"],
            value="Son 1 Saat"
        )
    
    # Saate çevir
    hours_map = {"Son 1 Saat": 1, "Son 6 Saat": 6, "Son 24 Saat": 24, "Son 1 Hafta": 168, "Son 1 Ay": 720}
    selected_hours = hours_map[time_period]

    if selected_id:
        # GEÇMİŞ VERİYİ ÇEK (Yeni Fonksiyon)
        hist = veritabani.gecmis_verileri_getir(selected_id, saat=selected_hours)
        
        if hist and len(hist) > 0:
            hdf = pd.DataFrame(hist, columns=["zaman", "guc", "voltaj", "akim", "sicaklik"])
            hdf["zaman"] = pd.to_datetime(hdf["zaman"])
            
            st.markdown(f"#### 📊 Cihaz {selected_id} - {time_period} Performansı")
            
            # 1. GÜÇ GRAFİĞİ (Area)
            fig_p = px.area(hdf, x="zaman", y="guc", title="Güç Üretimi (Watt)", markers=len(hdf)<100)
            fig_p.update_traces(line_color="#FBBF24", fillcolor="rgba(251, 191, 36, 0.2)")
            fig_p.update_layout(height=350, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font_color="white")
            st.plotly_chart(fig_p, use_container_width=True)
            
            # 2. VOLTAJ & AKIM
            c1, c2 = st.columns(2)
            with c1:
                fig_v = px.line(hdf, x="zaman", y="voltaj", title="Voltaj (V)")
                fig_v.update_traces(line_color="#60A5FA")
                fig_v.update_layout(height=250, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font_color="white")
                st.plotly_chart(fig_v, use_container_width=True)
            with c2:
                fig_t = px.line(hdf, x="zaman", y="sicaklik", title="Sıcaklık (°C)")
                fig_t.update_traces(line_color="#F87171")
                fig_t.add_hline(y=60, line_dash="dot", line_color="red")
                fig_t.update_layout(height=250, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font_color="white")
                st.plotly_chart(fig_t, use_container_width=True)
        else:
            st.info(f"Cihaz {selected_id} için seçilen aralıkta veri bulunamadı. (Veritabanı yeni olabilir)")

# TAB 3: ÇOKLU ANALİZ
with tab_multi:
    ids = st.multiselect("Karşılaştırılacak Cihazlar:", all_ids, default=all_ids[:2] if len(all_ids)>0 else None)
    if ids:
        for sid in ids:
            with st.container():
                st.markdown(f"#### 📡 Cihaz {sid}")
                # Buraya da sadece son 1 saati getirelim ki hızlı açılsın
                h_data = veritabani.gecmis_verileri_getir(sid, saat=1)
                if h_data:
                    tdf = pd.DataFrame(h_data, columns=["zaman", "guc", "voltaj", "akim", "sicaklik"])
                    tdf["zaman"] = pd.to_datetime(tdf["zaman"])
                    c_a, c_b = st.columns(2)
                    with c_a:
                        fp = px.line(tdf, x="zaman", y="guc", title="Güç (W)")
                        fp.update_traces(line_color="#FBBF24")
                        fp.update_layout(height=200, margin=dict(t=30,b=0,l=0,r=0), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font_color="white")
                        st.plotly_chart(fp, use_container_width=True)
                    with c_b:
                        fv = px.line(tdf, x="zaman", y="voltaj", title="Voltaj (V)")
                        fv.update_traces(line_color="#60A5FA")
                        fv.update_layout(height=200, margin=dict(t=30,b=0,l=0,r=0), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font_color="white")
                        st.plotly_chart(fv, use_container_width=True)
                st.markdown("---")

# OTOMATİK YENİLEME
if auto_refresh:
    time.sleep(3)
    st.rerun()