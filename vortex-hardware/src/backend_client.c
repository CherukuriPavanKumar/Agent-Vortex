#include <ctype.h>
#include <stdlib.h>
#include <string.h>

#include "cJSON.h"
#include "esp_http_client.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

#include "app_config.h"
#include "app_state.h"
#include "backend_client.h"

static const char *TAG = "backend";

/* ── SSE callback registration ──────────────────────────── */

static sse_event_callback_t s_sse_cb      = NULL;
static void                *s_sse_cb_ctx  = NULL;

void backend_set_sse_callback(sse_event_callback_t cb, void *user_ctx)
{
    s_sse_cb     = cb;
    s_sse_cb_ctx = user_ctx;
}

const char *sse_event_type_name(sse_event_type_t type)
{
    switch (type) {
        case SSE_EVENT_TOKEN:     return "token";
        case SSE_EVENT_DONE:      return "done";
        case SSE_EVENT_ERROR:     return "error";
        case SSE_EVENT_TITLE:     return "title";
        case SSE_EVENT_INTERRUPT: return "interrupt";
        default:                  return "unknown";
    }
}

/* ── Response accumulator ───────────────────────────────── */

typedef struct {
    char  *buf;
    size_t len;
    size_t cap;
} accumulator_t;

static accumulator_t s_accum = {0};

static void accum_reset(void)
{
    if (s_accum.buf) {
        s_accum.buf[0] = '\0';
    }
    s_accum.len = 0;
}

static bool accum_init(void)
{
    if (s_accum.buf != NULL) {
        accum_reset();
        return true;
    }
    s_accum.cap = RESPONSE_ACCUM_INIT_SIZE;
    s_accum.buf = (char *)calloc(1, s_accum.cap);
    s_accum.len = 0;
    return s_accum.buf != NULL;
}

static void accum_append(const char *text)
{
    if (text == NULL || s_accum.buf == NULL) return;

    size_t add = strlen(text);
    if (add == 0) return;

    /* Grow if needed */
    while (s_accum.len + add + 1 > s_accum.cap) {
        size_t new_cap = s_accum.cap * 2;
        if (new_cap > RESPONSE_ACCUM_MAX_SIZE) {
            new_cap = RESPONSE_ACCUM_MAX_SIZE;
        }
        if (new_cap <= s_accum.cap) {
            ESP_LOGW(TAG, "Accumulator at max size (%u), truncating", (unsigned)RESPONSE_ACCUM_MAX_SIZE);
            return;
        }
        char *new_buf = (char *)realloc(s_accum.buf, new_cap);
        if (new_buf == NULL) {
            ESP_LOGE(TAG, "Accumulator realloc failed");
            return;
        }
        s_accum.buf = new_buf;
        s_accum.cap = new_cap;
    }

    memcpy(s_accum.buf + s_accum.len, text, add);
    s_accum.len += add;
    s_accum.buf[s_accum.len] = '\0';
}

/* ── HTTP receive buffer ────────────────────────────────── */

typedef struct {
    int    mode;
    char  *data;
    size_t capacity;
    size_t length;
    char   line[512];
    size_t line_length;
} response_buffer_t;

enum {
    HTTP_MODE_CAPTURE = 0,
    HTTP_MODE_STREAM  = 1,
};

/* Forward declaration */
static void sse_process_line(const char *line);

static esp_err_t http_event_handler(esp_http_client_event_t *evt)
{
    response_buffer_t *buf = (response_buffer_t *)evt->user_data;

    if (evt->event_id == HTTP_EVENT_ON_DATA && buf != NULL) {
        if (buf->mode == HTTP_MODE_CAPTURE && buf->data != NULL) {
            /* Collect into flat buffer */
            size_t copy = evt->data_len;
            if (buf->length + copy >= buf->capacity) {
                copy = buf->capacity - buf->length - 1;
            }
            if (copy > 0) {
                memcpy(buf->data + buf->length, evt->data, copy);
                buf->length += copy;
                buf->data[buf->length] = '\0';
            }

        } else if (buf->mode == HTTP_MODE_STREAM) {
            /* Line-based SSE parsing */
            const char *chunk = (const char *)evt->data;
            for (int i = 0; i < evt->data_len; ++i) {
                char ch = chunk[i];
                if (ch == '\r') continue;

                if (ch == '\n') {
                    buf->line[buf->line_length] = '\0';
                    sse_process_line(buf->line);
                    buf->line_length = 0;
                    continue;
                }

                if (buf->line_length + 1 < sizeof(buf->line)) {
                    buf->line[buf->line_length++] = ch;
                } else {
                    ESP_LOGW(TAG, "SSE line too long, discarding");
                    buf->line_length = 0;
                }
            }
        }
    }

    return ESP_OK;
}

/* ── SSE line processor (uses cJSON) ────────────────────── */

static sse_event_type_t sse_type_from_string(const char *s)
{
    if (strcmp(s, "token") == 0)     return SSE_EVENT_TOKEN;
    if (strcmp(s, "done") == 0)      return SSE_EVENT_DONE;
    if (strcmp(s, "error") == 0)     return SSE_EVENT_ERROR;
    if (strcmp(s, "title") == 0)     return SSE_EVENT_TITLE;
    if (strcmp(s, "interrupt") == 0) return SSE_EVENT_INTERRUPT;
    return SSE_EVENT_ERROR; /* fallback */
}

static void sse_process_line(const char *line)
{
    if (line == NULL || strncmp(line, "data:", 5) != 0) return;

    const char *payload = line + 5;
    while (*payload && isspace((unsigned char)*payload)) payload++;
    if (*payload == '\0') return;

    cJSON *json = cJSON_Parse(payload);
    if (json == NULL) {
        ESP_LOGW(TAG, "SSE JSON parse failed: %s", payload);
        return;
    }

    cJSON *type_item = cJSON_GetObjectItemCaseSensitive(json, "type");
    if (!cJSON_IsString(type_item) || type_item->valuestring == NULL) {
        ESP_LOGW(TAG, "SSE payload missing 'type': %s", payload);
        cJSON_Delete(json);
        return;
    }

    sse_event_type_t etype = sse_type_from_string(type_item->valuestring);
    const char *content = NULL;

    cJSON *content_item = cJSON_GetObjectItemCaseSensitive(json, "content");
    if (cJSON_IsString(content_item)) {
        content = content_item->valuestring;
    }

    /* Log based on type */
    switch (etype) {
        case SSE_EVENT_TOKEN:
            if (content) {
                ESP_LOGI(TAG, "TOKEN: %s", content);
                accum_append(content);
            }
            break;

        case SSE_EVENT_DONE:
            ESP_LOGI(TAG, "DONE: %s",
                     content ? content : "(final)");
            break;

        case SSE_EVENT_ERROR:
            ESP_LOGE(TAG, "STREAM ERROR: %s",
                     content ? content : payload);
            break;

        case SSE_EVENT_TITLE:
            ESP_LOGI(TAG, "TITLE: %s",
                     content ? content : "untitled");
            break;

        case SSE_EVENT_INTERRUPT: {
            cJSON *risk = cJSON_GetObjectItemCaseSensitive(json, "risk_level");
            ESP_LOGW(TAG, "INTERRUPT (risk=%s): %s",
                     cJSON_IsString(risk) ? risk->valuestring : "unknown",
                     payload);
            break;
        }
    }

    /* Fire callback */
    if (s_sse_cb) {
        s_sse_cb(etype, content ? content : payload, s_sse_cb_ctx);
    }

    cJSON_Delete(json);
}

/* ── HTTP helpers ───────────────────────────────────────── */

static bool http_request_collect(const char *method, const char *url,
                                 const char *body, char *response,
                                 size_t response_len, int *status_out)
{
    response_buffer_t buffer = {
        .mode        = HTTP_MODE_CAPTURE,
        .data        = response,
        .capacity    = response_len,
        .length      = 0,
        .line_length = 0,
    };

    if (response && response_len > 0) response[0] = '\0';

    esp_http_client_config_t config = {
        .url           = url,
        .method        = strcmp(method, "POST") == 0 ? HTTP_METHOD_POST : HTTP_METHOD_GET,
        .timeout_ms    = HTTP_REQUEST_TIMEOUT_MS,
        .event_handler = http_event_handler,
        .user_data     = &buffer,
    };

    esp_http_client_handle_t client = esp_http_client_init(&config);
    if (client == NULL) {
        ESP_LOGE(TAG, "Failed to create HTTP client");
        return false;
    }

    esp_http_client_set_header(client, "Accept", "application/json");
    esp_http_client_set_header(client, "Content-Type", "application/json");
    esp_http_client_set_header(client, "Authorization", "Bearer " AGENT_PASSWORD);
    esp_http_client_set_header(client, "Connection", "close");

    if (body) {
        esp_http_client_set_post_field(client, body, (int)strlen(body));
    }

    ESP_LOGI(TAG, "HTTP %s %s", method, url);
    esp_err_t err = esp_http_client_perform(client);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "HTTP error: %s (%d)", esp_err_to_name(err), err);
        esp_http_client_cleanup(client);
        return false;
    }

    if (status_out) {
        *status_out = esp_http_client_get_status_code(client);
    }

    if (response && response_len > 0 && buffer.length > 0) {
        ESP_LOGI(TAG, "Response (%u bytes): %.128s%s",
                 (unsigned)buffer.length, response,
                 buffer.length > 128 ? "..." : "");
    }

    esp_http_client_cleanup(client);
    return true;
}

/**
 * Retry wrapper around http_request_collect with exponential backoff.
 */
static bool http_request_with_retry(const char *method, const char *url,
                                    const char *body, char *response,
                                    size_t response_len, int *status_out)
{
    for (int attempt = 0; attempt < HTTP_MAX_RETRIES; attempt++) {
        if (attempt > 0) {
            int delay = HTTP_RETRY_BASE_DELAY_MS * (1 << (attempt - 1));
            ESP_LOGW(TAG, "Retry %d/%d in %d ms", attempt + 1, HTTP_MAX_RETRIES, delay);
            vTaskDelay(pdMS_TO_TICKS(delay));
        }

        int status = 0;
        if (http_request_collect(method, url, body, response, response_len, &status)) {
            if (status_out) *status_out = status;

            /* Retry on 5xx server errors */
            if (status >= 500) {
                ESP_LOGW(TAG, "Server error %d, will retry", status);
                continue;
            }
            return true;
        }
    }

    ESP_LOGE(TAG, "All %d retries exhausted for %s %s", HTTP_MAX_RETRIES, method, url);
    return false;
}

static bool http_stream_chat(const char *url, const char *body)
{
    response_buffer_t stream_ctx = {
        .mode        = HTTP_MODE_STREAM,
        .data        = NULL,
        .capacity    = 0,
        .length      = 0,
        .line_length = 0,
    };

    esp_http_client_config_t config = {
        .url           = url,
        .method        = HTTP_METHOD_POST,
        .timeout_ms    = HTTP_STREAM_TIMEOUT_MS,
        .event_handler = http_event_handler,
        .user_data     = &stream_ctx,
    };

    esp_http_client_handle_t client = esp_http_client_init(&config);
    if (client == NULL) {
        ESP_LOGE(TAG, "Failed to create stream client");
        return false;
    }

    esp_http_client_set_header(client, "Accept", "text/event-stream");
    esp_http_client_set_header(client, "Content-Type", "application/json");
    esp_http_client_set_header(client, "Authorization", "Bearer " AGENT_PASSWORD);

    esp_http_client_set_post_field(client, body, (int)strlen(body));

    ESP_LOGI(TAG, "SSE POST %s (timeout %d ms)", url, HTTP_STREAM_TIMEOUT_MS);
    esp_err_t err = esp_http_client_perform(client);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "SSE request failed: %s (%d)", esp_err_to_name(err), err);
        esp_http_client_cleanup(client);
        return false;
    }

    int status = esp_http_client_get_status_code(client);
    esp_http_client_cleanup(client);

    if (status != 200) {
        ESP_LOGE(TAG, "SSE stream returned HTTP %d", status);
        return false;
    }

    return true;
}

/* ── cJSON helper ───────────────────────────────────────── */

/**
 * Extract the "id" from the first object in a JSON array,
 * or from a plain JSON object.
 */
static bool json_extract_first_id(const char *raw, char *out, size_t out_len)
{
    if (!raw || !out || out_len == 0) return false;

    cJSON *root = cJSON_Parse(raw);
    if (!root) return false;

    cJSON *target = root;
    if (cJSON_IsArray(root)) {
        target = cJSON_GetArrayItem(root, 0);
        if (!target) {
            cJSON_Delete(root);
            return false;
        }
    }

    cJSON *id_item = cJSON_GetObjectItemCaseSensitive(target, "id");
    bool ok = false;
    if (cJSON_IsString(id_item) && id_item->valuestring) {
        strncpy(out, id_item->valuestring, out_len - 1);
        out[out_len - 1] = '\0';
        ok = strlen(id_item->valuestring) > 0;
    }

    cJSON_Delete(root);
    return ok;
}

/* ── Public API ─────────────────────────────────────────── */

bool backend_authenticate(void)
{
    app_state_set(APP_STATE_AUTHENTICATING);

    char url[192];
    snprintf(url, sizeof(url), "%s/api/auth", BACKEND_BASE_URL);

    /* Build JSON body with cJSON */
    cJSON *body_json = cJSON_CreateObject();
    cJSON_AddStringToObject(body_json, "password", AGENT_PASSWORD);
    char *body = cJSON_PrintUnformatted(body_json);
    cJSON_Delete(body_json);

    if (!body) {
        ESP_LOGE(TAG, "Failed to build auth JSON");
        app_state_set(APP_STATE_ERROR);
        return false;
    }

    char response[256];
    int status = 0;
    bool ok = http_request_with_retry("POST", url, body, response, sizeof(response), &status);
    free(body);

    if (!ok || status != 200) {
        ESP_LOGE(TAG, "Auth failed (status=%d)", status);
        app_state_set(APP_STATE_ERROR);
        return false;
    }

    ESP_LOGI(TAG, "Authentication succeeded");
    app_state_set(APP_STATE_AUTHENTICATED);
    return true;
}

bool backend_get_or_create_conversation(char *conversation_id, size_t conversation_id_len)
{
    if (!conversation_id || conversation_id_len == 0) return false;

    app_state_set(APP_STATE_LOADING_CONVERSATION);

    char url[192];
    snprintf(url, sizeof(url), "%s/api/conversations", BACKEND_BASE_URL);

    enum { BUF_SIZE = 8192 };
    char *response = (char *)calloc(1, BUF_SIZE);
    if (!response) {
        ESP_LOGE(TAG, "Failed to allocate conversation buffer");
        app_state_set(APP_STATE_ERROR);
        return false;
    }

    int status = 0;

    /* Try to reuse an existing conversation */
    if (http_request_with_retry("GET", url, NULL, response, BUF_SIZE, &status)
        && status == 200
        && json_extract_first_id(response, conversation_id, conversation_id_len)) {
        ESP_LOGI(TAG, "Reusing conversation: %s", conversation_id);
        free(response);
        app_state_set(APP_STATE_READY);
        return true;
    }

    /* Create a new one */
    ESP_LOGI(TAG, "No reusable conversation, creating new");
    memset(response, 0, BUF_SIZE);

    if (http_request_with_retry("POST", url, "{}", response, BUF_SIZE, &status)
        && (status == 200 || status == 201)
        && json_extract_first_id(response, conversation_id, conversation_id_len)) {
        ESP_LOGI(TAG, "Created conversation: %s", conversation_id);
        free(response);
        app_state_set(APP_STATE_READY);
        return true;
    }

    ESP_LOGE(TAG, "Could not obtain a conversation id");
    free(response);
    app_state_set(APP_STATE_ERROR);
    return false;
}

bool backend_stream_message(const char *conversation_id, const char *message,
                            char *out_response, size_t out_response_len)
{
    if (!conversation_id || conversation_id[0] == '\0' || !message) return false;

    app_state_set(APP_STATE_STREAMING);

    /* Initialize accumulator for this stream */
    if (!accum_init()) {
        ESP_LOGE(TAG, "Failed to init response accumulator");
        app_state_set(APP_STATE_ERROR);
        return false;
    }
    accum_reset();

    char url[256];
    snprintf(url, sizeof(url), "%s/api/chat/%s/stream", BACKEND_BASE_URL, conversation_id);

    /* Build JSON body with cJSON */
    cJSON *body_json = cJSON_CreateObject();
    cJSON_AddStringToObject(body_json, "message", message);
    char *body = cJSON_PrintUnformatted(body_json);
    cJSON_Delete(body_json);

    if (!body) {
        ESP_LOGE(TAG, "Failed to build chat JSON");
        app_state_set(APP_STATE_ERROR);
        return false;
    }

    bool ok = http_stream_chat(url, body);
    free(body);

    /* Copy accumulated response out if requested */
    if (ok && out_response && out_response_len > 0) {
        if (s_accum.buf && s_accum.len > 0) {
            strncpy(out_response, s_accum.buf, out_response_len - 1);
            out_response[out_response_len - 1] = '\0';
        } else {
            out_response[0] = '\0';
        }
    }

    if (ok) {
        ESP_LOGI(TAG, "Stream complete (%u chars accumulated)", (unsigned)s_accum.len);
        app_state_set(APP_STATE_STREAM_COMPLETE);
    } else {
        app_state_set(APP_STATE_ERROR);
    }

    return ok;
}