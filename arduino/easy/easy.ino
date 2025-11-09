void setup() {  
   pinMode(5,OUTPUT);  
   pinMode(6,OUTPUT);  
   pinMode(7,OUTPUT);  
   pinMode(8,OUTPUT);  
   digitalWrite(7,HIGH);  
   digitalWrite(8,HIGH);  
}  
void loop() {  
   digitalWrite(5,LOW);  
   analogWrite(6,100);  
   delay(3000);  
   digitalWrite(6,LOW);  
   analogWrite(5,100);  
   delay(3000);  
}  