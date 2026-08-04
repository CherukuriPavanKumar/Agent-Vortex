#pragma once

#include <stdbool.h>

/** Initialize Wi-Fi STA and block until connected or timeout. */
bool wifi_connect_and_wait(void);

/** Returns true if Wi-Fi is currently connected. */
bool wifi_is_connected(void);

/** Device IP as a string, or NULL when not connected. */
const char *wifi_get_ip_string(void);

/** How many reconnect attempts since last success. */
int wifi_get_retry_count(void);