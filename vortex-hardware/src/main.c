#include <stdio.h>

#include "esp_log.h"
#include "esp_system.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

#include "app_config.h"
#include "app_state.h"
#include "backend_client.h"
#include "wifi_client.h"

static const char *TAG = "agent-vortex";

/* ── Heap diagnostics ───────────────────────────────────── */

static void log_heap_status(const char *label)
{
    ESP_LOGI(TAG, "[HEAP %s] free=%u  min-ever=%u",
             label,
             (unsigned)esp_get_free_heap_size(),
             (unsigned)esp_get_minimum_free_heap_size());
}

/* ── Demo SSE callback (logs events, replace with display later) ── */

static void demo_sse_callback(sse_event_type_t type, const char *content, void *ctx)
{
    (void)ctx;
    switch (type) {
        case SSE_EVENT_TOKEN:
            /* Tokens are already logged by backend_client, keep quiet here */
            break;
        case SSE_EVENT_DONE:
            ESP_LOGI(TAG, "[CB] Stream finished");
            break;
        case SSE_EVENT_ERROR:
            ESP_LOGE(TAG, "[CB] Stream error: %s", content ? content : "unknown");
            break;
        case SSE_EVENT_TITLE:
            ESP_LOGI(TAG, "[CB] Conversation titled: %s", content ? content : "");
            break;
        case SSE_EVENT_INTERRUPT:
            ESP_LOGW(TAG, "[CB] HITL interrupt received");
            break;
    }
}

/* ── Main task ──────────────────────────────────────────── */

static void vortex_main_task(void *param)
{
    (void)param;

    ESP_LOGI(TAG, "========================================");
    ESP_LOGI(TAG, "  Agent Vortex Handheld Client");
    ESP_LOGI(TAG, "  Backend: %s", BACKEND_BASE_URL);
    ESP_LOGI(TAG, "========================================");
    log_heap_status("BOOT");

    /* Register the demo SSE callback */
    backend_set_sse_callback(demo_sse_callback, NULL);

    /* Step 1: Wi-Fi */
    if (!wifi_connect_and_wait()) {
        ESP_LOGE(TAG, "Wi-Fi failed — halting");
        goto halt;
    }
    ESP_LOGI(TAG, "Device IP: %s", wifi_get_ip_string() ? wifi_get_ip_string() : "unknown");
    log_heap_status("WIFI");

    /* Step 2: Authenticate */
    if (!backend_authenticate()) {
        ESP_LOGE(TAG, "Backend auth failed — halting");
        goto halt;
    }
    log_heap_status("AUTH");

    /* Step 3: Get or create conversation */
    char conversation_id[64];
    if (!backend_get_or_create_conversation(conversation_id, sizeof(conversation_id))) {
        ESP_LOGE(TAG, "Conversation setup failed — halting");
        goto halt;
    }
    log_heap_status("CONV");

    /* Step 4: Send message and stream response */
    char response[4096];
    if (!backend_stream_message(conversation_id, AGENT_TEST_MESSAGE, response, sizeof(response))) {
        ESP_LOGE(TAG, "Streaming failed — halting");
        goto halt;
    }

    log_heap_status("STREAM_DONE");
    ESP_LOGI(TAG, "========================================");
    ESP_LOGI(TAG, "  Full response (%u chars):", (unsigned)strlen(response));
    ESP_LOGI(TAG, "  %.256s%s", response, strlen(response) > 256 ? "..." : "");
    ESP_LOGI(TAG, "========================================");
    ESP_LOGI(TAG, "Demo chat stream completed successfully");

halt:
    if (app_state_is_error()) {
        ESP_LOGE(TAG, "Device halted in ERROR state");
    }

    ESP_LOGI(TAG, "Final state: %s", app_state_name(app_state_get()));
    log_heap_status("FINAL");

    /* Task done — delete self */
    vTaskDelete(NULL);
}

/* ── Entry point ────────────────────────────────────────── */

void app_main(void)
{
    app_state_set(APP_STATE_BOOT);

    BaseType_t ret = xTaskCreate(
        vortex_main_task,
        "vortex_main",
        MAIN_TASK_STACK_SIZE,
        NULL,
        MAIN_TASK_PRIORITY,
        NULL);

    if (ret != pdPASS) {
        ESP_LOGE(TAG, "Failed to create main task (stack=%d)", MAIN_TASK_STACK_SIZE);
    }
}