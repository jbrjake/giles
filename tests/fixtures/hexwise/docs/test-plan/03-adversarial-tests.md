# Adversarial Tests

Checker Macready's favorites. These are the inputs that break things on purpose —
the ones that fall through format detection, overflow buffers, or quietly produce
wrong answers when no one is watching.

---

### TC-ADV-001: Empty string input returns helpful error

**Persona:** Checker Macready
**Priority:** P0
**Story:** US-0101

**Preconditions:**
- hexwise binary is on PATH

**Steps:**
1. Run `hexwise ""`
2. Capture stderr and exit code

**Expected Results:**
- Exit code is non-zero
- Stderr contains a message explaining that an empty string is not a valid color
- Message suggests correct usage (e.g., shows an example)
- No panic or unhandled exception

**Acceptance:** PASS if error message is present, helpful, and exit code is non-zero

---

### TC-ADV-002: Invalid hex characters identified in error

**Persona:** Checker Macready
**Priority:** P0
**Story:** US-0101

**Preconditions:**
- hexwise binary is on PATH

**Steps:**
1. Run `hexwise #GGGGGG`
2. Capture stderr and exit code

**Expected Results:**
- Exit code is non-zero
- Stderr message identifies `G` as the invalid character
- Message does not say "unknown error" or generic parse failure
- Stdout is empty

**Acceptance:** PASS if error names the offending character(s) explicitly

---

### TC-ADV-003: 3-digit hex shorthand expands correctly

**Persona:** Checker Macready
**Priority:** P1
**Story:** US-0101

**Preconditions:**
- hexwise binary is on PATH

**Steps:**
1. Run `hexwise #FFF`
2. Run `hexwise #FFFFFF`
3. Compare outputs

**Expected Results:**
- Both commands exit with code 0
- Outputs are equivalent — `#FFF` expands to `#FFFFFF`, not `#FFF000` or similar
- Expansion rule: each digit is doubled (F→FF, A→AA, etc.)

**Acceptance:** PASS if `#FFF` produces the same result as `#FFFFFF`

---

### TC-ADV-004: Unicode fullwidth hex input is rejected with suggestion

**Persona:** Checker Macready
**Priority:** P1
**Story:** US-0101

**Preconditions:**
- hexwise binary is on PATH

**Steps:**
1. Run `hexwise ＃ＦＦ５７３３` (fullwidth `#` and digits, U+FF03 prefix)
2. Capture stderr and exit code

**Expected Results:**
- Exit code is non-zero
- Stderr explains the input contains non-ASCII characters
- Error suggests using the ASCII equivalent `#FF5733`
- No silent misparse to a wrong color

**Acceptance:** PASS if fullwidth input is rejected and error suggests ASCII equivalent

---

### TC-ADV-005: Contrast of a color against itself is exactly 1:1

**Persona:** Checker Macready
**Priority:** P0
**Story:** US-0202

**Preconditions:**
- hexwise binary is on PATH

**Steps:**
1. Run `hexwise contrast #3498DB #3498DB`
2. Run `hexwise contrast #000000 #000000`
3. Run `hexwise contrast #FFFFFF #FFFFFF`
4. Capture stdout from all three runs

**Expected Results:**
- All three output `1:1`
- All three exit with code 0
- No floating point drift (e.g., `1.0000000001:1`)

**Acceptance:** PASS if all three self-contrast operations return exactly `1:1`

---

### TC-ADV-006: Extremely long input completes within timeout without OOM

**Persona:** Checker Macready
**Priority:** P0
**Story:** US-0101

**Preconditions:**
- hexwise binary is on PATH
- System has normal memory constraints (no special ulimit override)

**Steps:**
1. Generate a string of 1,048,576 `F` characters
2. Run `hexwise <that string>`
3. Measure elapsed time and peak memory

**Expected Results:**
- Exit code is non-zero (input is not a valid color)
- Error is returned within 2 seconds
- Peak memory does not exceed 50MB for this operation
- Process does not crash with OOM or SIGKILL

**Acceptance:** PASS if error is returned within 2s with non-zero exit and no OOM event

---

### TC-ADV-007: Null bytes in input are rejected gracefully

**Persona:** Checker Macready
**Priority:** P1
**Story:** US-0101

**Preconditions:**
- hexwise binary is on PATH

**Steps:**
1. Pipe a string containing null bytes: `printf '#FF\x005733' | hexwise`
2. Capture stdout, stderr, and exit code

**Expected Results:**
- Exit code is non-zero
- Error message indicates the input contains invalid characters
- No silent truncation (treating `#FF` as the input and succeeding)
- No crash or undefined behavior

**Acceptance:** PASS if null-byte input produces a rejection error with non-zero exit

---

### TC-ADV-008: HSL with out-of-range values is handled

**Persona:** Checker Macready
**Priority:** P1
**Story:** US-0103

**Preconditions:**
- hexwise binary is on PATH

**Steps:**
1. Run `hexwise hsl(400, 200%, 50%)` — hue > 360, saturation > 100%
2. Capture stdout, stderr, and exit code

**Expected Results:**
- Either: error message explaining the values are out of range (preferred)
- Or: values are clamped to valid range (400→360 or 400 mod 360=40, saturation→100%) and result is computed
- In either case: no silent garbage output that looks like a valid color

**Acceptance:** PASS if out-of-range HSL produces either a clear error or a documented clamping behavior, not silent corruption

---

### TC-ADV-009: Named color with extra whitespace is trimmed and matched

**Persona:** Checker Macready
**Priority:** P2
**Story:** US-0106

**Preconditions:**
- hexwise binary is on PATH

**Steps:**
1. Run `hexwise name "  coral  "` (leading and trailing spaces)
2. Capture stdout and exit code

**Expected Results:**
- Exit code is 0
- Output matches the result of `hexwise name coral`
- Input is trimmed before lookup; spaces do not cause "unknown color name" error

**Acceptance:** PASS if whitespace-padded color name resolves to the same result as the unpadded name

---

### TC-ADV-010: Batch mode with 10,000 lines completes within 10 seconds

**Persona:** Checker Macready
**Priority:** P1
**Story:** US-0207, US-0208

**Preconditions:**
- hexwise binary is on PATH
- Input file generated: 10,000 lines, each a valid random hex color

**Steps:**
1. Generate `10000_colors.txt` with 10,000 valid hex colors
2. Run `time cat 10000_colors.txt | hexwise > /dev/null`
3. Record elapsed wall time and exit code

**Expected Results:**
- Exit code is 0
- Wall time is under 10 seconds
- No intermediate crash or hang
- Memory usage stays below 200MB throughout

**Acceptance:** PASS if 10,000-line batch completes in under 10s with exit code 0
