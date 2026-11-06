#!/usr/bin/env bash
#   SRC          kernel source tree (default /src, mounted read/write)
#   OUT          output directory   (default /out)
#   DEFCONFIG    defconfig to build (default a9y18qlte_defconfig)
#   JOBS         parallel jobs      (default: number of CPUs)
#   USE_WRAPPER  1 = keep the tree's scripts/gcc-wrapper.py, which aborts the
#                build on ANY compiler warning (needs python2). Default 0:
#                CC is passed on the command line, which bypasses the wrapper.
#                Only the warning gate is skipped; generated code is identical.
#   HOST_UID / HOST_GID   chown $OUT to this user when finished

set -euo pipefail

SRC="${SRC:-/src}"
OUT="${OUT:-/out}"
DEFCONFIG="${DEFCONFIG:-a9y18qlte_defconfig}"
JOBS="${JOBS:-$(nproc)}"
USE_WRAPPER="${USE_WRAPPER:-0}"

BUILD_DIR="$OUT/build"
DIST_DIR="$OUT/dist"
BOOT_DIR="$BUILD_DIR/arch/arm64/boot"

export ARCH=arm64
export CROSS_COMPILE=aarch64-linux-android-

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

finish() {
  if [ -n "${HOST_UID:-}" ] && [ -d "$OUT" ]; then
    chown -R "$HOST_UID:${HOST_GID:-$HOST_UID}" "$OUT" || true
  fi
}
trap finish EXIT

command -v "${CROSS_COMPILE}gcc" >/dev/null || fail "${CROSS_COMPILE}gcc is not on PATH"
[ -f "$SRC/Makefile" ] || fail "no kernel source at $SRC"
[ ! -e "$SRC/.config" ] || fail "$SRC/.config exists; run 'make mrproper' in the source tree (out-of-tree builds need a clean tree)"

if grep -qs 'drivers/kernelsu/Kconfig' "$SRC/drivers/Kconfig" && [ ! -f "$SRC/drivers/kernelsu/Kconfig" ]; then
  fail "BakaSU is wired into drivers/Kconfig but drivers/kernelsu/Kconfig is missing: the KernelSU/ folder is empty or the symlink is broken. Fix: rm -rf KernelSU && git clone https://github.com/Baka-SU/BakaSU KernelSU (run on the host, in the kernel source root)"
fi

mkdir -p "$BUILD_DIR" "$DIST_DIR"

CC_ARGS=()
if [ "$USE_WRAPPER" != "1" ]; then
  CC_ARGS=(CC="${CROSS_COMPILE}gcc")
fi

kmake() {
  make -C "$SRC" O="$BUILD_DIR" ARCH=arm64 CROSS_COMPILE="$CROSS_COMPILE" \
    KCFLAGS=-mno-android "${CC_ARGS[@]}" "$@"
}

echo "==> toolchain: $(${CROSS_COMPILE}gcc --version | head -1)"
echo "==> defconfig: $DEFCONFIG   jobs: $JOBS   wrapper: $USE_WRAPPER"
kmake "$DEFCONFIG"

# With CONFIG_BUILD_ARM64_APPENDED_DTB_IMAGE_NAMES="" the Makefile appends every
# dtb it finds *at parse time*, so the dtbs must exist before the image target.
echo "==> dtbs"
kmake -j"$JOBS" dtbs

echo "==> kernel (Image.gz-dtb)"
kmake -j"$JOBS"

# verify
IMG="$BOOT_DIR/Image.gz-dtb"
[ -s "$BOOT_DIR/Image" ] || fail "Image was not produced"
[ -s "$BOOT_DIR/Image.gz" ] || fail "Image.gz was not produced"
[ -s "$IMG" ] || fail "Image.gz-dtb was not produced"

dtb_count=$(find -L "$BOOT_DIR/dts" -name '*.dtb' | wc -l)
dtb_bytes=$(find -L "$BOOT_DIR/dts" -name '*.dtb' -printf '%s\n' | awk '{s+=$1} END{print s+0}')
appended=$(($(stat -c %s "$IMG") - $(stat -c %s "$BOOT_DIR/Image.gz")))
echo "==> $dtb_count dtbs built ($dtb_bytes bytes); $appended bytes appended to Image.gz-dtb"
[ "$dtb_count" -gt 0 ] || fail "no dtbs were built"
[ "$appended" -eq "$dtb_bytes" ] || fail "Image.gz-dtb does not contain all dtbs (rebuild: rm $IMG && rerun)"

# collect
cp "$BOOT_DIR/Image" "$BOOT_DIR/Image.gz" "$IMG" "$DIST_DIR/"
cp "$BUILD_DIR/.config" "$DIST_DIR/config"
kmake -s kernelrelease >"$DIST_DIR/kernel_release.txt"
(cd "$DIST_DIR" && sha256sum Image Image.gz Image.gz-dtb config >SHA256SUMS)

echo "==> done: $(cat "$DIST_DIR/kernel_release.txt")"
ls -l "$DIST_DIR"
