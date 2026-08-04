#pragma once

/* ── Wi-Fi ──────────────────────────────────────────────── */
#ifndef WIFI_SSID
#define WIFI_SSID "motorola edge 50 fusion"
#endif

#ifndef WIFI_PASSWORD
#define WIFI_PASSWORD "Pavan@369"
#endif

#ifndef WIFI_CONNECT_TIMEOUT_MS
#define WIFI_CONNECT_TIMEOUT_MS 30000
#endif

#ifndef WIFI_MAX_RETRIES
#define WIFI_MAX_RETRIES 10
#endif

/* ── Backend ────────────────────────────────────────────── */
#ifndef BACKEND_BASE_URL
#define BACKEND_BASE_URL "http://10.236.151.250:8000"
#endif

#ifndef AGENT_PASSWORD
#define AGENT_PASSWORD "vortex2026"
#endif

#ifndef AGENT_TEST_MESSAGE
#define AGENT_TEST_MESSAGE "Hello from Agent Vortex handheld."
#endif

/* ── HTTP Tuning ────────────────────────────────────────── */
#ifndef HTTP_REQUEST_TIMEOUT_MS
#define HTTP_REQUEST_TIMEOUT_MS 10000
#endif

#ifndef HTTP_STREAM_TIMEOUT_MS
#define HTTP_STREAM_TIMEOUT_MS 120000
#endif

#ifndef HTTP_MAX_RETRIES
#define HTTP_MAX_RETRIES 3
#endif

#ifndef HTTP_RETRY_BASE_DELAY_MS
#define HTTP_RETRY_BASE_DELAY_MS 1000
#endif

/* ── FreeRTOS Task ──────────────────────────────────────── */
#ifndef MAIN_TASK_STACK_SIZE
#define MAIN_TASK_STACK_SIZE 8192
#endif

#ifndef MAIN_TASK_PRIORITY
#define MAIN_TASK_PRIORITY 5
#endif

/* ── Response Buffer ────────────────────────────────────── */
#ifndef RESPONSE_ACCUM_INIT_SIZE
#define RESPONSE_ACCUM_INIT_SIZE 1024
#endif

#ifndef RESPONSE_ACCUM_MAX_SIZE
#define RESPONSE_ACCUM_MAX_SIZE 16384
#endif