# =============================================================================
# Agent Vortex Handheld — Top-level CMakeLists.txt
#
# This file is the ESP-IDF CMake entry point.  PlatformIO with framework=espidf
# calls cmake with this file as the project root.
#
# Keep it minimal — component-specific CMakeLists files live under src/.
# =============================================================================

cmake_minimum_required(VERSION 3.16)

include($ENV{IDF_PATH}/tools/cmake/project.cmake)

project(agent_vortex_handheld)

