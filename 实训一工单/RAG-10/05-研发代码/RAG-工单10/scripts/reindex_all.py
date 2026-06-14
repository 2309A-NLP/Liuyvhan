from pathlib import Path
import os
import sys
import time


PROJECT_ROOT = Path(__file__).resolve().parent.parent
os.chdir(PROJECT_ROOT)
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Prefer local model files when available.
os.environ.setdefault("HF_HUB_OFFLINE", "1")

print("Loading application container...", flush=True)
from app.core.container import container
from app.core.config import settings


def main() -> None:
    print(f"Project root: {PROJECT_ROOT}", flush=True)
    print(f"Raw data dir: {settings.raw_dir}", flush=True)

    pdf_files = sorted(settings.raw_dir.glob("*.pdf"))
    print(f"Found {len(pdf_files)} PDF file(s).", flush=True)
    for pdf_file in pdf_files:
        print(f"  - {pdf_file.name}", flush=True)

    if not pdf_files:
        print("No PDF files found. Nothing to index.", flush=True)
        return

    print("\nRebuilding index for all PDFs...", flush=True)
    started = time.perf_counter()
    try:
        results = container.rag_service.ingest_all_files(rebuild=True)
    except Exception as exc:
        print(f"Index build failed: {exc}", flush=True)
        raise

    elapsed = round(time.perf_counter() - started, 3)
    print(f"\nIndex build finished in {elapsed}s", flush=True)
    for result in results:
        if result["status"] == "success":
            print(
                f"  OK  {result['file_name']}: "
                f"{result['pages']} pages, {result['chunks']} chunks, "
                f"{result['duration_seconds']}s",
                flush=True,
            )
        else:
            print(
                f"  FAIL {result['file_name']}: {result.get('error', 'unknown error')}",
                flush=True,
            )


if __name__ == "__main__":
    main()
