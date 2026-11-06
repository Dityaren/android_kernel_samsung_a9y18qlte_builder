#!/usr/bin/env python3
"""
Hooks follow https://bakasu.org/guide/manual-integrate with the 4.4 variants:
  execve    -> fs/exec.c      (3.14+ pattern, do_execveat_common)
  faccessat -> fs/open.c      (4.19- pattern)
  stat      -> fs/stat.c      (newfstatat/fstatat64 + newfstat/fstat64 return hooks)
  reboot    -> kernel/reboot.c (3.11+ pattern)
Not needed on 4.4: setuid / sys_read / input hooks (done by BakaSU through LSM and
input_handler when the CONFIG_KSU_MANUAL_HOOK_AUTO_* options are enabled, default y),
and the SELinux static-symbol exports (CONFIG_KALLSYMS_ALL=y is already set).

Usage: apply_bakasu_hooks.py /path/to/kernel_source
Every anchor must match exactly once, otherwise nothing is written for that file.
"""
import sys
from pathlib import Path

root = Path(sys.argv[1])


def patch(rel, edits):
    p = root / rel
    s = p.read_text()
    if "CONFIG_KSU_MANUAL_HOOK" in s:
        print(f"skip   {rel} (already patched)")
        return
    for old, new in edits:
        n = s.count(old)
        if n != 1:
            sys.exit(f"ERROR {rel}: anchor matched {n} times (expected 1):\n{old}")
        s = s.replace(old, new)
    p.write_text(s)
    print(f"patched {rel} ({len(edits)} edits)")


# fs/exec.c
patch("fs/exec.c", [
    (
        "/*\n * sys_execve() executes a new program.\n */\n"
        "static int do_execveat_common(",
        "#ifdef CONFIG_KSU_MANUAL_HOOK\n"
        "__attribute__((hot))\n"
        "extern int ksu_handle_execveat(int *fd, struct filename **filename_ptr,\n"
        "\t\t\t\tvoid *argv, void *envp, int *flags);\n"
        "__attribute__((hot))\n"
        "extern int ksu_handle_post_execveat(int *fd, struct filename **filename_ptr,\n"
        "\t\t\t\tvoid *argv, void *envp, int *flags, int *retval);\n"
        "#endif\n\n"
        "/*\n * sys_execve() executes a new program.\n */\n"
        "static int do_execveat_common(",
    ),
    (
        "\tint retval;\n\n\tif (IS_ERR(filename))\n\t\treturn PTR_ERR(filename);\n\n\t/*\n\t * We move the actual failure",
        "\tint retval;\n\n"
        "#ifdef CONFIG_KSU_MANUAL_HOOK\n"
        "\tksu_handle_execveat(&fd, &filename, &argv, &envp, &flags);\n"
        "#endif\n\n"
        "\tif (IS_ERR(filename))\n\t\treturn PTR_ERR(filename);\n\n\t/*\n\t * We move the actual failure",
    ),
    (
        "out_ret:\n\tputname(filename);\n\treturn retval;\n}\n",
        "out_ret:\n"
        "#ifdef CONFIG_KSU_MANUAL_HOOK\n"
        "\tksu_handle_post_execveat(&fd, &filename, &argv, &envp, &flags, &retval);\n"
        "#endif\n"
        "\tputname(filename);\n\treturn retval;\n}\n",
    ),
])

# fs/open.c
patch("fs/open.c", [
    (
        "/*\n * access() needs to use the real uid/gid, not the effective uid/gid.",
        "#ifdef CONFIG_KSU_MANUAL_HOOK\n"
        "__attribute__((hot))\n"
        "extern int ksu_handle_faccessat(int *dfd, const char __user **filename_user,\n"
        "\t\t\t\tint *mode, int *flags);\n"
        "#endif\n\n"
        "/*\n * access() needs to use the real uid/gid, not the effective uid/gid.",
    ),
    (
        "\tunsigned int lookup_flags = LOOKUP_FOLLOW;\n\n\tif (mode & ~S_IRWXO)",
        "\tunsigned int lookup_flags = LOOKUP_FOLLOW;\n\n"
        "#ifdef CONFIG_KSU_MANUAL_HOOK\n"
        "\tksu_handle_faccessat(&dfd, &filename, &mode, NULL);\n"
        "#endif\n\n"
        "\tif (mode & ~S_IRWXO)",
    ),
])

# kernel/reboot.c
patch("kernel/reboot.c", [
    (
        "static DEFINE_MUTEX(reboot_mutex);\n",
        "static DEFINE_MUTEX(reboot_mutex);\n\n"
        "#ifdef CONFIG_KSU_MANUAL_HOOK\n"
        "extern int ksu_handle_sys_reboot(int magic1, int magic2, unsigned int cmd, void __user **arg);\n"
        "#endif\n",
    ),
    (
        "\tint ret = 0;\n\n\t/* We only trust the superuser with rebooting the system. */",
        "\tint ret = 0;\n\n"
        "#ifdef CONFIG_KSU_MANUAL_HOOK\n"
        "\tksu_handle_sys_reboot(magic1, magic2, cmd, &arg);\n"
        "#endif\n\n"
        "\t/* We only trust the superuser with rebooting the system. */",
    ),
])

# fs/stat.c
patch("fs/stat.c", [
    (
        "#if !defined(__ARCH_WANT_STAT64) || defined(__ARCH_WANT_SYS_NEWFSTATAT)\n"
        "SYSCALL_DEFINE4(newfstatat, int, dfd, const char __user *, filename,\n"
        "\t\tstruct stat __user *, statbuf, int, flag)\n"
        "{\n\tstruct kstat stat;\n\tint error;\n\n"
        "\terror = vfs_fstatat(dfd, filename, &stat, flag);",
        "#ifdef CONFIG_KSU_MANUAL_HOOK\n"
        "__attribute__((hot))\n"
        "extern int ksu_handle_stat(int *dfd, const char __user **filename_user,\n"
        "\t\t\t\tint *flags);\n\n"
        "extern void ksu_handle_newfstat_ret(unsigned int *fd, struct stat __user **statbuf_ptr);\n"
        "#if defined(__ARCH_WANT_STAT64) || defined(__ARCH_WANT_COMPAT_STAT64)\n"
        "extern void ksu_handle_fstat64_ret(unsigned long *fd, struct stat64 __user **statbuf_ptr); // optional\n"
        "#endif\n"
        "#endif\n\n"
        "#if !defined(__ARCH_WANT_STAT64) || defined(__ARCH_WANT_SYS_NEWFSTATAT)\n"
        "SYSCALL_DEFINE4(newfstatat, int, dfd, const char __user *, filename,\n"
        "\t\tstruct stat __user *, statbuf, int, flag)\n"
        "{\n\tstruct kstat stat;\n\tint error;\n\n"
        "#ifdef CONFIG_KSU_MANUAL_HOOK\n"
        "\tksu_handle_stat(&dfd, &filename, &flag);\n"
        "#endif\n"
        "\terror = vfs_fstatat(dfd, filename, &stat, flag);",
    ),
    (
        "SYSCALL_DEFINE2(newfstat, unsigned int, fd, struct stat __user *, statbuf)\n"
        "{\n\tstruct kstat stat;\n\tint error = vfs_fstat(fd, &stat);\n\n"
        "\tif (!error)\n\t\terror = cp_new_stat(&stat, statbuf);\n\n\treturn error;",
        "SYSCALL_DEFINE2(newfstat, unsigned int, fd, struct stat __user *, statbuf)\n"
        "{\n\tstruct kstat stat;\n\tint error = vfs_fstat(fd, &stat);\n\n"
        "\tif (!error)\n\t\terror = cp_new_stat(&stat, statbuf);\n\n"
        "#ifdef CONFIG_KSU_MANUAL_HOOK\n"
        "\tksu_handle_newfstat_ret(&fd, &statbuf);\n"
        "#endif\n"
        "\treturn error;",
    ),
    (
        "SYSCALL_DEFINE2(fstat64, unsigned long, fd, struct stat64 __user *, statbuf)\n"
        "{\n\tstruct kstat stat;\n\tint error = vfs_fstat(fd, &stat);\n\n"
        "\tif (!error)\n\t\terror = cp_new_stat64(&stat, statbuf);\n\n\treturn error;",
        "SYSCALL_DEFINE2(fstat64, unsigned long, fd, struct stat64 __user *, statbuf)\n"
        "{\n\tstruct kstat stat;\n\tint error = vfs_fstat(fd, &stat);\n\n"
        "\tif (!error)\n\t\terror = cp_new_stat64(&stat, statbuf);\n\n"
        "#ifdef CONFIG_KSU_MANUAL_HOOK // for 32-bit\n"
        "\tksu_handle_fstat64_ret(&fd, &statbuf);\n"
        "#endif\n"
        "\treturn error;",
    ),
    (
        "SYSCALL_DEFINE4(fstatat64, int, dfd, const char __user *, filename,\n"
        "\t\tstruct stat64 __user *, statbuf, int, flag)\n"
        "{\n\tstruct kstat stat;\n\tint error;\n\n"
        "\terror = vfs_fstatat(dfd, filename, &stat, flag);",
        "SYSCALL_DEFINE4(fstatat64, int, dfd, const char __user *, filename,\n"
        "\t\tstruct stat64 __user *, statbuf, int, flag)\n"
        "{\n\tstruct kstat stat;\n\tint error;\n\n"
        "#ifdef CONFIG_KSU_MANUAL_HOOK // 32-bit su\n"
        "\tksu_handle_stat(&dfd, &filename, &flag);\n"
        "#endif\n"
        "\terror = vfs_fstatat(dfd, filename, &stat, flag);",
    ),
])

# defconfig
cfg = root / "arch/arm64/configs/a9y18qlte_defconfig"
s = cfg.read_text()
if "CONFIG_KSU=y" in s:
    print("skip   defconfig (already has CONFIG_KSU)")
else:
    if not s.endswith("\n"):
        s += "\n"
    s += "\n# BakaSU\nCONFIG_KSU=y\nCONFIG_KSU_MANUAL_HOOK=y\n"
    cfg.write_text(s)
    print("patched a9y18qlte_defconfig")
