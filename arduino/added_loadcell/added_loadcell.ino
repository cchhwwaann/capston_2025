/*
 * 캡톤 프로젝트: 3-액추에이터 제어 + 로드셀 측정 (통합본)
 * - Python과 연동
 * - Go(소문자), Stop(대문자) 명령 수신 (제어)
 * - 로드셀 값을 PC로 실시간 전송 (측정)
 */

#include "HX711.h"

// --- 핀 설정 ---
// 붐 (Boom): 핀 3, 5
constexpr uint8_t PIN_BOOM_RPWM = 3;
constexpr uint8_t PIN_BOOM_LPWM = 5;

// 암 (Arm): 핀 6, 9
constexpr uint8_t PIN_ARM_RPWM = 6;
constexpr uint8_t PIN_ARM_LPWM = 9;

// 버킷 (Bucket): 핀 10, 11
constexpr uint8_t PIN_BUCKET_RPWM = 10;
constexpr uint8_t PIN_BUCKET_LPWM = 11;

// 속도 (0~255)
constexpr uint8_t PWM_MAX = 200;

// 로드셀 핀 설정 (A0, A1로 변경)
const int LOADCELL_DOUT_PIN = A0; // DT 핀
const int LOADCELL_SCK_PIN = A1;  // SCK 핀

// 로드셀 객체 생성
HX711 scale;

// --- 헬퍼 함수: 드라이버 제어 ---
void drive(int pinPwm, int pinLow, int speed) {
  digitalWrite(pinLow, LOW);
  analogWrite(pinPwm, speed);
}
void stop(int pin1, int pin2) {
  digitalWrite(pin1, LOW);
  digitalWrite(pin2, LOW);
}

void setup() {
  // 6개 핀 모두 OUTPUT으로 설정
  pinMode(PIN_BOOM_RPWM, OUTPUT);
  pinMode(PIN_BOOM_LPWM, OUTPUT);
  pinMode(PIN_ARM_RPWM, OUTPUT);
  pinMode(PIN_ARM_LPWM, OUTPUT);
  pinMode(PIN_BUCKET_RPWM, OUTPUT);
  pinMode(PIN_BUCKET_LPWM, OUTPUT);

  // 모든 액추에이터 정지 상태로 시작
  stop(PIN_BOOM_RPWM, PIN_BOOM_LPWM);
  stop(PIN_ARM_RPWM, PIN_ARM_LPWM);
  stop(PIN_BUCKET_RPWM, PIN_BUCKET_LPWM);

  Serial.begin(9600);
  Serial.println("제어 및 로드셀 측정 대기 중...");

  // 로드셀 초기화
  Serial.println("로드셀 초기화 중...");
  scale.begin(LOADCELL_DOUT_PIN, LOADCELL_SCK_PIN);
  
  Serial.println("현재 무게를 0점(Tare)으로 설정합니다.");
  scale.tare(); // 현재 무게를 0으로 설정
  Serial.println("0점 설정 완료. 데이터 전송 시작.");
}

void loop() {
  
  // --- 1. Python으로부터 제어 명령 수신 ---
  if (Serial.available()) {
    char cmd = Serial.read();
    switch (cmd) {
      // === 붐 (i/k) ===
      case 'i': drive(PIN_BOOM_RPWM, PIN_BOOM_LPWM, PWM_MAX); break;
      case 'k': drive(PIN_BOOM_LPWM, PIN_BOOM_RPWM, PWM_MAX); break;
      case 'I':
      case 'K': stop(PIN_BOOM_RPWM, PIN_BOOM_LPWM); break;

      // === 암 (w/s) ===
      case 'w': drive(PIN_ARM_RPWM, PIN_ARM_LPWM, PWM_MAX); break;
      case 's': drive(PIN_ARM_LPWM, PIN_ARM_RPWM, PWM_MAX); break;
      case 'W':
      case 'S': stop(PIN_ARM_RPWM, PIN_ARM_LPWM); break;

      // === 버킷 (j/l) ===
      case 'l': drive(PIN_BUCKET_RPWM, PIN_BUCKET_LPWM, PWM_MAX); break;
      case 'j': drive(PIN_BUCKET_LPWM, PIN_BUCKET_RPWM, PWM_MAX); break;
      case 'L':
      case 'J': stop(PIN_BUCKET_RPWM, PIN_BUCKET_LPWM); break;
    }
  }

  // --- 2. 로드셀 값 측정 및 PC로 전송 ---
  if (scale.is_ready()) {
    long reading = scale.get_value(5); // 5번 평균
    Serial.println(reading); // PC(Python)로 전송
  }
  
  delay(10); // 루프 안정화
}