import os
import requests
import sys

def load_config(cfg_path="config.sh"):
    """Load exports from config.sh into os.environ and return a dict of values."""
    loaded = {}
    try:
        with open(cfg_path, "r", encoding="utf-8") as config_file:
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
                    loaded[key] = value
    except FileNotFoundError:
        pass
    return loaded

def write_config():
    load_config()

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

def update_localversion():
    load_config()
    KERN_DEFCONFIG = os.environ.get('KERN_DEFCONFIG', None)
    DEFCONFIG_PATH = os.path.join(os.getcwd(), "kernel", "arch", os.environ.get('ARCH', ''), "configs", KERN_DEFCONFIG)
    build_type = os.environ.get('B_TYPE', 'normal')
    localversion_found = False
    # Rewrite the file with updated localversion
    with open(DEFCONFIG_PATH, "r", encoding="utf-8") as defconfig_file:
        lines = defconfig_file.readlines()
    with open(DEFCONFIG_PATH, "w", encoding="utf-8") as defconfig_file:
        for line in lines:
            if (
                line.strip().startswith("CONFIG_LOCALVERSION")
                and not (
                    line.strip().startswith("CONFIG_LOCALVERSION_AUTO")
                    or line.strip().startswith("# CONFIG_LOCALVERSION_AUTO")
                    or line.strip().startswith("CONFIG_LOCALVERSION_EXTEND")
                    or line.strip().startswith("# CONFIG_LOCALVERSION_EXTEND")
                )
            ):
                old_localversion = line.strip().split("=", 1)[1].strip().strip('"').strip("'")
                if build_type == 'ksu':
                    new_localversion = old_localversion + '-#'
                elif build_type == 'susfs':
                    new_localversion = old_localversion + '-ඞ'
                else:
                    new_localversion = old_localversion
                defconfig_file.write(f'CONFIG_LOCALVERSION="{new_localversion}"\n')
                localversion_found = True
            elif (
                line.strip().startswith("# CONFIG_LOCALVERSION")
                and not (
                    line.strip().startswith("CONFIG_LOCALVERSION_AUTO")
                    or line.strip().startswith("# CONFIG_LOCALVERSION_AUTO")
                    or line.strip().startswith("CONFIG_LOCALVERSION_EXTEND")
                    or line.strip().startswith("# CONFIG_LOCALVERSION_EXTEND")
                )
            ):
                if build_type == 'ksu':
                    new_localversion = os.environ.get('KERNEL_NAME') + '-#' if os.environ.get('KERNEL_NAME') else '#'
                elif build_type == 'susfs':
                    new_localversion = os.environ.get('KERNEL_NAME') + '-ඞ' if os.environ.get('KERNEL_NAME') else 'ඞ'
                else:
                    new_localversion = os.environ.get('KERNEL_NAME') if os.environ.get('KERNEL_NAME') else ''
                if new_localversion:
                    defconfig_file.write(f'CONFIG_LOCALVERSION="-{new_localversion}"\n')
                else:
                    defconfig_file.write(line)
                localversion_found = True
            else:
                defconfig_file.write(line)
    if not localversion_found:
        with open(DEFCONFIG_PATH, "a", encoding="utf-8") as defconfig_file:
            if build_type == 'ksu':
                new_localversion = os.environ.get('KERNEL_NAME') + '-#' if os.environ.get('KERNEL_NAME') else '#'
            elif build_type == 'susfs':
                new_localversion = os.environ.get('KERNEL_NAME') + '-ඞ' if os.environ.get('KERNEL_NAME') else 'ඞ'
            else:
                new_localversion = os.environ.get('KERNEL_NAME') if os.environ.get('KERNEL_NAME') else ''
            if new_localversion:
                defconfig_file.write(f'\nCONFIG_LOCALVERSION="-{new_localversion}"\n')
    print(f"Localversion updated to -{new_localversion} in {DEFCONFIG_PATH}")

def append_config(config_name):
    load_config()
    KERN_DEFCONFIG = os.environ.get('KERN_DEFCONFIG', None)
    DEFCONFIG_PATH = os.path.join(os.getcwd(), "kernel", "arch", os.environ.get('ARCH', ''), "configs", KERN_DEFCONFIG)
    if config_name == 'ksu':
        with open(DEFCONFIG_PATH, "a", encoding="utf-8") as defconfig_file:
            defconfig_file.write('\n# NoMount\nCONFIG_NOMOUNT=y\n\n# ReSukiSU\nCONFIG_KERNELSU=y\nCONFIG_KSU_MANUAL_HOOK=y\nCONFIG_NOMOUNT=y\n')
    elif config_name == 'susfs':
        with open(DEFCONFIG_PATH, "a", encoding="utf-8") as defconfig_file:
            defconfig_file.write('\n# NoMount\nCONFIG_NOMOUNT=y\n\n# ReSukiSU\nCONFIG_KERNELSU=y\nCONFIG_KSU_SUSFS=y\nCONFIG_NOMOUNT=y\n')
    elif config_name == 'droidspaces':
        with open(DEFCONFIG_PATH, "a", encoding="utf-8") as defconfig_file:
            with open(os.path.join(os.getcwd(), "droidspaces_config"), 'r', encoding='utf-8') as f:
                content = f.read()
                defconfig_file.write('\n' + content)
    elif config_name == 'basebandguard':
        with open(DEFCONFIG_PATH, "a", encoding="utf-8") as defconfig_file:
            defconfig_file.write('\n# Baseband-Guard\nCONFIG_LSM="lockdown,yama,loadpin,safesetid,integrity,selinux,smack,tomoyo,apparmor,bpf,baseband_guard"\nCONFIG_BBG=y')

def upload(file_name, url):
    load_config()
    file_path = os.path.join(os.environ.get('BASE_DIR'), 'dist', file_name)
    files = {
        'file': open(file_path, 'rb'),
    }
    try:
        response = requests.post(url, files=files)
        if response.status_code == 200:
            print(f"File {file_name} uploaded successfully.")
        else:
            print(f"Failed to upload {file_name}. Status code: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"An error occurred while uploading {file_name}: {e}")

def show_help():
    print(f"Usage: python {os.path.basename(__file__)} <argument>")
    print("")
    print("Available arguments:")
    print("  write_config               - Setup configuration.")
    print("  update_localversion        - Update kernel localversion.")
    print("  append_config <ksu/susfs>  - Write ksu/susfs config to defconfig.")
    print("  upload <filename> <url>    - Upload file to given url.")
    print("  help                       - Show help.")

def main():
    if len(sys.argv) < 2:
        print("No arguments provided.")
        print("")
        show_help()
        return
    cmd = sys.argv[1]
    if cmd == "write_config":
        write_config()
    elif cmd == "update_localversion":
        update_localversion()
    elif cmd == "append_config":
        if len(sys.argv) < 3:
            print("Please provide a config name to append.")
            return
        config_name = sys.argv[2]
        append_config(config_name)
    elif cmd == "upload":
        if len(sys.argv) < 4:
            print("Please provide a file name and upload URL.")
            return
        file_name = sys.argv[2]
        url = sys.argv[3]
        upload(file_name, url)
    elif cmd == "help":
        show_help()
    else:
        print(f"Unknown command: {cmd}")
        show_help()

main()
