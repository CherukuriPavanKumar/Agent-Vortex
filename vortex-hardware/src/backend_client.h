#pragma once

#include <stdbool.h>
#include <stddef.h>

/* ── SSE event callback system ──────────────────────────── */

typedef enum {
    SSE_EVENT_TOKEN = 0,
    SSE_EVENT_DONE,
    SSE_EVENT_ERROR,
    SSE_EVENT_TITLE,
    SSE_EVENT_INTERRUPT,
} sse_event_type_t;

/** Called for every SSE event during streaming. */
typedef void (*sse_event_callback_t)(sse_event_type_t type,
                                     const char *content,
                                     void *user_ctx);

/**
 * Register a callback for SSE events (e.g. to drive a display).
 * Pass NULL to clear. user_ctx is forwarded to every invocation.
 */
void backend_set_sse_callback(sse_event_callback_t cb, void *user_ctx);

/* ── Backend operations ─────────────────────────────────── */

/** POST /api/auth – authenticate with the backend. */
bool backend_authenticate(void);

/** GET + POST /api/conversations – reuse or create a conversation. */
bool backend_get_or_create_conversation(char *conversation_id,
                                        size_t conversation_id_len);

/**
 * POST /api/chat/{id}/stream – send a message and stream the response.
 * The full accumulated response is written into out_response (if non-NULL).
 */
bool backend_stream_message(const char *conversation_id,
                            const char *message,
                            char *out_response,
                            size_t out_response_len);

/**
 * Return the name of an SSE event type (for logging).
 */
const char *sse_event_type_name(sse_event_type_t type);