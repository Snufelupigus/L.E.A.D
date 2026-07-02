#include <EEPROM.h>
#include <FastLED.h>

#define DATA_PIN 5
#define CHIPSET WS2812B
#define COLOR_ORDER GRB
#define SERIAL_BAUD 9600
#define MAX_LEDS 260
#define DEFAULT_ACTIVE_LEDS 104
#define DEFAULT_BRIGHTNESS 96
#define EEPROM_LED_COUNT_ADDR 0
#define COMMAND_BUFFER_SIZE 96

CRGB leds[MAX_LEDS];
char commandBuffer[COMMAND_BUFFER_SIZE];
uint8_t commandLength = 0;
uint16_t activeLedCount = DEFAULT_ACTIVE_LEDS;
uint8_t brightness = DEFAULT_BRIGHTNESS;

uint16_t loadStoredLedCount() {
  uint16_t storedCount = 0;
  EEPROM.get(EEPROM_LED_COUNT_ADDR, storedCount);
  if (storedCount == 0 || storedCount > MAX_LEDS) {
    return DEFAULT_ACTIVE_LEDS;
  }
  return storedCount;
}

void storeLedCount(uint16_t count) {
  EEPROM.put(EEPROM_LED_COUNT_ADDR, count);
}

void clearActiveLeds() {
  for (uint16_t index = 0; index < activeLedCount; index++) {
    leds[index] = CRGB::Black;
  }
  FastLED.show();
}

bool parseUnsignedLong(const char *text, unsigned long *valueOut) {
  if (text == NULL || *text == '\0') {
    return false;
  }

  char *endPointer = NULL;
  unsigned long value = strtoul(text, &endPointer, 10);
  if (endPointer == text || *endPointer != '\0') {
    return false;
  }

  *valueOut = value;
  return true;
}

void sendInfo() {
  Serial.print("INFO MAX_LEDS ");
  Serial.print(MAX_LEDS);
  Serial.print(" ACTIVE_LEDS ");
  Serial.print(activeLedCount);
  Serial.print(" BRIGHTNESS ");
  Serial.print(brightness);
  Serial.print(" PIN ");
  Serial.println(DATA_PIN);
}

void setActiveLedCount(uint16_t count) {
  activeLedCount = count;
  storeLedCount(activeLedCount);
  clearActiveLeds();
}

void processSetCommand(char *args) {
  char *indexToken = strtok(args, " ");
  char *redToken = strtok(NULL, " ");
  char *greenToken = strtok(NULL, " ");
  char *blueToken = strtok(NULL, " ");

  if (indexToken == NULL || redToken == NULL || greenToken == NULL || blueToken == NULL) {
    Serial.println("ERR SET_FORMAT");
    return;
  }

  unsigned long indexValue = 0;
  unsigned long redValue = 0;
  unsigned long greenValue = 0;
  unsigned long blueValue = 0;

  if (
    !parseUnsignedLong(indexToken, &indexValue) ||
    !parseUnsignedLong(redToken, &redValue) ||
    !parseUnsignedLong(greenToken, &greenValue) ||
    !parseUnsignedLong(blueToken, &blueValue)
  ) {
    Serial.println("ERR SET_VALUE");
    return;
  }

  if (indexValue >= activeLedCount) {
    Serial.println("ERR LED_RANGE");
    return;
  }

  leds[indexValue] = CRGB((uint8_t)redValue, (uint8_t)greenValue, (uint8_t)blueValue);
  FastLED.show();
}

void processCountCommand(char *args) {
  if (args == NULL || *args == '\0') {
    Serial.print("COUNT ");
    Serial.println(activeLedCount);
    return;
  }

  unsigned long countValue = 0;
  if (!parseUnsignedLong(args, &countValue) || countValue == 0 || countValue > MAX_LEDS) {
    Serial.println("ERR COUNT_RANGE");
    return;
  }

  setActiveLedCount((uint16_t)countValue);
}

void processBrightnessCommand(char *args) {
  if (args == NULL || *args == '\0') {
    Serial.print("BRIGHTNESS ");
    Serial.println(brightness);
    return;
  }

  unsigned long brightnessValue = 0;
  if (!parseUnsignedLong(args, &brightnessValue) || brightnessValue > 255) {
    Serial.println("ERR BRIGHTNESS_RANGE");
    return;
  }

  brightness = (uint8_t)brightnessValue;
  FastLED.setBrightness(brightness);
  FastLED.show();
}

void processCommand(char *line) {
  while (*line == ' ') {
    line++;
  }
  if (*line == '\0') {
    return;
  }

  char *separator = strchr(line, ' ');
  char *args = NULL;
  if (separator != NULL) {
    *separator = '\0';
    args = separator + 1;
    while (args != NULL && *args == ' ') {
      args++;
    }
  }

  if (strcmp(line, "PING") == 0) {
    Serial.println("PONG");
    return;
  }

  if (strcmp(line, "INFO") == 0) {
    sendInfo();
    return;
  }

  if (strcmp(line, "CLEAR") == 0) {
    clearActiveLeds();
    return;
  }

  if (strcmp(line, "SET") == 0) {
    processSetCommand(args);
    return;
  }

  if (strcmp(line, "COUNT") == 0) {
    processCountCommand(args);
    return;
  }

  if (strcmp(line, "BRIGHTNESS") == 0) {
    processBrightnessCommand(args);
    return;
  }

  Serial.println("ERR UNKNOWN_COMMAND");
}

void readSerialCommands() {
  while (Serial.available() > 0) {
    char incoming = (char)Serial.read();

    if (incoming == '\r') {
      continue;
    }

    if (incoming == '\n') {
      commandBuffer[commandLength] = '\0';
      processCommand(commandBuffer);
      commandLength = 0;
      continue;
    }

    if (commandLength < COMMAND_BUFFER_SIZE - 1) {
      commandBuffer[commandLength++] = incoming;
    } else {
      commandLength = 0;
      Serial.println("ERR COMMAND_TOO_LONG");
    }
  }
}

void setup() {
  Serial.begin(SERIAL_BAUD);
  activeLedCount = loadStoredLedCount();

  FastLED.addLeds<CHIPSET, DATA_PIN, COLOR_ORDER>(leds, MAX_LEDS);
  FastLED.setBrightness(brightness);
  FastLED.clear(true);

  leds[0] = CRGB::White;
  FastLED.show();
  delay(250);
  clearActiveLeds();
}

void loop() {
  readSerialCommands();
}
