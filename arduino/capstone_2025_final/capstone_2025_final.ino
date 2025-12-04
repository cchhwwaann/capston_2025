#include "HX711.h"

// --- 핀 설정 ---
constexpr uint8_t PIN_BOOM_RPWM = 3;
constexpr uint8_t PIN_BOOM_LPWM = 5;
constexpr uint8_t PIN_ARM_RPWM = 6;
constexpr uint8_t PIN_ARM_LPWM = 9;
constexpr uint8_t PIN_BUCKET_RPWM = 10;
constexpr uint8_t PIN_BUCKET_LPWM = 11;
constexpr uint8_t PWM_MAX = 200; 

// 로드셀 핀
const int LC1_DOUT = A0;
const int LC1_SCK = A1;
const int LC2_DOUT = A2;
const int LC2_SCK = A3;

HX711 scale1;
HX711 scale2;

void drive(int pinPwm, int pinLow, int speed) {
  digitalWrite(pinLow, LOW);
  analogWrite(pinPwm, speed);
}
void stop(int pin1, int pin2) {
  digitalWrite(pin1, LOW);
  digitalWrite(pin2, LOW);
}

void setup() {
  pinMode(PIN_BOOM_RPWM, OUTPUT); pinMode(PIN_BOOM_LPWM, OUTPUT);
  pinMode(PIN_ARM_RPWM, OUTPUT);  pinMode(PIN_ARM_LPWM, OUTPUT);
  pinMode(PIN_BUCKET_RPWM, OUTPUT); pinMode(PIN_BUCKET_LPWM, OUTPUT);

  stop(PIN_BOOM_RPWM, PIN_BOOM_LPWM);
  stop(PIN_ARM_RPWM, PIN_ARM_LPWM);
  stop(PIN_BUCKET_RPWM, PIN_BUCKET_LPWM);

  Serial.begin(115200); // 속도 유지
  
  scale1.begin(LC1_DOUT, LC1_SCK);
  scale2.begin(LC2_DOUT, LC2_SCK);
}

void loop() {
  // 1. 명령 수신
  if (Serial.available()) {
    char cmd = Serial.read();
    switch (cmd) {
      case 'i': drive(PIN_BOOM_RPWM, PIN_BOOM_LPWM, PWM_MAX); break;
      case 'k': drive(PIN_BOOM_LPWM, PIN_BOOM_RPWM, PWM_MAX); break;
      case 'I': case 'K': stop(PIN_BOOM_RPWM, PIN_BOOM_LPWM); break;

      case 'w': drive(PIN_ARM_RPWM, PIN_ARM_LPWM, PWM_MAX); break;
      case 's': drive(PIN_ARM_LPWM, PIN_ARM_RPWM, PWM_MAX); break;
      case 'W': case 'S': stop(PIN_ARM_RPWM, PIN_ARM_LPWM); break;

      case 'l': drive(PIN_BUCKET_RPWM, PIN_BUCKET_LPWM, PWM_MAX); break;
      case 'j': drive(PIN_BUCKET_LPWM, PIN_BUCKET_RPWM, PWM_MAX); break;
      case 'L': case 'J': stop(PIN_BUCKET_RPWM, PIN_BUCKET_LPWM); break;
    }
  }

  // 2. 데이터 전송 (Non-blocking)
  static long last_val1 = 0;
  static long last_val2 = 0;
  
  if (scale1.is_ready()) last_val1 = scale1.read();
  if (scale2.is_ready()) last_val2 = scale2.read();

  static unsigned long last_send_time = 0;
  if (millis() - last_send_time > 50) { 
    Serial.print(last_val1);
    Serial.print(",");
    Serial.println(last_val2);
    last_send_time = millis();
  }
}