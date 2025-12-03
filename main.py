import os
import sys

def write_config():
    # Load existing exports from config.sh into environment
    with open("config.sh", "r", encoding="utf-8") as config_file:
        for line in config_file:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[len("export "):]
            if "=" in line:
                key, value = line.split("=", 1)
                value = value.strip().strip('"').strip("'")
                os.environ[key] = value

    BASE_DIR = os.getcwd()
    ARCH = os.environ.get('ARCH', None)
    KERNEL_IMG = os.environ.get('KERNEL_IMG', None)
    KERNEL_DTB = os.environ.get('KERNEL_DTB', None)
    BUILD_TYPE = os.environ.get('BUILD_TYPE', None)
    KERNEL_IMG = f"{BASE_DIR}/out/arch/{ARCH}/boot/{KERNEL_IMG}" if ARCH and KERNEL_IMG else None
    KERNEL_DEFCONFIG = os.environ.get('KERNEL_DEFCONFIG', None)
    DTB_PATH = f"{BASE_DIR}/out/arch/{ARCH}/boot/dts/{KERNEL_DTB}" if ARCH and KERNEL_DTB else None

    defconfig = {}
    if ARCH and KERNEL_DEFCONFIG:
        defconfig_path = os.path.join(BASE_DIR, "kernel", "arch", ARCH, "configs", KERNEL_DEFCONFIG)
        if os.path.exists(defconfig_path):
            with open(defconfig_path, "r", encoding="utf-8") as defconfig_file:
                for line in defconfig_file:
                    line = line.strip()
                    if line.startswith("# CONFIG_") and "is not set" in line:
                        continue
                    if line.startswith("CONFIG_") and "=" in line:
                        key, value = line.split("=", 1)
                        defconfig[key] = value

    DEVICE = None
    overlay_key = 'CONFIG_BUILD_ARM64_DTB_OVERLAY_IMAGE_NAMES'
    if overlay_key in defconfig and defconfig[overlay_key]:
        DEVICE = defconfig[overlay_key].replace('mediatek/', '').strip().strip('"').strip("'")

    DTBO_PATH = f"{BASE_DIR}/out/arch/{ARCH}/boot/dts/mediatek/{DEVICE}.dtbo" if DEVICE else None

    print("New configuration:")
    print(f"BASE_DIR={BASE_DIR}")
    print(f"KERNEL_IMG={KERNEL_IMG}")
    print(f"DEVICE={DEVICE}")
    print(f"BUILD_TYPE={BUILD_TYPE}")
    print(f"KERNEL_DEFCONFIG={KERNEL_DEFCONFIG}")
    print(f"DTB_PATH={DTB_PATH}")
    print(f"DTBO_PATH={DTBO_PATH}")

    NEW_CONFIG = f"""export B_TYPE="{BUILD_TYPE}"
export DEVICE="{DEVICE}"
export KERN_IMG="{KERNEL_IMG}"
export DTB_PATH="{DTB_PATH}"
export DTBO_PATH="{DTBO_PATH}"
export KERN_DEFCONFIG="{KERNEL_DEFCONFIG}"
    """

    # Replace the placeholder "# Reserved" in config.sh with NEW_CONFIG
    cfg_path = os.path.join(BASE_DIR, "config.sh")
    with open(cfg_path, "r", encoding="utf-8") as f:
        content = f.read()

    base_dir_placeholder = 'export BASE_DIR="$(pwd)"'
    if base_dir_placeholder in content:
        content = content.replace(base_dir_placeholder, f'export BASE_DIR="{BASE_DIR}"')
    placeholder = "# Reserved"
    if placeholder in content:
        content = content.replace(placeholder, NEW_CONFIG.rstrip())
    else:
        # append if placeholder not found
        content += "\n" + NEW_CONFIG

    with open(cfg_path, "w", encoding="utf-8") as f:
        f.write(content)

    print("config.sh updated.")

def update_localversion(new_localversion):
    # Load existing exports from config.sh into environment
    with open("config.sh", "r", encoding="utf-8") as config_file:
        for line in config_file:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[len("export "):]
            if "=" in line:
                key, value = line.split("=", 1)
                value = value.strip().strip('"').strip("'")
                os.environ[key] = value
    KERN_DEFCONFIG = os.environ.get('KERN_DEFCONFIG', None)
    DEFCONFIG_PATH = os.path.join(os.getcwd(), "kernel", "arch", os.environ.get('ARCH', ''), "configs", KERN_DEFCONFIG)
    localversion_found = False
    # Rewrite the file with updated localversion
    with open(DEFCONFIG_PATH, "r", encoding="utf-8") as defconfig_file:
        lines = defconfig_file.readlines()
    with open(DEFCONFIG_PATH, "w", encoding="utf-8") as defconfig_file:
        for line in lines:
            if (
                (
                    line.strip().startswith("# CONFIG_LOCALVERSION")
                    or line.strip().startswith("CONFIG_LOCALVERSION")
                ) and not (
                    line.strip().startswith("CONFIG_LOCALVERSION_AUTO")
                    or line.strip().startswith("# CONFIG_LOCALVERSION_AUTO")
                    or line.strip().startswith("CONFIG_LOCALVERSION_EXTEND")
                    or line.strip().startswith("# CONFIG_LOCALVERSION_EXTEND")
                )
            ):
                defconfig_file.write(f'CONFIG_LOCALVERSION="{new_localversion}"\n')
                localversion_found = True
            else:
                defconfig_file.write(line)
    if not localversion_found:
        with open(DEFCONFIG_PATH, "a", encoding="utf-8") as defconfig_file:
            defconfig_file.write(f'\nCONFIG_LOCALVERSION="{new_localversion}"\n')
    print(f"Localversion updated to {new_localversion} in {DEFCONFIG_PATH}")

def append_config(config_name):
    # Load existing exports from config.sh into environment
    with open("config.sh", "r", encoding="utf-8") as config_file:
        for line in config_file:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[len("export "):]
            if "=" in line:
                key, value = line.split("=", 1)
                value = value.strip().strip('"').strip("'")
                os.environ[key] = value
    KERN_DEFCONFIG = os.environ.get('KERN_DEFCONFIG', None)
    DEFCONFIG_PATH = os.path.join(os.getcwd(), "kernel", "arch", os.environ.get('ARCH', ''), "configs", KERN_DEFCONFIG)
    if config_name == 'ksu':
        with open(DEFCONFIG_PATH, "a", encoding="utf-8") as defconfig_file:
            defconfig_file.write('\n# KernelSU\nCONFIG_KERNELSU=y\nCONFIG_KSU_MANUAL_HOOK=y\n')
    elif config_name == 'susfs':
        with open(DEFCONFIG_PATH, "a", encoding="utf-8") as defconfig_file:
            defconfig_file.write('\n# KernelSU - SusFs\nCONFIG_KSU_SUSFS=y\nCONFIG_KSU_SUSFS_HAS_MAGIC_MOUNT=y\nCONFIG_KSU_SUSFS_SUS_PATH=y\nCONFIG_KSU_SUSFS_SUS_MOUNT=y\nCONFIG_KSU_SUSFS_SUS_KSTAT=y\nCONFIG_KSU_SUSFS_TRY_UMOUNT=y\nCONFIG_KSU_SUSFS_SPOOF_UNAME=y\nCONFIG_KSU_SUSFS_ENABLE_LOG=y\nCONFIG_KSU_SUSFS_OPEN_REDIRECT=y\n')

def main():
    if len(sys.argv) < 2:
        print("No arguments provided.")
        return

    cmd = sys.argv[1]
    if cmd == "write_config":
        write_config()
    elif cmd == "update_localversion":
        if len(sys.argv) < 3:
            print("Please provide a new localversion string.")
            return
        new_localversion = sys.argv[2]
        update_localversion(new_localversion)
    elif cmd == "append_config":
        if len(sys.argv) < 3:
            print("Please provide a config name to append.")
            return
        config_name = sys.argv[2]
        append_config(config_name)
    else:
        print(f"Unknown command: {cmd}")

main()
