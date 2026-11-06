# Ubuntu 20.04 on purpose: its GCC 9 / OpenSSL 1.1.1 still build the 4.4-era
# host tools (in-tree dtc, sign-file) without patches, and python2 is available
# for the optional scripts/gcc-wrapper.py strict mode.
FROM ubuntu:20.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential bc bison flex libssl-dev libelf-dev libncurses-dev \
      cpio rsync kmod lz4 xz-utils zip unzip device-tree-compiler \
      git curl ca-certificates file python2 python3 \
    && ln -sf /usr/bin/python2 /usr/bin/python \
    && rm -rf /var/lib/apt/lists/*

# Google's Android GCC 4.9 aarch64 toolchain (the one Samsung's build scripts expect;
# it understands -mno-android). Pinned to an exact commit for reproducibility.
ARG TOOLCHAIN_REPO=https://github.com/LineageOS/android_prebuilts_gcc_linux-x86_aarch64_aarch64-linux-android-4.9
ARG TOOLCHAIN_REF=5e030eafe024784a73cdf47e6936ac0dbfc763dc
RUN git init -q /opt/aarch64-linux-android-4.9 \
 && cd /opt/aarch64-linux-android-4.9 \
 && git fetch -q --depth 1 "$TOOLCHAIN_REPO" "$TOOLCHAIN_REF" \
 && git checkout -q FETCH_HEAD \
 && rm -rf .git
ENV PATH=/opt/aarch64-linux-android-4.9/bin:$PATH
RUN aarch64-linux-android-gcc --version | head -1

# The source tree is bind-mounted from the host with a different owner.
RUN git config --system --add safe.directory '*'

COPY build.sh /usr/local/bin/build-kernel
RUN chmod +x /usr/local/bin/build-kernel

WORKDIR /src
ENTRYPOINT ["/usr/local/bin/build-kernel"]
