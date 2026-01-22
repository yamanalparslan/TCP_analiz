import streamlit as st
import time
import pandas as pd
import json
import veritabani

st.set_page_config(page_title="Solar Admin Panel", layout="wide", page_icon="🎛️")
veritabani.init_db()

st.title("🎛️ Solar SCADA Yönetim Merkezi")

# --- SIDEBAR: AYARLAR (Buradan DB'yi güncelleyeceğiz) ---
with st.sidebar:
    st.header("⚙️ Sistem Konfigürasyonu")
    
    # Mevcut ayarları DB'den çek
    curr_ip = veritabani.get_ayar("ip")
    curr_port = int(veritabani.get_ayar("port"))
    curr_ids = veritabani.get_ayar("ids")
    curr_refresh = int(veritabani.get_ayar("refresh"))
    curr_conf = json.loads(veritabani.get_ayar("modbus_config"))

    # Form
    with st.form("settings_form"):
        new_ip = st.text_input("IP Adresi", value=curr_ip)
        new_port = st.number_input("Port", value=curr_port)
        new_ids = st.text_input("ID Listesi (Örn: 1,2)", value=curr_ids)
        new_refresh = st.number_input("Tarama Sıklığı (sn)", value=curr_refresh)
        
        st.markdown("### Adres Haritası")
        c1, c2 = st.columns(2)
        n_guc_a = c1.number_input("Güç Adr", value=curr_conf['guc_addr'])
        n_guc_s = c2.number_input("Güç Çarpan", value=curr_conf['guc_scale'])
        
        n_volt_a = c1.number_input("Voltaj Adr", value=curr_conf['volt_addr'])
        n_volt_s = c2.number_input("Voltaj Çarpan", value=curr_conf['volt_scale'])
        
        n_akim_a = c1.number_input("Akım Adr", value=curr_conf['akim_addr'])
        n_akim_s = c2.number_input("Akım Çarpan", value=curr_conf['akim_scale'])
        
        n_isi_a = c1.number_input("Isı Adr", value=curr_conf['isi_addr'])
        n_isi_s = c2.number_input("Isı Çarpan", value=curr_conf['isi_scale'])

        if st.form_submit_button("💾 AYARLARI KAYDET VE UYGULA"):
            veritabani.set_ayar("ip", new_ip)
            veritabani.set_ayar("port", new_port)
            veritabani.set_ayar("ids", new_ids)
            veritabani.set_ayar("refresh", new_refresh)
            
            new_json = {
                'guc_addr': n_guc_a, 'guc_scale': n_guc_s,
                'volt_addr': n_volt_a, 'volt_scale': n_volt_s,
                'akim_addr': n_akim_a, 'akim_scale': n_akim_s,
                'isi_addr': n_isi_a, 'isi_scale': n_isi_s
            }
            veritabani.set_ayar("modbus_config", json.dumps(new_json))
            st.success("Ayarlar Veritabanına Yazıldı! Servis bir sonraki döngüde bunları alacak.")

# --- ANA EKRAN (Sadece DB'den okur, Modbus'a gitmez) ---
st.info(f"📡 Arka plan servisi **{curr_ip}:{curr_port}** adresini **{curr_refresh}** saniyede bir tarıyor.")

# Canlı Tablo
table_spot = st.empty()
def update_ui():
    data = veritabani.tum_cihazlarin_son_durumu()
    if data:
        df = pd.DataFrame(data, columns=["ID", "Son Güncelleme", "Güç", "Voltaj", "Akım", "Isı"])
        df["Son Güncelleme"] = pd.to_datetime(df["Son Güncelleme"]).dt.strftime('%H:%M:%S')
        table_spot.dataframe(df.set_index("ID"), use_container_width=True)
    else:
        table_spot.warning("Henüz veri yok. Servisin çalışmasını bekleyin...")

# Otomatik Yenileme Döngüsü
while True:
    update_ui()
    time.sleep(2) # UI yenileme hızı (Veri çekme değil!)