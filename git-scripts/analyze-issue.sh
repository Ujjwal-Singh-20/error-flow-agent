#!/bin/bash
# Analyze a GitHub issue using Cline CLI

if [ -z "$1" ]; then
    echo "Usage: $0 <github-issue-url> [prompt] [address]"
    echo "Example: $0 https://github.com/owner/repo/issues/123"
    echo "Example: $0 https://github.com/owner/repo/issues/123 'What is the root cause of this issue?'"
    echo "Example: $0 https://github.com/owner/repo/issues/123 'What is the root cause of this issue?' 127.0.0.1:46529"
    exit 1
fi

# Gather the args
ISSUE_URL="$1"
PROMPT="${2:-What is the root cause of this issue?}"
if [ -n "$3" ]; then
    ADDRESS="--address $3"
fi

# Debugging: Print the command being executed
echo "Running command: cline -y \"$PROMPT: $ISSUE_URL\" --mode act $ADDRESS -F json"

# Ask Cline for its analysis, showing only the summary
RESULT=$(cline -y "$PROMPT: $ISSUE_URL" --mode act $ADDRESS -F json 2>&1)

# Check if the command succeeded
if [ $? -ne 0 ]; then
    echo "Error: $RESULT"
    exit 1
fi

# Process the result
echo "$RESULT" | \
    sed -n '/^{/,$p' | \
    jq -r 'select(.say == "completion_result") | .text' | \
    sed 's/\\n/\n/g'