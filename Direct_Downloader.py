import os, re, subprocess, zipfile, shutil
from google.colab import drive, files

# ============================================================
#  CELL 1 — Setup
# ============================================================
def setup():
    print("🔧 Checking tools...")
    wget = subprocess.run(['wget', '--version'], capture_output=True, text=True)
    print(f"✅ {wget.stdout.splitlines()[0]}")
    print("✅ Setup complete.\n")

setup()

# ============================================================
#  CONFIGURATION — edit if needed
# ============================================================
GDRIVE_FOLDER = "Downloads"           # folder name inside your Google Drive root
TEMP_DIR      = "/content/temp_work"  # scratch space inside Colab

# ============================================================
#  STEP 1 — Provide download URLs
# ============================================================
print("How would you like to provide download URLs?")
print("  1 — Paste links directly")
print("  2 — Upload a .txt file")
print()
choice = input("Enter 1 or 2: ").strip()

urls = []

if choice == "1":
    print()
    print("Paste your URLs below, one per line.")
    print("When done, type END on a new line and press Enter.")
    print()
    while True:
        line = input()
        if line.strip().upper() == "END":
            break
        line = line.strip()
        if line and not line.startswith("#"):
            urls.append(line)

elif choice == "2":
    print()
    print("📂 Upload your .txt file containing one URL per line.")
    uploaded = files.upload()
    if not uploaded:
        raise Exception("No file uploaded.")
    url_file = list(uploaded.keys())[0]
    with open(url_file) as f:
        urls = [line.strip() for line in f if line.strip() and not line.startswith("#")]

else:
    raise Exception("Invalid choice. Please enter 1 or 2.")

if not urls:
    raise Exception("No URLs provided.")

print(f"\n✅ Found {len(urls)} URL(s):\n")
for u in urls:
    print(f"  {u}")
print()

# ============================================================
#  STEP 2 — Mount Google Drive
# ============================================================
if not os.path.exists('/content/drive'):
    drive.mount('/content/drive')
else:
    print("✅ Drive already mounted.")

save_path    = f"/content/drive/MyDrive/{GDRIVE_FOLDER}"
archive_file = f"{save_path}/.download_archive.txt"
os.makedirs(save_path, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)
print(f"📁 Output folder: Drive/{GDRIVE_FOLDER}")

# Load existing archive
archived = set()
if os.path.exists(archive_file):
    with open(archive_file) as f:
        for line in f:
            parts = line.strip().split(None, 1)
            if len(parts) == 2 and parts[0] == 'file':
                archived.add(parts[1])
    print(f"📋 Archive: {len(archived)} file(s) already done (will skip)")
else:
    print("📋 No archive found — starting fresh.")
print()

def archive_add(filename):
    with open(archive_file, 'a', encoding='utf-8') as f:
        f.write(f"file {filename}\n")

# ============================================================
#  HELPERS
# ============================================================
def download_file(url, dest_dir):
    """Download a file with wget, return local path."""
    filename = url.split('/')[-1].split('?')[0]
    dest     = os.path.join(dest_dir, filename)
    if os.path.exists(dest):
        print(f"  ⏭️  Already in temp: {filename}")
        return dest
    print(f"  ⬇️  Downloading: {filename}")
    result = subprocess.run(
        ['wget', '-q', '--show-progress', '-O', dest, url],
        text=True
    )
    if result.returncode != 0:
        raise RuntimeError(f"wget failed for {url}")
    print(f"  ✅ Downloaded: {filename}")
    return dest


def is_zip(path):
    return path.lower().endswith('.zip')


def extract_zip(zip_path, output_dir):
    """Extract zip contents directly into output_dir."""
    print(f"  📦 Extracting: {os.path.basename(zip_path)}")
    with zipfile.ZipFile(zip_path, 'r') as zf:
        zf.extractall(output_dir)
    print(f"  ✅ Extracted to: Drive/{GDRIVE_FOLDER}/")


def copy_to_drive(src_path, output_dir):
    """Copy a non-zip file directly to Drive folder."""
    filename = os.path.basename(src_path)
    dest     = os.path.join(output_dir, filename)
    if os.path.exists(dest):
        print(f"  ⏭️  Already in Drive: {filename}")
        return
    print(f"  📋 Copying to Drive: {filename}")
    shutil.copy2(src_path, dest)
    print(f"  ✅ Copied: {filename}")

# ============================================================
#  STEP 3 — Process each URL
# ============================================================
total_done = 0
empty_trash_cmd = 'rm -rf ~/.local/share/Trash/files/* ~/.local/share/Trash/info/* 2>/dev/null; true'

for i, url in enumerate(urls, 1):
    print(f"\n{'='*60}")
    print(f"[{i}/{len(urls)}] {url}")
    print('='*60)

    filename = url.split('/')[-1].split('?')[0]

    # Check archive
    if filename in archived:
        print(f"  ⏭️  Skipping (archived): {filename}")
        continue

    try:
        # 1) Download
        local_path = download_file(url, TEMP_DIR)

        # 2) If zip → extract, else copy as-is
        if is_zip(local_path):
            # Extract into a subfolder named after the zip
            folder_name = os.path.splitext(filename)[0]
            output_dir  = os.path.join(save_path, folder_name)
            os.makedirs(output_dir, exist_ok=True)
            extract_zip(local_path, output_dir)
        else:
            # Copy directly into the Drive folder
            copy_to_drive(local_path, save_path)

        # 3) Mark as done in archive
        archive_add(filename)
        archived.add(filename)
        total_done += 1

        # 4) Clean up temp file
        os.remove(local_path)
        subprocess.run(empty_trash_cmd, shell=True)
        print(f"  🗑️  Temp file cleaned up.")

    except Exception as e:
        print(f"\n  ❌ Error processing {url}:\n     {e}")
        continue

# ============================================================
#  DONE
# ============================================================
print(f"\n{'='*60}")
print(f"✅ All done! {total_done} file(s) processed.")
print(f"📁 Saved to: Drive/{GDRIVE_FOLDER}/")
print(f"📋 Archive: Drive/{GDRIVE_FOLDER}/.download_archive.txt ({len(archived)} total entries)")
print('='*60)
print()
print("─" * 60)
print("💡 HOW TO RE-RUN")
print("─" * 60)
print("Completed files are recorded in .download_archive.txt.")
print("Re-runs skip them automatically even if deleted from Drive.")
print()
print("To force re-download a specific file:")
print("  1. Open .download_archive.txt in Drive")
print("  2. Delete the line:  file filename.zip")
print("  3. Save and re-run")
