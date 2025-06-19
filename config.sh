#!/bin/bash

export ARCH="arm64"
export DEVICE
export KBUILD_BUILD_USER="wulan17"
export KBUILD_BUILD_HOST="Github"
export CLANG_URL="https://github.com/wulan17/tc-build/releases/download/21.0.0git-dca74f794/Mayuri-clang_21.0.0gitgit-bookworm-aarch64-dca74f794.tar.xz"
export CLANG_NAME="$(basename "$CLANG_URL")"
export BASE_DIR=$(pwd)

export DTB_PATH="$BASE_DIR"/out/arch/"$ARCH"/boot/dts/mediatek/mt6768.dtb
export ZIP_DIR="$BASE_DIR"/AnyKernel
export CORES=$(nproc --all)
export PATH="$BASE_DIR/clang/bin:/usr/lib/ccache:$PATH"
export IS_SUSFS

if [ $IS_SUSFS -eq 1 ]; then
    export ZIP_NAME="Mayuri-kernel-$DEVICE-rksu-susfs-"$(env TZ='Asia/Jakarta' date +%Y%m%d)
else
    export ZIP_NAME="Mayuri-kernel-$DEVICE-rksu-"$(env TZ='Asia/Jakarta' date +%Y%m%d)
fi
