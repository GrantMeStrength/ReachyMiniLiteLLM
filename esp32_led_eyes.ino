/*
 * Reachy Mini LED Eyes — ESP32 Firmware
 *
 * Controls two RGB LEDs inside the robot's head via serial commands.
 * Connected to the robot's internal USB hub.
 *
 * Commands (115200 baud, newline-terminated):
 *   L0:r,g,b   — Set left eye  (values 0-255)
 *   L1:r,g,b   — Set right eye (values 0-255)
 *   LA:r,g,b   — Set both eyes (values 0-255)
 *   OFF        — Turn off both LEDs
 *   PING       — Returns PONG (health check)
 *   RESET      — Reboot the board (re-emits READY on boot)
 *
 * Responses: OK, ERR, PONG, READY (on boot)
 *
 * Wiring (XIAO ESP32-C6, one tri-color RGB LED per eye):
 *   Each color leg connects to its pin through a 150 ohm resistor.
 *   L0 (left eye):  D0=GPIO0 (R), D1=GPIO1 (G), D2=GPIO2 (B)
 *   L1 (right eye): D3=GPIO21 (R), D4=GPIO22 (B), D5=GPIO23 (G)
 *   Common leg: 3V3 (common-anode LEDs — inverted PWM below).
 */

#define L0_R  0
#define L0_G  1
#define L0_B  2
#define L1_R  21
#define L1_B  22
#define L1_G  23

String inputBuffer = "";

void setLeft(int r, int g, int b) {
  analogWrite(L0_R, 255 - r);
  analogWrite(L0_G, 255 - g);
  analogWrite(L0_B, 255 - b);
}

void setRight(int r, int g, int b) {
  analogWrite(L1_R, 255 - r);
  analogWrite(L1_G, 255 - g);
  analogWrite(L1_B, 255 - b);
}

void allOff() {
  setLeft(0, 0, 0);
  setRight(0, 0, 0);
}

void processCommand(String cmd) {
  cmd.trim();
  cmd.toUpperCase();

  if (cmd == "OFF") { allOff(); Serial.println("OK"); return; }
  if (cmd == "PING") { Serial.println("PONG"); return; }
  if (cmd == "RESET") {
    allOff();
    Serial.println("OK");
    Serial.flush();
    delay(50);
    ESP.restart();  // reboots and re-emits READY
    return;
  }

  if (cmd.length() < 6 || cmd.charAt(0) != 'L' || cmd.charAt(2) != ':') {
    Serial.println("ERR"); return;
  }

  char target = cmd.charAt(1);
  String rgb = cmd.substring(3);
  int c1 = rgb.indexOf(',');
  int c2 = rgb.indexOf(',', c1 + 1);
  if (c1 < 0 || c2 < 0) { Serial.println("ERR"); return; }

  int r = constrain(rgb.substring(0, c1).toInt(), 0, 255);
  int g = constrain(rgb.substring(c1+1, c2).toInt(), 0, 255);
  int b = constrain(rgb.substring(c2+1).toInt(), 0, 255);

  switch (target) {
    case '0': setLeft(r, g, b); break;
    case '1': setRight(r, g, b); break;
    case 'A': setLeft(r, g, b); setRight(r, g, b); break;
    default: Serial.println("ERR"); return;
  }
  Serial.println("OK");
}

void setup() {
  Serial.begin(115200);
  pinMode(L0_R, OUTPUT); pinMode(L0_G, OUTPUT); pinMode(L0_B, OUTPUT);
  pinMode(L1_R, OUTPUT); pinMode(L1_G, OUTPUT); pinMode(L1_B, OUTPUT);

  // Blue flash on boot
  setLeft(0, 0, 128);
  delay(500);
  allOff();
  Serial.println("READY");
}

void loop() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n' || c == '\r') {
      if (inputBuffer.length() > 0) {
        processCommand(inputBuffer);
        inputBuffer = "";
      }
    } else {
      inputBuffer += c;
    }
  }
}
