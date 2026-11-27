# Agent Vortex Handheld — Firmware Architecture

> Last updated: Milestone 2 (reuse-first component stack adopted)

---

## 1. Overview

The Agent Vortex Handheld is a physical device that runs a subset of the Agent Vortex AI-operator console on an ESP32-S3 microcontroller. The firmware connects to the existing Python/LangGraph backend over Wi-Fi and renders a chat interface on a 2.4-inch SPI TFT display.

This document describes the firmware-side architecture only. The backend is an independent service documented in the main repository.

---

## 2. Technology stack & reuse-first components

| Layer | Technology / Component | Target / Pinned Version | Milestone |
|---|---|---|---|
| Language | C (C17, GNU extensions) | `-std=gnu17` | M1+ |
| Firmware framework | ESP-IDF (native) | 6.1.0 | M1+ |
| Build system | PlatformIO + CMake + IDF Component Manager | PIO 6.2.0 / `espressif32@8.0.0` | M1+ |
| Display driver | `espressif/esp_lcd_ili9341` (`esp_lcd`) | `==2.1.0` (pinned) | M2 |
| Graphics library | `lvgl/lvgl` | `8.3.x` (`8.3.11` / `<9.0`) | M3 |
| LVGL port | `espressif/esp_lvgl_port` | `2.9.0` | M3 |
| Touch driver | `atanisoft/esp_lcd_touch_xpt2046` | `1.0.6` | M4 |
| Networking / HTTP / JSON / NVS | Native `esp_wifi`, `esp_http_client`, `cJSON`, `nvs_flash` | Bundled ESP-IDF | M5–M7 |

> **Strictly prohibited:** Arduino framework, TFT_eSPI, LovyanGFX, Arduino_GFX.  
> **Reuse-first policy:** Official ESP Component Registry components and native ESP-IDF APIs are used directly via `src/idf_component.yml` without custom driver reimplementations or wrapper layers.

### Alternative evaluated: `ESP32_Display_Panel`

We evaluated [`esp-arduino-libs/ESP32_Display_Panel`](https://github.com/esp-arduino-libs/ESP32_Display_Panel) (`v1.0.5`) before committing to the modular component stack:

| Criterion | `ESP32_Display_Panel` | Modular `esp_lcd` stack (`esp_lcd_ili9341` + `esp_lcd_touch_xpt2046` + `esp_lvgl_port`) |
|---|---|---|
| Native ESP-IDF compatibility | Supported (`idf >= 5.1`, wraps `esp_lcd` / `esp_lcd_touch`) | Native `esp_lcd` components directly (`idf >= 5.2` / `>= 4.4`) |
| PlatformIO support | `library.json` and `idf_component.yml` | `src/idf_component.yml` via IDF Component Manager |
| C / C++ requirement | **C++17 public API** (`esp_display_panel.hpp`, classes) | **Pure C** public APIs — matches `-std=gnu17` |
| ILI9341 & XPT2046 support | Both supported internally via `esp_lcd` | Official/maintained `esp_lcd_ili9341` + `esp_lcd_touch_xpt2046` |
| Custom GPIOs & separate SPI buses | Supported via board config headers / C++ bus constructors | Explicit `spi_bus_initialize()` per SPI host (`SPI2_HOST` LCD, `SPI3_HOST` touch) |

**Decision:** Retain the modular `esp_lcd` component stack. `ESP32_Display_Panel` exposes a C++17 object-oriented API and Arduino-ecosystem board abstractions, which would require either migrating our C firmware to C++ or writing unnecessary `extern "C"` wrapper shims. Our modular C stack directly uses Espressif's underlying `esp_lcd` primitives with zero C++ overhead and clear per-milestone dependency isolation.

---

## 3. Directory structure

```
firmware/
├── platformio.ini          # PlatformIO project + environment config
├── CMakeLists.txt          # ESP-IDF top-level CMake project
├── dependencies.lock       # Resolved/pinned ESP-IDF component lockfile
├── sdkconfig.defaults      # Kconfig overrides (16 MB flash, OPI PSRAM, logging)
├── .gitignore
├── README.md
│
├── src/                    # Main application component ("main" in ESP-IDF terms)
│   ├── CMakeLists.txt      # idf_component_register(SRCS "main.c")
│   ├── idf_component.yml   # Pinned ESP Component Registry dependencies (progressive per milestone)
│   └── main.c              # app_main() entry point + boot diagnostics + M2 display test
│
├── include/                # Reserved for application-specific headers (e.g. Vortex net/UI)
├── managed_components/     # Gitignored cache populated by IDF Component Manager
│
└── docs/
    ├── HARDWARE.md
    ├── ARCHITECTURE.md     # This file
    └── MILESTONES.md
```

---

## 4. Application entry point

`app_main()` in `src/main.c` is the first user code to run after:
1. ESP-IDF second-stage bootloader completes.
2. FreeRTOS scheduler is started.
3. System tasks (idle, timer, Wi-Fi if enabled) are created.

`app_main()` runs in the "main" FreeRTOS task (stack: 4 KB by default). It:
1. Prints the boot banner.
2. Calls individual `report_*()` functions for chip/flash/heap/reset diagnostics.
3. Creates the `heartbeat` FreeRTOS task.
4. Returns — ESP-IDF deletes the main task; the heartbeat task continues.

---

## 5. Planned component separation

```
app_main()
│
├── hw/                         Milestone 2–4: hardware drivers
│   ├── display_init()          ILI9341 via esp_lcd
│   ├── touch_init()            XPT2046 polling
│   └── psram_init()            OPI PSRAM enable
│
├── ui/                         Milestone 3+: LVGL UI
│   ├── lvgl_port_init()        LVGL + esp_lcd bridge
│   ├── screen_chat.c           Chat conversation view
│   └── screen_keyboard.c       On-screen touch keyboard
│
├── net/                        Milestone 5+: networking
│   ├── wifi_connect()          Station mode
│   ├── http_client.c           REST calls to backend
│   └── sse_stream.c            Server-Sent Events reader
│
└── app/                        Milestone 6+: application logic
    ├── auth.c                  Token storage / refresh
    ├── conversation.c          Thread management
    └── hitl.c                  HITL approval UI
```

---

## 6. Relationship with the Agent Vortex backend

The existing Python backend (`api.py`, LangGraph agent, Docker Compose stack) is **unmodified** by this firmware. The handheld connects to it as a thin client:

```
ESP32-S3 Handheld
  └─► Wi-Fi (STA mode)
        └─► Local network
              └─► Agent Vortex backend  (HTTP :8000)
                    ├── POST /api/auth         (password auth)
                    ├── GET  /api/conversations
                    ├── POST /api/chat/:id     (SSE stream)
                    └── POST /api/approve/:id  (HITL)
```

The backend requires no changes. The handheld is purely an additional frontend.

---

## 7. Build and flash workflow

```bash
cd firmware/

# Clean build
pio run -t clean
pio run

# List connected serial devices
pio device list

# Flash (after confirming detected port — e.g. /dev/ttyACM0 or /dev/ttyUSB0)
pio run -t upload --upload-port <detected-port>

# Monitor serial output
pio device monitor --port <detected-port> --baud 115200
```

---

## 8. ESP-IDF vs PlatformIO responsibilities

| Concern | Managed by |
|---|---|
| Toolchain (xtensa-esp-elf-gcc) | PlatformIO package manager |
| CMake build system | ESP-IDF + PlatformIO integration |
| Kconfig / sdkconfig | ESP-IDF (`sdkconfig.defaults`) |
| Flash partitioning | ESP-IDF default partition table |
| FreeRTOS | ESP-IDF (compiled in) |
| Serial upload / monitor | PlatformIO (`esptool.py`) |
| Library / component management | ESP-IDF Component Manager (`src/idf_component.yml` + `dependencies.lock`) |

