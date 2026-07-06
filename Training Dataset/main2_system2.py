import firebase_admin
from firebase_admin import credentials, db
import joblib
import pandas as pd
import time
import warnings

# Mengabaikan peringatan jika ada
warnings.simplefilter(action='ignore', category=FutureWarning)

print("=== SISTEM REKOMENDASI PUPUK (AI BACKEND) AKTIF ===")
print("1. Memuat Model AI XGBoost...")
# (PERBAIKAN 1) Menggunakan model terbaru yang sudah diselaraskan dengan Bab 3
nama_model = 'model_rekomendasi_npk_fix5.pkl' 
try:
    model_ai = joblib.load(nama_model) 
    print(f"-> Model AI '{nama_model}' Berhasil Dimuat!")
except FileNotFoundError:
    print(f"[ERROR] File {nama_model} tidak ditemukan! Pastikan Anda sudah menjalankan file training.")
    exit()

print("2. Menghubungkan ke Proyek Firebase...")
cred = credentials.Certificate("kredensial_firebase.json")
URL_DB = 'https://rekomendasi-pupuk-default-rtdb.asia-southeast1.firebasedatabase.app/'

firebase_admin.initialize_app(cred, {
    'databaseURL': URL_DB
})
print(f"-> Terhubung ke: {URL_DB}")
print("-> Menunggu data masuk dari ESP32...")

def proses_data_baru(event):
    data_masuk = event.data
    
    # Memastikan data yang masuk tidak kosong dan berupa dictionary
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
            
            # Nilai Target Berdasarkan Literatur (Untuk Input AI)
            n_target, p_target, k_target = 30.0, 40.0, 100.0

            # Rule-Based Logic: Cek apakah tanah sudah berada di Zona Aman
            if (n_min <= n_sekarang <= n_max) and (p_min <= p_sekarang <= p_max) and (k_min <= k_sekarang <= k_max):
                print(f"\n--- DATA BARU DITERIMA (N:{n_sekarang} P:{p_sekarang} K:{k_sekarang}) ---")
                print("-> Status Tanah: IDEAL. Memasuki Zona Toleransi (Deadband).")
                
                kebutuhan_n = kebutuhan_p = kebutuhan_k = 0.0
                dosis_final = 0.0
                volume_air_ml = 200 # Hanya siram air biasa untuk menjaga kelembapan
                jadwal_selanjutnya = "Lusa"
            
            else:
                print(f"\n--- DATA BARU DITERIMA (N:{n_sekarang} P:{p_sekarang} K:{k_sekarang}) ---")
                print("-> Status Tanah: KURANG/TIDAK SEIMBANG. Memanggil AI...")
                
                # ===============================================================
                # (PERBAIKAN 2) Input AI disesuaikan menjadi 6 dimensi (Bab 3 Hal. 10)
                # ===============================================================
                input_ai = pd.DataFrame([{
                    'N_awal': n_sekarang, 
                    'P_awal': p_sekarang, 
                    'K_awal': k_sekarang,
                    'N_target': n_target,
                    'P_target': p_target,
                    'K_target': k_target
                }])
                
                # ===============================================================
                # (PERBAIKAN 3) AI langsung mengeluarkan nilai Dosis (Gram)
                # ===============================================================
                # Prediksi AI XGBoost (menghasilkan 1 angka numerik)
                prediksi_dosis = float(model_ai.predict(input_ai)[0])
                
                # PEMBATASAN DOSIS MAKSIMAL 5 GRAM (Fungsi Relasional Bab 3 Hal. 12)
                dosis_final = max(0.0, min(5.0, prediksi_dosis))
                dosis_final = round(dosis_final, 1)

                if dosis_final > 5.0:
                    print(f"-> [INFO] Dosis asli dari AI adalah {prediksi_dosis}g, namun dibatasi ke 5.0g demi keamanan tanaman.")
                elif dosis_final == 0.0:
                     # Mencegah dosis 0 jika ternyata status tanah tidak seimbang tapi error pembulatan
                    dosis_final = 1.0 

                # Menghitung selisih manual untuk dikirimkan sebagai informasi ke Firebase
                kebutuhan_n = max(0.0, n_target - n_sekarang)
                kebutuhan_p = max(0.0, p_target - p_sekarang)
                kebutuhan_k = max(0.0, k_target - k_sekarang)

                volume_air_ml = round(dosis_final * 100) # Misal: 1 gram pupuk dilarutkan ke 100ml air
                jadwal_selanjutnya = "Besok Pagi"
            
            print(f"Hasil AI      : Direkomendasikan {dosis_final} gram pupuk")
            print(f"Air Pelarut   : {volume_air_ml} ml")
            print(f"Jadwal Berikut: {jadwal_selanjutnya}")

            # MENGIRIM KEMBALI PAKET BALASAN LENGKAP KE FIREBASE
            ref_balasan = db.reference('/rekomendasi_keluar')
            ref_balasan.set({
                'kebutuhan_N_poin': round(float(kebutuhan_n), 1),
                'kebutuhan_P_poin': round(float(kebutuhan_p), 1),
                'kebutuhan_K_poin': round(float(kebutuhan_k), 1),
                'dosis_gram': float(dosis_final),
                'volume_air_ml': int(volume_air_ml), # Diubah menjadi integer (angka bulat) agar lebih aman
                'jadwal': jadwal_selanjutnya,
                'status': 'online',
                'timestamp': time.strftime("%d-%m-%Y | %H:%M:%S")
            })
            
            print("-> Rekomendasi berhasil dikirim ke Firebase.")

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