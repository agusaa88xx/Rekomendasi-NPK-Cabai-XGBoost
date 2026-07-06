import pandas as pd
import numpy as np

# ==========================================
# 1. MEMUAT DATA MENTAH DARI CSV
# ==========================================
# Pastikan file csv ini berada di folder (direktori) yang sama dengan script Python ini
nama_file_mentah = 'dataset_bersih_vertikal day 4.csv'

try:
    # Membaca data yang Anda lampirkan
    df_awal = pd.read_csv(nama_file_mentah)
    print(f"Berhasil memuat {len(df_awal)} baris data mentah dari '{nama_file_mentah}'.\n")
except FileNotFoundError:
    print(f"Error: File '{nama_file_mentah}' tidak ditemukan.")
    print("Pastikan file berada di folder yang sama dengan script ini.")
    exit()

# ==========================================
# 2. PENGATURAN TARGET & PARAMETER (DI-OPTIMASI)
# ==========================================
N_TARGET = 30
P_TARGET = 40
K_TARGET = 100

# (Tuning) Ditingkatkan menjadi 10.000 baris untuk ruang sampel yang maksimal
JUMLAH_DATA_SINTETIS = 10000 
# (Tuning) Faktor variasi dinaikkan menjadi 2.5 agar data mencakup kondisi lapangan yang ekstrem
FAKTOR_VARIASI = 2.5 

# ==========================================
# 3. PROSES AUGMENTASI (Pembuatan Data Sintetis)
# ==========================================
np.random.seed(42) # Agar hasil random konsisten jika dijalankan ulang

# Menggunakan distribusi normal berdasarkan data awal dari kolom dataset Anda
N_sintetis = np.random.normal(df_awal['nitrogen'].mean(), df_awal['nitrogen'].std() * FAKTOR_VARIASI, JUMLAH_DATA_SINTETIS)
P_sintetis = np.random.normal(df_awal['fosfor'].mean(), df_awal['fosfor'].std() * FAKTOR_VARIASI, JUMLAH_DATA_SINTETIS)
K_sintetis = np.random.normal(df_awal['kalium'].mean(), df_awal['kalium'].std() * FAKTOR_VARIASI, JUMLAH_DATA_SINTETIS)

# Menambahkan fungsi clip agar nilai sensor tidak ada yang minus
N_sintetis = np.clip(N_sintetis, 0, None)
P_sintetis = np.clip(P_sintetis, 0, None)
K_sintetis = np.clip(K_sintetis, 0, None)

# Membulatkan nilai ke 1 angka di belakang koma 
N_sintetis = np.round(N_sintetis, 1)
P_sintetis = np.round(P_sintetis, 1)
K_sintetis = np.round(K_sintetis, 1)

# ==========================================
# 4. MENGHITUNG KEBUTUHAN & DOSIS PUPUK (0-5 Gram)
# ==========================================
# Kebutuhan = Target - Nilai Saat ini. Jika nilai saat ini melebihi target, kebutuhannya 0
N_butuh = np.clip(N_TARGET - N_sintetis, 0, None)
P_butuh = np.clip(P_TARGET - P_sintetis, 0, None)
K_butuh = np.clip(K_TARGET - K_sintetis, 0, None)

# --- LOGIKA PENENTUAN DOSIS ---
# Menghitung rasio kekurangan (0.0 hingga 1.0) dari masing-masing elemen
rasio_N = N_butuh / N_TARGET
rasio_P = P_butuh / P_TARGET
rasio_K = K_butuh / K_TARGET

# AI harus merekomendasikan pupuk berdasarkan elemen yang "paling krisis / paling kurang"
rasio_maks = np.maximum.reduce([rasio_N, rasio_P, rasio_K])

# Mengonversi rasio kekurangan menjadi gram (Maksimal absolut 5 Gram sesuai Bab 3)
dosis_gram = rasio_maks * 5.0
dosis_gram = np.clip(dosis_gram, 0, 5.0) 
dosis_gram = np.round(dosis_gram, 1)

# ==========================================
# 5. MENYUSUN DAN MENYIMPAN KE CSV
# ==========================================
df_final = pd.DataFrame({
    'N_awal': N_sintetis,
    'P_awal': P_sintetis,
    'K_awal': K_sintetis,
    'N_target': N_TARGET,
    'P_target': P_TARGET,
    'K_target': K_TARGET,
    'Kekurangan_N': np.round(N_butuh, 1),
    'Kekurangan_P': np.round(P_butuh, 1),
    'Kekurangan_K': np.round(K_butuh, 1),
    'Dosis_Pupuk_Gram': dosis_gram  # <--- KOLOM BARU YANG DIBUTUHKAN XGBOOST
})

# Menyimpan ke file CSV (Menggunakan format Indonesia dengan ; dan ,)
nama_file_output = 'dataset_optimasi_npk4.csv'
df_final.to_csv(nama_file_output, index=False, sep=';', decimal=',')

print(f"Berhasil! {JUMLAH_DATA_SINTETIS} baris data sintetis telah dibuat.")
print(f"-> Kolom target 'Dosis_Pupuk_Gram' berhasil ditambahkan.")
print(f"Silakan periksa file '{nama_file_output}'.")