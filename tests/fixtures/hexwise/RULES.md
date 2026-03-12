# Project Rules

- No `.unwrap()` in library code — use `Result` with descriptive errors.
- All public functions must have doc comments.
- Run `cargo clippy -- -D warnings` before every commit.
- Keep dependencies at zero unless absolutely necessary.
- Tests go in the same file as the code they test (unit) or in `tests/` (integration).
- Color values are always stored internally as sRGB u8 triples.
- All floating-point comparisons use an epsilon (handles contrast ratio edge cases).
- Error messages include what was expected and what was received.
- CLI exit codes: 0 = success, 1 = invalid input, 2 = system error.
