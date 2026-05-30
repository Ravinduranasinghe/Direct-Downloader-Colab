import os, time, zipfile, shutil, subprocess
from urllib.parse import urlparse, unquote
from google.colab import drive, files
import requests
from tqdm.notebook import tqdm

# ============================================================
#  CELL 1 — Setup
# ============================================================
def setup():
    print("🔧 Checking tools...")
    import importlib
    for pkg in ['requests', 'tqdm']:
        if importlib.util.find_spec(pkg):
            print(f"  ✅ {pkg} available")
        else:
            print(f"  ⚙️  Installing {pkg}...")
            subprocess.run(['pip', 'install', '-q', pkg], check=True)
    print("✅ Setup complete.\n")

setup()

# ============================================================
#  CONFIGURATION — edit if needed
# ============================================================
GDRIVE_FOLDER    = "Downloads"           # folder inside your Google Drive root
TEMP_DIR         = "/content/temp_work"  # scratch space in Colab
DELAY_BETWEEN    = 2                     # seconds to wait between downloads (be polite)

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
#  SESSION — mimics a real browser, handles cookies automatically
# ============================================================
session = requests.Session()
session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate",
    "Connection":      "keep-alive",
})

# ============================================================
#  HELPERS
# ============================================================
def get_filename_from_url(url):
    """Decode and extract a clean filename from a URL."""
    path = urlparse(url).path
    name = unquote(path.split('/')[-1])
    return name or "downloaded_file"


def download_file(url, dest_dir):
    """
    Download using a requests session that:
    - Sends real browser headers
    - Carries cookies across requests (some servers need a page visit first)
    - Shows a progress bar
    """
    filename = get_filename_from_url(url)
    dest     = os.path.join(dest_dir, filename)

    if os.path.exists(dest):
        print(f"  ⏭️  Already in temp: {filename}")
        return dest

    # Visit the item page first to pick up any session cookies
    item_page = url.split('/bitstream/')[0] + '/bitstream/' + url.split('/bitstream/')[1].split('?')[0]
    try:
        session.get(item_page.rsplit('/', 1)[0], timeout=15)  # visit parent page
    except Exception:
        pass  # best-effort; continue even if page visit fails

    print(f"  ⬇️  Downloading: {filename}")
    resp = session.get(url, stream=True, timeout=60)

    if resp.status_code != 200:
        raise RuntimeError(f"HTTP {resp.status_code} for {url}")

    total = int(resp.headers.get('content-length', 0))
    with open(dest, 'wb') as f, tqdm(
        total=total, unit='B', unit_scale=True,
        unit_divisor=1024, desc=f"  {filename[:40]}",
        leave=False
    ) as bar:
        for chunk in resp.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)
                bar.update(len(chunk))

    # Sanity check — if file is tiny it's probably an error page
    size = os.path.getsize(dest)
    if size < 1024:
        os.remove(dest)
        raise RuntimeError(f"Downloaded file too small ({size} bytes) — likely an error page")

    print(f"  ✅ Downloaded: {filename} ({size/1024/1024:.1f} MB)")
    return dest


def is_zip(path):
    return path.lower().endswith('.zip')


def extract_zip(zip_path, output_dir):
    print(f"  📦 Extracting: {os.path.basename(zip_path)}")
    with zipfile.ZipFile(zip_path, 'r') as zf:
        zf.extractall(output_dir)
    print(f"  ✅ Extracted to: Drive/{GDRIVE_FOLDER}/")


def copy_to_drive(src_path, output_dir):
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

for i, url in enumerate(urls, 1):
    print(f"\n{'='*60}")
    print(f"[{i}/{len(urls)}] {url}")
    print('='*60)

    filename = get_filename_from_url(url)

    if filename in archived:
        print(f"  ⏭️  Skipping (archived): {filename}")
        continue

    try:
        local_path = download_file(url, TEMP_DIR)

        if is_zip(local_path):
            folder_name = os.path.splitext(filename)[0]
            output_dir  = os.path.join(save_path, folder_name)
            os.makedirs(output_dir, exist_ok=True)
            extract_zip(local_path, output_dir)
        else:
            copy_to_drive(local_path, save_path)

        archive_add(filename)
        archived.add(filename)
        total_done += 1

        os.remove(local_path)
        print(f"  🗑️  Temp file cleaned up.")

        # Polite delay between requests
        if i < len(urls):
            time.sleep(DELAY_BETWEEN)

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
print("  2. Delete the line:  file filename.pdf")
print("  3. Save and re-run")
