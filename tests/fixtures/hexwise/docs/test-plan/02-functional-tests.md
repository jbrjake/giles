# Functional Tests

~30 test cases across six domains. Heading format is `### TC-PREFIX-NNN: Title`
for extraction by the sprint-run orchestrator.

---

## Parsing & Conversion

### TC-PAR-001: Valid 6-digit hex with hash prefix

**Persona:** Rusti Ferris
**Priority:** P0
**Story:** US-0101

**Preconditions:**
- hexwise binary is on PATH

**Steps:**
1. Run `hexwise #FF5733`
2. Capture stdout and exit code

**Expected Results:**
- Exit code is 0
- Stdout contains `#FF5733` (or normalized uppercase equivalent)
- Stdout contains `rgb(255, 87, 51)`

**Acceptance:** PASS if exit code is 0 and both values appear in output

---

### TC-PAR-002: Valid 3-digit hex shorthand expansion

**Persona:** Rusti Ferris
**Priority:** P1
**Story:** US-0101

**Preconditions:**
- hexwise binary is on PATH

**Steps:**
1. Run `hexwise #FFF`
2. Capture stdout and exit code

**Expected Results:**
- Exit code is 0
- Output shows expanded form `#FFFFFF`
- Output shows `rgb(255, 255, 255)`

**Acceptance:** PASS if 3-digit input is expanded to 6-digit equivalent without error

---

### TC-PAR-003: Case-insensitive hex parsing

**Persona:** Rusti Ferris
**Priority:** P1
**Story:** US-0101

**Preconditions:**
- hexwise binary is on PATH

**Steps:**
1. Run `hexwise #ff5733`
2. Run `hexwise #FF5733`
3. Compare output of both runs

**Expected Results:**
- Both commands produce identical output (modulo the normalized hex case)
- Both exit with code 0

**Acceptance:** PASS if outputs are equivalent

---

### TC-PAR-004: Missing hash prefix is accepted

**Persona:** Rusti Ferris
**Priority:** P1
**Story:** US-0101

**Preconditions:**
- hexwise binary is on PATH

**Steps:**
1. Run `hexwise FF5733` (no leading `#`)
2. Capture stdout and exit code

**Expected Results:**
- Exit code is 0
- Output is identical to `hexwise #FF5733`

**Acceptance:** PASS if bare hex string without `#` is parsed identically to prefixed form

---

### TC-PAR-005: Invalid hex characters produce clear error

**Persona:** Rusti Ferris
**Priority:** P0
**Story:** US-0101

**Preconditions:**
- hexwise binary is on PATH

**Steps:**
1. Run `hexwise #GGGGGG`
2. Capture stderr and exit code

**Expected Results:**
- Exit code is non-zero
- Stderr contains an error identifying `G` as an invalid hex character
- Stdout is empty

**Acceptance:** PASS if error message names the invalid character and exit code is non-zero

---

### TC-PAR-006: RGB tuple input parsing

**Persona:** Rusti Ferris
**Priority:** P1
**Story:** US-0102

**Preconditions:**
- hexwise binary is on PATH

**Steps:**
1. Run `hexwise rgb(255,87,51)` or `hexwise 255,87,51`
2. Capture stdout and exit code

**Expected Results:**
- Exit code is 0
- Output includes the hex equivalent `#FF5733`
- Output includes the normalized RGB values

**Acceptance:** PASS if RGB tuple input produces the same color data as the equivalent hex input

---

## Named Colors

### TC-NAM-001: Exact CSS named color match

**Persona:** Palette Jones
**Priority:** P0
**Story:** US-0106

**Preconditions:**
- hexwise binary is on PATH
- CSS named color database is embedded

**Steps:**
1. Run `hexwise name coral`
2. Capture stdout and exit code

**Expected Results:**
- Exit code is 0
- Output includes `#FF7F50`
- Output includes `rgb(255, 127, 80)`

**Acceptance:** PASS if canonical CSS named color resolves to correct hex and RGB

---

### TC-NAM-002: Case-insensitive name lookup

**Persona:** Palette Jones
**Priority:** P1
**Story:** US-0106

**Preconditions:**
- hexwise binary is on PATH

**Steps:**
1. Run `hexwise name Coral`
2. Run `hexwise name CORAL`
3. Compare both outputs to `hexwise name coral`

**Expected Results:**
- All three commands produce identical output
- All exit with code 0

**Acceptance:** PASS if name lookup is case-insensitive

---

### TC-NAM-003: Unknown color name returns error

**Persona:** Palette Jones
**Priority:** P0
**Story:** US-0106

**Preconditions:**
- hexwise binary is on PATH

**Steps:**
1. Run `hexwise name notacolor`
2. Capture stderr and exit code

**Expected Results:**
- Exit code is non-zero
- Stderr contains "unknown color name: notacolor" or equivalent
- Stdout is empty

**Acceptance:** PASS if unknown name produces non-zero exit and a message identifying the unknown name

---

## Output & Formatting

### TC-OUT-001: Default plain text output

**Persona:** Palette Jones
**Priority:** P0
**Story:** US-0107

**Preconditions:**
- hexwise binary is on PATH

**Steps:**
1. Run `hexwise #3498DB` without any output flags
2. Capture stdout

**Expected Results:**
- Output is plain text (no JSON braces or brackets)
- Output is human-readable with labeled fields (e.g., "Hex:", "RGB:")
- Output fits in a standard 80-column terminal without wrapping

**Acceptance:** PASS if output is plain text, labeled, and within 80 columns

---

### TC-OUT-002: JSON output flag

**Persona:** Palette Jones
**Priority:** P1
**Story:** US-0107

**Preconditions:**
- hexwise binary is on PATH

**Steps:**
1. Run `hexwise --json #3498DB`
2. Capture stdout
3. Parse stdout as JSON

**Expected Results:**
- Exit code is 0
- Stdout is valid JSON
- JSON contains fields for hex, rgb (as object or array), and name (if found)

**Acceptance:** PASS if stdout parses as valid JSON with expected fields

---

### TC-OUT-003: Color description in default output

**Persona:** Palette Jones
**Priority:** P2
**Story:** US-0108

**Preconditions:**
- hexwise binary is on PATH

**Steps:**
1. Run `hexwise #FF5733`
2. Capture stdout

**Expected Results:**
- Output includes a descriptive phrase about the color's character
- Description is not a bare hex dump — it should evoke a sensory quality

**Acceptance:** PASS if output contains a non-empty description field beyond the raw numbers

---

## Contrast Checking

### TC-CON-001: Black-on-white contrast is 21:1

**Persona:** Checker Macready
**Priority:** P0
**Story:** US-0201, US-0202

**Preconditions:**
- hexwise binary is on PATH

**Steps:**
1. Run `hexwise contrast #000000 #FFFFFF`
2. Capture stdout and exit code

**Expected Results:**
- Exit code is 0
- Output states contrast ratio as `21:1`
- WCAG AA: PASS
- WCAG AAA: PASS

**Acceptance:** PASS if ratio is exactly 21:1 and both WCAG levels pass

---

### TC-CON-002: Same color contrast is 1:1

**Persona:** Checker Macready
**Priority:** P0
**Story:** US-0202

**Preconditions:**
- hexwise binary is on PATH

**Steps:**
1. Run `hexwise contrast #3498DB #3498DB`
2. Capture stdout and exit code

**Expected Results:**
- Exit code is 0
- Output states contrast ratio as `1:1`
- WCAG AA: FAIL
- WCAG AAA: FAIL

**Acceptance:** PASS if ratio is exactly 1:1 and both WCAG levels fail

---

### TC-CON-003: AA threshold boundary check

**Persona:** Checker Macready
**Priority:** P0
**Story:** US-0203

**Preconditions:**
- hexwise binary is on PATH

**Steps:**
1. Identify two colors with a contrast ratio just above 4.5:1 (AA-passing boundary)
2. Run `hexwise contrast <color1> <color2>`
3. Identify two colors with ratio just below 4.5:1
4. Run `hexwise contrast <color3> <color4>`

**Expected Results:**
- Pair above threshold: WCAG AA PASS
- Pair below threshold: WCAG AA FAIL
- Boundary is respected without rounding in the wrong direction

**Acceptance:** PASS if threshold enforcement is correct for both sides of 4.5:1

---

### TC-CON-004: Large text threshold (3:1) is evaluated separately

**Persona:** Checker Macready
**Priority:** P1
**Story:** US-0203

**Preconditions:**
- hexwise binary is on PATH

**Steps:**
1. Run `hexwise contrast #888888 #FFFFFF`
2. Capture stdout (this pair is above 3:1 but below 4.5:1)

**Expected Results:**
- Output includes both a "normal text" verdict and a "large text" verdict
- Normal text: FAIL
- Large text: PASS
- Both verdicts are visible without extra flags

**Acceptance:** PASS if output distinguishes normal text and large text WCAG thresholds

---

## Palette Generation

### TC-PAL-001: Complementary color of red is cyan

**Persona:** Palette Jones
**Priority:** P0
**Story:** US-0204

**Preconditions:**
- hexwise binary is on PATH

**Steps:**
1. Run `hexwise palette --complementary #FF0000`
2. Capture stdout

**Expected Results:**
- Exit code is 0
- Output includes exactly 2 colors
- The complement of `#FF0000` (hue=0°) is at hue=180°, which is `#00FFFF`

**Acceptance:** PASS if the second color is `#00FFFF` or equivalent cyan

---

### TC-PAL-002: Analogous palette produces 3 colors

**Persona:** Palette Jones
**Priority:** P1
**Story:** US-0205

**Preconditions:**
- hexwise binary is on PATH

**Steps:**
1. Run `hexwise palette --analogous #3498DB`
2. Capture stdout

**Expected Results:**
- Exit code is 0
- Output includes exactly 3 colors
- Colors are at −30°, 0°, and +30° from the anchor hue

**Acceptance:** PASS if exactly 3 colors are output with correct hue spacing

---

### TC-PAL-003: Triadic palette uses 120° rotation

**Persona:** Palette Jones
**Priority:** P0
**Story:** US-0205

**Preconditions:**
- hexwise binary is on PATH

**Steps:**
1. Run `hexwise palette --triadic #3498DB`
2. Capture stdout
3. Compute expected hues: anchor, anchor+120°, anchor+240°

**Expected Results:**
- Exit code is 0
- Output includes exactly 3 colors
- Hue values of the three colors differ by 120° each

**Acceptance:** PASS if three distinct colors appear with 120° hue separation

---

### TC-PAL-004: Palette JSON output

**Persona:** Palette Jones
**Priority:** P1
**Story:** US-0206

**Preconditions:**
- hexwise binary is on PATH

**Steps:**
1. Run `hexwise palette --triadic --json #3498DB`
2. Capture stdout
3. Parse stdout as JSON

**Expected Results:**
- Exit code is 0
- Stdout is valid JSON
- JSON is an array of 3 color objects, each with at minimum a `hex` field

**Acceptance:** PASS if stdout parses as a JSON array of 3 objects with hex values

---

## Batch Mode

### TC-BAT-001: Stdin multi-line batch processing

**Persona:** Checker Macready
**Priority:** P0
**Story:** US-0207, US-0208

**Preconditions:**
- hexwise binary is on PATH
- Input file `colors.txt` contains 10 valid hex values, one per line

**Steps:**
1. Run `cat colors.txt | hexwise`
2. Capture stdout, stderr, and exit code

**Expected Results:**
- Exit code is 0
- Stdout contains exactly 10 lines of output
- Output lines correspond to input lines in order
- Stderr is empty

**Acceptance:** PASS if output line count matches input line count and exit code is 0

---

### TC-BAT-002: Mixed valid and invalid input in batch

**Persona:** Checker Macready
**Priority:** P0
**Story:** US-0209

**Preconditions:**
- hexwise binary is on PATH
- Input contains 8 valid hex values and 2 invalid values (e.g., `#GGGGGG`, `notahex`)

**Steps:**
1. Pipe the 10-line mixed input to hexwise
2. Capture stdout, stderr, and exit code

**Expected Results:**
- Exit code is non-zero (reflects at least one failure)
- Valid lines produce normal output
- Invalid lines produce per-line error messages (on stdout or stderr, consistently)
- Total output lines = 10 (one result per input line, error or not)

**Acceptance:** PASS if all 10 lines get a result (success or error) and final exit code is non-zero

---

### TC-BAT-003: Empty stdin produces no output

**Persona:** Checker Macready
**Priority:** P1
**Story:** US-0207

**Preconditions:**
- hexwise binary is on PATH

**Steps:**
1. Run `echo -n "" | hexwise` or equivalent empty pipe
2. Capture stdout, stderr, and exit code

**Expected Results:**
- Exit code is 0
- Stdout is empty
- Stderr is empty
- No crash or hang

**Acceptance:** PASS if empty stdin produces clean exit with no output and no error
