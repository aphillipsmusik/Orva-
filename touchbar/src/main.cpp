// Orva touch bar firmware
//
// LILYGO T-Display-S3 Long on the front of Orva's base, connected to the
// CB1 by USB.  The printer's orva_touchbar module sends newline-delimited
// JSON status; taps send commands back.  See klipper/extras/orva_touchbar.py.
//
// Screens: startup animation (O squircle -> circle, arm slides out), homing,
// leveling map, flow test, printing, paused, idle (network info), tower
// detached, error, shutdown (startup animation in reverse).
//
// Copyright (C) 2026  Orva contributors.  GPLv3 (links LILYGO's GPL libs).
#include <Arduino.h>
#include <ArduinoJson.h>
#include <Wire.h>
#include "Arduino_GFX_Library.h"
#include "Arduino_DriveBus_Library.h"
#include "config.h"
#include "logo.h"

// ---------------------------------------------------------------- display
static Arduino_DataBus *bus = new Arduino_ESP32QSPI(
    LCD_CS, LCD_SCLK, LCD_D0, LCD_D1, LCD_D2, LCD_D3);
static Arduino_GFX *panel = new Arduino_AXS15231(bus, LCD_RST, 0, false,
                                                 PANEL_W, PANEL_H);
// Landscape off-screen canvas; rotated into the panel's portrait layout
static Arduino_Canvas *cv = new Arduino_Canvas(W, H, panel);
static uint16_t *rotbuf = nullptr;

static std::shared_ptr<Arduino_IIC_DriveBus> iic =
    std::make_shared<Arduino_HWIIC>(TOUCH_SDA, TOUCH_SCL, &Wire);

static inline uint16_t rgb(uint8_t r, uint8_t g, uint8_t b)
{
    return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3);
}
static const uint16_t C_BG = rgb(0x12, 0x16, 0x19);
static const uint16_t C_TEXT = rgb(0xe8, 0xed, 0xf0);
static const uint16_t C_DIM = rgb(0x9a, 0xa6, 0xae);
static const uint16_t C_TRACK = rgb(0x2b, 0x34, 0x39);
static const uint16_t C_LINE = rgb(0x4a, 0x53, 0x5b);
static const uint16_t C_BLUE = rgb(0x4a, 0xa3, 0xff);
static const uint16_t C_ARM = rgb(0x5e, 0x69, 0x73);
static const uint16_t C_WARN = rgb(0xff, 0xb8, 0x4a);
static const uint16_t C_BTN = rgb(0x22, 0x2a, 0x30);

static void present()
{
    uint16_t *fb = cv->getFramebuffer();
    for (int y = 0; y < H; y++) {
        const uint16_t *row = fb + y * W;
        for (int x = 0; x < W; x++) {
#if FLIP_180
            int px = y, py = PANEL_H - 1 - x;
#else
            int px = PANEL_W - 1 - y, py = x;
#endif
            rotbuf[py * PANEL_W + px] = row[x];
        }
    }
    panel->draw16bitRGBBitmap(0, 0, rotbuf, PANEL_W, PANEL_H);
}

static void backlight(uint8_t v) { ledcWrite(1, v); }

// ---------------------------------------------------------------- touch
static volatile bool touch_irq = false;
static void IRAM_ATTR on_touch() { touch_irq = true; }

static bool read_touch(int &x, int &y)
{
    static const uint8_t cmd[] = {0xB5, 0xAB, 0xA5, 0x5A, 0x00, 0x00,
                                  0x00, 0x08, 0x00, 0x00, 0x00};
    uint8_t buf[8] = {0};
    if (!iic->IIC_ReadCData_Data(TOUCH_ADDR, cmd, sizeof(cmd), buf,
                                 sizeof(buf)))
        return false;
    uint8_t fingers = buf[1], event = buf[2] >> 4;
    if (fingers != 1 || event != 0x08)
        return false;
    int px = ((buf[4] & 0x0F) << 8) | buf[5];
    int py = PANEL_H - (((buf[2] & 0x0F) << 8) | buf[3]);
#if FLIP_180
    x = PANEL_H - 1 - py; y = px;
#else
    x = py; y = PANEL_W - 1 - px;
#endif
    return x >= 0 && x < W && y >= 0 && y < H;
}

// ---------------------------------------------------------------- state
struct Pt { float x, y, z; };
struct State {
    String phase = "connect";
    float pct = 0;
    int layer = 0, layers = 0;
    String file;
    float te = 0, tet = 0, tb = 0, tbt = 0;
    int lvp = 0, lvr = 0, lvn = 0;
    int fts = 0;
    float ftf[3] = {0, 0, 0};
    float ftr[3] = {-1, -1, -1};
    String netMode, ssid, ip, hsSsid, hsPass;
    String msg;
    uint32_t msgUntil = 0;
    Pt cur[16]; int ncur = 0;
    Pt old[120]; int nold = 0;
    uint32_t lastRx = 0;
} st;

static void send_cmd(const char *c)
{
    Serial.printf("{\"cmd\":\"%s\"}\n", c);
}

static void handle_line(const String &line)
{
    JsonDocument doc;
    if (deserializeJson(doc, line))
        return;
    st.lastRx = millis();
    const char *t = doc["t"] | "";
    if (!strcmp(t, "s")) {
        st.phase = (const char *)(doc["ph"] | "idle");
        st.pct = doc["pct"] | 0.f;
        st.layer = doc["ly"] | 0;
        st.layers = doc["lyt"] | 0;
        st.file = (const char *)(doc["file"] | "");
        st.te = doc["te"] | 0.f; st.tet = doc["tet"] | 0.f;
        st.tb = doc["tb"] | 0.f; st.tbt = doc["tbt"] | 0.f;
        st.lvp = doc["lvp"] | 0; st.lvr = doc["lvr"] | 0;
        st.lvn = doc["lvn"] | 0;
        st.fts = doc["fts"] | 0;
        for (int i = 0; i < 3; i++) {
            st.ftf[i] = doc["ftf"][i] | 0.f;
            st.ftr[i] = doc["ftr"][i].isNull() ? -1.f : (float)(doc["ftr"][i] | -1.f);
        }
        JsonObject net = doc["net"];
        st.netMode = (const char *)(net["mode"] | "");
        st.ssid = (const char *)(net["ssid"] | "");
        st.ip = (const char *)(net["ip"] | "");
        st.hsSsid = (const char *)(net["hotspot_ssid"] | "");
        st.hsPass = (const char *)(net["hotspot_pass"] | "");
    } else if (!strcmp(t, "map")) {
        JsonArray cur = doc["cur"], old = doc["old"];
        st.ncur = 0;
        for (JsonArray p : cur) {
            if (st.ncur >= 16) break;
            st.cur[st.ncur++] = {p[0] | 0.f, p[1] | 0.f, p[2] | 0.f};
        }
        st.nold = 0;
        for (JsonArray p : old) {
            if (st.nold >= 120) break;
            st.old[st.nold++] = {p[0] | 0.f, p[1] | 0.f, p[2] | 0.f};
        }
    } else if (!strcmp(t, "msg") || !strcmp(t, "err")) {
        st.msg = (const char *)(doc["text"] | "");
        st.msgUntil = millis() + 6000;
    } else if (!strcmp(t, "off")) {
        st.phase = "off";
    } else if (!strcmp(t, "hello")) {
        if (st.phase == "off" || st.phase == "dark")
            st.phase = "boot";
    }
}

static void poll_serial()
{
    static String buf;
    while (Serial.available()) {
        char c = (char)Serial.read();
        if (c == '\n') {
            handle_line(buf);
            buf = "";
        } else if (buf.length() < 12000) {
            buf += c;
        }
    }
}

// ---------------------------------------------------------------- drawing
static void text(int x, int y, const String &s, uint16_t col, int size)
{
    cv->setTextColor(col);
    cv->setTextSize(size);
    cv->setCursor(x, y);
    cv->print(s);
}

static void bar(int x, int y, int w, int h, float frac, uint16_t col)
{
    if (frac < 0) frac = 0;
    if (frac > 1) frac = 1;
    cv->fillRoundRect(x, y, w, h, h / 2, C_TRACK);
    if (frac > 0)
        cv->fillRoundRect(x, y, max((int)(w * frac), h), h, h / 2, col);
}

struct Button { int x, y, w, h; const char *label; const char *cmd; };
static Button buttons[3];
static int nbuttons = 0;

static void button(int x, int y, int w, int h, const char *label,
                   const char *cmd)
{
    cv->fillRoundRect(x, y, w, h, 10, C_BTN);
    cv->drawRoundRect(x, y, w, h, 10, C_LINE);
    int16_t bx, by; uint16_t bw, bh;
    cv->setTextSize(2);
    cv->getTextBounds(label, 0, 0, &bx, &by, &bw, &bh);
    text(x + (w - bw) / 2, y + (h - bh) / 2, label, C_TEXT, 2);
    if (nbuttons < 3)
        buttons[nbuttons++] = {x, y, w, h, label, cmd};
}

static uint16_t dev_color(float z)
{
    // blue = low, amber = high, over +-0.06 mm
    float t = (z + 0.06f) / 0.12f;
    if (t < 0) t = 0;
    if (t > 1) t = 1;
    return rgb(0x4a + (0xff - 0x4a) * t, 0xa3 + (0xb8 - 0xa3) * t,
               0xff + (0x4a - 0xff) * t);
}

// Logo: render font-unit geometry into the canvas, scaled
static void draw_logo(float m, float fade)
{
    const float s = 150.f / 1600.f;
    const float ox = W / 2 - logo::CX * s, oy = H / 2 - logo::CY * s;
    logo::Frame f = logo::frame(m);
    uint16_t cols[4] = {C_BG,
                        rgb(0xe8 * fade, 0xed * fade, 0xf0 * fade),
                        rgb(0x5e * fade, 0x69 * fade, 0x73 * fade),
                        rgb(0x4a * fade, 0xa3 * fade, 0xff * fade)};
    uint16_t *fb = cv->getFramebuffer();
    int x0 = (int)(ox + 100 * s), x1 = (int)(ox + 2045 * s);
    int y0 = (int)(oy - 20 * s), y1 = (int)(oy + 1620 * s);
    for (int y = max(0, y0); y < min(H, y1); y++) {
        float fy = (y + 0.5f - oy) / s;
        for (int x = max(0, x0); x < min(W, x1); x++) {
            float fx = (x + 0.5f - ox) / s;
            int c = logo::sample(f, fx, fy);
            if (c)
                fb[y * W + x] = cols[c];
        }
    }
}

static const uint32_t BOOT_MS = 3600, SHUT_MS = 3150;

// t = seconds into the startup animation
static void draw_boot(float t)
{
    cv->fillScreen(C_BG);
    float fade = min(1.f, t / 0.5f);
    float m = logo::ease((t - 1.1f) / 1.1f);
    draw_logo(m, fade);
    present();
}

static void draw_map(int cx, int cy, int R)
{
    cv->drawCircle(cx, cy, R, C_LINE);
    cv->drawCircle(cx, cy, R - 1, C_LINE);
    for (int i = 0; i < st.nold; i++) {
        uint16_t c = dev_color(st.old[i].z);
        cv->fillCircle(cx + st.old[i].x / 100.f * R,
                       cy - st.old[i].y / 100.f * R, 3,
                       rgb(((c >> 11) & 31) << 2, ((c >> 5) & 63) << 1,
                           (c & 31) << 2));   // dimmed
    }
    for (int i = 0; i < st.ncur; i++)
        cv->fillCircle(cx + st.cur[i].x / 100.f * R,
                       cy - st.cur[i].y / 100.f * R, 7, dev_color(st.cur[i].z));
}

static void draw_ui()
{
    nbuttons = 0;
    cv->fillScreen(C_BG);
    const String &ph = st.phase;
    if (ph == "connect") {
        text(30, 40, "Orva", C_TEXT, 4);
        text(30, 100, "Waiting for the printer...", C_DIM, 2);
    } else if (ph == "home" || ph == "level") {
        text(24, 22, ph == "home" ? "Homing Z" : "Leveling bed", C_TEXT, 3);
        String sub = ph == "home" ? String("On the stop by the wiper")
            : String("Probing point ") + min(9, st.lvp + 1) + " of 9"
              + (st.lvp == 7 ? "  past center" : "");
        text(24, 66, sub, C_DIM, 2);
        text(24, 96, String("Run ") + (st.lvr + 1) + " since power-on, "
             + st.lvn + " pts", C_DIM, 2);
        bar(24, 140, 360, 14, st.lvp / 9.f, C_BLUE);
        draw_map(530, 90, 80);
    } else if (ph == "flow") {
        text(24, 22, "Flow test", C_TEXT, 3);
        text(24, 66, String("Outline section ") + (st.fts + 1) + " of 3",
             C_DIM, 2);
        text(24, 96, String("up to ") + String(st.ftf[st.fts], 1)
             + " mm3/s", C_DIM, 2);
        bar(24, 140, 360, 14, (st.fts + 0.5f) / 3.f, C_BLUE);
        for (int i = 0; i < 3; i++) {
            int x = 430 + i * 66, h = 130 * min(1.f, st.ftf[i] / 12.f);
            cv->fillRect(x, 20, 44, 130, C_TRACK);
            cv->fillRect(x, 150 - h, 44, h,
                         st.ftr[i] >= 0 ? C_BLUE : C_LINE);
            if (st.ftr[i] >= 0)
                text(x, 158, String((int)(st.ftr[i] * 100)) + "%", C_TEXT, 1);
        }
    } else if (ph == "print" || ph == "paused") {
        String f = st.file;
        int slash = f.lastIndexOf('/');
        if (slash >= 0) f = f.substring(slash + 1);
        if (f.length() > 22) f = f.substring(0, 22);
        text(24, 18, f.length() ? f : String("Printing"), C_TEXT, 2);
        text(24, 50, String((int)st.pct) + "%", C_TEXT, 5);
        if (st.layers)
            text(170, 64, String("layer ") + st.layer + " / " + st.layers,
                 C_DIM, 2);
        text(24, 104, String("nozzle ") + (int)st.te + "/" + (int)st.tet
             + "C  bed " + (int)st.tb + "/" + (int)st.tbt + "C", C_DIM, 2);
        bar(24, 140, 380, 14, st.pct / 100.f,
            ph == "paused" ? C_WARN : C_BLUE);
        if (ph == "print")
            button(430, 22, 190, 60, "Pause", "pause");
        else
            button(430, 22, 190, 60, "Resume", "resume");
        button(430, 98, 190, 60, "Cancel", "cancel");
    } else if (ph == "detached") {
        text(24, 40, "Tower detached", C_WARN, 3);
        text(24, 92, "Seat the tower; Orva will re-home", C_DIM, 2);
        text(24, 118, "and re-level by itself.", C_DIM, 2);
    } else if (ph == "error") {
        text(24, 40, "Printer error", C_WARN, 3);
        text(24, 92, "Check Mainsail for details", C_DIM, 2);
    } else {    // idle
        text(24, 20, "Orva ready", C_TEXT, 3);
        if (st.netMode == "hotspot") {
            text(24, 66, String("Wi-Fi setup: join ") + st.hsSsid, C_DIM, 2);
            text(24, 92, String("password ") + st.hsPass, C_DIM, 2);
            text(24, 118, "then open 10.42.0.1:8090", C_DIM, 2);
        } else if (st.netMode == "client") {
            text(24, 66, String("Wi-Fi ") + st.ssid, C_DIM, 2);
            text(24, 92, String("http://orva.local  ") + st.ip, C_DIM, 2);
        } else {
            text(24, 66, "No network", C_DIM, 2);
        }
        if (st.lvr)
            text(24, 148, String("Leveled ") + st.lvr + "x, " + st.lvn
                 + " points in map", C_DIM, 1);
        button(430, 22, 190, 60, "Re-level", "relevel");
        button(430, 98, 190, 60, "Power off", "shutdown");
    }
    if (st.msg.length() && millis() < st.msgUntil) {
        cv->fillRoundRect(10, 128, 400, 40, 8, C_BTN);
        text(20, 141, st.msg.substring(0, 32), C_WARN, 2);
    }
    present();
}

// ---------------------------------------------------------------- main
static uint32_t bootStart = 0, shutStart = 0;
static bool dark = false;

void setup()
{
    Serial.setRxBufferSize(16384);
    Serial.begin(LINK_BAUD);

    pinMode(LCD_BL, OUTPUT);
    ledcAttachPin(LCD_BL, 1);
    ledcSetup(1, 2000, 8);
    backlight(0);

    pinMode(TOUCH_RST, OUTPUT);
    pinMode(TOUCH_INT, INPUT_PULLUP);
    attachInterrupt(TOUCH_INT, on_touch, FALLING);
    digitalWrite(TOUCH_RST, HIGH); delay(2);
    digitalWrite(TOUCH_RST, LOW); delay(100);
    digitalWrite(TOUCH_RST, HIGH); delay(2);
    iic->begin();
    // Board power chip (as in LILYGO's example): no input current limit
    // pin, maximum USB input current, battery FET off (no battery fitted)
    iic->IIC_WriteC8D8(0x6A, 0x00, 0b00111111);
    iic->IIC_WriteC8D8(0x6A, 0x09, 0b01100100);

    cv->begin();        // also starts the panel
    rotbuf = (uint16_t *)ps_malloc(PANEL_W * PANEL_H * sizeof(uint16_t));
    cv->fillScreen(C_BG);
    present();
    backlight(255);
    bootStart = millis();
    st.phase = "boot";
}

void loop()
{
    poll_serial();
    uint32_t now = millis();

    if (st.phase == "boot") {
        float t = (now - bootStart) / 1000.f;
        if (t < BOOT_MS / 1000.f) {
            draw_boot(t);
            return;
        }
        st.phase = st.lastRx ? "idle" : "connect";
    }
    if (st.phase == "off") {
        if (!shutStart) shutStart = now;
        float t = (now - shutStart) / 1000.f;
        if (t < SHUT_MS / 1000.f) {
            draw_boot(SHUT_MS / 1000.f - t);   // startup in reverse
            return;
        }
        backlight(0);
        dark = true;
        st.phase = "dark";
        shutStart = 0;
        return;
    }
    if (st.phase == "dark") {
        delay(50);
        return;
    }
    if (dark) {
        backlight(255);
        dark = false;
        bootStart = now;
        st.phase = "boot";
        return;
    }
    if (st.lastRx && now - st.lastRx > LINK_TIMEOUT_MS)
        st.phase = "connect";

    if (touch_irq) {
        touch_irq = false;
        static uint32_t lastTap = 0;
        int x, y;
        if (now - lastTap > 400 && read_touch(x, y)) {
            for (int i = 0; i < nbuttons; i++) {
                Button &b = buttons[i];
                if (x >= b.x && x < b.x + b.w && y >= b.y && y < b.y + b.h) {
                    send_cmd(b.cmd);
                    lastTap = now;
                }
            }
        }
    }
    static uint32_t lastDraw = 0;
    if (now - lastDraw > 100) {
        lastDraw = now;
        draw_ui();
    }
}
