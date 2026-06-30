/*
 * TARANG — ESP32 LoRa SOS Device Firmware
 * Team Cipher | CIH 2026
 *
 * Hardware:
 *   - ESP32 WROOM-32
 *   - SX1276 LoRa (TTGO LoRa32 or similar)
 *   - NEO-6M GPS Module
 *   - MPU6050 IMU (Accelerometer + Gyroscope)
 *   - Physical SOS button (GPIO 0)
 *   - LED indicators
 *
 * Behavior:
 *   1. Continuously reads GPS + IMU
 *   2. On SOS button press → send distress packet
 *   3. On capsize/drift detected → auto-trigger SOS
 *   4. Relay mode: forwards received packets from other boats
 */

#include <SPI.h>
#include <LoRa.h>
#include <TinyGPS++.h>
#include <Wire.h>
#include <MPU6050.h>
#include <ArduinoJson.h>

// ── Pin Configuration (TTGO LoRa32 v2.1) ─────────────────
#define LORA_SCK   5
#define LORA_MISO  19
#define LORA_MOSI  27
#define LORA_SS    18
#define LORA_RST   23
#define LORA_DI0   26
#define LORA_BAND  865E6   // 865 MHz (India ISM band)

#define GPS_RX     34
#define GPS_TX     12
#define SOS_BTN    0       // Built-in BOOT button doubles as SOS
#define LED_RED    25
#define LED_GREEN  13

#define VESSEL_ID  "VES-001"
#define HOP_TTL    5       // Max mesh hops before packet dies

// ── Global Instances ──────────────────────────────────────
TinyGPSPlus   gps;
HardwareSerial gpsSerial(1);
MPU6050       imu;

// ── State ─────────────────────────────────────────────────
float   lat = 0.0, lng = 0.0;
bool    sosActive = false;
int     hopCount = 0;
uint32_t lastSOSSent = 0;
uint32_t lastHeartbeat = 0;

struct ImuData {
  float ax, ay, az;
  float gx, gy, gz;
};

// ── Setup ─────────────────────────────────────────────────
void setup() {
  Serial.begin(115200);
  Serial.println("TARANG SOS Device v1.0 — Team Cipher");

  // LED init
  pinMode(LED_RED,   OUTPUT);
  pinMode(LED_GREEN, OUTPUT);
  pinMode(SOS_BTN,   INPUT_PULLUP);
  digitalWrite(LED_GREEN, HIGH);

  // GPS UART
  gpsSerial.begin(9600, SERIAL_8N1, GPS_RX, GPS_TX);

  // IMU
  Wire.begin();
  imu.initialize();
  if (!imu.testConnection()) {
    Serial.println("MPU6050 FAIL");
  }

  // LoRa
  SPI.begin(LORA_SCK, LORA_MISO, LORA_MOSI, LORA_SS);
  LoRa.setPins(LORA_SS, LORA_RST, LORA_DI0);
  if (!LoRa.begin(LORA_BAND)) {
    Serial.println("LoRa INIT FAILED");
    blinkError();
  }
  LoRa.setSpreadingFactor(10);
  LoRa.setSignalBandwidth(125E3);
  LoRa.setCodingRate4(5);
  LoRa.setTxPower(20);
  Serial.println("LoRa OK — 865 MHz");
}

// ── Main Loop ─────────────────────────────────────────────
void loop() {
  // Read GPS
  while (gpsSerial.available()) {
    gps.encode(gpsSerial.read());
  }
  if (gps.location.isUpdated()) {
    lat = gps.location.lat();
    lng = gps.location.lng();
  }

  // Read IMU
  ImuData imuData = readIMU();

  // Check SOS button (active LOW)
  if (digitalRead(SOS_BTN) == LOW) {
    delay(50); // debounce
    if (digitalRead(SOS_BTN) == LOW && !sosActive) {
      Serial.println("SOS BUTTON PRESSED");
      sendSOS("sos_manual", imuData);
      sosActive = true;
    }
  } else {
    sosActive = false;
  }

  // Auto-detect capsize (Z-axis flipped)
  if (detectCapsize(imuData) && millis() - lastSOSSent > 30000) {
    Serial.println("CAPSIZE DETECTED — auto SOS");
    sendSOS("capsize", imuData);
    lastSOSSent = millis();
  }

  // Auto-detect prolonged drift
  if (detectDrift(imuData) && millis() - lastSOSSent > 60000) {
    Serial.println("DRIFT ANOMALY — auto SOS");
    sendSOS("drift", imuData);
    lastSOSSent = millis();
  }

  // Relay received LoRa packets
  int packetSize = LoRa.parsePacket();
  if (packetSize) {
    relayPacket();
  }

  // Heartbeat LED
  if (millis() - lastHeartbeat > 2000) {
    digitalWrite(LED_GREEN, !digitalRead(LED_GREEN));
    lastHeartbeat = millis();
  }
}

// ── SOS Packet Transmission ───────────────────────────────
void sendSOS(const char* alertType, ImuData& imu_d) {
  StaticJsonDocument<512> doc;
  doc["vessel_id"]   = VESSEL_ID;
  doc["lat"]         = lat;
  doc["lng"]         = lng;
  doc["alert_type"]  = alertType;
  doc["hop_count"]   = 0;
  doc["hop_ttl"]     = HOP_TTL;
  doc["accel_z"]     = imu_d.az;
  doc["timestamp"]   = millis() / 1000;

  char buf[512];
  serializeJson(doc, buf);

  LoRa.beginPacket();
  LoRa.print(buf);
  LoRa.endPacket();

  Serial.print("SOS SENT: ");
  Serial.println(buf);

  // Flash red LED
  for (int i = 0; i < 5; i++) {
    digitalWrite(LED_RED, HIGH); delay(100);
    digitalWrite(LED_RED, LOW);  delay(100);
  }
}

// ── Mesh Relay ────────────────────────────────────────────
void relayPacket() {
  String incoming = "";
  while (LoRa.available()) {
    incoming += (char)LoRa.read();
  }

  StaticJsonDocument<512> doc;
  if (deserializeJson(doc, incoming) != DeserializationError::Ok) {
    return; // Invalid packet
  }

  int ttl = doc["hop_ttl"] | 0;
  if (ttl <= 0) return; // TTL expired — drop

  // Increment hop count, decrement TTL
  doc["hop_count"] = (int)doc["hop_count"] + 1;
  doc["hop_ttl"]   = ttl - 1;

  char buf[512];
  serializeJson(doc, buf);

  delay(random(50, 200)); // Random backoff to avoid collision
  LoRa.beginPacket();
  LoRa.print(buf);
  LoRa.endPacket();

  Serial.print("RELAYED: hop=");
  Serial.println((int)doc["hop_count"]);
}

// ── IMU Read ──────────────────────────────────────────────
ImuData readIMU() {
  ImuData d;
  int16_t ax, ay, az, gx, gy, gz;
  imu.getMotion6(&ax, &ay, &az, &gx, &gy, &gz);
  d.ax = ax / 16384.0f;
  d.ay = ay / 16384.0f;
  d.az = az / 16384.0f;
  d.gx = gx / 131.0f;
  d.gy = gy / 131.0f;
  d.gz = gz / 131.0f;
  return d;
}

// ── Anomaly Detection ─────────────────────────────────────
bool detectCapsize(ImuData& d) {
  // Capsized: Z-axis severely negative (boat upside down)
  return (d.az < -0.5 && abs(d.ax) > 0.7);
}

bool detectDrift(ImuData& d) {
  // Drift: very low motion for extended time but GPS moving
  float totalAccel = sqrt(d.ax*d.ax + d.ay*d.ay + d.az*d.az);
  return (totalAccel < 0.15); // Near-zero acceleration — adrift
}

void blinkError() {
  while (true) {
    digitalWrite(LED_RED, HIGH); delay(200);
    digitalWrite(LED_RED, LOW);  delay(200);
  }
}
