# Agent Vortex Handheld — Hardware Reference

> Last updated: Milestone 1

---

## 1. Main microcontroller

| Property | Value |
|---|---|
| Module | ESP32-S3-N16R8 |
| MCU | ESP32-S3 (dual-core Xtensa LX7, 240 MHz) |
| Flash | 16 MB SPI (Quad/Octal IO) — onboard |
| PSRAM | 8 MB OPI PSRAM (W83 / SRAM model) — onboard |
| Development board | Generic ESP32-S3 DevKit-compatible |
| USB connectors | Two USB-C ports |
| USB peripherals | Native USB (USB OTG / USB-Serial-JTAG on GPIO 19/20) + optional UART bridge |

> **Important:** GPIO 19 and GPIO 20 are occupied by the native USB peripheral. Do not assign them to any other function.

---

## 2. Display module

| Property | Value |
|---|---|
| Screen size | 2.4-inch diagonal |
| Physical resolution | 240 × 320 pixels |
| Display controller | ILI9341 (to be confirmed during M2) |
| Touch controller | XPT2046 (resistive) |
| Onboard storage | MicroSD card slot (unused — deferred) |
| Display interface | SPI |
| Touch interface | Separate SPI bus |

---

## 3. Display SPI wiring (ILI9341)

| TFT Signal | ESP32-S3 GPIO | Notes |
|---|---:|---|
| SCK (clock) | GPIO 12 | SPI SCLK |
| SDI / MOSI | GPIO 11 | SPI MOSI |
| SDO / MISO | GPIO 13 | SPI MISO (read-back, optional for write-only) |
| DC (data/cmd) | GPIO 10 | High = data, Low = command |
| RESET | GPIO 15 | Active-low hardware reset |
| CS (chip select) | GPIO 9 | Active-low |
| LED (backlight) | 3V3 | Tied directly — always-on, no PWM in M1 |
| VCC | 3V3 | |
| GND | GND | |

> These GPIOs are **fixed**. Do not reassign them.

---

## 4. Touchscreen SPI wiring (XPT2046)

| TFT Signal | ESP32-S3 GPIO | Notes |
|---|---:|---|
| T_CLK | GPIO 17 | Separate SPI bus from display |
| T_DIN | GPIO 18 | SPI MOSI |
| T_DO | GPIO 21 | SPI MISO |
| T_CS | GPIO 4 | Active-low |
| T_IRQ | Not connected | Polling-only mode in M4 |

> The display and touchscreen use **separate SPI buses** to allow independent control and avoid CS arbitration complexity.

---

## 5. MicroSD card slot

The 2.4-inch TFT module includes a MicroSD card slot. It is **not used in any current milestone**. Its SPI signals are **unconnected** at the ESP32-S3 side.

---

## 6. Power

| Rail | Source | Notes |
|---|---|---|
| 3.3 V | USB-C → onboard LDO | Powers ESP32-S3, TFT, touch IC |
| GND | USB-C GND | Common ground |

The TFT backlight is tied directly to 3V3 (always on). PWM brightness control is deferred to a future milestone.

---

## 7. Reserved GPIOs

| GPIO | Reason |
|---|---|
| GPIO 19 | Native USB D– (DO NOT USE) |
| GPIO 20 | Native USB D+ (DO NOT USE) |
| GPIO 9  | Display CS |
| GPIO 10 | Display DC |
| GPIO 11 | Display MOSI |
| GPIO 12 | Display SCK |
| GPIO 13 | Display MISO |
| GPIO 15 | Display RESET |
| GPIO 4  | Touch CS |
| GPIO 17 | Touch SCK |
| GPIO 18 | Touch MOSI |
| GPIO 21 | Touch MISO |

---

## 8. PSRAM configuration notes (deferred to M2)

The N16R8 module includes **8 MB of OPI PSRAM** (Octal SPI, `W83` variant).  
To enable it in `sdkconfig.defaults`:

```
CONFIG_SPIRAM=y
CONFIG_SPIRAM_MODE_OCT=y
CONFIG_ESP32S3_SPIRAM_SUPPORT=y
CONFIG_SPIRAM_SPEED_80M=y
CONFIG_SPIRAM_USE_MALLOC=y
```

> **Why deferred:** Enabling PSRAM changes the memory map and heap reporting. M1 diagnostics intentionally capture the IRAM/DRAM-only baseline before PSRAM is introduced.

---

## 9. Unresolved hardware questions

| # | Question | Status |
|---|---|---|
| 1 | ILI9341 controller confirmed? | Pending — verify display ID register in M2 |
| 2 | Exact dev board PCB variant? | Generic DevKit-compatible; no datasheet available |
| 3 | PSRAM variant (W83 vs W84)? | Assumed W83 (OPI) based on N16R8 naming; verify in M2 |
| 4 | Touch IRQ connected? | T_IRQ confirmed not connected; polling mode planned |

