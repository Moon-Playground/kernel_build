#!/bin/bash

source config.sh

function parse_parameters() {
    while (($#)); do
        case $1 in
            all | clang | kernel | anykernel | cleanup | write_config | switch_to_ksu ) action=$1 ;;
            *) exit 33 ;;
        esac
        shift
    done
}

function do_clang(){
	wget "$CLANG_URL" > /dev/null || { echo "Download failed!"; exit 1; }
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
	DEVICE=$(echo "$DEFCONFIG" | cut -d'-' -f1)
	sed -i "s/export DEVICE/export DEVICE=\"$DEVICE\"/g" "$BASE_DIR"/config.sh
	sed -i "s/export IS_SUSFS/export IS_SUSFS=$IS_SUSFS/g" "$BASE_DIR"/config.sh
	echo "export KERN_IMG=$BASE_DIR/out/arch/$ARCH/boot/$KERNEL_IMG" >> "$BASE_DIR"/config.sh
	echo "export DTB_PATH=$BASE_DIR/out/arch/$ARCH/boot/dts/$KERNEL_DTB" >> "$BASE_DIR"/config.sh
	echo "export DEFCONFIG=$DEFCONFIG" >> "$BASE_DIR"/config.sh
}

function do_kernel(){
	mkdir -p "$BASE_DIR"/Logs

	cd "$BASE_DIR"/kernel
	make O=../out CC=clang CXX=clang++ CROSS_COMPILE=aarch64-linux-gnu- CROSS_COMPILE_ARM32=arm-linux-gnueabi- CLANG_TRIPLE=aarch64-linux-gnu- LD=ld.lld LLVM=1 "$DEFCONFIG"_defconfig || { echo "Defconfig failed!"; exit 1; }
	make O=../out CC=clang CXX=clang++ CROSS_COMPILE=aarch64-linux-gnu- CROSS_COMPILE_ARM32=arm-linux-gnueabi- CLANG_TRIPLE=aarch64-linux-gnu- LD=ld.lld LLVM=1 -j"$CORES"  > >(tee ../Logs/stdout.log) 2> >(tee ../Logs/stderr.log) || { echo "Kernel build failed!"; exit 1; }
}

function do_cleanup(){
	rm -rf "$BASE_DIR"/out
}

function do_switch_to_ksu(){
	git -C "$BASE_DIR"/kernel/KernelSU checkout main
	sed -i 's/IS_SUSFS=1/IS_SUSFS=0/g' "$BASE_DIR"/config.sh
	sed -i 's/rksu\+susfs/rksu/g' "$BASE_DIR"/AnyKernel/anykernel.sh
}

function do_anykernel(){
	if [ -e "$KERN_IMG" ]; then
		echo "Compressing output..."
		cp "$KERN_IMG" "$ZIP_DIR"/Image.gz
		cp "$DTB_PATH" "$ZIP_DIR"/dtb
		cd "$ZIP_DIR"
		zip -r "$ZIP_NAME".zip .
		mkdir -p "$BASE_DIR"/dist
		mv "$ZIP_NAME".zip "$BASE_DIR"/dist
		upload=$(curl -X POST -F "file=@$BASE_DIR/dist/$ZIP_NAME.zip" https://temp.wulan17.dev/api/v1/upload)
		echo "Download link: $(echo "$upload" | jq -r '.direct_link')"
	else
		return 1
	fi
}

function do_all(){
	do_clang
	do_kernel
	do_anykernel
	do_cleanup
	do_switch_to_ksu
	do_kernel
	do_anykernel
}

parse_parameters "$@"
do_"${action:=all}"
