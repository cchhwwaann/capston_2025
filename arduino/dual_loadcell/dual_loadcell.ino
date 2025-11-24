/*
 * 캡스톤 프로젝트: 반응속도 최적화 (Non-blocking)
 * - 통신 속도: 115200 bps (고속)
 * - 로드셀: 기다리지 않고(is_ready) 데이터가 있을 때만 읽음
 */

#include "HX711.h"

// --- 핀 설정 ---
constexpr uint8_t PIN_BOOM_RPWM = 3;
constexpr uint8_t PIN_BOOM_LPWM = 5;
constexpr uint8_t PIN_ARM_RPWM = 6;
constexpr uint8_t PIN_ARM_LPWM = 9;
constexpr uint8_t PIN_BUCKET_RPWM = 10;
constexpr uint8_t PIN_BUCKET_LPWM = 11;
constexpr uint8_t PWM_MAX = 200; // 최대 속도 (필요시 255로 상향 가능)

// 로드셀 핀
const int LC1_DOUT = A0;
const int LC1_SCK = A1;
const int LC2_DOUT = A2;
const int LC2_SCK = A3;

HX711 scale1;
HX711 scale2;

// --- 모터 함수 ---
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

  // 🚀 [중요] 통신 속도를 115200으로 올림
  Serial.begin(115200); 
  
  // 로드셀 시작 (tare 사용 안 함 -> 멈춤 방지)
  scale1.begin(LC1_DOUT, LC1_SCK);
  scale2.begin(LC2_DOUT, LC2_SCK);
}

void loop() {
  // ==========================================
  // 1. 모터 제어 (최우선 처리 - 딜레이 0초)
  // ==========================================
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

  // ==========================================
  // 2. 로드셀 읽기 (비동기 방식 - Non-blocking)
  // ==========================================
  // "지금 값 줄 수 있어?"라고 물어보고, "아니"라고 하면 바로 넘어감
  // 절대 기다리지 않음(while문 없음)
  
  static long last_val1 = 0;
  static long last_val2 = 0;
  bool updated = false;

  // 센서 1 확인
  if (scale1.is_ready()) {
    last_val1 = scale1.read(); // get_value() 대신 read() 사용 (더 빠름)
    updated = true;
  }
  
  // 센서 2 확인
  if (scale2.is_ready()) {
    last_val2 = scale2.read();
    updated = true;
  }

  // 값이 갱신되었을 때만 데이터 전송 (또는 일정 주기마다)
  // 너무 자주 보내면 파이썬이 힘들어하므로, 간단한 타이머 적용
  static unsigned long last_send_time = 0;
  if (millis() - last_send_time > 50) { // 50ms (초당 20회) 마다 전송
    Serial.print(last_val1);
    Serial.print(",");
    Serial.println(last_val2);
    last_send_time = millis();
  }
}