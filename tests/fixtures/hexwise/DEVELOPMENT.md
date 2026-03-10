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
