#!/usr/bin/env python3
import sys
import json
import subprocess
import os
import re

# Block list for destructive shell commands
BLOCKED_PATTERNS = [
    r"\brm\s+-[rf]+\s+/",           # rm -rf /
    r"\brm\s+-[rf]+\s+\*",           # rm -rf *
    r"\bformat\b",                  # format disk
    r"\bpush\b.*\b--force\b",       # git push --force
    r"\bpush\b.*\b-f\b",            # git push -f
]

# Regex to detect potential API keys / secrets
SECRET_REGEXES = [
    re.compile(r"GEMINI_API_KEY\s*=\s*[\"']?[a-zA-Z0-9_\-]{10,}[\"']?", re.IGNORECASE),
    re.compile(r"GITHUB_TOKEN\s*=\s*[\"']?[a-zA-Z0-9_\-]{10,}[\"']?", re.IGNORECASE),
    re.compile(r"GH_TOKEN\s*=\s*[\"']?[a-zA-Z0-9_\-]{10,}[\"']?", re.IGNORECASE),
    re.compile(r"\bAIzaSy[a-zA-Z0-9_\-]{30,40}\b"),  # Google API Key format
]

def log(msg):
    sys.stderr.write(f"[Antigravity Hook] {msg}\n")

def parse_input():
    """Parse hook event JSON from stdin."""
    if sys.stdin.isatty():
        return {}
    try:
        data = sys.stdin.read().strip()
        if not data:
            return {}
        return json.loads(data)
    except Exception as e:
        log(f"Failed to parse stdin JSON: {e}")
        return {}

def run_cmd(args, cwd=None):
    """Run a shell command, returning (exit_code, stdout, stderr)."""
    try:
        res = subprocess.run(args, capture_output=True, text=True, cwd=cwd, shell=True)
        return res.returncode, res.stdout, res.stderr
    except Exception as e:
        return -1, "", str(e)

def scan_file_for_secrets(filepath):
    """Scan file content for credentials."""
    if not os.path.exists(filepath):
        return None
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        for regex in SECRET_REGEXES:
            match = regex.search(content)
            if match:
                return match.group(0)
    except Exception as e:
        log(f"Error reading file for secret scan: {e}")
    return None

def handle_pre_cmd(event):
    """Check command safety before run_command executes."""
    # Example input: {"tool": "run_command", "arguments": {"CommandLine": "..."}}
    args = event.get("arguments", {})
    command = args.get("CommandLine", "")
    
    if not command:
        # Fallback to command-line arg if stdin is empty
        if len(sys.argv) > 2:
            command = sys.argv[2]
            
    if not command:
        print(json.dumps({"decision": "allow"}))
        return

    # Check blocked patterns
    for pattern in BLOCKED_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            log(f"Blocked destructive command: {command}")
            print(json.dumps({
                "decision": "deny",
                "message": f"Command contains a blocked destructive pattern: {pattern}"
            }))
            return

    # Check for raw API keys in command line
    for regex in SECRET_REGEXES:
        if regex.search(command):
            log("Blocked command containing secrets.")
            print(json.dumps({
                "decision": "deny",
                "message": "Command line contains an API key or credential."
            }))
            return

    # Default allow
    print(json.dumps({"decision": "allow"}))

def handle_post_write(event):
    """Formats code and verifies tests after editing a file."""
    args = event.get("arguments", {})
    target_file = args.get("TargetFile")

    # If no target file in event, check git status for modified files
    modified_files = []
    if target_file and os.path.exists(target_file):
        modified_files.append(target_file)
    else:
        # Fallback: check git status
        ret, stdout, _ = run_cmd("git status --porcelain")
        if ret == 0:
            for line in stdout.splitlines():
                if line.startswith((" M", "M ", " A", "A ")):
                    path = line[3:].strip()
                    # Resolve to absolute path
                    abs_path = os.path.abspath(path)
                    if os.path.exists(abs_path) and abs_path.endswith(".py"):
                        modified_files.append(abs_path)

    # 1. Scan for secrets
    for filepath in modified_files:
        found_secret = scan_file_for_secrets(filepath)
        if found_secret:
            log(f"CRITICAL: Secret detected in {os.path.basename(filepath)}: '{found_secret}'")
            print(json.dumps({
                "decision": "deny",
                "message": f"Operation aborted: Secret detected in file: {os.path.basename(filepath)}"
            }))
            # Revert the write using git checkout
            run_cmd(f"git checkout -- {filepath}")
            return

    # 2. Run Ruff formatting & checks
    for filepath in modified_files:
        if filepath.endswith(".py"):
            log(f"Running ruff formatting on {os.path.basename(filepath)}...")
            run_cmd(f"ruff format {filepath}")
            run_cmd(f"ruff check --fix {filepath}")

    # 3. Run Pytest to verify integrity
    log("Running pytest suite...")
    ret, stdout, stderr = run_cmd("python -m pytest")
    if ret != 0:
        log("WARNING: Tests are failing after this edit!")
        # Print failure output to stderr so the agent sees it
        sys.stderr.write(stdout + "\n" + stderr + "\n")
        print(json.dumps({
            "decision": "allow", 
            "message": "Files saved, but the test suite is failing. Please fix the broken tests."
        }))
    else:
        log("All tests passed successfully.")
        print(json.dumps({"decision": "allow"}))

def main():
    # If running in test/dry-run mode, do not read stdin to avoid blocking
    if any(arg in sys.argv for arg in ["--test-write", "--test-cmd"]):
        event = {}
    else:
        event = parse_input()
    
    # Process by CLI flag
    if "--pre-cmd" in sys.argv:
        handle_pre_cmd(event)
    elif "--post-write" in sys.argv:
        handle_post_write(event)
    elif "--test-write" in sys.argv:
        # Dry-run write handler
        handle_post_write({})
    elif "--test-cmd" in sys.argv:
        # Dry-run command safety check
        cmd_idx = sys.argv.index("--test-cmd")
        test_cmd = sys.argv[cmd_idx + 1] if len(sys.argv) > cmd_idx + 1 else ""
        handle_pre_cmd({"arguments": {"CommandLine": test_cmd}})
    else:
        # Default fallback
        print(json.dumps({"decision": "allow"}))

if __name__ == "__main__":
    main()
