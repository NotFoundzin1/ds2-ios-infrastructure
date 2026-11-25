cmake_minimum_required(VERSION 3.25)
project(PhoneOSProbe LANGUAGES NONE)

if(NOT CMAKE_SYSTEM_NAME STREQUAL "iOS")
    find_package(Python3 3.10 REQUIRED COMPONENTS Interpreter)
    enable_testing()
    add_test(NAME infrastructure
        COMMAND "${Python3_EXECUTABLE}" -B -m unittest discover -s "${CMAKE_SOURCE_DIR}/tests" -v)
    return()
endif()

if(NOT CMAKE_GENERATOR STREQUAL "Ninja"
   OR NOT CMAKE_OSX_ARCHITECTURES STREQUAL "arm64"
   OR NOT CMAKE_OSX_SYSROOT MATCHES "(^iphoneos$|/iPhoneOS[0-9.]*[.]sdk/?$)"
   OR NOT CMAKE_OSX_DEPLOYMENT_TARGET STREQUAL "16.3")
    message(FATAL_ERROR "Use Ninja, iphoneos, arm64 and deployment target 16.3")
endif()
enable_language(C OBJC)

foreach(component IN ITEMS ProbeBase ProbePlugin)
    add_library(${component} SHARED "src/${component}.c")
    set_target_properties(${component} PROPERTIES
        FRAMEWORK TRUE
        MACOSX_FRAMEWORK_IDENTIFIER "org.iosprobe.${component}"
        INSTALL_NAME_DIR "@rpath"
        BUILD_WITH_INSTALL_NAME_DIR TRUE
        BUILD_WITH_INSTALL_RPATH TRUE
        INSTALL_RPATH "")
endforeach()
target_link_libraries(ProbePlugin PRIVATE ProbeBase)

find_library(FOUNDATION Foundation REQUIRED)
find_library(UIKIT UIKit REQUIRED)
find_library(METAL Metal REQUIRED)
add_executable(PhoneOSProbe MACOSX_BUNDLE src/main.m)
target_compile_options(PhoneOSProbe PRIVATE -fobjc-arc)
target_link_libraries(PhoneOSProbe PRIVATE ProbePlugin "${FOUNDATION}" "${UIKIT}" "${METAL}")
set_target_properties(PhoneOSProbe PROPERTIES
    MACOSX_BUNDLE_INFO_PLIST "${CMAKE_SOURCE_DIR}/ios/Info.plist.in"
    BUILD_WITH_INSTALL_RPATH TRUE
    INSTALL_RPATH "@executable_path/Frameworks")
foreach(component IN ITEMS ProbeBase ProbePlugin)
    add_custom_command(TARGET PhoneOSProbe POST_BUILD
        COMMAND "${CMAKE_COMMAND}" -E copy_directory
            "$<TARGET_BUNDLE_DIR:${component}>"
            "$<TARGET_FILE_DIR:PhoneOSProbe>/Frameworks/$<TARGET_BUNDLE_DIR_NAME:${component}>"
        VERBATIM)
endforeach()
