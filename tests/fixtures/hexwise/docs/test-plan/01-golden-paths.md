# Golden Path Scenarios

Five end-to-end scenarios covering the workflows a real user will hit first.
Each includes boundary tests and an error variant so the happy path doesn't
become a blind spot.

---

### GP-001: First Impression

**Personas:** Rusti Ferris, Palette Jones

**Given:** hexwise is installed and available on PATH

**When:**
1. User runs `hexwise #FF5733`
2. hexwise parses the input as a 6-digit hex color
3. hexwise converts to RGB components
4. hexwise queries the named color database for the nearest CSS name
5. hexwise generates a synesthetic description of the color

**Then:**
- Exit code is 0
- Output includes the normalized hex value `#FF5733`
- Output includes the RGB breakdown `rgb(255, 87, 51)`
- Output includes the nearest CSS named color (e.g., `tomato` or `orangered`)
- Output includes a one-line color description (warm, saturated quality)
- Output is human-readable plain text by default

**Boundary tests:**
- Input `#ff5733` (lowercase) produces identical output — normalization is case-insensitive
- Input `FF5733` (no leading `#`) is accepted and treated as equivalent
- Input `#F53` (3-digit shorthand) is rejected with a clear error (3-digit expansion is covered in GP-005 variant and TC-PAR-002)

**Error variant:**
- Input `#FF573` (5 digits) produces an error: "invalid hex length: expected 6 digits, got 5"
- Exit code is non-zero
- Error message goes to stderr, stdout is empty

**Traceability:** US-0101, US-0105, US-0107, US-0108, TC-PAR-001

---

### GP-002: The Contrast Question

**Personas:** Checker Macready

**Given:** hexwise is installed; user is checking text legibility for a web design

**When:**
1. User runs `hexwise contrast #000000 #FFFFFF`
2. hexwise parses both colors
3. hexwise computes relative luminance for each
4. hexwise computes the contrast ratio
5. hexwise evaluates WCAG AA and AAA thresholds

**Then:**
- Exit code is 0
- Contrast ratio displayed as `21:1`
- WCAG AA verdict: PASS (normal text requires 4.5:1)
- WCAG AAA verdict: PASS (requires 7:1)
- Large text verdict: PASS (requires 3:1)
- Output is unambiguous — verdict is spelled out, not encoded

**Boundary tests:**
- `hexwise contrast #777777 #FFFFFF` — near the AA boundary for normal text (~4.48:1); verify the ratio and PASS/FAIL is correctly computed
- `hexwise contrast #757575 #FFFFFF` — crosses the 4.5:1 AA threshold; verify FAIL
- `hexwise contrast #888888 #FFFFFF` — large text threshold (3:1) should PASS, normal text should FAIL

**Error variant:**
- `hexwise contrast #000000` (only one color) produces an error: "contrast requires two color arguments"
- Exit code is non-zero

**Traceability:** US-0201, US-0202, US-0203, TC-CON-001

---

### GP-003: Palette Party

**Personas:** Palette Jones

**Given:** hexwise is installed; user wants a color scheme starting from a single anchor

**When:**
1. User runs `hexwise palette --triadic #3498DB`
2. hexwise parses the input hex color
3. hexwise converts to HSL for rotation math
4. hexwise rotates the hue by 120° and 240° to produce the triadic companions
5. hexwise converts results back to hex and displays all three

**Then:**
- Exit code is 0
- Output includes exactly 3 colors
- First color is `#3498DB` (the anchor, converted to canonical form)
- Second color is at hue +120° from the anchor
- Third color is at hue +240° from the anchor
- Each color is shown with its hex value
- Colors are visually distinct (not the same hex repeated)

**Boundary tests:**
- `hexwise palette --complementary #3498DB` — produces exactly 2 colors, 180° apart
- `hexwise palette --analogous #3498DB` — produces 3 colors, ±30° from anchor
- Anchor near hue 360° (e.g., `#FF0000`, hue=0) — rotation wraps correctly; no negative hue values in output

**Error variant:**
- `hexwise palette --triadic` (no color argument) produces an error: "palette requires a base color"
- `hexwise palette --unknown-mode #3498DB` produces an error listing valid modes
- Exit code is non-zero in both cases

**Traceability:** US-0205, US-0206, TC-PAL-003

---

### GP-004: Batch Judgment

**Personas:** Checker Macready

**Given:** hexwise is installed; user has a file of 10 hex colors, one per line

**When:**
1. User pipes the file to hexwise: `cat colors.txt | hexwise`
2. hexwise detects stdin input (non-TTY)
3. hexwise reads lines one at a time
4. hexwise processes each color and emits one result line per input
5. hexwise flushes output after each line (streaming, not buffered to end)

**Then:**
- Exit code is 0 (all 10 are valid hex values)
- Exactly 10 lines of output, in input order
- Each output line contains the parsed color information for the corresponding input
- Output is machine-parseable (consistent delimiter or JSON with `--json`)

**Boundary tests:**
- 10 colors where 2 are invalid — exit code is non-zero, valid colors still produce output, invalid lines produce inline error messages
- Empty file piped to stdin — exit code is 0, no output, no crash
- File with trailing whitespace on each line — colors are parsed correctly after trimming

**Error variant:**
- A line contains `#GGGGGG` — output for that line is an error message identifying the invalid character
- Processing continues for subsequent lines (non-fatal per-line errors)
- Final exit code reflects that at least one line failed

**Traceability:** US-0207, US-0208, US-0209, TC-BAT-001

---

### GP-005: Name That Color

**Personas:** Palette Jones

**Given:** hexwise is installed; user remembers a color name but not its hex value

**When:**
1. User runs `hexwise name coral`
2. hexwise looks up "coral" in the CSS named color database
3. hexwise finds the exact match
4. hexwise returns the hex value and RGB components

**Then:**
- Exit code is 0
- Output includes `#FF7F50`
- Output includes `rgb(255, 127, 80)`
- Output is terse — just the conversion, not a full analysis

**Boundary tests:**
- `hexwise name Coral` (capital C) — case-insensitive match, same output
- `hexwise name CORAL` (all caps) — same output
- `hexwise name rebeccapurple` — matches CSS4 extended palette entry `#663399`

**Error variant:**
- `hexwise name chartreuse-ish` — no exact match; error "unknown color name: chartreuse-ish"
- If fuzzy matching is implemented: suggest the closest known name
- Exit code is non-zero when no match is found

**Traceability:** US-0105, US-0106, TC-NAM-001, TC-NAM-002
