#!/bin/bash

source config.sh

function parse_parameters() {
    while (($#)); do
        case $1 in
            all | clang | kernel | anykernel | cleanup | write_config | release ) action=$1 ;;
            *) exit 33 ;;
        esac
        shift
    done
}

function do_clang(){
	aria2c --file-allocation=falloc -x16 -s16 "$CLANG_URL" || { echo "Download failed!"; exit 1; }
	mkdir -p clang
	cd clang
	if [[ "$CLANG_NAME" == *.tar.xz ]]; then
		tar -xJf "$BASE_DIR"/"$CLANG_NAME" || { echo "Extraction failed!"; exit 1; }
	elif [[ "$CLANG_NAME" == *.tar.gz ]]; then
		tar -xzf "$BASE_DIR"/"$CLANG_NAME" || { echo "Extraction failed!"; exit 1; }
	elif [[ "$CLANG_NAME" == *.tar.bz2 ]]; then
		tar -xjf "$BASE_DIR"/"$CLANG_NAME" || { echo "Extraction failed!"; exit 1; }
	else
		echo "Unsupported archive format: $CLANG_NAME"
		exit 1
	fi
	cd "$BASE_DIR" && rm "$CLANG_NAME"
}

function do_write_config() {
	DEVICE=$(echo "$KERNEL_DEFCONFIG" | cut -d '-' -f1 | cut -d '_' -f1)

	sed -i "s#export DEVICE#export DEVICE=\"$DEVICE\"#g" "$BASE_DIR"/config.sh
	sed -i "s#export B_TYPE#export B_TYPE=\"$BUILD_TYPE\"#g" "$BASE_DIR"/config.sh
	sed -i "s#export KERN_IMG#export KERN_IMG=\"$BASE_DIR/out/arch/$ARCH/boot/$KERNEL_IMG\"#g" "$BASE_DIR"/config.sh
	sed -i "s#export DTB_PATH#export DTB_PATH=\"$BASE_DIR/out/arch/$ARCH/boot/dts/$KERNEL_DTB\"#g" "$BASE_DIR"/config.sh
	sed -i "s#export KERN_DEFCONFIG#export KERN_DEFCONFIG=\"$KERNEL_DEFCONFIG\"#g" "$BASE_DIR"/config.sh
}


function write_ksu_config() {
	echo """
# KernelSU
CONFIG_KSU=y
CONFIG_KSU_MANUAL_HOOK=y""" >> "$BASE_DIR"/kernel/arch/"$ARCH"/configs/"$KERN_DEFCONFIG"
}

function write_susfs_config() {
	echo """
# KernelSU
CONFIG_KSU=y
CONFIG_KSU_MANUAL_HOOK=y

# KernelSU - SusFs
CONFIG_KSU_SUSFS=y
CONFIG_KSU_SUSFS_SUS_PATH=y
CONFIG_KSU_SUSFS_SUS_MOUNT=y
CONFIG_KSU_SUSFS_SUS_KSTAT=y
CONFIG_KSU_SUSFS_SUS_OVERLAYFS=y
CONFIG_KSU_SUSFS_TRY_UMOUNT=y
CONFIG_KSU_SUSFS_SPOOF_UNAME=y
CONFIG_KSU_SUSFS_ENABLE_LOG=y
CONFIG_KSU_SUSFS_OPEN_REDIRECT=y
CONFIG_KSU_SUSFS_SUS_SU=y
CONFIG_KSU_SUSFS_HAS_MAGIC_MOUNT=y""" >> "$BASE_DIR"/kernel/arch/"$ARCH"/configs/"$KERN_DEFCONFIG"
}

function do_kernel(){
	mkdir -p "$BASE_DIR"/Logs

	cd "$BASE_DIR"/kernel
	if [[ $(uname -m) == "aarch64" ]]; then
		rm tools/build/cpio
		ln -sf $(which cpio) tools/build/cpio
	fi
	# 🕵️ Read LOCAL_VERSION line from defconfig
	local_version_line=$(grep '^CONFIG_LOCALVERSION=' "$BASE_DIR"/kernel/arch/"$ARCH"/configs/"$KERN_DEFCONFIG")

	# ✅ Check if it's set
	if [[ -n "$local_version_line" ]]; then
		# Extract the value (removing quotes)
		current_local_version=$(echo "$local_version_line" | cut -d '=' -f2 | tr -d '"')
	fi

	git config --local user.name "$KBUILD_BUILD_USER"
	git config --local user.email "$KBUILD_BUILD_USER@example.com"

	if [[ "$B_TYPE" == "ksu" ]]; then
		git am --3way "$BASE_DIR"/patches/0001-KernelSU-Patch.patch || { echo "Patch application failed!"; exit 1; }
		write_ksu_config
		if [[ -n "$local_version_line" ]]; then
			export LOCAL_VERSION="$current_local_version"-"#"
		else
			export LOCAL_VERSION="-$KERNEL_NAME-#"
		fi
	elif [[ "$B_TYPE" == "susfs" ]]; then
		git am --3way "$BASE_DIR"/patches/0001-KernelSU-Patch.patch || { echo "Patch application failed!"; exit 1; }
		git am --3way "$BASE_DIR"/patches/0002-Susfs-Patch.patch || { echo "Patch application failed!"; exit 1; }
		write_susfs_config
		if [[ -n "$local_version_line" ]]; then
			export LOCAL_VERSION="$current_local_version"-"ඞ"
		else
			export LOCAL_VERSION="-$KERNEL_NAME-ඞ"
		fi
	else
		if [[ -z "$local_version_line" ]]; then
			export LOCAL_VERSION="-$KERNEL_NAME"
		fi
	fi
	make O=../out CC=clang CXX=clang++ CROSS_COMPILE=aarch64-linux-gnu- CROSS_COMPILE_ARM32=arm-linux-gnueabi- CLANG_TRIPLE=aarch64-linux-gnu- LD=ld.lld LLVM=1 "$KERN_DEFCONFIG" || { echo "Defconfig failed!"; exit 1; }
	make O=../out CC=clang CXX=clang++ CROSS_COMPILE=aarch64-linux-gnu- CROSS_COMPILE_ARM32=arm-linux-gnueabi- CLANG_TRIPLE=aarch64-linux-gnu- LD=ld.lld LLVM=1 -j"$CORES"  > >(tee ../Logs/stdout.log) 2> >(tee ../Logs/stderr.log) || { echo "Kernel build failed!"; exit 1; }
}

function do_cleanup(){
	rm -rf "$BASE_DIR"/out
}

function do_anykernel(){
	if [[ -e "$KERN_IMG" ]]; then
		echo "Compressing output..."
		cp "$KERN_IMG" "$ZIP_DIR"/Image.gz
		cp "$DTB_PATH" "$ZIP_DIR"/dtb
		cd "$ZIP_DIR"
		if [[ "$B_TYPE" == "susfs" ]]; then
			sed -i "s#kernel.string=#kernel.string=$KERNEL_NAME kernel rksu+susfs for $DEVICE#g" anykernel.sh
		elif [[ "$B_TYPE" == "ksu" ]]; then
			sed -i "s#kernel.string=#kernel.string=$KERNEL_NAME kernel rksu for $DEVICE#g" anykernel.sh
		else
			sed -i "s#kernel.string=#kernel.string=$KERNEL_NAME kernel for $DEVICE#g" anykernel.sh
		fi
		zip -r "$ZIP_NAME".zip .
		mkdir -p "$BASE_DIR"/dist
		mv "$ZIP_NAME".zip "$BASE_DIR"/dist
	else
		return 1
	fi
}

function do_release() {
    # Upload to GitHub Releases using GitHub CLI
    file_name="$ZIP_NAME".zip

    TAG="$DEVICE"-"$GITHUB_RUN_ID"
    ASSET="$BASE_DIR/dist/$file_name"
    REPO="$GITHUB_REPOSITORY"
    DEVICE_TITLE="${DEVICE^}"
    TITLE="$DEVICE_TITLE ($(env TZ='Asia/Jakarta' date +%Y%m%d)) ($GITHUB_RUN_ID)"
    NOTES="""$KERNEL_NAME Kernel
Device: $DEVICE_TITLE
Commit hash: $(git -C $BASE_DIR/kernel rev-parse HEAD)
Build date: $(env TZ='Asia/Jakarta' date +%Y%m%d)
Workflows id: $GITHUB_RUN_ID"""

    # Check if release exists
    if gh release view "$TAG" --repo "$REPO" &>/dev/null; then
        echo "Release $TAG exists, uploading asset..."
        gh release upload "$TAG" "$ASSET" --repo "$REPO" --clobber
    else
        echo "Release $TAG does not exist, creating release and uploading asset..."
        gh release create "$TAG" "$ASSET" \
            --title "$TITLE" \
            --notes "$NOTES" \
            --target "$GITHUB_REF_NAME" \
            --repo "$REPO"
    fi
    echo "Released successfully."
}

function do_all(){
	do_clang
	do_kernel
	do_anykernel
	do_cleanup
	do_kernel
	do_anykernel
	do_release
}

parse_parameters "$@"
do_"${action:=all}"
