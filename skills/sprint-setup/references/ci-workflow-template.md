# CI Workflow Template

GitHub Actions workflow template for continuous integration. Generated from
project.toml `[ci]` section. The setup script reads `check_commands` and
`build_command` to generate the CI YAML.

## Workflow Template

```yaml
name: CI

on:
  pull_request:
    branches: [{base_branch}]
  push:
    branches: [{base_branch}]

jobs:
  check:
    name: Check
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      # Tool setup steps — generated from project.toml [ci] setup
      - name: Setup toolchain
        run: echo "Add project-specific toolchain setup here"

      # Check steps — generated from project.toml [ci] check_commands
      - name: Run checks
        run: |
          # Each command from project.toml [ci] check_commands
          echo "Run lint, format, and test commands here"

      # Build step — generated from project.toml [ci] build_command
      - name: Build
        run: |
          # Command from project.toml [ci] build_command
          echo "Run build command here"
```

## Notes

- `{base_branch}` is a placeholder replaced by the setup script. Comes from `project.toml [project] base_branch` (defaults to `main`)
- The workflow runs on every PR and push to the base branch
- Check and build commands are defined in project.toml `[ci]` section
- Add platform matrix when cross-platform targets are needed
- The setup script generates the final workflow YAML from this template
