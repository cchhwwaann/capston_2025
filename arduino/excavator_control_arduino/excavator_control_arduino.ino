// ===== Python 스크립트와 연동하는 아두이노 코드 =====
// Python이 'j', 'k', 'l' 문자를 직접 보내줍니다.

constexpr uint8_t PIN_RPWM = 5;
constexpr uint8_t PIN_LPWM = 6;
constexpr uint8_t PIN_REN  = 7;
constexpr uint8_t PIN_LEN  = 8;
constexpr uint8_t PWM_MAX  = 200;

void setup() {
  pinMode(PIN_RPWM, OUTPUT);
  pinMode(PIN_LPWM, OUTPUT);
  pinMode(PIN_REN,  OUTPUT);
  pinMode(PIN_LEN,  OUTPUT);

  digitalWrite(PIN_REN, HIGH);
  digitalWrite(PIN_LEN, HIGH);
  digitalWrite(PIN_RPWM, LOW); // 정지 상태로 시작
  digitalWrite(PIN_LPWM, LOW);

  Serial.begin(9600);
  Serial.println("Python 제어 대기 중...");
}

void loop() {
  if (Serial.available()) {
    char cmd = Serial.read(); // 파이썬에서 보낸 명령 읽기

    if (cmd == 'j') {
      // 전진
      digitalWrite(PIN_LPWM, LOW);
      analogWrite(PIN_RPWM, PWM_MAX);
    } else if (cmd == 'k') {
      // 후진
      digitalWrite(PIN_RPWM, LOW);
      analogWrite(PIN_LPWM, PWM_MAX);
    } else if (cmd == 'l') {
      // 정지
      digitalWrite(PIN_RPWM, LOW);
      digitalWrite(PIN_LPWM, LOW);
    }
  }
}