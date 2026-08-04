# Vortex Hardware – ESP-IDF main component

FILE(GLOB_RECURSE app_sources ${CMAKE_SOURCE_DIR}/src/*.*)

idf_component_register(
    SRCS ${app_sources}
    INCLUDE_DIRS "."
    PRIV_REQUIRES esp_http_client esp_wifi esp_event esp_netif nvs_flash freertos
)
