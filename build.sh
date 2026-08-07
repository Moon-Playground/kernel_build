#!/bin/bash

source config.sh

function parse_parameters() {
    while (($#)); do
        case $1 in
            help | clang | kernel | anykernel | cleanup | release ) action=$1 ;;
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

function do_kernel(){
	mkdir -p "$BASE_DIR"/Logs

	if [[ $(uname -m) == "aarch64" ]]; then
		rm kernel/tools/build/cpio
		ln -sf $(which cpio) kernel/tools/build/cpio
	fi

	git -C kernel config --local user.name "$KBUILD_BUILD_USER"
	git -C kernel config --local user.email "$KBUILD_BUILD_USER@example.com"

	if [[ "$B_TYPE" == "ksu" ]]; then
		git -C kernel am --3way "$BASE_DIR"/patches/0001-gale-ReSukiSU-manual-hook.patch || { echo "Patch application failed!"; exit 1; }
		git -C kernel am --3way "$BASE_DIR"/patches/0001-NoMount-Integration.patch || { echo "Patch application failed!"; exit 1; }
		python main.py append_config "ksu"
	elif [[ "$B_TYPE" == "susfs" ]]; then
		git -C kernel am --3way "$BASE_DIR"/patches/0001-gale-ReSukiSU-susfs.patch || { echo "Patch application failed!"; exit 1; }
		git -C kernel am --3way "$BASE_DIR"/patches/0001-NoMount-Integration-susfs.patch || { echo "Patch application failed!"; exit 1; }
		python main.py append_config "susfs"
	fi
	python main.py append_config "droidspaces"
	python main.py update_localversion
	cd "$BASE_DIR"/kernel
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
		if [[ "$SHIP_DTBO" -eq 1 ]];then
			cp "$DTBO_PATH" "$ZIP_DIR"/dtbo.img
		else
			echo "Skipping dtbo.img as SHIP_DTBO is set to 0"
		fi
		cd "$ZIP_DIR"
		if [[ "$B_TYPE" == "susfs" ]]; then
			sed -i "s#kernel.string=#kernel.string=$KERNEL_NAME kernel ReSukiSU+susfs for $DEVICE#g" anykernel.sh
		elif [[ "$B_TYPE" == "ksu" ]]; then
			sed -i "s#kernel.string=#kernel.string=$KERNEL_NAME kernel ReSukiSU for $DEVICE#g" anykernel.sh
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
    TITLE="$DEVICE_TITLE ($(env TZ='UTC' date +%Y%m%d)) ($GITHUB_RUN_ID)"
    NOTES="""$KERNEL_NAME Kernel
Device: $DEVICE_TITLE
Commit hash: $(git -C $BASE_DIR/kernel rev-parse HEAD)
Build date: $(env TZ='UTC' date +%Y%m%d)
Workflows id: [$GITHUB_RUN_ID](https://github.com/$GITHUB_REPOSITORY/actions/runs/$GITHUB_RUN_ID)"""

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
            --repo "$REPO" || gh release upload "$TAG" "$ASSET" --repo "$REPO" --clobber || { echo "Release creation/upload failed!"; exit 1; }
    fi
	if [[ -n $UPLOAD_URL ]];then
		python main.py upload "$file_name" "$UPLOAD_URL"
	fi
    echo "Released successfully."
}

function do_help() {
    echo "Usage: $0 <command>"
    echo
    echo "Available commands:"
    echo "  clang      - Setup Clang toolchain"
    echo "  kernel     - Compile  kernel sources"
    echo "  anykernel  - Package kernel with AnyKernel installer"
    echo "  cleanup    - Remove build artifacts and temporary files"
    echo "  release    - Release package to github"
    echo
    echo "Example:"
    echo "  $0 kernel   # Compile the kernel"
}

parse_parameters "$@"
do_"${action:=help}"
