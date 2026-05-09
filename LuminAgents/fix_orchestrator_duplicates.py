"""
fix_orchestrator_duplicates.py
One-shot repair: removes duplicate/orphaned methods from orchestrator.py
that were introduced during emergency restoration session.

Run from D:\Apps\LuminAgents:
    venv\Scripts\python.exe fix_orchestrator_duplicates.py
"""
import re
import sys
import shutil
from pathlib import Path

SRC = Path("orchestrator.py")

if not SRC.exists():
    print("ERROR: orchestrator.py not found. Run from D:\\Apps\\LuminAgents")
    sys.exit(1)

# Backup first
backup = SRC.with_suffix(".py.bak_fix")
shutil.copy(SRC, backup)
print(f"Backup saved → {backup}")

text = SRC.read_text(encoding="utf-8")
original_len = len(text.splitlines())

# ── Step 1: Fix "No active Task" typo back to lowercase ──────────────────
text = text.replace('return "No active Task", ""', 'return "No active task", ""')

# ── Step 2: Remove the _CLEANUP_MARKER stub ───────────────────────────────
text = text.replace("\n    def _CLEANUP_MARKER(self): pass\n", "\n")

# ── Step 3: Remove orphaned background_discourse body fragments ───────────
# These are code blocks outside any method (indented with 12 spaces) that
# appear between _get_discourse_context and _hard_reset_user.
# Strategy: find the LAST occurrence of _get_discourse_context and keep only
# the first one (ours), then find _hard_reset_user and stitch them together.

# Split on class-level method boundaries (4-space indent "    def ")
# Find positions of key methods
MARKER_BD  = "\n    async def background_discourse(\n"
MARKER_GDC = "\n    def _get_discourse_context(self, user_id: str) -> tuple:\n"
MARKER_HRU = "\n    def _hard_reset_user(self, user_id: str) -> None:\n"

idx_bd_list  = [m.start() for m in re.finditer(re.escape(MARKER_BD),  text)]
idx_gdc_list = [m.start() for m in re.finditer(re.escape(MARKER_GDC), text)]
idx_hru      = text.find(MARKER_HRU)

print(f"background_discourse occurrences : {len(idx_bd_list)}  at lines: "
      f"{[text[:i].count(chr(10))+1 for i in idx_bd_list]}")
print(f"_get_discourse_context occurrences: {len(idx_gdc_list)} at lines: "
      f"{[text[:i].count(chr(10))+1 for i in idx_gdc_list]}")
print(f"_hard_reset_user at line          : {text[:idx_hru].count(chr(10))+1 if idx_hru >= 0 else 'NOT FOUND'}")

if len(idx_bd_list) > 1:
    # Keep everything up to (not including) second background_discourse,
    # then jump straight to _hard_reset_user
    keep_head = text[:idx_bd_list[1]]   # everything before duplicate bd
    keep_tail = text[idx_hru:]           # from _hard_reset_user onward
    text = keep_head.rstrip() + "\n" + keep_tail
    print("✓ Removed duplicate background_discourse + orphaned code")
elif len(idx_gdc_list) > 1:
    # No duplicate bd but duplicate _get_discourse_context
    keep_head = text[:idx_gdc_list[1]]
    keep_tail = text[idx_hru:]
    text = keep_head.rstrip() + "\n" + keep_tail
    print("✓ Removed duplicate _get_discourse_context + orphaned code")
else:
    print("No duplicates detected — checking for orphaned fragments only")

# ── Step 4: Syntax check ─────────────────────────────────────────────────
import ast
try:
    ast.parse(text)
    new_len = len(text.splitlines())
    print(f"\n✅ SYNTAX OK — {original_len} → {new_len} lines (removed {original_len - new_len})")
except SyntaxError as e:
    lines = text.splitlines()
    print(f"\n❌ SyntaxError at line {e.lineno}: {e.msg}")
    start = max(0, e.lineno - 4)
    for i, ln in enumerate(lines[start : e.lineno + 3], start=start + 1):
        mark = " <<<" if i == e.lineno else ""
        print(f"{i:5}: {ln}{mark}")
    print("\nFile NOT written — backup safe at", backup)
    sys.exit(1)

# ── Step 5: Write fixed file ─────────────────────────────────────────────
SRC.write_text(text, encoding="utf-8")
print(f"✅ orchestrator.py written successfully.")
print(f"\nNext step: venv\\Scripts\\python.exe test_scenarios.py")
