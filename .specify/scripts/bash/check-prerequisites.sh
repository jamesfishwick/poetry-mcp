#!/bin/bash
# check-prerequisites.sh - Verify prerequisites for implementation
# Usage: ./check-prerequisites.sh [--json] [--require-tasks] [--include-tasks]

set -e

JSON_OUTPUT=false
REQUIRE_TASKS=false
INCLUDE_TASKS=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --json)
            JSON_OUTPUT=true
            shift
            ;;
        --require-tasks)
            REQUIRE_TASKS=true
            shift
            ;;
        --include-tasks)
            INCLUDE_TASKS=true
            shift
            ;;
        *)
            shift
            ;;
    esac
done

# Get current branch
BRANCH=$(git branch --show-current)

# Extract feature info
if [[ ! "$BRANCH" =~ ^[0-9]+- ]]; then
    echo '{"error": "Not on a feature branch"}' >&2
    exit 1
fi

FEATURE_DIR="specs/${BRANCH}"
TASKS_FILE="${FEATURE_DIR}/tasks.md"
PLAN_FILE="${FEATURE_DIR}/plan.md"
SPEC_FILE="${FEATURE_DIR}/spec.md"

# Check tasks file if required
if [[ "$REQUIRE_TASKS" == "true" && ! -f "$TASKS_FILE" ]]; then
    echo '{"error": "tasks.md not found"}' >&2
    exit 1
fi

# Build available docs list
AVAILABLE_DOCS=()
for doc in spec.md plan.md tasks.md research.md data-model.md quickstart.md; do
    if [[ -f "${FEATURE_DIR}/${doc}" ]]; then
        AVAILABLE_DOCS+=("${doc}")
    fi
done

# Get absolute path
ABS_FEATURE_DIR="$(cd "$(dirname "$FEATURE_DIR")" && pwd)/$(basename "$FEATURE_DIR")"

if [[ "$JSON_OUTPUT" == "true" ]]; then
    DOCS_JSON=$(printf '%s\n' "${AVAILABLE_DOCS[@]}" | jq -R . | jq -s .)
    cat << EOF
{
  "BRANCH": "${BRANCH}",
  "FEATURE_DIR": "${ABS_FEATURE_DIR}",
  "AVAILABLE_DOCS": ${DOCS_JSON}
}
EOF
else
    echo "Branch: ${BRANCH}"
    echo "Feature Dir: ${ABS_FEATURE_DIR}"
    echo "Available Docs: ${AVAILABLE_DOCS[*]}"
fi
