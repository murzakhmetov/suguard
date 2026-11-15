#!/usr/bin/env bash
# Cross-build C++ sources for the instruction set of the ESP32-C3 (RV32IMC, no
# FPU: soft-float) as a bare-metal program with picolibc, and optionally run it
# under QEMU. stdio, files and the command line go through semihosting.
#
#   bash build_rv32.sh <out.elf> <sources...>                 build only
#   bash build_rv32.sh <out.elf> <sources...> -- <args...>    build, then run: argv[1..] = <args>
#
# The program sees the host file system, so file names in <args> are host
# paths (relative ones resolve against the current directory). The exit status
# is the compiler's or, when the program is run, the program's.
#
# The compiler flags are the ones the firmware core must build cleanly with.
# Environment: RV32_CXX, RV32_QEMU (tool names), RV32_CXXFLAGS (extra flags),
# RV32_TIMEOUT (seconds QEMU may run, default 900).
set -euo pipefail

CXX=${RV32_CXX:-riscv64-unknown-elf-g++}
QEMU=${RV32_QEMU:-qemu-system-riscv32}
CORE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/suguard/src/core"

if [ "$#" -lt 2 ]; then
  sed -n '2,15p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//' >&2
  exit 2
fi
out=$1
shift
sources=()
while [ "$#" -gt 0 ] && [ "$1" != "--" ]; do
  sources+=("$1")
  shift
done
run=0
if [ "$#" -gt 0 ]; then
  run=1
  shift  # the "--"
fi

# shellcheck disable=SC2086  # RV32_CXXFLAGS is a list of flags
"$CXX" -std=gnu++17 -march=rv32imc -mabi=ilp32 -O2 -Wall -Wextra -Werror \
  -fno-exceptions -fno-rtti -fno-threadsafe-statics -nostdlib++ -ffp-contract=off \
  --specs=picolibc.specs --oslib=semihost --crt0=semihost \
  -Wl,--defsym=__flash=0x80000000 -Wl,--defsym=__flash_size=0x00800000 \
  -Wl,--defsym=__ram=0x80800000 -Wl,--defsym=__ram_size=0x00800000 \
  ${RV32_CXXFLAGS:-} -I "$CORE" -o "$out" "${sources[@]}"

[ "$run" -eq 1 ] || exit 0

# QEMU splits the semihosting option string at commas; a doubled comma is a literal one.
config="enable=on,target=native,arg=$(basename "$out")"
for arg in "$@"; do
  config+=",arg=${arg//,/,,}"
done
exec timeout "${RV32_TIMEOUT:-900}" "$QEMU" -M virt -bios none -nographic \
  -semihosting-config "$config" -kernel "$out"
