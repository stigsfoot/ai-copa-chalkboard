# Safety Hooks & Colab CLI Guidelines

1.  **Secret Scanning Hook**: Tool-use hooks automatically scan modified files for credentials matching `GEMINI_API_KEY`, `GITHUB_TOKEN`, or raw key structures. If any secrets are detected, the tool write will be blocked.
2.  **Command Safety Gate**: The `PreToolUse` hook blocks any command that runs outside the workspace or attempts dangerous system commands (e.g. `rm -rf`, modifying system config).
3.  **Google Colab Integration**:
    - When running notebook tests or provisioning GPU resources, use the official `google-colab-cli` (`colab`).
    - Use `colab exec` to run scripts on remote Colab environments rather than local GPU runtimes when performance is needed.
    - Retrieve artifacts and weights from Colab back to the workspace using `colab download`.
