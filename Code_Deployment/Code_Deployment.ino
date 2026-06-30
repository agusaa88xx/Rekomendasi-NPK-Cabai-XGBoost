#include <WiFi.h>
#include <Firebase_ESP_Client.h> 

// ================= KONFIGURASI JARINGAN =================
#define WIFI_SSID "PC-DC-1A"
#define WIFI_PASSWORD "karakter"

// ================= KONFIGURASI FIREBASE =================
#define FIREBASE_HOST "rekomendasi-pupuk-default-rtdb.asia-southeast1.firebasedatabase.app"
#define FIREBASE_AUTH "ZpAdb1bhcuWDd6WLSI2hid3ZGVwQNX7MYtMx62JJ" 

// ================= PIN SENSOR RS485 =================
#define RX_PIN 16
#define TX_PIN 17

FirebaseData fbdo;
FirebaseAuth auth;
FirebaseConfig config;

// Variabel Global
float n_sekarang = 0, p_sekarang = 0, k_sekarang = 0;

unsigned long waktuKirimTerakhir = 0;
const long intervalKirim = 10000; // Eksekusi tiap 10 detik

void setup() {
  Serial.begin(115200);
  Serial2.begin(9600, SERIAL_8N1, RX_PIN, TX_PIN); 
  
  Serial.println("\n=== SISTEM REKOMENDASI PUPUK IoT (DEPLOYMENT) ===");
  
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("Menghubungkan ke Wi-Fi");
  while (WiFi.status() != WL_CONNECTED) {
    Serial.print(".");
    delay(500);
  }
  Serial.println("\n[SUKSES] Terhubung ke Wi-Fi!");

  config.database_url = FIREBASE_HOST;
  config.signer.tokens.legacy_token = FIREBASE_AUTH;
  Firebase.begin(&config, &auth);
  Firebase.reconnectWiFi(true);
  Serial.println("[SUKSES] Terhubung ke Firebase!");
}

void loop() {
  if (millis() - waktuKirimTerakhir >= intervalKirim) {
    waktuKirimTerakhir = millis();
    
    bacaSensorNPK(); 
    
    Serial.println("\n--- MENGIRIM DATA AKTUAL KE FIREBASE ---");
    Serial.printf("Kondisi Tanah: N:%.1f P:%.1f K:%.1f\n", n_sekarang, p_sekarang, k_sekarang);
    
    // ESP32 hanya mengirim nilai aktual, tidak lagi mengirim target
    Firebase.RTDB.setFloat(&fbdo, "/sensor_masuk/nitrogen", n_sekarang);
    Firebase.RTDB.setFloat(&fbdo, "/sensor_masuk/fosfor", p_sekarang);
    Firebase.RTDB.setFloat(&fbdo, "/sensor_masuk/kalium", k_sekarang);
    
    Serial.println("Menunggu AI di Backend Python berpikir...");
    delay(2500); // Jeda sinkronisasi untuk memberi waktu Python mengeksekusi XGBoost
    
    // --- MEMBACA PAKET DATA BALASAN DARI AI ---
    float dosis_rekomendasi = 0;
    int air_ml = 0;
    String jadwal = "";

    // 1. Ambil Dosis Gram
    if (Firebase.RTDB.getFloat(&fbdo, "/rekomendasi_keluar/dosis_gram")) {
      dosis_rekomendasi = fbdo.to<float>();
    }
    // 2. Ambil Volume Air
    if (Firebase.RTDB.getInt(&fbdo, "/rekomendasi_keluar/volume_air_ml")) {
      air_ml = fbdo.to<int>();
    }
    // 3. Ambil Jadwal Pemupukan
    if (Firebase.RTDB.getString(&fbdo, "/rekomendasi_keluar/jadwal")) {
      jadwal = fbdo.to<String>();
    }

    // Tampilkan Output Eksekusi di Serial Monitor
    Serial.println("\n===================================");
    Serial.printf(" REKOMENDASI AI : %s GRAM PUPUK NPK\n", String(dosis_rekomendasi, 1).c_str());
    Serial.printf(" KEBUTUHAN AIR  : %d ML\n", air_ml);
    Serial.printf(" JADWAL SIRAM   : %s\n", jadwal.c_str());
    Serial.println("===================================");
  }
}

void bacaSensorNPK() {
  const byte npkInquiry[] = {0x01, 0x03, 0x00, 0x1E, 0x00, 0x03, 0x65, 0xCD};
  byte respons[11];
  
  while(Serial2.available()) Serial2.read();
  
  Serial2.write(npkInquiry, sizeof(npkInquiry));
  delay(100); 
  
  if (Serial2.available() >= 11) {
    for (int i = 0; i < 11; i++) {
      respons[i] = Serial2.read();
    }
    n_sekarang = (respons[3] << 8) | respons[4];
    p_sekarang = (respons[5] << 8) | respons[6];
    k_sekarang = (respons[7] << 8) | respons[8];
  } else {
    Serial.println("[INFO] Sensor tidak merespons, menggunakan data dummy.");
    n_sekarang = random(10, 20);
    p_sekarang = random(15, 25);
    k_sekarang = random(40, 50);
  }
}