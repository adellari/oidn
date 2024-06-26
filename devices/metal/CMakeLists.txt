## Copyright 2023 Apple Inc.
## Copyright 2023 Intel Corporation
## SPDX-License-Identifier: Apache-2.0

cmake_minimum_required(VERSION 3.21)

if(NOT CMAKE_CXX_COMPILER_ID STREQUAL "AppleClang" OR
   CMAKE_CXX_COMPILER_VERSION VERSION_LESS 14)
  message(FATAL_ERROR "Building with Metal support requires Xcode 14 or newer")
endif()

include(oidn_metal)

set(OIDN_METAL_SOURCES
  metal_buffer.mm
  metal_buffer.h
  metal_common.h
  metal_common.mm
  metal_device.mm
  metal_device.h
  metal_conv.mm
  metal_conv.h
  metal_engine.mm
  metal_engine.h
  metal_heap.h
  metal_heap.mm
  metal_module.mm
)

add_library(OpenImageDenoise_device_metal ${OIDN_LIB_TYPE} ${OIDN_METAL_SOURCES} ${OIDN_RESOURCE_FILE})

if (${CMAKE_SYSTEM_NAME} MATCHES "iOS")
    set(MIN_OS_VERSION 16.0)
    set(PLATFORM_OPTION "-mios-version-min")
else()
    set(MIN_OS_VERSION 13.0)
    set(PLATFORM_OPTION "-mmacosx-version-min")
endif()

metallib_target_add_sources(OpenImageDenoise_device_metal metal_kernels
  metal_kernels.metal
  INCLUDE_DIRECTORIES
    ${PROJECT_SOURCE_DIR}
  COMPILE_OPTIONS
    -std=metal3.0 -fno-fast-math ${PLATFORM_OPTION}=${MIN_OS_VERSION}
)

set_property(TARGET OpenImageDenoise_device_metal PROPERTY VERSION ${PROJECT_VERSION})
set_property(TARGET OpenImageDenoise_device_metal PROPERTY CXX_STANDARD 17)

target_compile_definitions(OpenImageDenoise_device_metal PRIVATE OIDN_COMPILE_METAL_HOST)

target_link_libraries(OpenImageDenoise_device_metal PRIVATE "-framework Foundation")
target_link_libraries(OpenImageDenoise_device_metal PRIVATE "-framework Metal")
target_link_libraries(OpenImageDenoise_device_metal PRIVATE "-framework MetalPerformanceShadersGraph")
target_link_libraries(OpenImageDenoise_device_metal PRIVATE "-framework MetalPerformanceShaders")
target_link_libraries(OpenImageDenoise_device_metal PRIVATE OpenImageDenoise_core)

if(OIDN_STATIC_LIB)
  oidn_install_static_module(OpenImageDenoise_device_metal)
  target_link_libraries(OpenImageDenoise PRIVATE OpenImageDenoise_device_metal)
else()
  oidn_strip_symbols(OpenImageDenoise_device_metal)
  oidn_install_module(OpenImageDenoise_device_metal)
endif()
