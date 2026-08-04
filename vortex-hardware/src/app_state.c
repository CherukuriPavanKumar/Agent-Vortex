#include "app_state.h"
#include "esp_log.h"

static const char *TAG = "state";

static volatile app_state_t s_current_state = APP_STATE_BOOT;

static const char *s_state_names[] = {
    [APP_STATE_BOOT]                 = "BOOT",
    [APP_STATE_WIFI_CONNECTING]      = "WIFI_CONNECTING",
    [APP_STATE_WIFI_CONNECTED]       = "WIFI_CONNECTED",
    [APP_STATE_AUTHENTICATING]       = "AUTHENTICATING",
    [APP_STATE_AUTHENTICATED]        = "AUTHENTICATED",
    [APP_STATE_LOADING_CONVERSATION] = "LOADING_CONVERSATION",
    [APP_STATE_READY]                = "READY",
    [APP_STATE_STREAMING]            = "STREAMING",
    [APP_STATE_STREAM_COMPLETE]      = "STREAM_COMPLETE",
    [APP_STATE_ERROR]                = "ERROR",
};

const char *app_state_name(app_state_t state)
{
    if (state >= APP_STATE_BOOT && state <= APP_STATE_ERROR) {
        return s_state_names[state];
    }
    return "UNKNOWN";
}

app_state_t app_state_get(void)
{
    return s_current_state;
}

void app_state_set(app_state_t new_state)
{
    if (new_state != s_current_state) {
        ESP_LOGI(TAG, "%s -> %s",
                 app_state_name(s_current_state),
                 app_state_name(new_state));
        s_current_state = new_state;
    }
}

bool app_state_is_error(void)
{
    return s_current_state == APP_STATE_ERROR;
}
