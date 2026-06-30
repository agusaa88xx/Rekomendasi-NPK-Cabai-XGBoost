#include <WiFi.h>
#include <Firebase_ESP_Client.h>
#include "secret.h"

// Helper untuk Firebase
#include "addons/TokenHelper.h"
#include "addons/RTDBHelper.h"

// Library untuk mengambil waktu dari Internet
#include <time.h> 

// ========================================================
// 1. KREDENSIAL WIFI & FIREBASE
// ========================================================
#define WIFI_SSID WIFI_NAME
#define WIFI_PASSWORD WIFI_PASS
#define API_KEY HOST_APIKEY
#define DATABASE_URL URL_APIKEY

// Objek Firebase
FirebaseData fbdo;
FirebaseAuth auth;
FirebaseConfig config;

// ========================================================
// 2. SETUP SERIAL RS485
// ========================================================
HardwareSerial modbus(2); 

// Perintah Hex untuk Sensor NPK (Alamat Memori 0)
const byte npkInquiry[] = {0x01, 0x03, 0x00, 0x1E, 0x00, 0x03, 0x65, 0xCD};
byte values[11]; 

void setup() {
  Serial.begin(115200);
  
  // Baudrate 9600 sesuai yang berhasil di percobaan terakhir
  modbus.begin(9600, SERIAL_8N1, 16, 17); 

  // Bersihkan buffer serial
  modbus.flush(); 
  while(modbus.available()) modbus.read(); 

  Serial.println("\n--- Memulai Sistem Logger NPK ---");

  // ========================================================
  // 3. KONEKSI WIFI
  // ========================================================
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("Menghubungkan ke WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    Serial.print(".");
    delay(500);
  }
  Serial.println("\nWiFi Terhubung!");

  // ========================================================
  // 4. SINKRONISASI WAKTU (NTP) UNTUK TIMESTAMP
  // ========================================================
  Serial.print("Menyinkronkan waktu...");
  // Set zona waktu WIB (UTC+7) -> 7 * 3600 detik.
  configTime(7 * 3600, 0, "pool.ntp.org", "time.nist.gov");
  
  struct tm timeinfo;
  while (!getLocalTime(&timeinfo)) {
    Serial.print(".");
    delay(1000);
  }
  Serial.println("\nWaktu berhasil disinkronisasi!");

  // ========================================================
  // 5. KONEKSI FIREBASE
  // ========================================================
  config.api_key = API_KEY;
  config.database_url = DATABASE_URL;
  config.signer.test_mode = true; 
  
  Firebase.begin(&config, &auth);
  Firebase.reconnectWiFi(true);
  
  // Toleransi timeout Firebase
  Firebase.RTDB.setMaxRetry(&fbdo, 3);
  Firebase.RTDB.setMaxErrorQueue(&fbdo, 10);
  
  Serial.println("Firebase Siap!");
  Serial.println("---------------------------------");
}

void loop() {
  int n_val = 0, p_val = 0, k_val = 0;

  // Bersihkan sisa data sampah di buffer serial sebelum bertanya
  while(modbus.available()) {
    modbus.read(); 
  }

  // 1. Minta data dari sensor
  modbus.write(npkInquiry, sizeof(npkInquiry));
  modbus.flush(); 
  
  delay(100); // Beri jeda sensor merespon

  // 2. Baca balasan
  if (modbus.available() >= 11) { 
    Serial.print("RAW DATA SENSOR: "); // <-- TAMBAHAN X-RAY
    for (int i = 0; i < 11; i++) {
      values[i] = modbus.read();
      Serial.print(values[i], HEX);    // <-- Menampilkan wujud asli data
      Serial.print(" ");
    }
    Serial.println(); 
    
    // Ekstraksi NPK
    n_val = (values[3] << 8) | values[4];
    p_val = (values[5] << 8) | values[6];
    k_val = (values[7] << 8) | values[8];

    Serial.printf("Data Sensor -> N: %d | P: %d | K: %d\n", n_val, p_val, k_val);

    // 3. Ambil waktu saat ini (Timestamp)
    struct tm timeinfo;
    String timestamp_str = "Waktu_Error";
    if (getLocalTime(&timeinfo)) {
      char timeStringBuff[50];
      // Format waktu: Tahun-Bulan-Tanggal Jam:Menit:Detik
      strftime(timeStringBuff, sizeof(timeStringBuff), "%Y-%m-%d %H:%M:%S", &timeinfo);
      timestamp_str = String(timeStringBuff);
    }

    // 4. Kirim Data ke Firebase
    if (Firebase.ready()) {
      FirebaseJson json;
      json.set("timestamp", timestamp_str); // <-- Timestamp ditambahkan di sini
      json.set("nitrogen", n_val);
      json.set("fosfor", p_val);
      json.set("kalium", k_val);
      
      // Label eksperimen
      json.set("polybag_id", "Polybag-D");
      json.set("fase", "akhir");
      json.set("dosis_pupuk_gram", 3); 
      json.set("volume_air_ml", 40); 

      if (Firebase.RTDB.pushJSON(&fbdo, "/dataset_npk", &json)) {
        Serial.println("-> [SUKSES] Data + Timestamp tersimpan.");
      } else {
        Serial.println("-> [GAGAL] Menyimpan data: " + fbdo.errorReason());
      }
    }
  } else {
    Serial.println("-> [ERROR] Sensor NPK tidak terdeteksi.");
  }

  Serial.println("---------------------------------");
  
  // Jeda pengambilan data 15 detik
  delay(15000); 
}
