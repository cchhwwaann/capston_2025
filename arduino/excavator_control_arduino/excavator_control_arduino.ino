/*
 * 캡톤 프로젝트: 3-액추에이터 제어 (직관적인 1:1 키매핑)
 * - Python과 연동
 * - Go(소문자), Stop(대문자) 명령 수신
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
  Serial.println("1:1 키매핑 제어 대기 중...");
}

void loop() {
  if (Serial.available()) {
    char cmd = Serial.read(); // 파이썬에서 보낸 명령 읽기

    // ※주의: 실제 동작이 반대라면 drive() 함수의 핀 순서를 서로 바꾸세요.
    switch (cmd) {
      // === 붐 (i/k) ===
      case 'i': // 'I' (붐 내림)
        drive(PIN_BOOM_RPWM, PIN_BOOM_LPWM, PWM_MAX); 
        break;
      case 'k': // 'K' (붐 올림)
        drive(PIN_BOOM_LPWM, PIN_BOOM_RPWM, PWM_MAX);
        break;
      case 'I': // 붐 정지 (i 뗌)
      case 'K': // 붐 정지 (k 뗌)
        stop(PIN_BOOM_RPWM, PIN_BOOM_LPWM);
        break;

      // === 암 (w/s) ===
      case 'w': // 'W' (암 펼침)
        drive(PIN_ARM_RPWM, PIN_ARM_LPWM, PWM_MAX);
        break;
      case 's': // 'S' (암 오므림)
        drive(PIN_ARM_LPWM, PIN_ARM_RPWM, PWM_MAX);
        break;
      case 'W': // 암 정지 (w 뗌)
      case 'S': // 암 정지 (s 뗌)
        stop(PIN_ARM_RPWM, PIN_ARM_LPWM);
        break;

      // === 버킷 (j/l) ===
      case 'l': // 'L' (버킷 펼침)
        drive(PIN_BUCKET_RPWM, PIN_BUCKET_LPWM, PWM_MAX);
        break;
      case 'j': // 'J' (버킷 접기)
        drive(PIN_BUCKET_LPWM, PIN_BUCKET_RPWM, PWM_MAX);
        break;
      case 'L': // 버킷 정지 (l 뗌)
      case 'J': // 버킷 정지 (j 뗌)
        stop(PIN_BUCKET_RPWM, PIN_BUCKET_LPWM);
        break;
    }
  }
}