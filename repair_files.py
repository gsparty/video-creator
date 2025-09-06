# repair_files.py — safe in-place repairs for BOM / stray-import / missing-body issues
import io, sys, re
from pathlib import Path
ROOT = Path.cwd()

def backup(path: Path):
    bak = path.with_suffix(path.suffix + ".bak_repair")
    if not bak.exists():
        bak.write_bytes(path.read_bytes())
    return bak

def remove_bom_and_normalize(path: Path):
    s = path.read_text(encoding="utf-8")
    if s.startswith("\ufeff"):
        print(f"Removing BOM from {path.name}")
        s = s.lstrip("\ufeff")
        path.write_text(s, encoding="utf-8")
    else:
        print(f"No BOM in {path.name}")

def gather_and_move_imports(path: Path):
    s = path.read_text(encoding="utf-8")
    lines = s.splitlines()
    import_lines = []
    others = []
    import_pattern = re.compile(r'^\s*(import\s+\w+|from\s+[.\w]+\s+import\s+.+)')
    for L in lines:
        if import_pattern.match(L):
            import_lines.append(L.strip())
        else:
            others.append(L)
    # put imports at top (after any shebang or leading comments)
    head_idx = 0
    while head_idx < len(others) and (others[head_idx].strip().startswith("#!") or others[head_idx].strip().startswith("#") or others[head_idx].strip() == ""):
        head_idx += 1
    new_lines = others[:head_idx] + import_lines + [""] + others[head_idx:]
    new_s = "\n".join(new_lines) + "\n"
    if new_s != s:
        print(f"Moved {len(import_lines)} import lines to top of {path.name}")
        path.write_text(new_s, encoding="utf-8")
    else:
        print(f"No import relocation needed for {path.name}")

def ensure_functions_have_bodies(path: Path):
    s = path.read_text(encoding="utf-8")
    lines = s.splitlines()
    out = []
    i = 0
    changed = 0
    while i < len(lines):
        L = lines[i]
        out.append(L)
        m = re.match(r'^(\s*)def\s+[A-Za-z_][A-Za-z0-9_]*\s*\(.*\)\s*:\s*$', L)
        if m:
            indent = m.group(1)
            # look ahead for the next non-empty, non-comment line
            j = i + 1
            while j < len(lines) and lines[j].strip() == "":
                out.append(lines[j])
                j += 1
            if j < len(lines):
                next_line = lines[j]
                # if the next meaningful line is not indented further, insert a pass
                if not next_line.startswith(indent + " " ) and not next_line.startswith(indent + "\t"):
                    pad = indent + "    pass"
                    out.append(pad)
                    changed += 1
                    # continue from j (we already appended blank lines up to j)
                    i = j - 1
                else:
                    # body looks indented properly, continue normally
                    i = j - 1
            else:
                # file ended after def — insert pass
                pad = indent + "    pass"
                out.append(pad)
                changed += 1
                i = j - 1
        i += 1
    if changed:
        print(f"Inserted pass into {changed} function(s) in {path.name}")
        path.write_text("\n".join(out) + "\n", encoding="utf-8")
    else:
        print(f"No empty function bodies found in {path.name}")

def run():
    for fname in ("text_overlay.py", "video_builder.py"):
        p = ROOT / fname
        if not p.exists():
            print(f"{fname} not found — skipping")
            continue
        backup(p)
        remove_bom_and_normalize(p)
        # move imports to top to avoid imports inside function bodies
        gather_and_move_imports(p)
        # ensure defs have at least a pass if missing a body
        ensure_functions_have_bodies(p)
    print("Repair script finished. Originals backed up with .bak_repair suffix.")

if __name__ == "__main__":
    run()
