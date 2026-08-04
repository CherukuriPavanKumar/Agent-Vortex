#pragma once

#include <stdbool.h>

typedef enum {
    APP_STATE_BOOT = 0,
    APP_STATE_WIFI_CONNECTING,
    APP_STATE_WIFI_CONNECTED,
    APP_STATE_AUTHENTICATING,
    APP_STATE_AUTHENTICATED,
    APP_STATE_LOADING_CONVERSATION,
    APP_STATE_READY,
    APP_STATE_STREAMING,
    APP_STATE_STREAM_COMPLETE,
    APP_STATE_ERROR,
} app_state_t;

/** Human-readable name for a state. */
const char *app_state_name(app_state_t state);

/** Get the current application state. */
app_state_t app_state_get(void);

/** Transition to a new state (logs the change). */
void app_state_set(app_state_t new_state);

/** Quick error-state check. */
bool app_state_is_error(void);
