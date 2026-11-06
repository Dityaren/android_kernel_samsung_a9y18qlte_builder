# Galaxy A9 (2018) Kernel Docker Build

Docker-based out-of-tree build environment for Samsung Galaxy A9 (2018) kernel (`a9y18qlte`).

- **Source:** [thongass000/android_kernel_samsung_a9y18qlte](https://github.com/thongass000/android_kernel_samsung_a9y18qlte)
- **Branch:** `CAF` | **Linux Version:** `4.4.205` | **SoC:** `SDM660` (non-GKI)

---

## Quick Start

```bash
git clone https://github.com/thongass000/android_kernel_samsung_a9y18qlte
docker build -t a9-kernel-builder .

docker run --rm \
  -v "$PWD/android_kernel_samsung_a9y18qlte":/src \
  -v "$PWD/out":/out \
  -e HOST_UID=$(id -u) -e HOST_GID=$(id -g) \
  a9-kernel-builder

```

### Build Output Locations

- `out/dist/`: `Image`, `Image.gz`, `Image.gz-dtb`, `config`, `kernel_release.txt`, `SHA256SUMS`
- `out/build/`: Object files (~6.4 GB). Preserve between runs for incremental compilation.

---

## Environment & Build Configuration

### Environment Variables

| Variable      | Default               | Description                                                                               |
| ------------- | --------------------- | ----------------------------------------------------------------------------------------- |
| `DEFCONFIG`   | `a9y18qlte_defconfig` | Target kernel config                                                                      |
| `JOBS`        | All CPUs              | Parallel compilation threads                                                              |
| `USE_WRAPPER` | `0`                   | Set `1` to enable `scripts/gcc-wrapper.py` (strict warnings-as-errors; requires Python 2) |

### Key Technical Notes

- **Region Support:** `a9y18qlte_defconfig` sets `CONFIG_MACH_A9Y18QLTE_EUR=y`. Builds EUR DTBs (`r01`–`r06`) only. CHN, CIS, and KOR variants require dedicated defconfigs.
- **Toolchain:** Google Android GCC 4.9 (LineageOS mirror commit `5e030eaf…`). Required for `-mno-android` support.
- **Container Base:** Ubuntu 20.04. Avoids GCC $\ge$ 10 in-tree `dtc` compilation failures (missing `-fcommon`) and OpenSSL 3 deprecation warnings.
- **Packaging:** Output produces the kernel payload (`Image.gz-dtb`). `mkbootimg` integration with stock ramdisk/header offsets must be performed downstream.

---

## BakaSU Integration (Manual Hooks)

Integrates BakaSU `v4.2.0-rc3` (KernelSU commit `516d3e87`).

### Build Steps

```bash
cd android_kernel_samsung_a9y18qlte
git checkout -b bakasu

# 1. Fetch BakaSU drivers and symlinks
curl -LSs "https://raw.githubusercontent.com/Baka-SU/BakaSU/main/kernel/setup.sh" | bash

# 2. Pin BakaSU commit for reproducible builds
rm -rf KernelSU && git clone https://github.com/Baka-SU/BakaSU KernelSU
git -C KernelSU checkout 516d3e87

# 3. Apply kernel hooks and defconfig flags
python3 ../apply_bakasu_hooks.py "$PWD"

# 4. Build (isolated output directory)
docker run --rm \
  -v "$PWD":/src \
  -v "$PWD/../out-ksu":/out \
  -e HOST_UID=$(id -u) -e HOST_GID=$(id -g) \
  a9-kernel-builder

```

### Hook Target Files

| File                  | Functions Modified / Hooks Applied                                                                    |
| --------------------- | ----------------------------------------------------------------------------------------------------- |
| `fs/exec.c`           | `ksu_handle_execveat` (pre-`IS_ERR`), `ksu_handle_post_execveat` (at `out_ret`)                       |
| `fs/open.c`           | `ksu_handle_faccessat` inside `faccessat`                                                             |
| `fs/stat.c`           | `ksu_handle_stat` inside `newfstatat`/`fstatat64`; `ksu_handle_newfstat_ret`/`ksu_handle_fstat64_ret` |
| `kernel/reboot.c`     | `ksu_handle_sys_reboot`                                                                               |
| `a9y18qlte_defconfig` | `CONFIG_KSU=y`, `CONFIG_KSU_MANUAL_HOOK=y`                                                            |

> **Note:** LSM/input*handler auto-hooks cover setuid, `sys_read`, and input hooks (`CONFIG_KSU_MANUAL_HOOK_AUTO*\*=y`). Static SELinux exports are satisfied by existing `CONFIG_KALLSYMS_ALL=y`.

### Known BakaSU Issues & Fixes

- **Execve Semicolons:** Official BakaSU docs contain syntax errors (missing semicolons) in the execve diff. Use `apply_bakasu_hooks.py`.
- **Empty Directory Trap:** If an empty `KernelSU/` folder exists, `setup.sh` exits silently without cloning, causing `drivers/Kconfig` build errors. Run the explicit `git clone` command from Step 2 above to resolve.

---

## SUSFS Compatibility

Kernel 4.4.205 supports backported SUSFS:

1. Port kernel-side SUSFS patches manually from the `gki-android12-5.10` branch of [susfs4ksu](https://gitlab.com/simonpunk/susfs4ksu).
2. Replace `CONFIG_KSU_MANUAL_HOOK=y` with `CONFIG_KSU_SUSFS=y` in your defconfig.
3. Validate basic BakaSU boot before applying SUSFS patches.
