import sys
from pathlib import Path
import shutil

if len(sys.argv) != 2:
    print(f"Usage: {sys.argv[0]} <acutal output file>")
    print("   This will copy output file such that it's picked up as a reference the next time around")
    exit(1)

src = Path(sys.argv[1]).absolute()
base = src.parent.parent.parent
dst = base / "reference" / src.parent.name / src.name
print(f"Copying {src} to {dst}")
while dst.exists():
    response = input("Destination exists. Overwrite? (Y/n)")
    if response in  "nN":
        print("Aborting")
        exit(0)
    if response not in "yY":
        continue # we'll retry asking the user
    break

dst.parent.mkdir(parents=True, exist_ok=True)
shutil.copy(src, dst)
print("Done")