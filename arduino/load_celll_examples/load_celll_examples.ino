/*
  HX711 증폭기 및 로드셀 기본 작동 테스트
  
  이 코드는 4선식 로드셀과 HX711 모듈이 아두이노와 
  정상적으로 통신하고 값을 읽어오는지 확인하기 위한 기본 예제입니다.
  
  시리얼 모니터를 열어 (9600-N-8-1) 값이 출력되는지 확인하세요.
  
  [ HX711 모듈과 아두이노 연결 ]
  VCC -> 5V
  GND -> GND
  DT  -> A0 (Data Out - 데이터 핀, 다른 디지털/아날로그 핀도 가능)
  SCK -> A1 (Serial Clock - 클럭 핀, 다른 디지털/아날로그 핀도 가능)
  
  [ 4선식 로드셀과 HX711 모듈 연결 ]
  (로드셀 선 색상은 제조사마다 다를 수 있습니다. 일반적인 경우입니다.)
  Red   (E+) -> E+
  Black (E-) -> E-
  White (A-) -> A-
  Green (A+) -> A+
*/

// 설치하신 HX711 라이브러리를 포함합니다.
#include "HX711.h"

// HX711 모듈에 연결된 핀을 정의합니다.
// 아두이노의 아날로그 핀도 디지털 I/O로 사용할 수 있습니다.
const int LOADCELL_DOUT_PIN = 3; // DT 핀
const int LOADCELL_SCK_PIN = 2;  // SCK 핀

// HX711 객체를 생성합니다.
HX711 scale;

void setup() {
  // 시리얼 통신을 9600 속도로 시작합니다. (PC와 통신용)
  Serial.begin(9600);
  while (!Serial) {
    ; // 시리얼 포트가 연결될 때까지 대기 (Leonardo/Micro 등)
  }
  
  Serial.println("HX711 로드셀 테스트 시작");
  Serial.println("센서 초기화 중...");

  // HX711 모듈을 초기화합니다.
  scale.begin(LOADCELL_DOUT_PIN, LOADCELL_SCK_PIN);

  Serial.println("초기화 완료. 현재 상태의 무게를 0점(Tare)으로 설정합니다.");
  Serial.println("잠시 기다려주세요...");

  // 현재 무게를 0점으로 설정(Taring)합니다.
  // 이 작업을 통해 빈 버킷(또는 아무것도 없는 상태)을 '0'으로 만듭니다.
  scale.tare(); 

  Serial.println("0점 설정 완료. 값 읽기를 시작합니다.");
  Serial.println("-------------------------------------");
  Serial.println("측정 값 (Raw Value):");
}

void loop() {
  // 센서에서 값이 준비되었는지 확인합니다.
  if (scale.is_ready()) {
    // 5번 읽은 값의 평균을 가져와 노이즈를 줄입니다.
    long reading = scale.get_value(5); 
    
    // 읽은 값을 시리얼 모니터에 출력합니다.
    // 지금은 'g' 단위가 아닌 센서의 원시 값(raw data)입니다.
    Serial.print("Raw: ");
    Serial.println(reading);
    
  } else {
    // 센서가 준비되지 않았을 경우 메시지를 출력합니다.
    // (이 메시지가 계속 뜬다면 연결을 확인해보세요)
    Serial.println("HX711 모듈을 찾을 수 없습니다.");
  }

  // 0.5초 대기 후 다음 값을 읽습니다.
  delay(500); 
}