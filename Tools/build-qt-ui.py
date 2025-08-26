from pathlib import Path
from subprocess import run

my_dir = Path(__file__).parent

for ui_file in my_dir.glob("imgCIF_app/ui/*.ui"):
    py_file = ui_file.with_suffix(".py")
    print(f"{ui_file.relative_to(my_dir)} -> {py_file.relative_to(my_dir)}")
    run(['pyside6-uic', '-o', py_file, ui_file], check=True)
