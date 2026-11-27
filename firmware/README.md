# Agent Vortex Handheld — Firmware

This directory contains the **ESP32-S3 firmware** for the Agent Vortex Handheld — a physical AI-operator console built on the ESP32-S3-N16R8 module.

The firmware connects to the existing [Agent Vortex backend](../README.md) over Wi-Fi and renders a chat interface on a 2.4-inch SPI TFT display.

> **This directory is entirely independent of the web UI and Python backend.**  
> Do not modify `frontend/` or any backend files from this directory.

---

## Hardware

- **MCU:** ESP32-S3-N16R8 (16 MB Flash, 8 MB OPI PSRAM, dual-core Xtensa LX7 @ 240 MHz)
- **Display:** 2.4-inch ILI9341 SPI TFT (240×320)
- **Touch:** XPT2046 resistive touchscreen (separate SPI bus)

Full wiring details → [`docs/HARDWARE.md`](docs/HARDWARE.md)

---

## Stack

| Layer | Technology |
|---|---|
| Language | C (C17, GNU extensions) |
| Framework | ESP-IDF (native) |
| Build | PlatformIO + CMake |
| Graphics | `lvgl/lvgl ==8.3.11` + `espressif/esp_lvgl_port ==2.9.0` (M3+) |
| Display | `espressif/esp_lcd_ili9341 ==2.1.0` (`esp_lcd`, M2+) |
| Touch | `atanisoft/esp_lcd_touch_xpt2046` (M4+) |

Arduino, TFT_eSPI, LovyanGFX and Arduino_GFX are **explicitly prohibited**.

---

## Quick start

```bash
# Prerequisites: PlatformIO Core installed
cd firmware/

# Build
pio run

# List connected devices
pio device list

# Flash (replace <detected-port> with the port shown by `pio device list`)
pio run -t upload --upload-port <detected-port>

# Monitor
pio device monitor --port <detected-port> --baud 115200
```

---

## Documentation

| Document | Description |
|---|---|
| [`docs/HARDWARE.md`](docs/HARDWARE.md) | GPIO mapping, module specs, electrical notes |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Firmware structure, component plan, backend integration |
| [`docs/MILESTONES.md`](docs/MILESTONES.md) | Milestone roadmap and acceptance criteria |

---

## Current milestone

**M3 — LVGL 8.3 Integration (`lvgl/lvgl ==8.3.11` + `espressif/esp_lvgl_port ==2.9.0`)**

Initialises LVGL 8.3 via `espressif/esp_lvgl_port` with DMA double-buffering and PSRAM-backed object allocation, and renders the AgentVortex Handheld boot splash screen with a live spinner and 5-second heartbeat counter.

