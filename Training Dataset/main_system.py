import firebase_admin
from firebase_admin import credentials, db
import joblib
import pandas as pd
import time
import warnings
import "secret.h"

# Mengabaikan peringatan jika ada
warnings.simplefilter(action='ignore', category=FutureWarning)

print("=== SISTEM REKOMENDASI PUPUK (XGBOOST) - BACKEND AKTIF ===")
print("1. Memuat Model AI...")
model_ai = joblib.load('model_xgboost_jujur.pkl')
print("-> Model AI Berhasil Dimuat!")

print("2. Menghubungkan ke Proyek Firebase...")
cred = credentials.Certificate("kredensial_firebase.json")
URL_DB = URL_APIKEY

firebase_admin.initialize_app(cred, {
    'databaseURL': URL_DB
})
print(f"-> Terhubung ke: {URL_DB}")
print("-> Menunggu data masuk dari ESP32...")

def proses_data_baru(event):
    data_masuk = event.data
    
    if data_masuk and isinstance(data_masuk, dict):
        try:
            # A. MEMBACA KONDISI TANAH AKTUAL DARI SENSOR ESP32
            n_sekarang = float(data_masuk.get('nitrogen', 0))
            p_sekarang = float(data_masuk.get('fosfor', 0))
            k_sekarang = float(data_masuk.get('kalium', 0))
            
            # Rentang Aman Berdasarkan Literatur
            n_min, n_max = 20.0, 40.0
            p_min, p_max = 30.0, 50.0
            k_min, k_max = 80.0, 120.0
            
            # Titik Ekuilibrium (Target AI)
            n_target = 30.0
            p_target = 40.0
            k_target = 100.0

            # Rule-Based Logic: Cek apakah tanah sudah berada di Zona Aman
            if (n_min <= n_sekarang <= n_max) and (p_min <= p_sekarang <= p_max) and (k_min <= k_sekarang <= k_max):
                print(f"\n--- DATA BARU DITERIMA (N:{n_sekarang} P:{p_sekarang} K:{k_sekarang}) ---")
                print("-> Status Tanah: IDEAL. Memasuki Zona Toleransi (Deadband).")
                dosis_final = 0.0
                volume_air_ml = 200 # Hanya siram air biasa untuk menjaga kelembapan
                jadwal_selanjutnya = "Lusa"
            
            else:
                print(f"\n--- DATA BARU DITERIMA (N:{n_sekarang} P:{p_sekarang} K:{k_sekarang}) ---")
                print("-> Status Tanah: KURANG/TIDAK SEIMBANG. Memanggil AI XGBoost...")
                input_ai = pd.DataFrame([{
                    'N_Awal': n_sekarang, 
                    'P_Awal': p_sekarang, 
                    'K_Awal': k_sekarang,
                    'N_Target': n_target, 
                    'P_Target': p_target, 
                    'K_Target': k_target
                }])
                
                prediksi = model_ai.predict(input_ai)[0]
                dosis_final = round(float(prediksi), 1)
                volume_air_ml = round(dosis_final * 100)
                jadwal_selanjutnya = "Besok Pagi"
            
            print(f"Hasil AI      : Direkomendasikan {dosis_final} gram")
            print(f"Air Pelarut   : {volume_air_ml} ml")
            print(f"Jadwal Berikut: {jadwal_selanjutnya}")

            # MENGIRIM KEMBALI PAKET BALASAN LENGKAP KE FIREBASE
            ref_balasan = db.reference('/rekomendasi_keluar')
            ref_balasan.set({
                'dosis_gram': dosis_final,
                'volume_air_ml': volume_air_ml,
                'jadwal': jadwal_selanjutnya,
                'status': 'online',
                'timestamp': time.strftime("%H:%M:%S | %d-%m-%Y")
            })
            
            print("-> Rekomendasi berhasil dikirim ke RTDB.")

        except Exception as e:
            print(f"[GAGAL] Error saat memproses: {e}")

# Memasang listener pada node /sensor_masuk
ref_sensor = db.reference('/sensor_masuk')
listener = ref_sensor.listen(proses_data_baru)

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("\nMenonaktifkan sistem backend...")
    listener.close()
