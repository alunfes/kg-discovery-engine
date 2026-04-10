# Compile Attempt Log

**Date**: 2026-04-10  
**Session**: submission-readiness sanity pass

---

## Attempt 1 — Local pdflatex

**Command**: `which pdflatex && pdflatex --version`  
**Result**: `pdflatex NOT FOUND`  
**Status**: FAILED — pdflatex not installed

**Checked for existing TeX installations**:
```
brew list | grep -i tex    → no tex via brew
ls /usr/local/texlive      → not found
ls /Library/TeX            → not found
```

**Conclusion**: No TeX/LaTeX distribution installed on this machine.

---

## Predicted Failure Points (Static Analysis)

In lieu of actual compilation, static analysis was performed on all `.tex` files.
The following issues would arise during actual compilation:

### P1 — TODO-* bibkeys (BLOCKING for bibliography)
- 14 out of 15 bib entries are `TODO-*` placeholders with `author = {TODO}` or
  partially filled fields.
- `bibtex` will process these and generate warnings; `natbib` may render
  author fields as "TODO" in the PDF.
- **Impact**: PDF compiles but bibliography section shows malformed entries.
- **Fix required**: Replace all `TODO-*` entries with verified citation data
  before final submission. See `docs/bibliography_todo.md`.

### P2 — Figure symlinks (FIXED in this session)
- **Original state**: `paper/figures/*.png` were symlinks pointing to
  `.claude/worktrees/serene-leavitt/paper_assets/figures/` — a worktree-specific
  path that would not exist on any other machine or after worktree deletion.
- **Fix applied**: Replaced all 4 symlinks with actual file copies from
  `paper_assets/figures/`. All 4 PNGs now exist as regular files.
- **Status**: RESOLVED

### P3 — \xrightarrow across line break (FALSE POSITIVE)
- `paper/sections/08_threats_to_validity.tex` lines 105–106 contain an inline
  math expression `$...$` that spans two source lines.
- Python per-line `$` counting flagged this as an odd `$` count.
- **Assessment**: Valid LaTeX — inline math can span lines without blank line
  separator. `amsmath` (required for `\xrightarrow`) is loaded in `main.tex`.
- **Status**: NOT a bug. No fix needed.

### P4 — \xrightarrow package dependency
- `\xrightarrow` requires `amsmath`. Line 20 of `main.tex`: `\usepackage{amsmath}`.
- **Status**: OK

### P5 — natbib + plainnat style
- `main.tex` uses `\usepackage{natbib}` and `\bibliographystyle{plainnat}`.
- All `\cite{}` calls use standard `\cite{}` (not `\citep` or `\citet`).
- `natbib` with `\cite{}` in text mode will produce author-year citations.
- **Potential issue**: If venue requires numbered citations, style must change.
- **Status**: WATCH — confirm target venue citation style.

### P6 — tabularx with no X column in some tables
- `tabularx` is loaded. Not verified whether all `tabular` environments that
  use `tabularx` syntax actually use X columns.
- **Status**: LOW RISK — standard `tabular` environments don't require `tabularx`.

---

## Steps to Enable Actual Compilation

```bash
# Option A: MacTeX (full, ~4GB)
brew install --cask mactex

# Option B: BasicTeX (minimal, ~100MB) + add packages
brew install --cask basictex
sudo tlmgr update --self
sudo tlmgr install booktabs hyperref natbib microtype enumitem xcolor \
                   tabularx multirow url amsmath

# After installation:
cd paper/
pdflatex -interaction=nonstopmode main.tex
bibtex main
pdflatex -interaction=nonstopmode main.tex
pdflatex -interaction=nonstopmode main.tex
# Check: main.pdf exists and is >1 page
```

---

## Static Analysis Summary

| Check | Result |
|-------|--------|
| Broken `\ref{}` | 0 — all refs resolve to defined labels |
| Duplicate `\label{}` | 0 — 35 unique labels |
| Missing `\includegraphics` paths | 0 — all 4 figures exist as real files |
| Empty `\cite{}` | 0 |
| Math `$` mismatch | 0 real issues (1 false positive: multiline inline math) |
| Bare `#` outside comments | 0 |
| `\toprule`/`\bottomrule` mismatch | 0 — all tables balanced |
| TODO cite keys in text | **17** — requires bibliography completion |
| Orphaned bib entries (not cited) | 2 — `TODO-Wikidata`, `TODO-swanson-survey` |

**Net structural issues requiring fixes before submission**: bibliography completion only.
