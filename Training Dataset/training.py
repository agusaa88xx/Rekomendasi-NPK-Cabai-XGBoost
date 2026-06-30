import pandas as pd
import numpy as np
from scipy.interpolate import interp1d
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, r2_score
import joblib
import warnings

warnings.simplefilter(action='ignore', category=FutureWarning)

print("=== TAHAP 1: MEMBANGUN DATASET (MODE BERTAHAP) ===")
N_AWAL, P_AWAL, K_AWAL = 16.0, 22.0, 46.0

# Rentang Dosis Bertahap (0 sampai 5 gram) dan proyeksi kenaikan unsur haranya
# Pastikan angka proyeksi ini logis dan tidak over-saturasi
dosis_0 = [0, 1, 2, 3, 4, 5]
n_0 = [10.0, 20.0, 28.7, 32.9, 35.0, 37.0] 
p_0 = [14.0, 28.0, 41.0, 45.8, 50.0, 52.1] 
k_0 = [28.0, 55.0, 82.1, 92.7, 100.0, 105.1]

# Fungsi Garis Penghubung (Interpolasi)
f_n0 = interp1d(dosis_0, n_0, kind='linear')
f_p0 = interp1d(dosis_0, p_0, kind='linear')
f_k0 = interp1d(dosis_0, k_0, kind='linear')

dataset = []
np.random.seed(42)
n_samples_per_dose = 100 # Diperbanyak agar AI lebih pintar

# Mencetak Data Sintetis 
for d in np.arange(0, 5.1, 0.1):
    for _ in range(n_samples_per_dose):
        dataset.append({
            'N_Awal': max(0, round(np.random.normal(N_AWAL, 1.0), 1)), 
            'P_Awal': max(0, round(np.random.normal(P_AWAL, 1.0), 1)), 
            'K_Awal': max(0, round(np.random.normal(K_AWAL, 1.5), 1)),
            'N_Target': max(0, round(np.random.normal(f_n0(d), 1.5), 1)), 
            'P_Target': max(0, round(np.random.normal(f_p0(d), 2.0), 1)), 
            'K_Target': max(0, round(np.random.normal(f_k0(d), 3.0), 1)),
            'Dosis_Pupuk_Gram': round(d, 1)
        })

df_augmented = pd.DataFrame(dataset)
print(f"Berhasil membuat {df_augmented.shape[0]} baris data yang realistis!")

print("\n=== TAHAP 2: TRAINING MODEL XGBOOST ===")
# Hanya 6 Vektor Fitur (Tanpa Metode_Pemberian)
X = df_augmented[['N_Awal', 'P_Awal', 'K_Awal', 'N_Target', 'P_Target', 'K_Target']]
y = df_augmented['Dosis_Pupuk_Gram']

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

model_xgb = xgb.XGBRegressor(
    objective='reg:squarederror',
    n_estimators=150,
    learning_rate=0.1,
    max_depth=6,
    random_state=42
)

model_xgb.fit(X_train, y_train)
y_pred = model_xgb.predict(X_test)
rmse = np.sqrt(mean_squared_error(y_test, y_pred))
r2 = r2_score(y_test, y_pred)

print("\n=== HASIL EVALUASI MODEL YANG JUJUR ===")
print(f"Nilai RMSE      : {rmse:.4f} gram")
print(f"Nilai R-Squared : {r2:.4f} (atau {r2*100:.2f}%)")
print("========================================")

joblib.dump(model_xgb, 'model_xgboost_jujur.pkl')
print("Model berhasil disimpan sebagai 'model_xgboost_jujur.pkl'")