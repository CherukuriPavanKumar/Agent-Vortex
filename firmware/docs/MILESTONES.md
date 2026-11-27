# Agent Vortex Handheld — Milestone Roadmap

> Last updated: Milestone 4 — 2026-11-27 (M3 hardware-verified by user; M4 XPT2046 touch driver in progress)

---

## Status legend

| Symbol | Meaning |
|---|---|
| ✅ | Complete and hardware-verified |
| 🔧 | In progress |
| ⬜ | Pending |
| ⏭ | Deferred |

---

## Roadmap Checklist

- [x] M1 — ESP32-S3 boot and diagnostics ✅ Hardware verified 2026-11-25
- [x] M2 — ILI9341 display driver ✅ Hardware verified 2026-11-26 (`espressif/esp_lcd_ili9341 ==2.1.0`)
- [x] M3 — LVGL 8.3 integration ✅ Hardware-verified 2026-11-27 (`lvgl/lvgl ==8.3.11` + `espressif/esp_lvgl_port ==2.9.0`)
- [ ] M4 — XPT2046 touch driver and calibration (`atanisoft/esp_lcd_touch_xpt2046` 1.0.6) 🔧
- [ ] M5 — Wi-Fi connectivity
- [ ] M6 — Agent Vortex backend authentication
- [ ] M7 — HTTP and SSE streaming
- [ ] M8 — Chat interface and conversation navigation
- [ ] M9 — Touch keyboard and message composition
- [ ] M10 — Complete handheld integration

---

## M1 — ESP32-S3 Boot and Diagnostics

**Status:** ✅ Complete — hardware-verified 2026-11-25

### Acceptance criteria

- [x] Firmware project exists in isolated `firmware/` directory
- [x] Existing web UI and backend are untouched
- [x] PlatformIO uses native ESP-IDF (no Arduino)
- [x] Firmware compiles successfully
- [x] Chip model, cores, revision reported
- [x] ESP-IDF version reported
- [x] Flash size reported (runtime query via `esp_flash_get_size()`)
- [x] Free and minimum-free heap reported
- [x] Reset reason reported
- [x] 5-second heartbeat task implemented
- [x] Hardware flashing tested and serial boot output observed ✅
- [x] HARDWARE.md, ARCHITECTURE.md, MILESTONES.md present

### Hardware verification — 2026-11-25

Flashed and verified on physical hardware via `/dev/ttyACM0` (QinHeng CH343 UART bridge, `1a86:55d3`).

**Actual serial boot output:**

```
========================================
       AGENT VORTEX HANDHELD
         FIRMWARE BOOT
========================================

I (280) VORTEX_BOOT: Firmware initialisation started.
I (285) VORTEX_BOOT: ------------------------------------
I (290) VORTEX_BOOT: ESP-IDF version  : 6.1.0
I (294) VORTEX_BOOT: Chip model       : ESP32-S3
I (299) VORTEX_BOOT: CPU cores        : 2
I (302) VORTEX_BOOT: Chip revision    : v0.2
I (306) VORTEX_BOOT: Embedded flash   : no
I (310) VORTEX_BOOT: Wi-Fi            : yes
I (314) VORTEX_BOOT: Bluetooth LE     : yes
I (318) VORTEX_BOOT: Flash size       : 16 MB (16777216 bytes)
I (324) VORTEX_BOOT: Free heap        : 396940 bytes (387.6 KB)
I (329) VORTEX_BOOT: Min free heap    : 396940 bytes (387.6 KB)
I (335) VORTEX_BOOT: Reset reason     : Power-on reset (1)
I (340) VORTEX_BOOT: ------------------------------------
I (345) VORTEX_BOOT: System initialised successfully.
I (350) VORTEX_BOOT: Starting heartbeat task (5 s interval) ...
I (356) VORTEX_BOOT: Heartbeat        : 1
I (5359) VORTEX_BOOT: Heartbeat        : 2
I (10359) VORTEX_BOOT: Heartbeat        : 3
I (15359) VORTEX_BOOT: Heartbeat        : 4
```

**Confirmed hardware details:**
- Chip: ESP32-S3 (QFN56), revision v0.2
- Flash: 16 MB detected correctly (Boya chip, DIO mode, 80 MHz)
- PSRAM: 8 MB embedded AP_3v3 (not yet enabled — M2)
- MAC: `28:84:85:8a:98:80`
- Free heap at boot: 387.6 KB (IRAM/DRAM, PSRAM disabled)
- Heartbeat: firing every 5 seconds ✅

### Implementation notes

- Board: `esp32-s3-devkitc-1` with `board_upload.flash_size = 16MB` override
- Framework: ESP-IDF (via PlatformIO `espressif32@8.0.0`)
- ESP-IDF version: 6.1.0 (bundled as `framework-espidf@4.60100.0`)
- PSRAM: disabled — M1 baseline captures IRAM/DRAM-only heap
- GPIO 19/20 reserved (native USB); no pin reassignment
- Console: UART0 primary (GPIO 43/44, CH343 UART bridge) at 115200 baud
- Upload port: `/dev/ttyACM0` (QinHeng CH343, USB ID `1a86:55d3`)

---

## M2 — ILI9341 Display Driver

**Status:** ✅ Complete — hardware-verified 2026-11-26

### Acceptance criteria

- [x] 8 MB OPI PSRAM enabled in `sdkconfig.defaults` and confirmed at boot
- [x] SPI2_HOST initialised on GPIO 12/11/13 (SCK/MOSI/MISO)
- [x] Official `espressif/esp_lcd_ili9341 ==2.1.0` component pinned in `src/idf_component.yml` and verified against ESP-IDF 6.1.0
- [x] Custom `src/ili9341.c` / `include/ili9341.h` removed (reuse-first policy)
- [x] Firmware compiles cleanly and boots with `LCD panel create success, version: 2.1.0`
- [x] Visual confirmation of full 240×320 coverage (zero noise/black strip) and accurate R/G/B/W colours using `espressif/esp_lcd_ili9341` + `ili9341_vendor_config_t` minimal MIPI-DCS override (`0x13` NORON) ✅
- [x] PSRAM heap reported (8,386,156 bytes free = 8 MB confirmed)

### Hardware verification — 2026-11-26 (`espressif/esp_lcd_ili9341 ==2.1.0`)

**Actual serial boot output:**

```
I (826) VORTEX_BOOT: Internal heap    : 375567 bytes free (min 343536)
I (832) VORTEX_BOOT: PSRAM heap       : 8386156 bytes free (min 8386156)
I (849) VORTEX_BOOT: -------- Display Init (esp_lcd_ili9341) --------
I (857) ili9341: LCD panel create success, version: 2.1.0
I (982) VORTEX_BOOT: Fill: RED    (0xF800)
I (2038) VORTEX_BOOT: Fill: GREEN  (0x07E0)
I (3093) VORTEX_BOOT: Fill: BLUE   (0x001F)
I (4148) VORTEX_BOOT: Fill: WHITE  (0xFFFF)
I (5203) VORTEX_BOOT: Drawing 4 full-width test bars (R / G / B / W, 240x320)...
I (5308) VORTEX_BOOT: Display test complete.
```

### Key findings

- **PSRAM**: AP Memory generation 3, 64 Mbit (8 MB), OPI/OctalSPI at 80 MHz ✅
- **Official driver**: `espressif/esp_lcd_ili9341` `2.1.0` natively handles ESP-IDF 6.x `rgb_ele_order` and registers `esp_lcd_new_panel_ili9341()` cleanly.
- **Note from earlier diagnostic testing**: This display panel showed a ~25–30% dark bottom strip when sent ILI9341 vendor-specific registers (`0xCB/0xCF/0xE8/0xEA/0xED/0xF7/0xB6`) via a custom driver, whereas pure MIPI-DCS init lit all 320 rows edge-to-edge. If `esp_lcd_ili9341`'s `vendor_specific_init_default` reproduces the bottom strip visually, `ili9341_vendor_config_t` provides the public API hook to pass a minimal `init_cmds` table without modifying the component.
- **RGB565 endianness**: ESP32-S3 is little-endian while SPI RGB565 expects big-endian byte order on the wire; pixel fills byte-swap with `__builtin_bswap16()` (and LVGL in M3 will set `LV_COLOR_16_SWAP`).

### Implementation notes

- Dependency: `espressif/esp_lcd_ili9341: "==2.1.0"` in `src/idf_component.yml` (transitive `espressif/cmake_utilities: 0.5.3` locked in `dependencies.lock`)
- SPI host: `SPI2_HOST` @ 20 MHz, 40-row DMA chunk buffer in `MALLOC_CAP_DMA | MALLOC_CAP_INTERNAL`
- Panel config: `reset_gpio_num = 15`, `rgb_ele_order = LCD_RGB_ELEMENT_ORDER_RGB`, `bits_per_pixel = 16`

---

## M3 — LVGL 8.3 Integration

**Status:** ✅ Complete — hardware-verified 2026-11-27

### Acceptance criteria

- [x] Pin `lvgl/lvgl ==8.3.11` (strictly `<9.0`) and `espressif/esp_lvgl_port ==2.9.0` in `src/idf_component.yml`
- [x] Configure `CONFIG_LV_COLOR_DEPTH_16=y`, `CONFIG_LV_COLOR_16_SWAP=y`, `CONFIG_LV_MEM_CUSTOM=y`, and Montserrat fonts in `sdkconfig.defaults`
- [x] Initialise LVGL and display registration via `lvgl_port_init()` + `lvgl_port_add_disp()` (no custom tick/task/flush boilerplate)
- [x] Render Agent Vortex Handheld boot splash screen with `lv_spinner` animation and live 5 s heartbeat counter
- [x] Visual confirmation of splash screen rendering, colours, and spinner animation on physical LCD ✅ user-verified 2026-11-27

### Hardware verification — 2026-11-26

```
I (893) VORTEX_BOOT: -------- Display + LVGL Init --------
I (900) ili9341: LCD panel create success, version: 2.1.0
I (1024) LVGL: Starting LVGL task
I (1028) VORTEX_BOOT: LVGL 8.3.11 + esp_lvgl_port ready (240x320)
I (1040) VORTEX_BOOT: Boot splash rendered.
I (1041) VORTEX_BOOT: System initialised successfully.
I (1041) VORTEX_BOOT: Starting heartbeat task (5 s interval) ...
I (1045) VORTEX_BOOT: Heartbeat        : 1
I (6052) VORTEX_BOOT: Heartbeat        : 2
```

### Implementation notes

- Locked versions in `dependencies.lock`: `lvgl/lvgl` `8.3.11`, `espressif/esp_lvgl_port` `2.9.0`, `espressif/esp_lcd_ili9341` `2.1.0`
- Draw buffer: double-buffered 40-line strips (`240 × 40` px) in internal DMA SRAM (`buff_dma = true`)
- LVGL dynamic memory routed to `stdlib` `malloc()` (`CONFIG_LV_MEM_CUSTOM=y` -> 8 MB PSRAM pool)

---

## M4 — XPT2046 Touch Driver and Calibration

**Status:** 🔧 In progress — flashed 2026-11-27, awaiting hardware touch verification

### Acceptance criteria

- [x] Pin `atanisoft/esp_lcd_touch_xpt2046 ==1.0.6` in `src/idf_component.yml` (pulls `espressif/esp_lcd_touch >=1.0.4` transitively)
- [x] `SPI3_HOST` initialised on GPIO 17 (SCK) / 18 (MOSI) / 21 (MISO) / 4 (CS), 2 MHz — separate from display SPI2_HOST
- [x] `T_IRQ` confirmed not connected — polling-only via `touch_poll_task` at 20 Hz
- [x] `esp_lcd_touch_new_spi_xpt2046()` driver initialised with public API (`rst_gpio_num=-1`, `int_gpio_num=-1`)
- [x] Touch registered with LVGL via `lvgl_port_add_touch()` using `espressif/esp_lvgl_port 2.9.0`
- [x] `esp_lcd_touch_get_data()` (non-deprecated v2 API) used in `touch_poll_task`
- [x] Raw XPT2046 ADC coordinates logged to serial on each tap: `TOUCH [tap #N] raw x=NNN y=NNN strength=NNN`
- [x] On-screen blue "Touch: awaiting..." label updates to `Touch #N: (x, y)` on tap
- [x] Blue "TAP ME" button added to splash — LVGL event propagation testable
- [ ] Hardware touch verification — physical tap produces serial log output *(awaiting user confirmation)*
- [ ] Calibration mapping — raw ADC → pixel coordinates

### Hardware verification — 2026-11-27

> Pending user verification. Run:
> ```bash
> pio device monitor --port /dev/ttyACM0 --baud 115200
> ```
> Then tap the display and confirm `TOUCH [tap #1] raw x=NNN  y=NNN` appears in serial log.

### Implementation notes

- Component: `atanisoft/esp_lcd_touch_xpt2046 ==1.0.6` + transitive `espressif/esp_lcd_touch` (auto-resolved)
- Deprecation: `esp_lcd_touch_get_coordinates()` deprecated in v2 of `esp_lcd_touch` → switched to `esp_lcd_touch_get_data()` with `esp_lcd_touch_point_data_t` struct
- Touch task priority: `tskIDLE_PRIORITY + 2` (higher than heartbeat at +1) to ensure responsive polling
- Flash budget after M4: RAM 5.7%, Flash 48.5% (508,313 / 1,048,576 bytes)

---

## M5 — Wi-Fi Connectivity

**Status:** ⬜ Pending M4

### Planned scope

- Station mode Wi-Fi provisioning (hardcoded SSID/password → later: BLE provisioning)
- mDNS / fixed IP backend discovery
- TCP connectivity confirmed to Agent Vortex backend `:8000`
- Reconnect logic with exponential back-off

---

## M6 — Agent Vortex Backend Authentication

**Status:** ⬜ Pending M5

### Planned scope

- `POST /api/auth` with password
- Bearer token storage in NVS (non-volatile storage)
- Token refresh on 401 responses
- Keypad UI for password entry

---

## M7 — HTTP and SSE Streaming

**Status:** ⬜ Pending M6

### Planned scope

- `GET /api/conversations` — conversation list
- `POST /api/chat/:id` — SSE streaming response
- Chunked transfer / event-stream parser
- Partial response rendering in LVGL text area

---

## M8 — Chat Interface and Conversation Navigation

**Status:** ⬜ Pending M7

### Planned scope

- Conversation list screen
- Thread view with assistant/user message bubbles
- HITL approval card with approve/deny buttons
- Scroll through message history

---

## M9 — Touch Keyboard and Message Composition

**Status:** ⬜ Pending M8

### Planned scope

- Full LVGL keyboard widget
- Compose area with send button
- Shift / backspace / enter handling
- IME-safe input (single-character commits)

---

## M10 — Complete Handheld Integration

**Status:** ⬜ Pending M1–M9

### Planned scope

- End-to-end: power on → Wi-Fi connect → auth → chat → response stream
- Low-power idle (light sleep between interactions)
- OTA firmware update over Wi-Fi
- Hardware enclosure fitting (if applicable)
- Final acceptance testing and documentation freeze

