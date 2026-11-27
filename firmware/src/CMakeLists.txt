# =============================================================================
# Agent Vortex Handheld — src/CMakeLists.txt
#
# Registers the main application component.
# Dependencies in idf_component.yml (espressif/esp_lcd_ili9341) are resolved
# automatically by the ESP-IDF Component Manager into managed_components/.
# =============================================================================

idf_component_register(
    SRCS "main.c"
    INCLUDE_DIRS "."
)
