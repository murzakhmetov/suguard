#!/bin/bash
# Type-checks the firmware against the real Arduino-ESP32 headers without the
# ESP32 toolchain: every source file is run through a GCC front end
# (-fsyntax-only) with the include paths and defines of the core, for
#   * core 2.0.17 (ESP-IDF 4.4, what PlatformIO's espressif32 6.x uses), as C++17
#   * core 3.3.12 (ESP-IDF 5.5, what the Arduino IDE installs), as C++20
# It finds wrong API names and signatures, missing includes and name clashes.
# It is NOT a build: no code is generated or linked, the compiler is a generic
# 32-bit newlib one (arm-none-eabi-g++), not Espressif's.
#
#   sudo apt install gcc-arm-none-eabi libnewlib-arm-none-eabi libstdc++-arm-none-eabi-dev unzip curl
#   firmware/tools/typecheck_arduino.sh [cache-dir]      (downloads about 370 MB once)
set -euo pipefail
SKETCH="$(cd "$(dirname "$0")/../suguard" && pwd)"
CACHE="${1:-$HOME/.cache/suguard-typecheck}"
CXX="${CXX:-arm-none-eabi-g++}"
REL=https://github.com/espressif/arduino-esp32/releases/download
mkdir -p "$CACHE"

fetch() {   # fetch <url> <marker dir> <unzip patterns...>
  local url=$1 marker=$2; shift 2
  [ -d "$CACHE/$marker" ] && return 0
  echo "downloading $url"
  curl -fsSL -o "$CACHE/pkg.zip" "$url"
  (cd "$CACHE" && unzip -q -o pkg.zip "$@" || true)      # some patterns do not exist in every package
  rm -f "$CACHE/pkg.zip"
  [ -d "$CACHE/$marker" ] || { echo "could not unpack $url"; exit 1; }
}

fetch "$REL/2.0.17/esp32-2.0.17.zip" esp32-2.0.17 \
  'esp32-2.0.17/cores/esp32/*' 'esp32-2.0.17/variants/esp32c3/*' 'esp32-2.0.17/libraries/*/src/*' \
  'esp32-2.0.17/tools/sdk/esp32c3/include/*' 'esp32-2.0.17/tools/sdk/esp32c3/dio_qspi/include/*' 'esp32-2.0.17/platform.txt'
fetch "$REL/3.3.12/esp32-core-3.3.12.zip" esp32-core-3.3.12 \
  'esp32-core-3.3.12/cores/esp32/*' 'esp32-core-3.3.12/variants/esp32c3/*' 'esp32-core-3.3.12/libraries/*/src/*'
fetch "$REL/3.3.12/esp32c3-libs-3.3.12.zip" esp32c3-libs \
  'esp32c3-libs/include/*' 'esp32c3-libs/flags/*' 'esp32c3-libs/dio_qspi/include/*'

ARDUINO_DEFS=(-DF_CPU=160000000L -DARDUINO=10819 -DARDUINO_ESP32C3_DEV -DARDUINO_ARCH_ESP32 '-DARDUINO_BOARD="ESP32C3_DEV"'
              '-DARDUINO_VARIANT="esp32c3"' -DESP32=ESP32 -DCORE_DEBUG_LEVEL=0 -DARDUINO_USB_MODE=1 -DARDUINO_USB_CDC_ON_BOOT=1
              -D__riscv -D__riscv_xlen=32)      # select the RISC-V branches of the SDK headers
lib_includes() { for d in "$1"/libraries/*/src; do printf -- '-I%s\n' "$d"; done; }

core2() {   # include paths as listed in the core's platform.txt
  local core="$CACHE/esp32-2.0.17" sdk="$CACHE/esp32-2.0.17/tools/sdk/esp32c3"
  mapfile -t inc < <(grep '^compiler.cpreprocessor.flags.esp32c3=' "$core/platform.txt" | grep -o '"-I{compiler.sdk.path}[^"]*"' |
                     tr -d '"' | sed "s#{compiler.sdk.path}#$sdk#")
  mapfile -t libs < <(lib_includes "$core")
  "$CXX" -fsyntax-only -std=gnu++17 -fno-rtti -Wall -Wextra -Wno-unused-parameter \
    -DHAVE_CONFIG_H '-DMBEDTLS_CONFIG_FILE="mbedtls/esp_config.h"' -DUNITY_INCLUDE_CONFIG_H -DWITH_POSIX -D_GNU_SOURCE \
    '-DIDF_VER="v4.4.7"' -DESP_PLATFORM -D_POSIX_READER_WRITER_LOCKS "${ARDUINO_DEFS[@]}" \
    "${inc[@]}" -I"$sdk/dio_qspi/include" -I"$core/cores/esp32" -I"$core/variants/esp32c3" "${libs[@]}" -x c++ "$1"
}

core3() {   # flags files shipped with the core's SDK package
  local core="$CACHE/esp32-core-3.3.12" sdk="$CACHE/esp32c3-libs"
  mapfile -t libs < <(lib_includes "$core")
  "$CXX" -fsyntax-only -std=gnu++2a -fno-rtti -Wall -Wextra -Wno-unused-parameter \
    "@$sdk/flags/defines" -iprefix "$sdk/include/" "@$sdk/flags/includes" -I"$sdk/dio_qspi/include" "${ARDUINO_DEFS[@]}" \
    -I"$core/cores/esp32" -I"$core/variants/esp32c3" "${libs[@]}" -x c++ "$1"
}

cd "$SKETCH"
status=0
for core in core2 core3; do
  for src in suguard.ino src/app/*.cpp src/drivers/*.cpp src/core/*.cpp; do
    if out=$($core "$src" 2>&1); then rc=0; else rc=$?; fi
    mine=$(grep -E "^(suguard\.ino|src/)[^ ]*: (fatal error|error|warning)" <<<"$out" || true)
    if [ -n "$mine" ]; then                 # anything the compiler says about the firmware's own files
      echo "$core $src:"; echo "$mine"; status=1
    elif [ $rc -ne 0 ]; then                # the front end stopped somewhere else (SDK headers, missing package)
      echo "$core $src: failed outside the firmware sources:"; grep -E "error" <<<"$out" | head -5; status=1
    fi
  done
  echo "$core: checked $(ls suguard.ino src/app/*.cpp src/drivers/*.cpp src/core/*.cpp | wc -l) files"
done
[ $status = 0 ] && echo "type-check passed for Arduino core 2.0.17 and 3.3.12"
exit $status
