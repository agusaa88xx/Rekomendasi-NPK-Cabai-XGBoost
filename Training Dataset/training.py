import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
import xgboost as xgb
from sklearn.metrics import mean_squared_error, mean_absolute_error
import joblib

# ==========================================
# 1. MEMUAT DATASET
# ==========================================
nama_file_csv = 'dataset_optimasi_npk4.csv'

try:
    df = pd.read_csv(nama_file_csv, sep=';', decimal=',')
    print(f"Berhasil memuat dataset dengan {len(df)} baris.")
except FileNotFoundError:
    print(f"Error: File {nama_file_csv} tidak ditemukan.")
    exit()

# ==========================================
# 2. PEMISAHAN FITUR (X) DAN TARGET (y)
# Sesuai Bab 3: Input 6 Dimensi, Output 1 Dimensi (Gram)
# ==========================================
X = df[['N_awal', 'P_awal', 'K_awal', 'N_target', 'P_target', 'K_target']]
y = df['Dosis_Pupuk_Gram'] 

# --- TAMBAHAN NOISE SENSOR (Opsional, agar data lebih natural) ---
np.random.seed(42)
noise_n = np.random.normal(0, 4.5, len(df))
X.loc[:, 'N_awal'] = np.clip(X['N_awal'] + noise_n, 0, None)
# -----------------------------------------------------------

# Split rasio 80:20
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# ==========================================
# 3. INISIALISASI MODEL XGBOOST
# Sesuai Bab 3: Hyperparameter tuning 
# ==========================================
model = xgb.XGBRegressor(
    n_estimators=150,        # Sesuai Bab 3: Jumlah iterasi pohon 150
    learning_rate=0.1,       # Sesuai Bab 3: Laju pembelajaran (eta) 0.1
    max_depth=6,             # Sesuai Bab 3: Kedalaman cabang 6
    objective='reg:squarederror', 
    random_state=42
)

# ==========================================
# 4. PROSES TRAINING
# ==========================================
print("Sedang melatih model XGBOOST Regression... Mohon tunggu.")
model.fit(X_train, y_train)

# ==========================================
# 5. EVALUASI MODEL & KONVERSI PERSENTASE
# ==========================================
y_pred = model.predict(X_test)

# Menerapkan filter rentang absolut 0-5 gram sesuai Bab 3
y_pred = np.clip(y_pred, 0, 5)

rmse = np.sqrt(mean_squared_error(y_test, y_pred))
mae = mean_absolute_error(y_test, y_pred)

# Menghitung Persentase Error (Normalized Error)
# Rentang target kita adalah 5 gram (0 sampai 5)
rentang_dosis = 5.0 

rmse_persen = (rmse / rentang_dosis) * 100
mae_persen = (mae / rentang_dosis) * 100

akurasi_berdasarkan_rmse = 100 - rmse_persen
akurasi_berdasarkan_mae = 100 - mae_persen

print("\n" + "="*45)
print("HASIL EVALUASI METRIK REGRESI XGBOOST:")
print("="*45)
print(f"Root Mean Square Error (RMSE) : {rmse:.4f} Gram")
print(f"Mean Absolute Error (MAE)     : {mae:.4f} Gram")
print("-" * 45)
print("INTERPRETASI PRESENTASI SIDANG (SKALA 0-100%):")
print(f"Tingkat Error (Meleset) RMSE  : {rmse_persen:.2f}%")
print(f"Tingkat Error (Meleset) MAE   : {mae_persen:.2f}%")
print(f"Tingkat Akurasi Prediksi      : ~{akurasi_berdasarkan_mae:.2f}%")
print("="*45)

# ==========================================
# 6. MENYIMPAN MODEL KE FILE .PKL
# ==========================================
nama_file_pkl = 'model_rekomendasi_npk_final5.pkl'
joblib.dump(model, nama_file_pkl)

print(f"\nModel XGBoost berhasil dilatih dan disimpan ke dalam file: '{nama_file_pkl}'")