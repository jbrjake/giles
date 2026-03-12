# Development Guide

## Build

    cargo build

## Test

    cargo test

## Lint

    cargo fmt --check
    cargo clippy -- -D warnings

## Workflow
1. Write a failing test.
2. Write the minimal code to make it pass.
3. Run `cargo fmt` and `cargo clippy`.
4. Commit with a conventional commit message.

## Contrast Testing
Use known WCAG reference pairs as ground truth (e.g. black on white = 21:1, white on white = 1:1). Include an edge case at exactly 4.5:1 to verify the AA pass/fail boundary. Float comparison must use epsilon to avoid rounding surprises at the boundary.

## Palette Verification
Verify hue rotation math against known trigonometric values (e.g. rotating 0° hue by 120° should land on exactly 120°). Use exact integer hue inputs so expected outputs are deterministic without floating-point ambiguity.

## Batch Mode Testing
Mock stdin by passing a `Read` implementor in tests — do not rely on actual stdin. Feed multi-line input with a mix of valid and invalid hex codes and assert the output order and error codes match expectations.
