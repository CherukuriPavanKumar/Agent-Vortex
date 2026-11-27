/*
 * =============================================================================
 * Agent Vortex Handheld — Firmware Entry Point
 * Milestone 4: XPT2046 Touch Driver and Calibration
 *
 * Target:    ESP32-S3-N16R8 (16 MB Flash, 8 MB OPI PSRAM)
 * Framework: ESP-IDF 6.1.0 (native)
 * Build:     PlatformIO / CMake
 *
 * M4 scope (additive on top of M3):
 *   - Pin atanisoft/esp_lcd_touch_xpt2046 ==1.0.6 in idf_component.yml
 *   - Initialise separate SPI3_HOST for touch (GPIO 17/18/21/4)
 *   - T_IRQ not connected -> polling-only mode managed by esp_lvgl_port
 *   - Output raw 12-bit ADC coordinates (0..4095) via process_coordinates hook
 *   - Perform 3-point affine touch calibration and persist coefficients in NVS
 *   - Render splash screen with live raw + calibrated readout & TAP ME test
 *
 * M3 deliverables retained:
 *   - Boot diagnostics (chip, flash, PSRAM heap, reset reason)
 *   - ILI9341 display via espressif/esp_lcd_ili9341 2.1.0
 *   - LVGL 8.3.11 via espressif/esp_lvgl_port 2.9.0
 *   - Boot splash with spinner + live heartbeat badge
 *
 * Explicitly deferred:
 *   - Wi-Fi / HTTP / SSE / Auth / UI   -> M5-M10
 * =============================================================================
 */

#include <inttypes.h>
#include <math.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "driver/gpio.h"
#include "driver/spi_master.h"
#include "esp_chip_info.h"
#include "esp_flash.h"
#include "esp_heap_caps.h"
#include "esp_idf_version.h"
#include "esp_lcd_ili9341.h"
#include "esp_lcd_panel_io.h"
#include "esp_lcd_panel_ops.h"
#include "esp_lcd_panel_vendor.h"
#include "esp_lcd_touch_xpt2046.h"
#include "esp_log.h"
#include "esp_lvgl_port.h"
#include "esp_system.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "lvgl.h"
#include "nvs.h"
#include "nvs_flash.h"

/* ── Display wiring — SPI2_HOST (DO NOT CHANGE) ───────────────────────────── */
#define LCD_HOST               SPI2_HOST
#define LCD_PIN_SCK            12
#define LCD_PIN_MOSI           11
#define LCD_PIN_MISO           13
#define LCD_PIN_DC             10
#define LCD_PIN_RST            15
#define LCD_PIN_CS             9

#define LCD_H_RES              240
#define LCD_V_RES              320
#define LCD_SPI_HZ             (20 * 1000 * 1000)
#define LCD_LVGL_BUF_LINES     40

/* ── Touch wiring — SPI3_HOST (DO NOT CHANGE) ─────────────────────────────── */
/* T_IRQ is not connected; polling-only mode via esp_lvgl_port is used. */
#define TOUCH_HOST             SPI3_HOST
#define TOUCH_PIN_SCK          17
#define TOUCH_PIN_MOSI         18   /* T_DIN */
#define TOUCH_PIN_MISO         21   /* T_DO  */
#define TOUCH_PIN_CS           4    /* T_CS  */

/* ── Calibration constants & NVS storage ─────────────────────────────────── */
#define TOUCH_NVS_NS           "vortex_touch"
#define TOUCH_NVS_KEY          "cal_v1"
#define TOUCH_CAL_MAGIC        0x56544331u   /* "VTC1" */
#define TOUCH_CAL_POINTS       3

/* Non-collinear targets spaced across the 240x320 screen */
static const lv_point_t s_cal_targets[TOUCH_CAL_POINTS] = {
    { .x = 24,  .y = 32  },   /* Top-left */
    { .x = 216, .y = 160 },   /* Right-middle */
    { .x = 120, .y = 288 },   /* Bottom-center */
};

typedef struct {
    uint32_t magic;
    float    kx_x;
    float    kx_y;
    float    kx_c;
    float    ky_x;
    float    ky_y;
    float    ky_c;
} touch_cal_data_t;

/* ── Display init override ────────────────────────────────────────────────── */
/*
 * Override esp_lcd_ili9341's default vendor init sequence using its public
 * ili9341_vendor_config_t hook. On this physical panel the default vendor
 * registers (0xCF/0xED/0xE8/0xCB/0xF7/0xEA/0xB6/0xB7) leave the bottom ~25%
 * of rows un-driven; using standard MIPI-DCS commands drives all 240x320 rows.
 */
static const ili9341_lcd_init_cmd_t s_lcd_init_cmds[] = {
    { 0x13, NULL, 0, 0 }, /* MIPI-DCS Normal Display Mode On (NORON) */
};

/* ── Logging tag & shared state ───────────────────────────────────────────── */
static const char *TAG = "VORTEX_M4";

static lv_obj_t *s_heartbeat_label = NULL;
static lv_obj_t *s_touch_label     = NULL;
static lv_obj_t *s_tap_btn_label   = NULL;

static lv_obj_t *s_cal_overlay     = NULL;
static lv_obj_t *s_cal_status_lbl  = NULL;
static lv_obj_t *s_cal_raw_lbl     = NULL;
static lv_obj_t *s_cal_cross_h     = NULL;
static lv_obj_t *s_cal_cross_v     = NULL;
static lv_obj_t *s_cal_ring        = NULL;

static uint32_t  s_flash_mb        = 0;
static uint8_t   s_cpu_cores       = 0;
static uint32_t  s_screen_tap_cnt  = 0;
static uint32_t  s_btn_tap_cnt     = 0;

/* Touch calibration & raw ADC state (accessed from LVGL task only) */
static touch_cal_data_t s_cal            = { 0 };
static bool             s_has_cal        = false;
static bool             s_cal_active     = false;
static uint8_t          s_cal_step       = 0;
static uint16_t         s_cal_raw_x[TOUCH_CAL_POINTS] = { 0 };
static uint16_t         s_cal_raw_y[TOUCH_CAL_POINTS] = { 0 };
static bool             s_cal_holding    = false;

static uint16_t         s_last_raw_x     = 0;
static uint16_t         s_last_raw_y     = 0;
static uint16_t         s_last_raw_z     = 0;
static int64_t          s_last_raw_log_us = 0;

/* ── Helpers ──────────────────────────────────────────────────────────────── */

static uint16_t clamp_u16(int32_t val, int32_t min_v, int32_t max_v)
{
    if (val < min_v) return (uint16_t)min_v;
    if (val > max_v) return (uint16_t)max_v;
    return (uint16_t)val;
}

static void init_nvs(void)
{
    esp_err_t err = nvs_flash_init();
    if (err == ESP_ERR_NVS_NO_FREE_PAGES || err == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_LOGW(TAG, "NVS partition erased due to format update");
        ESP_ERROR_CHECK(nvs_flash_erase());
        err = nvs_flash_init();
    }
    ESP_ERROR_CHECK(err);
}

static bool load_touch_calibration(touch_cal_data_t *out)
{
    nvs_handle_t nvs = 0;
    esp_err_t err = nvs_open(TOUCH_NVS_NS, NVS_READONLY, &nvs);
    if (err != ESP_OK) {
        return false;
    }

    size_t sz = sizeof(*out);
    err = nvs_get_blob(nvs, TOUCH_NVS_KEY, out, &sz);
    nvs_close(nvs);

    if (err != ESP_OK || sz != sizeof(*out) || out->magic != TOUCH_CAL_MAGIC) {
        return false;
    }

    ESP_LOGI(TAG, "Loaded touch calibration from NVS");
    return true;
}

static void save_touch_calibration(const touch_cal_data_t *cal)
{
    nvs_handle_t nvs = 0;
    esp_err_t err = nvs_open(TOUCH_NVS_NS, NVS_READWRITE, &nvs);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Failed to open NVS for calibration save: %s", esp_err_to_name(err));
        return;
    }

    err = nvs_set_blob(nvs, TOUCH_NVS_KEY, cal, sizeof(*cal));
    if (err == ESP_OK) {
        err = nvs_commit(nvs);
    }
    nvs_close(nvs);

    if (err == ESP_OK) {
        ESP_LOGI(TAG, "Saved 3-point touch calibration to NVS");
    } else {
        ESP_LOGE(TAG, "Failed to save touch calibration: %s", esp_err_to_name(err));
    }
}

/*
 * Computes a 6-coefficient 2D affine calibration mapping:
 *   screen_x = kx_x * raw_x + kx_y * raw_y + kx_c
 *   screen_y = ky_x * raw_x + ky_y * raw_y + ky_c
 * Handles arbitrary rotation, X/Y swap, mirroring, scaling, and offsets.
 */
static bool compute_affine_calibration(const uint16_t rx[TOUCH_CAL_POINTS],
                                       const uint16_t ry[TOUCH_CAL_POINTS],
                                       touch_cal_data_t *out)
{
    double rx0 = rx[0], ry0 = ry[0];
    double rx1 = rx[1], ry1 = ry[1];
    double rx2 = rx[2], ry2 = ry[2];

    double x0 = s_cal_targets[0].x, y0 = s_cal_targets[0].y;
    double x1 = s_cal_targets[1].x, y1 = s_cal_targets[1].y;
    double x2 = s_cal_targets[2].x, y2 = s_cal_targets[2].y;

    double det = (rx0 - rx2) * (ry1 - ry2) - (rx1 - rx2) * (ry0 - ry2);
    if (fabs(det) < 50000.0) {
        ESP_LOGW(TAG, "Calibration points too close or collinear (det=%.1f)", det);
        return false;
    }

    out->magic = TOUCH_CAL_MAGIC;
    out->kx_x  = (float)(((x0 - x2) * (ry1 - ry2) - (x1 - x2) * (ry0 - ry2)) / det);
    out->kx_y  = (float)(((rx0 - rx2) * (x1 - x2) - (x0 - x2) * (rx1 - rx2)) / det);
    out->kx_c  = (float)(((ry2 * rx1 - ry1 * rx2) * x0 +
                          (ry0 * rx2 - ry2 * rx0) * x1 +
                          (ry1 * rx0 - ry0 * rx1) * x2) / det);

    out->ky_x  = (float)(((y0 - y2) * (ry1 - ry2) - (y1 - y2) * (ry0 - ry2)) / det);
    out->ky_y  = (float)(((rx0 - rx2) * (y1 - y2) - (y0 - y2) * (rx1 - rx2)) / det);
    out->ky_c  = (float)(((ry2 * rx1 - ry1 * rx2) * y0 +
                          (ry0 * rx2 - ry2 * rx0) * y1 +
                          (ry1 * rx0 - ry0 * rx1) * y2) / det);

    ESP_LOGI(TAG, "Calibration solved (det=%.0f):", det);
    ESP_LOGI(TAG, "  X = %.5f*rx + %.5f*ry + %.2f", out->kx_x, out->kx_y, out->kx_c);
    ESP_LOGI(TAG, "  Y = %.5f*rx + %.5f*ry + %.2f", out->ky_x, out->ky_y, out->ky_c);
    return true;
}

/* ── Diagnostics ──────────────────────────────────────────────────────────── */

static void print_banner(void)
{
    printf("\n");
    printf("========================================\n");
    printf("       AGENT VORTEX HANDHELD\n");
    printf("         FIRMWARE BOOT  [M4]\n");
    printf("========================================\n\n");
}

static void report_chip_info(void)
{
    esp_chip_info_t chip;
    esp_chip_info(&chip);
    s_cpu_cores = chip.cores;

    const char *model;
    switch (chip.model) {
        case CHIP_ESP32S3: model = "ESP32-S3"; break;
        case CHIP_ESP32:   model = "ESP32";    break;
        case CHIP_ESP32S2: model = "ESP32-S2"; break;
        case CHIP_ESP32C3: model = "ESP32-C3"; break;
        default:           model = "Unknown";  break;
    }

    ESP_LOGI(TAG, "ESP-IDF version  : %s", esp_get_idf_version());
    ESP_LOGI(TAG, "Chip model       : %s", model);
    ESP_LOGI(TAG, "CPU cores        : %d", chip.cores);
    ESP_LOGI(TAG, "Chip revision    : v%d.%d",
             chip.revision / 100, chip.revision % 100);
    ESP_LOGI(TAG, "Wi-Fi            : %s",
             (chip.features & CHIP_FEATURE_WIFI_BGN) ? "yes" : "no");
    ESP_LOGI(TAG, "Bluetooth LE     : %s",
             (chip.features & CHIP_FEATURE_BLE) ? "yes" : "no");
}

static void report_flash_size(void)
{
    uint32_t flash_size = 0;
    esp_err_t err = esp_flash_get_size(NULL, &flash_size);
    if (err == ESP_OK) {
        s_flash_mb = flash_size / (1024u * 1024u);
        ESP_LOGI(TAG, "Flash size       : %" PRIu32 " MB (%" PRIu32 " bytes)",
                 s_flash_mb, flash_size);
    } else {
        ESP_LOGE(TAG, "Flash size query failed: %s", esp_err_to_name(err));
    }
}

static void report_heap_info(void)
{
    size_t free_internal = heap_caps_get_free_size(MALLOC_CAP_INTERNAL);
    size_t min_internal  = heap_caps_get_minimum_free_size(MALLOC_CAP_INTERNAL);
    size_t free_spiram   = heap_caps_get_free_size(MALLOC_CAP_SPIRAM);
    size_t total_spiram  = heap_caps_get_total_size(MALLOC_CAP_SPIRAM);

    ESP_LOGI(TAG, "Internal heap    : %zu bytes free (%zu KB min)",
             free_internal, min_internal / 1024);
    if (total_spiram > 0) {
        ESP_LOGI(TAG, "PSRAM heap       : %zu bytes free / %zu bytes total (%.1f MB)",
                 free_spiram, total_spiram, (double)total_spiram / (1024.0 * 1024.0));
    } else {
        ESP_LOGW(TAG, "PSRAM            : not detected");
    }
}

static void report_reset_reason(void)
{
    esp_reset_reason_t reason = esp_reset_reason();
    const char *reason_str;
    switch (reason) {
        case ESP_RST_POWERON:  reason_str = "Power-on reset";      break;
        case ESP_RST_EXT:      reason_str = "External pin reset";  break;
        case ESP_RST_SW:       reason_str = "Software reset";      break;
        case ESP_RST_PANIC:    reason_str = "Panic / exception";   break;
        case ESP_RST_INT_WDT:  reason_str = "Interrupt WDT reset"; break;
        case ESP_RST_TASK_WDT: reason_str = "Task WDT reset";      break;
        case ESP_RST_WDT:      reason_str = "Other WDT reset";     break;
        case ESP_RST_DEEPSLEEP:reason_str = "Deep sleep wake";     break;
        case ESP_RST_BROWNOUT: reason_str = "Brownout reset";      break;
        case ESP_RST_SDIO:     reason_str = "SDIO reset";          break;
        default:               reason_str = "Unknown";             break;
    }
    ESP_LOGI(TAG, "Reset reason     : %s (%d)", reason_str, (int)reason);
}

/* ── Calibration UI & LVGL touch event handlers ───────────────────────────── */

static void position_cal_crosshair(uint8_t step)
{
    lv_coord_t tx = s_cal_targets[step].x;
    lv_coord_t ty = s_cal_targets[step].y;

    lv_obj_set_pos(s_cal_ring, tx - 14, ty - 14);
    lv_obj_set_pos(s_cal_cross_h, tx - 10, ty - 1);
    lv_obj_set_pos(s_cal_cross_v, tx - 1, ty - 10);
    lv_obj_set_style_border_color(s_cal_ring, lv_color_hex(0xE07A2F), 0);

    lv_label_set_text_fmt(s_cal_status_lbl,
                          "Touch Calibration (%u/%u)\nTap the orange target (%d, %d)",
                          (unsigned)(step + 1), TOUCH_CAL_POINTS,
                          (int)tx, (int)ty);
}

static void close_cal_overlay(void)
{
    s_cal_active  = false;
    s_cal_holding = false;
    if (s_cal_overlay) {
        lv_obj_del(s_cal_overlay);
        s_cal_overlay    = NULL;
        s_cal_status_lbl = NULL;
        s_cal_raw_lbl    = NULL;
        s_cal_cross_h    = NULL;
        s_cal_cross_v    = NULL;
        s_cal_ring       = NULL;
    }
}

static void on_cal_overlay_event(lv_event_t *e)
{
    if (!s_cal_active) return;

    lv_event_code_t code = lv_event_get_code(e);
    if (code == LV_EVENT_PRESSED || code == LV_EVENT_PRESSING) {
        s_cal_holding = true;
        s_cal_raw_x[s_cal_step] = s_last_raw_x;
        s_cal_raw_y[s_cal_step] = s_last_raw_y;
        lv_obj_set_style_border_color(s_cal_ring, lv_color_hex(0x22C55E), 0);
        lv_label_set_text_fmt(s_cal_raw_lbl,
                              "Raw ADC: (%u, %u)  z=%u",
                              s_last_raw_x, s_last_raw_y, s_last_raw_z);
        return;
    }

    if (code != LV_EVENT_RELEASED || !s_cal_holding) return;
    s_cal_holding = false;

    ESP_LOGI(TAG, "CAL point %u/%u: target=(%d, %d) -> raw=(%u, %u)",
             (unsigned)(s_cal_step + 1), TOUCH_CAL_POINTS,
             (int)s_cal_targets[s_cal_step].x, (int)s_cal_targets[s_cal_step].y,
             s_cal_raw_x[s_cal_step], s_cal_raw_y[s_cal_step]);

    s_cal_step++;
    if (s_cal_step < TOUCH_CAL_POINTS) {
        position_cal_crosshair(s_cal_step);
        return;
    }

    touch_cal_data_t solved = { 0 };
    if (!compute_affine_calibration(s_cal_raw_x, s_cal_raw_y, &solved)) {
        s_cal_step = 0;
        position_cal_crosshair(0);
        lv_label_set_text(s_cal_status_lbl,
                          "Calibration failed (points too close)\nRetry target 1/3");
        return;
    }

    s_cal     = solved;
    s_has_cal = true;
    save_touch_calibration(&s_cal);
    close_cal_overlay();

    if (s_touch_label) {
        lv_label_set_text(s_touch_label, "Calibrated! Tap anywhere or TAP ME");
    }
}

static void start_touch_calibration(void)
{
    if (s_cal_overlay) {
        close_cal_overlay();
    }

    s_cal_active  = true;
    s_cal_holding = false;
    s_cal_step    = 0;

    /* Full-screen overlay guarantees every raw press hits it regardless of orientation */
    lv_obj_t *ov = lv_obj_create(lv_layer_top());
    lv_obj_set_size(ov, LCD_H_RES, LCD_V_RES);
    lv_obj_set_pos(ov, 0, 0);
    lv_obj_set_style_bg_color(ov, lv_color_hex(0x111318), 0);
    lv_obj_set_style_bg_opa(ov, LV_OPA_COVER, 0);
    lv_obj_set_style_border_width(ov, 0, 0);
    lv_obj_set_style_radius(ov, 0, 0);
    lv_obj_set_style_pad_all(ov, 0, 0);
    lv_obj_clear_flag(ov, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_add_flag(ov, LV_OBJ_FLAG_CLICKABLE);
    s_cal_overlay = ov;

    s_cal_status_lbl = lv_label_create(ov);
    lv_obj_set_style_text_font(s_cal_status_lbl, &lv_font_montserrat_14, 0);
    lv_obj_set_style_text_color(s_cal_status_lbl, lv_color_hex(0xF3F4F6), 0);
    lv_obj_set_style_text_align(s_cal_status_lbl, LV_TEXT_ALIGN_CENTER, 0);
    lv_obj_align(s_cal_status_lbl, LV_ALIGN_CENTER, 0, -24);

    s_cal_raw_lbl = lv_label_create(ov);
    lv_label_set_text(s_cal_raw_lbl, "Raw ADC: awaiting tap...");
    lv_obj_set_style_text_font(s_cal_raw_lbl, &lv_font_montserrat_12, 0);
    lv_obj_set_style_text_color(s_cal_raw_lbl, lv_color_hex(0x60A5FA), 0);
    lv_obj_align(s_cal_raw_lbl, LV_ALIGN_CENTER, 0, 24);

    s_cal_ring = lv_obj_create(ov);
    lv_obj_set_size(s_cal_ring, 28, 28);
    lv_obj_set_style_bg_opa(s_cal_ring, LV_OPA_TRANSP, 0);
    lv_obj_set_style_border_width(s_cal_ring, 2, 0);
    lv_obj_set_style_radius(s_cal_ring, LV_RADIUS_CIRCLE, 0);
    lv_obj_clear_flag(s_cal_ring, LV_OBJ_FLAG_CLICKABLE | LV_OBJ_FLAG_SCROLLABLE);

    s_cal_cross_h = lv_obj_create(ov);
    lv_obj_set_size(s_cal_cross_h, 20, 2);
    lv_obj_set_style_bg_color(s_cal_cross_h, lv_color_hex(0xF3F4F6), 0);
    lv_obj_set_style_border_width(s_cal_cross_h, 0, 0);
    lv_obj_clear_flag(s_cal_cross_h, LV_OBJ_FLAG_CLICKABLE);

    s_cal_cross_v = lv_obj_create(ov);
    lv_obj_set_size(s_cal_cross_v, 2, 20);
    lv_obj_set_style_bg_color(s_cal_cross_v, lv_color_hex(0xF3F4F6), 0);
    lv_obj_set_style_border_width(s_cal_cross_v, 0, 0);
    lv_obj_clear_flag(s_cal_cross_v, LV_OBJ_FLAG_CLICKABLE);

    lv_obj_add_event_cb(ov, on_cal_overlay_event, LV_EVENT_ALL, NULL);
    position_cal_crosshair(0);
    ESP_LOGI(TAG, "Started 3-point touch calibration");
}

static void on_screen_pressed(lv_event_t *e)
{
    (void)e;
    lv_indev_t *indev = lv_indev_get_act();
    if (!indev) return;

    lv_point_t pt;
    lv_indev_get_point(indev, &pt);

    s_screen_tap_cnt++;
    ESP_LOGI(TAG, "TOUCH [tap #%" PRIu32 "] px=(%" PRId32 ", %" PRId32 ") raw=(%u, %u) z=%u",
             s_screen_tap_cnt, (int32_t)pt.x, (int32_t)pt.y,
             s_last_raw_x, s_last_raw_y, s_last_raw_z);

    if (s_touch_label) {
        lv_label_set_text_fmt(s_touch_label,
                              "px:(%" PRId32 ",%" PRId32 ") raw:(%u,%u)",
                              (int32_t)pt.x, (int32_t)pt.y,
                              s_last_raw_x, s_last_raw_y);
    }
}

static void on_tap_btn_clicked(lv_event_t *e)
{
    (void)e;
    s_btn_tap_cnt++;
    ESP_LOGI(TAG, "TAP ME clicked (count=%" PRIu32 ") — calibrated LVGL hit-test OK",
             s_btn_tap_cnt);
    if (s_tap_btn_label) {
        lv_label_set_text_fmt(s_tap_btn_label, "TAP ME (%" PRIu32 ")", s_btn_tap_cnt);
    }
}

static void on_recal_btn_clicked(lv_event_t *e)
{
    (void)e;
    start_touch_calibration();
}

/* ── Touch coordinate hook (called inside LVGL task) ─────────────────────── */
/*
 * With CONFIG_XPT2046_CONVERT_ADC_TO_COORDS=n, esp_lcd_touch_xpt2046 passes
 * raw 12-bit ADC readings (0..4095) into this hook. We record raw values for
 * diagnostics/calibration and emit pixel coordinates inside 0..LCD_RES-1.
 */
static void touch_process_coordinates(esp_lcd_touch_handle_t tp,
                                      uint16_t *x, uint16_t *y,
                                      uint16_t *strength,
                                      uint8_t *point_num,
                                      uint8_t max_point_num)
{
    (void)tp;
    (void)max_point_num;
    if (!point_num || *point_num == 0) return;

    uint16_t rx = x[0];
    uint16_t ry = y[0];
    uint16_t rz = strength ? strength[0] : 0;

    s_last_raw_x = rx;
    s_last_raw_y = ry;
    s_last_raw_z = rz;

    int64_t now_us = esp_timer_get_time();
    if ((now_us - s_last_raw_log_us) > 250000) {
        s_last_raw_log_us = now_us;
        ESP_LOGI(TAG, "XPT2046 raw ADC: rx=%u ry=%u z=%u", rx, ry, rz);
    }

    for (uint8_t i = 0; i < *point_num; i++) {
        int32_t px, py;
        if (s_has_cal && !s_cal_active) {
            px = (int32_t)lroundf(s_cal.kx_x * x[i] + s_cal.kx_y * y[i] + s_cal.kx_c);
            py = (int32_t)lroundf(s_cal.ky_x * x[i] + s_cal.ky_y * y[i] + s_cal.ky_c);
        } else {
            px = ((int32_t)x[i] * LCD_H_RES) / 4096;
            py = ((int32_t)y[i] * LCD_V_RES) / 4096;
        }
        x[i] = clamp_u16(px, 0, LCD_H_RES - 1);
        y[i] = clamp_u16(py, 0, LCD_V_RES - 1);
    }
}

/* ── Display + LVGL initialisation ───────────────────────────────────────── */

static lv_disp_t *init_display_and_lvgl(void)
{
    spi_bus_config_t disp_bus = {
        .mosi_io_num   = LCD_PIN_MOSI,
        .miso_io_num   = LCD_PIN_MISO,
        .sclk_io_num   = LCD_PIN_SCK,
        .quadwp_io_num = -1,
        .quadhd_io_num = -1,
    };
    ESP_ERROR_CHECK(spi_bus_initialize(LCD_HOST, &disp_bus, SPI_DMA_CH_AUTO));
    ESP_LOGI(TAG, "SPI2_HOST (display) bus initialised");

    esp_lcd_panel_io_handle_t io_handle = NULL;
    esp_lcd_panel_io_spi_config_t io_cfg = {
        .dc_gpio_num       = LCD_PIN_DC,
        .cs_gpio_num       = LCD_PIN_CS,
        .pclk_hz           = LCD_SPI_HZ,
        .lcd_cmd_bits      = 8,
        .lcd_param_bits    = 8,
        .spi_mode          = 0,
        .trans_queue_depth = 10,
    };
    ESP_ERROR_CHECK(esp_lcd_new_panel_io_spi(
        (esp_lcd_spi_bus_handle_t)LCD_HOST, &io_cfg, &io_handle));

    ili9341_vendor_config_t vendor_cfg = {
        .init_cmds      = s_lcd_init_cmds,
        .init_cmds_size = sizeof(s_lcd_init_cmds) / sizeof(s_lcd_init_cmds[0]),
    };
    esp_lcd_panel_handle_t panel = NULL;
    esp_lcd_panel_dev_config_t panel_cfg = {
        .reset_gpio_num  = LCD_PIN_RST,
        .rgb_ele_order   = LCD_RGB_ELEMENT_ORDER_RGB,
        .bits_per_pixel  = 16,
        .vendor_config   = &vendor_cfg,
    };
    ESP_ERROR_CHECK(esp_lcd_new_panel_ili9341(io_handle, &panel_cfg, &panel));
    ESP_ERROR_CHECK(esp_lcd_panel_reset(panel));
    ESP_ERROR_CHECK(esp_lcd_panel_init(panel));
    ESP_ERROR_CHECK(esp_lcd_panel_set_gap(panel, 0, 0));
    ESP_ERROR_CHECK(esp_lcd_panel_disp_on_off(panel, true));

    /* MADCTL: BGR=0, no axis flip -> correct R/G/B/W colour order */
    uint8_t madctl = 0x08;
    esp_lcd_panel_io_tx_param(io_handle, 0x36, &madctl, 1);
    ESP_LOGI(TAG, "ILI9341 panel ready");

    const lvgl_port_cfg_t lvgl_cfg = ESP_LVGL_PORT_INIT_CONFIG();
    ESP_ERROR_CHECK(lvgl_port_init(&lvgl_cfg));
    ESP_LOGI(TAG, "LVGL %d.%d.%d + esp_lvgl_port ready (%dx%d)",
             LVGL_VERSION_MAJOR, LVGL_VERSION_MINOR, LVGL_VERSION_PATCH,
             LCD_H_RES, LCD_V_RES);

    const lvgl_port_display_cfg_t disp_cfg = {
        .io_handle     = io_handle,
        .panel_handle  = panel,
        .buffer_size   = LCD_H_RES * LCD_LVGL_BUF_LINES,
        .double_buffer = true,
        .hres          = LCD_H_RES,
        .vres          = LCD_V_RES,
        .monochrome    = false,
        .rotation      = {
            .swap_xy  = false,
            .mirror_x = false,
            .mirror_y = false,
        },
        .flags         = {
            .buff_dma    = true,
            .buff_spiram = false,
        },
    };
    lv_disp_t *disp = lvgl_port_add_disp(&disp_cfg);
    ESP_LOGI(TAG, "LVGL display registered (double-buffer, %d-line DMA)",
             LCD_LVGL_BUF_LINES);

    return disp;
}

/* ── Touch (XPT2046) initialisation ──────────────────────────────────────── */

static esp_lcd_touch_handle_t init_touch(lv_disp_t *disp)
{
    spi_bus_config_t touch_bus = {
        .mosi_io_num     = TOUCH_PIN_MOSI,
        .miso_io_num     = TOUCH_PIN_MISO,
        .sclk_io_num     = TOUCH_PIN_SCK,
        .quadwp_io_num   = -1,
        .quadhd_io_num   = -1,
        .max_transfer_sz = 64,
    };
    esp_err_t err = spi_bus_initialize(TOUCH_HOST, &touch_bus, SPI_DMA_CH_AUTO);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Touch SPI3_HOST bus init failed: %s", esp_err_to_name(err));
        return NULL;
    }
    ESP_LOGI(TAG, "SPI3_HOST (touch) bus initialised");

    esp_lcd_panel_io_handle_t touch_io = NULL;
    esp_lcd_panel_io_spi_config_t touch_io_cfg =
        ESP_LCD_TOUCH_IO_SPI_XPT2046_CONFIG(TOUCH_PIN_CS);
    err = esp_lcd_new_panel_io_spi(
        (esp_lcd_spi_bus_handle_t)TOUCH_HOST, &touch_io_cfg, &touch_io);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Touch panel IO init failed: %s", esp_err_to_name(err));
        return NULL;
    }

    esp_lcd_touch_config_t tp_cfg = {
        .x_max               = LCD_H_RES,
        .y_max               = LCD_V_RES,
        .rst_gpio_num        = GPIO_NUM_NC,
        .int_gpio_num        = GPIO_NUM_NC, /* T_IRQ not connected — polling mode */
        .levels              = { .reset = 0, .interrupt = 0 },
        .flags               = { .swap_xy = false, .mirror_x = false, .mirror_y = false },
        .process_coordinates = touch_process_coordinates,
    };
    esp_lcd_touch_handle_t tp = NULL;
    err = esp_lcd_touch_new_spi_xpt2046(touch_io, &tp_cfg, &tp);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "XPT2046 touch controller init failed: %s", esp_err_to_name(err));
        return NULL;
    }
    ESP_LOGI(TAG, "XPT2046 touch controller ready (polling, 1 MHz SPI3)");

    const lvgl_port_touch_cfg_t touch_lvgl_cfg = {
        .disp   = disp,
        .handle = tp,
    };
    lvgl_port_add_touch(&touch_lvgl_cfg);
    ESP_LOGI(TAG, "XPT2046 registered with LVGL port");

    return tp;
}

/* ── Splash screen ────────────────────────────────────────────────────────── */

static void render_boot_splash(bool launch_cal)
{
    if (!lvgl_port_lock(0)) return;

    lv_obj_t *scr = lv_scr_act();
    lv_obj_set_style_bg_color(scr, lv_color_hex(0x111318), LV_PART_MAIN);
    lv_obj_set_style_bg_opa(scr, LV_OPA_COVER, LV_PART_MAIN);
    lv_obj_clear_flag(scr, LV_OBJ_FLAG_SCROLLABLE);

    /* Orange AV badge (non-clickable so taps pass through to screen) */
    lv_obj_t *emblem = lv_obj_create(scr);
    lv_obj_set_size(emblem, 48, 48);
    lv_obj_align(emblem, LV_ALIGN_TOP_MID, 0, 16);
    lv_obj_set_style_bg_color(emblem, lv_color_hex(0x1B1F27), 0);
    lv_obj_set_style_border_color(emblem, lv_color_hex(0xE07A2F), 0);
    lv_obj_set_style_border_width(emblem, 2, 0);
    lv_obj_set_style_radius(emblem, 10, 0);
    lv_obj_clear_flag(emblem, LV_OBJ_FLAG_SCROLLABLE | LV_OBJ_FLAG_CLICKABLE);

    lv_obj_t *emblem_txt = lv_label_create(emblem);
    lv_label_set_text(emblem_txt, "AV");
    lv_obj_set_style_text_font(emblem_txt, &lv_font_montserrat_20, 0);
    lv_obj_set_style_text_color(emblem_txt, lv_color_hex(0xE07A2F), 0);
    lv_obj_center(emblem_txt);

    /* Title & subtitle */
    lv_obj_t *title = lv_label_create(scr);
    lv_label_set_text(title, "AgentVortex");
    lv_obj_set_style_text_font(title, &lv_font_montserrat_24, 0);
    lv_obj_set_style_text_color(title, lv_color_hex(0xF3F4F6), 0);
    lv_obj_align(title, LV_ALIGN_TOP_MID, 0, 72);

    lv_obj_t *subtitle = lv_label_create(scr);
    lv_label_set_text(subtitle, "HANDHELD CONSOLE");
    lv_obj_set_style_text_font(subtitle, &lv_font_montserrat_12, 0);
    lv_obj_set_style_text_color(subtitle, lv_color_hex(0x9CA3AF), 0);
    lv_obj_align(subtitle, LV_ALIGN_TOP_MID, 0, 102);

    /* Hardware summary card (non-clickable so taps pass through to screen) */
    lv_obj_t *card = lv_obj_create(scr);
    lv_obj_set_size(card, 212, 86);
    lv_obj_align(card, LV_ALIGN_TOP_MID, 0, 126);
    lv_obj_set_style_bg_color(card, lv_color_hex(0x1B1F27), 0);
    lv_obj_set_style_border_color(card, lv_color_hex(0x2D3340), 0);
    lv_obj_set_style_border_width(card, 1, 0);
    lv_obj_set_style_radius(card, 8, 0);
    lv_obj_set_style_pad_all(card, 10, 0);
    lv_obj_clear_flag(card, LV_OBJ_FLAG_SCROLLABLE | LV_OBJ_FLAG_CLICKABLE);

    uint32_t psram_mb = (uint32_t)(heap_caps_get_total_size(MALLOC_CAP_SPIRAM) / (1024u * 1024u));
    char info_buf[160];
    snprintf(info_buf, sizeof(info_buf),
             "MCU: ESP32-S3 (%u cores)\n"
             "Flash: %" PRIu32 " MB  |  PSRAM: %" PRIu32 " MB\n"
             "IDF: %s  |  LVGL: %d.%d.%d",
             (unsigned)s_cpu_cores, s_flash_mb, psram_mb,
             esp_get_idf_version(),
             LVGL_VERSION_MAJOR, LVGL_VERSION_MINOR, LVGL_VERSION_PATCH);

    lv_obj_t *info_label = lv_label_create(card);
    lv_label_set_text(info_label, info_buf);
    lv_obj_set_style_text_font(info_label, &lv_font_montserrat_12, 0);
    lv_obj_set_style_text_color(info_label, lv_color_hex(0xD1D5DB), 0);
    lv_obj_set_style_text_line_space(info_label, 4, 0);
    lv_obj_align(info_label, LV_ALIGN_LEFT_MID, 0, 0);

    /* Animated spinner + live heartbeat */
    lv_obj_t *spinner = lv_spinner_create(scr, 1200, 60);
    lv_obj_set_size(spinner, 24, 24);
    lv_obj_align(spinner, LV_ALIGN_BOTTOM_LEFT, 14, -68);
    lv_obj_set_style_arc_color(spinner, lv_color_hex(0x2D3340), LV_PART_MAIN);
    lv_obj_set_style_arc_color(spinner, lv_color_hex(0x22C55E), LV_PART_INDICATOR);
    lv_obj_set_style_arc_width(spinner, 3, LV_PART_MAIN);
    lv_obj_set_style_arc_width(spinner, 3, LV_PART_INDICATOR);
    lv_obj_clear_flag(spinner, LV_OBJ_FLAG_CLICKABLE);

    s_heartbeat_label = lv_label_create(scr);
    lv_label_set_text(s_heartbeat_label, "LVGL Active  |  HB: 0");
    lv_obj_set_style_text_font(s_heartbeat_label, &lv_font_montserrat_14, 0);
    lv_obj_set_style_text_color(s_heartbeat_label, lv_color_hex(0x22C55E), 0);
    lv_obj_align(s_heartbeat_label, LV_ALIGN_BOTTOM_LEFT, 48, -72);

    /* Live touch coordinates status (raw + calibrated) */
    s_touch_label = lv_label_create(scr);
    lv_label_set_text(s_touch_label,
                      s_has_cal ? "Calibrated — tap screen" : "Uncalibrated — tap screen");
    lv_obj_set_style_text_font(s_touch_label, &lv_font_montserrat_12, 0);
    lv_obj_set_style_text_color(s_touch_label, lv_color_hex(0x60A5FA), 0);
    lv_obj_align(s_touch_label, LV_ALIGN_BOTTOM_MID, 0, -44);

    /* TAP ME button (left) */
    lv_obj_t *tap_btn = lv_btn_create(scr);
    lv_obj_set_size(tap_btn, 106, 32);
    lv_obj_align(tap_btn, LV_ALIGN_BOTTOM_LEFT, 12, -8);
    lv_obj_set_style_bg_color(tap_btn, lv_color_hex(0x1D4ED8), LV_STATE_DEFAULT);
    lv_obj_set_style_bg_color(tap_btn, lv_color_hex(0x2563EB), LV_STATE_PRESSED);
    lv_obj_set_style_radius(tap_btn, 6, 0);

    s_tap_btn_label = lv_label_create(tap_btn);
    lv_label_set_text(s_tap_btn_label, "TAP ME (0)");
    lv_obj_set_style_text_font(s_tap_btn_label, &lv_font_montserrat_12, 0);
    lv_obj_set_style_text_color(s_tap_btn_label, lv_color_hex(0xFFFFFF), 0);
    lv_obj_center(s_tap_btn_label);

    /* CALIBRATE button (right) */
    lv_obj_t *cal_btn = lv_btn_create(scr);
    lv_obj_set_size(cal_btn, 100, 32);
    lv_obj_align(cal_btn, LV_ALIGN_BOTTOM_RIGHT, -12, -8);
    lv_obj_set_style_bg_color(cal_btn, lv_color_hex(0x374151), LV_STATE_DEFAULT);
    lv_obj_set_style_bg_color(cal_btn, lv_color_hex(0xE07A2F), LV_STATE_PRESSED);
    lv_obj_set_style_radius(cal_btn, 6, 0);

    lv_obj_t *cal_lbl = lv_label_create(cal_btn);
    lv_label_set_text(cal_lbl, "CALIBRATE");
    lv_obj_set_style_text_font(cal_lbl, &lv_font_montserrat_12, 0);
    lv_obj_set_style_text_color(cal_lbl, lv_color_hex(0xF3F4F6), 0);
    lv_obj_center(cal_lbl);

    lv_obj_add_flag(scr, LV_OBJ_FLAG_CLICKABLE);
    lv_obj_add_event_cb(scr, on_screen_pressed, LV_EVENT_PRESSED, NULL);
    lv_obj_add_event_cb(tap_btn, on_tap_btn_clicked, LV_EVENT_CLICKED, NULL);
    lv_obj_add_event_cb(cal_btn, on_recal_btn_clicked, LV_EVENT_CLICKED, NULL);

    if (launch_cal) {
        start_touch_calibration();
    }

    lvgl_port_unlock();
    ESP_LOGI(TAG, "Boot splash rendered (cal_mode=%s).", launch_cal ? "yes" : "no");
}

/* ── Heartbeat task ───────────────────────────────────────────────────────── */

static void heartbeat_task(void *pvParameters)
{
    (void)pvParameters;
    uint32_t count = 0;
    for (;;) {
        count++;
        ESP_LOGI(TAG, "Heartbeat        : %" PRIu32, count);

        if (s_heartbeat_label && lvgl_port_lock(100)) {
            lv_label_set_text_fmt(s_heartbeat_label,
                                  "LVGL Active  |  HB: %" PRIu32, count);
            lvgl_port_unlock();
        }

        vTaskDelay(pdMS_TO_TICKS(5000));
    }
}

/* ── Application entry point ─────────────────────────────────────────────── */

void app_main(void)
{
    print_banner();

    ESP_LOGI(TAG, "Firmware initialisation started. [Milestone 4 — XPT2046 Touch]");
    ESP_LOGI(TAG, "------------------------------------");

    init_nvs();
    s_has_cal = load_touch_calibration(&s_cal);

    report_chip_info();
    report_flash_size();
    report_heap_info();
    report_reset_reason();

    ESP_LOGI(TAG, "------------------------------------");

    lv_disp_t *disp = init_display_and_lvgl();
    if (!disp) {
        ESP_LOGE(TAG, "Display/LVGL init failed — continuing headless");
    }

    esp_lcd_touch_handle_t touch = NULL;
    if (disp) {
        touch = init_touch(disp);
        if (!touch) {
            ESP_LOGW(TAG, "Touch init failed — UI will render but touch is inactive");
        }
        render_boot_splash(touch != NULL && !s_has_cal);
    }

    ESP_LOGI(TAG, "System initialised successfully.");
    ESP_LOGI(TAG, "Starting heartbeat task (5s interval) ...");
    xTaskCreate(heartbeat_task, "heartbeat", 3072, NULL, tskIDLE_PRIORITY + 1, NULL);
}
