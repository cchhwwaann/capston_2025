/*
 * 캡톤 프로젝트: 3-액추에이터 제어 (J/N, K/M, L/, 키매핑)
 * - Python과 연동
 * - EN 핀들은 모두 5V에 직접 연결 가정
 */

// --- 핀 설정 (이전과 동일) ---
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
  Serial.println("J/N, K/M, L/, 제어 대기 중...");
}

void loop() {
  if (Serial.available()) {
    char cmd = Serial.read(); // 파이썬에서 보낸 명령 읽기

    // ※ 방향이 반대이면 drive() 안의 핀 순서를 서로 바꾸세요.
    switch (cmd) {
      // === 붐 (j/n) ===
      case 'j': // 붐 전진
        drive(PIN_BOOM_RPWM, PIN_BOOM_LPWM, PWM_MAX);
        break;
      case 'n': // 붐 후진
        drive(PIN_BOOM_LPWM, PIN_BOOM_RPWM, PWM_MAX);
        break;
      case '0': // 붐 정지 (키 뗌)
        stop(PIN_BOOM_RPWM, PIN_BOOM_LPWM);
        break;

      // === 암 (k/m) ===
      case 'k': // 암 전진
        drive(PIN_ARM_RPWM, PIN_ARM_LPWM, PWM_MAX);
        break;
      case 'm': // 암 후진
        drive(PIN_ARM_LPWM, PIN_ARM_RPWM, PWM_MAX);
        break;
      case '1': // 암 정지 (키 뗌)
        stop(PIN_ARM_RPWM, PIN_ARM_LPWM);
        break;

      // === 버킷 (l / ,) ===
      case 'l': // 버킷 전진
        drive(PIN_BUCKET_RPWM, PIN_BUCKET_LPWM, PWM_MAX);
        break;
      case ',': // 버킷 후진
        drive(PIN_BUCKET_LPWM, PIN_BUCKET_RPWM, PWM_MAX);
        break;
      case '2': // 버킷 정지 (키 뗌)
        stop(PIN_BUCKET_RPWM, PIN_BUCKET_LPWM);
        break;
    }
  }
}