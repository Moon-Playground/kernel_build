import asyncio
import json
import logging
import niquests
import os
import sys

from git import Repo
from pathlib import Path
from pyrogram import Client
from pyrogram.types import InputMediaDocument

logging.getLogger("niquests").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

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

    import datetime, zoneinfo
    KERNEL_NAME = os.environ.get('KERNEL_NAME', 'kernel')
    GITHUB_RUN_ID = os.environ.get('GITHUB_RUN_ID', '')
    date_str = datetime.datetime.now(zoneinfo.ZoneInfo('Asia/Jakarta')).strftime('%Y%m%d')
    ZIP_NAME = f"{GITHUB_RUN_ID}-{KERNEL_NAME}-kernel-{DEVICE}"
    if BUILD_TYPE == 'ksu':
        ZIP_NAME += f"-bakasu"
    elif BUILD_TYPE == 'susfs':
        ZIP_NAME += f"-bakasu-susfs"
    ZIP_NAME += f"-spoof"
    ZIP_NAME += f"-{date_str}"

    print("New configuration:")
    print(f"BASE_DIR={BASE_DIR}")
    print(f"KERNEL_IMG={KERNEL_IMG}")
    print(f"DEVICE={DEVICE}")
    print(f"BUILD_TYPE={BUILD_TYPE}")
    print(f"KERNEL_DEFCONFIG={KERNEL_DEFCONFIG}")
    print(f"DTB_PATH={DTB_PATH}")
    print(f"DTBO_PATH={DTBO_PATH}")
    print(f"ZIP_NAME={ZIP_NAME}")

    NEW_CONFIG = f'''export B_TYPE="{BUILD_TYPE}"
export DEVICE="{DEVICE}"
export KERN_IMG="{KERNEL_IMG}"
export DTB_PATH="{DTB_PATH}"
export DTBO_PATH="{DTBO_PATH}"
export KERN_DEFCONFIG="{KERNEL_DEFCONFIG}"
export ZIP_NAME="{ZIP_NAME}"'''

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
                    new_localversion = old_localversion + '-#s'
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
                    new_localversion = os.environ.get('KERNEL_NAME') + '-#s' if os.environ.get('KERNEL_NAME') else '#s'
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
                new_localversion = os.environ.get('KERNEL_NAME') + '-#s' if os.environ.get('KERNEL_NAME') else '#s'
            else:
                new_localversion = os.environ.get('KERNEL_NAME') if os.environ.get('KERNEL_NAME') else ''
            if new_localversion:
                defconfig_file.write(f'\nCONFIG_LOCALVERSION="-{new_localversion}"\n')
    print(f"Localversion updated to -{new_localversion} in {DEFCONFIG_PATH}")

def append_config(config_name, arch=None, defconfig=None):
    load_config()
    KERN_DEFCONFIG = os.environ.get('KERN_DEFCONFIG', defconfig)
    DEFCONFIG_PATH = os.path.join(os.getcwd(), "kernel", "arch", os.environ.get('ARCH', arch), "configs", KERN_DEFCONFIG)
    if config_name == 'ksu':
        with open(DEFCONFIG_PATH, "a", encoding="utf-8") as defconfig_file:
            defconfig_file.write('\n# NoMount\nCONFIG_NOMOUNT=y\n\n# BakaSU\nCONFIG_KERNELSU=y\nCONFIG_KSU_MANUAL_HOOK=y\n')
    elif config_name == 'susfs':
        with open(DEFCONFIG_PATH, "a", encoding="utf-8") as defconfig_file:
            defconfig_file.write('\n# NoMount\nCONFIG_NOMOUNT=y\n\n# BakaSU\nCONFIG_KERNELSU=y\nCONFIG_KSU_SUSFS=y\n')
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
        response = niquests.post(url, files=files)
        if response.status_code == 200:
            print(f"File {file_name} uploaded successfully.")
        else:
            print(f"Failed to upload {file_name}. Status code: {response.status_code}")
    except niquests.exceptions.RequestException as e:
        print(f"An error occurred while uploading {file_name}: {e}")

def get_kernel_info(kernel_path):
    kernel_info = {}
    version = None
    patchlevel = None
    sublevel = None
    cip_version = None
    st_version = None
    with open(kernel_path + "/Makefile", 'r') as f:
        for line in f.read().split("\n"):
            if line.startswith("VERSION"):
                text = line.split()
                version = text[2]
            elif line.startswith("PATCHLEVEL"):
                text = line.split()
                patchlevel = text[2]
            elif line.startswith("SUBLEVEL"):
                text = line.split()
                sublevel = text[2]
            if version and patchlevel and sublevel:
                break
    if Path(kernel_path + "/localversion-cip").is_file():
        with open(kernel_path + "/localversion-cip", 'r') as f:
            cip_version = (f.read().split("\n")[0]).strip()
        with open(kernel_path + "/localversion-st", 'r') as f:
            st_version = (f.read().split("\n")[0]).strip()
    kernel_version = f"{version}.{patchlevel}.{sublevel}"
    if cip_version:
        kernel_version = kernel_version + cip_version + st_version
    kernel_repo = Repo(kernel_path)
    kernel_msg = kernel_repo.head.commit.summary
    kernel_sha = kernel_repo.head.commit.hexsha[:7]
    kernel_info["version"] = kernel_version
    kernel_info["device"] = os.environ.get("DEVICE")
    kernel_info["name"] = os.environ.get('KERNEL_NAME')
    kernel_info["repo"] = os.environ.get("KERNEL_REPO")
    kernel_info["branch"] = os.environ.get("KERNEL_BRANCH")
    kernel_info["kernel_msg"] = kernel_msg
    kernel_info["kernel_sha"] = kernel_sha
    kernel_info["compiler"] = os.environ.get("COMPILER")
    with open(os.environ.get("BASE_DIR") + "/dist/kernel_info.json", 'w') as f:
        f.write(json.dumps(kernel_info))

def get_ksu_info(kernel_path):
    kernel_info = {}
    with open(os.environ.get("BASE_DIR") + "/dist/kernel_info.json", 'r') as f:
        kernel_info = json.loads(f.read())
    ksu_rev = None
    ksu_version = None
    susfs_version = None
    nomount_version = None
    if Path(kernel_path + "/KernelSU").is_dir():
        repo = Repo(kernel_path + "/KernelSU")
        ksu_rev = int(repo.git.rev_list("--count", "HEAD"))
    ksu_version = 30000 + ksu_rev + 700
    with open(kernel_path + "/include/linux/susfs.h", 'r') as f:
        for line in f.read().split("\n"):
            if line.startswith("#define SUSFS_VERSION"):
                text = line.split()
                susfs_version = text[2]
    with open(kernel_path + '/NoMount/module/module.prop', 'r') as f:
        for line in f.read().split("\n"):
            if line.startswith("version="):
                text = line.split("=")
                nomount_version = text[1]
    kernel_info["ksu_version"] = ksu_version
    kernel_info["susfs_version"] = susfs_version.replace('"', '')
    kernel_info["nomount_version"] = nomount_version.replace('"', '')
    with open(os.environ.get("BASE_DIR") + "/dist/kernel_info.json", 'w') as f:
        f.write(json.dumps(kernel_info))

async def upload_tg(dir_path, prerelease=False):
    client = Client("mahiru", session_string=os.environ.get("TELEGRAM_SESSION"), no_updates=True)
    chat_id = os.environ.get("TELEGRAM_CHAT")
    try:
        chat_id = int(chat_id)
    except Exception:
        pass
    files = []
    path = Path(dir_path)
    for f in path.iterdir():
        if f.is_file() and f.name.endswith(".zip"):
            files.append(
                InputMediaDocument(
                    media=f
                )
            )
    kernel_info = None
    with open(dir_path + "/kernel_info.json", 'r') as f:
        kernel_info = json.loads(f.read())
    caption = ""
    if prerelease:
        caption += "⚠️ **WARNING: Dev / Experimental Build!**\n"
    script_repo = Repo(os.environ.get("GH_WORKDIR"))
    script_msg = script_repo.head.commit.summary
    caption += f"""
🚀 **New Kernel Build Success!**

🧬 **Kernel Name:** `{kernel_info['name']}`
📱 **Device:** `{kernel_info['device']}`
🏷️ **Version:** `{kernel_info['version']}`

📦 **Repository:** `{kernel_info['repo']}`
🌿 **Branch:** `{kernel_info['branch']}`
💻 **Commit:** <a href='https://github.com/{kernel_info['repo']}/commits/{kernel_info['kernel_sha']}'>{kernel_info['kernel_sha']}: {kernel_info['kernel_msg']}</a>

🔧 **BakaSU:** `{kernel_info['ksu_version']}`
🛡️ **SusFS:** `{kernel_info['susfs_version']}`
📂 **NoMount:** `{kernel_info['nomount_version']}`

🔧 **Script Commit:** <a href='https://github.com/{os.environ.get('GITHUB_ACTOR')}/kernel_build/commit/{os.environ.get('GITHUB_SHA')}'>{os.environ.get('GITHUB_SHA')[:7]}: {script_msg}</a>
⚙️ **Compiler:** `{kernel_info['compiler']}`
🛠️ **Workflow:** <a href='https://github.com/{os.environ.get('GITHUB_REPOSITORY')}/actions/runs/{os.environ.get('GITHUB_RUN_ID')}'>{os.environ.get('GITHUB_RUN_ID')}</a>
    """
    files[-1].caption = caption
    await client.start()
    try:
        _ = await client.send_media_group(chat_id, files)
    except Exception:
        pass
    await client.stop()

def gen_release_body(dir_path):
    kernel_info = None
    with open(dir_path + "/kernel_info.json", 'r') as f:
        kernel_info = json.loads(f.read())
    script_repo = Repo(os.environ.get("GH_WORKDIR"))
    script_msg = script_repo.head.commit.summary
    return f"""### 🚀 Build Information

* **Kernel Name:** `{kernel_info['name']}`
* **Device:** `{kernel_info['device']}`
* **Version:** `{kernel_info['version']}`
* **Repository:** [{kernel_info['repo']}](https://github.com/{kernel_info['repo']})
* **Branch:** `{kernel_info['branch']}`
* **Commit:** [`{kernel_info['kernel_sha']}:{kernel_info['kernel_msg']}`](https://github.com/{kernel_info['repo']}/commit/{kernel_info['kernel_sha']})

### 🔧 Components & Toolchain

* **BakaSU:** `{kernel_info['ksu_version']}`
* **SusFS:** `{kernel_info['susfs_version']}`
* **NoMount:** `{kernel_info['nomount_version']}`
* **Script Commit:** [`{os.environ.get('GITHUB_SHA')[:7]}:{script_msg}`](https://github.com/{os.environ.get('GITHUB_REPOSITORY')}/commit/{os.environ.get('GITHUB_SHA')})
* **Compiler:** `{kernel_info['compiler']}`
* **Workflow:** [`{os.environ.get('GITHUB_RUN_ID')}`](https://github.com/{os.environ.get('GITHUB_REPOSITORY')}/actions/runs/{os.environ.get('GITHUB_RUN_ID')})
    """

async def download_chunk(session: niquests.AsyncSession, url: str, start: int, end: int, chunk_id: int, filename: str):
    """Downloads a specific byte range using Niquests async streaming."""
    headers = {"Range": f"bytes={start}-{end}"}

    # stream=True ensures we stream chunks safely into storage without RAM spikes
    response = await session.get(url, headers=headers, stream=True)
    response.raise_for_status()

    # Open file in r+b to allow concurrent offset writing
    with open(filename, "r+b") as f:
        f.seek(start)
        # Niquests uses response.iter_content instead of aiter_bytes
        for chunk in response.iter_content(chunk_size=1024 * 64):
            f.write(chunk)

    print(f"✓ Chunk {chunk_id} finished ({start}-{end})")

async def download(URL, OUTPUT_FILE, CHUNKS = 16):
    # multiplexed=True forces Niquests to run connections in parallel over HTTP/2 or HTTP/3
    async with niquests.AsyncSession(multiplexed=True) as session:
        # 1. Request headers only to fetch the file size
        response = await session.head(URL)
        if response.headers.get("Accept-Ranges") == "none":
            print("Server does not support split downloads.")
            return
            
        total_size = int(response.headers["Content-Length"])
        print(f"Total file size: {total_size / (1024*1024):.2f} MB. Downloading via Niquests...")

        # 2. Pre-allocate the physical file on disk
        with open(OUTPUT_FILE, "wb") as f:
            f.truncate(total_size)

        # 3. Formulate chunk constraints
        chunk_size = total_size // CHUNKS
        tasks = []
        
        for i in range(CHUNKS):
            start = i * chunk_size
            end = total_size - 1 if i == CHUNKS - 1 else (start + chunk_size - 1)
            
            tasks.append(download_chunk(session, URL, start, end, i + 1, OUTPUT_FILE))

        # 4. Fire them concurrently
        await asyncio.gather(*tasks)
        print("🎉 Niquests parallel download completed successfully!")

def show_help():
    print(f"Usage: python {os.path.basename(__file__)} <argument>")
    print("")
    print("Available arguments:")
    print("  write_config               - Setup configuration.")
    print("  update_localversion        - Update kernel localversion.")
    print("  append_config <name>       - Write <name> config to defconfig.")
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
    elif cmd == "kernel_info":
        if len(sys.argv) < 3:
            print("Please provide a path.")
            return
        kernel_path = sys.argv[2]
        get_kernel_info(kernel_path)
    elif cmd == "ksu_info":
        if len(sys.argv) < 3:
            print("Please provide a path.")
            return
        kernel_path = sys.argv[2]
        get_ksu_info(kernel_path)
    elif cmd == "download":
        if len(sys.argv) < 4:
            print("Please provide a url and a output file.")
            return
        url = sys.argv[2]
        output = sys.argv[3]
        asyncio.run(download(url, output))
    elif cmd == "upload":
        if len(sys.argv) < 4:
            print("Please provide a file name and upload URL.")
            return
        file_name = sys.argv[2]
        url = sys.argv[3]
        upload(file_name, url)
    elif cmd == "release_body":
        if len(sys.argv) < 3:
            print("Please provide a path.")
            return
        dir_path = sys.argv[2]
        print(gen_release_body(dir_path))
    elif cmd == "upload_tg":
        if len(sys.argv) < 3:
            print("Please provide a path.")
            return
        dir_path = sys.argv[2]
        prerelease = False
        if len(sys.argv) > 3 and sys.argv[3] == '--prerelease':
            prerelease = True
        asyncio.run(upload_tg(dir_path, prerelease))
    elif cmd == "help":
        show_help()
    else:
        print(f"Unknown command: {cmd}")
        show_help()

main()
