# Project Rules

- No `.unwrap()` in library code — use `Result` with descriptive errors.
- All public functions must have doc comments.
- Run `cargo clippy -- -D warnings` before every commit.
- Keep dependencies at zero unless absolutely necessary.
- Tests go in the same file as the code they test (unit) or in `tests/` (integration).
