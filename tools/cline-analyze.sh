#!/usr/bin/env bash
set -euo pipefail

# Usage: ./tools/cline-analyze.sh path/to/repo '{"service":"user-api","error_type":"NullPointer","message":"..."}'


REPO_PATH="$1"
SERVICE="$2"
ERROR_MESSAGE="$3"

cd "$REPO_PATH"

cline task run <<EOF
You are a senior backend engineer looking at a Git repo and an error message.

Context:
- Service: $SERVICE
- Error message: $ERROR_MESSAGE

Goals:
1. Use repo files and git history (git log, git blame) to find which file is most likely responsible.
2. Identify the most recent commits touching that file.
3. Suggest 1–2 likely owners (authors of those commits).

Use git commands as needed. 
Output ONLY JSON with:
{
  "suspected_file": "relative/path/to/file.<extension>",
  "suspected_commits": [
    {"sha": "...", "author": "Name <email>", "message": "..."}
  ],
  "suspected_owners": ["Name", "..."]
}
EOF
