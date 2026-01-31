#!/bin/bash
# create-new-feature.sh - Create a new feature branch and spec directory
# Usage: ./create-new-feature.sh [--json] [--number N] [--short-name "name"] "Feature description"

set -e

# Parse arguments
JSON_OUTPUT=false
FEATURE_NUMBER=""
SHORT_NAME=""
DESCRIPTION=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --json)
            JSON_OUTPUT=true
            shift
            ;;
        --number)
            FEATURE_NUMBER="$2"
            shift 2
            ;;
        --short-name)
            SHORT_NAME="$2"
            shift 2
            ;;
        *)
            DESCRIPTION="$1"
            shift
            ;;
    esac
done

if [[ -z "$DESCRIPTION" ]]; then
    echo "Error: Feature description is required" >&2
    exit 1
fi

if [[ -z "$SHORT_NAME" ]]; then
    echo "Error: --short-name is required" >&2
    exit 1
fi

if [[ -z "$FEATURE_NUMBER" ]]; then
    FEATURE_NUMBER=1
fi

# Create branch name
BRANCH_NAME="${FEATURE_NUMBER}-${SHORT_NAME}"
SPEC_DIR="specs/${BRANCH_NAME}"
SPEC_FILE="${SPEC_DIR}/spec.md"
CHECKLIST_DIR="${SPEC_DIR}/checklists"

# Check if branch already exists
if git show-ref --verify --quiet "refs/heads/${BRANCH_NAME}"; then
    echo "Error: Branch ${BRANCH_NAME} already exists" >&2
    exit 1
fi

# Create and checkout new branch
git checkout -b "${BRANCH_NAME}"

# Create spec directory structure
mkdir -p "${SPEC_DIR}"
mkdir -p "${CHECKLIST_DIR}"

# Copy template
TEMPLATE_FILE=".specify/templates/spec-template.md"
if [[ -f "$TEMPLATE_FILE" ]]; then
    cp "$TEMPLATE_FILE" "$SPEC_FILE"
else
    # Create minimal spec if template missing
    cat > "$SPEC_FILE" << 'EOF'
# Feature Specification

## Overview

**Created**: $(date +%Y-%m-%d)
**Status**: Draft

### Summary

[Feature description to be added]

## Functional Requirements

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| FR-1 | | |

## Success Criteria

| Criterion | Target | Measurement Method |
|-----------|--------|-------------------|
| | | |
EOF
fi

# Replace placeholders in spec
sed -i '' "s/\[FEATURE_NAME\]/${SHORT_NAME}/g" "$SPEC_FILE" 2>/dev/null || true
sed -i '' "s/\[SHORT_NAME\]/${SHORT_NAME}/g" "$SPEC_FILE" 2>/dev/null || true
sed -i '' "s/\[DATE\]/$(date +%Y-%m-%d)/g" "$SPEC_FILE" 2>/dev/null || true

# Output result
if [[ "$JSON_OUTPUT" == "true" ]]; then
    cat << EOF
{
  "BRANCH_NAME": "${BRANCH_NAME}",
  "SPEC_DIR": "${SPEC_DIR}",
  "SPEC_FILE": "${SPEC_FILE}",
  "CHECKLIST_DIR": "${CHECKLIST_DIR}",
  "FEATURE_NUMBER": ${FEATURE_NUMBER},
  "SHORT_NAME": "${SHORT_NAME}",
  "DESCRIPTION": "${DESCRIPTION}"
}
EOF
else
    echo "Created feature branch: ${BRANCH_NAME}"
    echo "Spec file: ${SPEC_FILE}"
    echo "Checklist directory: ${CHECKLIST_DIR}"
fi
