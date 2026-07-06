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
# Pastikan nama file model sesuai dengan model XGBoost Anda
model_ai = joblib.load('model_rekomendasi_npk4.pkl') 
print("-> Model AI Berhasil Dimuat!")

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
                
                # Mempersiapkan data untuk diprediksi AI
                input_ai = pd.DataFrame([{
                    'N_awal': n_sekarang, 
                    'P_awal': p_sekarang, 
                    'K_awal': k_sekarang
                }])
                
                # Prediksi AI XGBoost
                prediksi = model_ai.predict(input_ai)[0] 
                
                # ===============================================================
                # PERBAIKAN: Konversi tipe data numpy float32 menjadi float standar Python
                # ===============================================================
                kebutuhan_n = float(max(0, prediksi[0]))
                kebutuhan_p = float(max(0, prediksi[1]))
                kebutuhan_k = float(max(0, prediksi[2]))
                
                # LOGIKA DOSIS DASAR
                total_kekurangan = kebutuhan_n + kebutuhan_p + kebutuhan_k
                dosis_final = round((total_kekurangan / 10), 1) 
                
                # Mencegah dosis 0 jika ternyata status tanah tidak seimbang tapi error pembulatan
                if dosis_final == 0.0 and total_kekurangan > 0:
                    dosis_final = 1.0 
                    
                # PEMBATASAN DOSIS MAKSIMAL 5 GRAM
                if dosis_final > 5.0:
                    print(f"-> [INFO] Dosis asli dari AI adalah {dosis_final}g, namun dibatasi ke 5.0g demi keamanan tanaman.")
                    dosis_final = 5.0

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