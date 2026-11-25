cmake_minimum_required(VERSION 3.25)

if(NOT CMAKE_SYSTEM_NAME STREQUAL "iOS"
   OR NOT CMAKE_OSX_ARCHITECTURES STREQUAL "arm64"
   OR NOT CMAKE_OSX_SYSROOT MATCHES "/iPhoneOS18[.]5[.]sdk/?$"
   OR NOT CMAKE_OSX_DEPLOYMENT_TARGET STREQUAL "16.3")
    message(FATAL_ERROR "The link probe requires iPhoneOS SDK 18.5, arm64 and minimum iOS 16.3")
endif()

project(MoltenVKLinkProbe LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 23)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

if(NOT CMAKE_CXX_COMPILER_ID STREQUAL "AppleClang")
    message(FATAL_ERROR "The link probe requires AppleClang")
endif()

set(MOLTENVK_ARCHIVE "" CACHE FILEPATH "Inspected device archive")
set(VULKAN_HEADERS "" CACHE PATH "Pinned Vulkan-Headers include directory")
if(NOT EXISTS "${MOLTENVK_ARCHIVE}" OR IS_DIRECTORY "${MOLTENVK_ARCHIVE}"
   OR NOT EXISTS "${VULKAN_HEADERS}/vulkan/vulkan.h")
    message(FATAL_ERROR "Provide the inspected archive and the pinned Vulkan headers")
endif()

add_library(MoltenVK::MoltenVK STATIC IMPORTED)
set_target_properties(MoltenVK::MoltenVK PROPERTIES IMPORTED_LOCATION "${MOLTENVK_ARCHIVE}")

add_executable(MoltenVKLinkProbe main.cpp)
target_include_directories(MoltenVKLinkProbe PRIVATE "${VULKAN_HEADERS}")
target_link_options(MoltenVKLinkProbe PRIVATE -ObjC -fexperimental-library)
target_link_libraries(MoltenVKLinkProbe PRIVATE MoltenVK::MoltenVK)
foreach(framework Metal Foundation QuartzCore CoreGraphics IOSurface UIKit)
    find_library(PROBE_${framework} ${framework}
        PATHS "${CMAKE_OSX_SYSROOT}/System/Library/Frameworks" NO_DEFAULT_PATH REQUIRED)
    target_link_libraries(MoltenVKLinkProbe PRIVATE "${PROBE_${framework}}")
endforeach()
