// Orva touch bar: hardware configuration (LILYGO T-Display-S3 Long)
// Pins from LILYGO's examples/GFX_AXS15231B_Image/pins_config.h
#pragma once

#define LCD_CS 12
#define LCD_SCLK 17
#define LCD_D0 13
#define LCD_D1 18
#define LCD_D2 21
#define LCD_D3 14
#define LCD_RST 16
#define LCD_BL 1

#define TOUCH_SDA 15
#define TOUCH_SCL 10
#define TOUCH_INT 11
#define TOUCH_RST 16
#define TOUCH_ADDR 0x3B

// Panel is natively 180 wide x 640 tall; the bar is mounted landscape.
#define PANEL_W 180
#define PANEL_H 640
#define W 640
#define H 180

// Set to 1 if the picture comes out upside down for the way the bar is
// mounted in the base.
#define FLIP_180 0

// Serial link to the printer (USB CDC to the CB1)
#define LINK_BAUD 115200
#define LINK_TIMEOUT_MS 4000
