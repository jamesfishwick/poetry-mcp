#!/bin/bash
# setup-plan.sh - Set up planning context for current feature branch
# Usage: ./setup-plan.sh [--json]

set -e

JSON_OUTPUT=false
if [[ "$1" == "--json" ]]; then
    JSON_OUTPUT=true
fi

# Get current branch
BRANCH=$(git branch --show-current)

# Extract feature number and name from branch
if [[ ! "$BRANCH" =~ ^[0-9]+- ]]; then
    echo "Error: Not on a feature branch (expected format: N-feature-name)" >&2
    exit 1
fi

FEATURE_NUMBER=$(echo "$BRANCH" | grep -oE '^[0-9]+')
SHORT_NAME=$(echo "$BRANCH" | sed 's/^[0-9]*-//')

# Set paths
SPECS_DIR="specs/${BRANCH}"
FEATURE_SPEC="${SPECS_DIR}/spec.md"
IMPL_PLAN="${SPECS_DIR}/plan.md"

# Verify spec exists
if [[ ! -f "$FEATURE_SPEC" ]]; then
    echo "Error: Feature spec not found at ${FEATURE_SPEC}" >&2
    exit 1
fi

# Create plan.md if it doesn't exist
if [[ ! -f "$IMPL_PLAN" ]]; then
    cat > "$IMPL_PLAN" << 'EOF'
# Implementation Plan

## Technical Context

[To be filled during planning]

## Constitution Check

[To be filled during planning]

## Research Findings

See research.md

## Data Model

See data-model.md

## Implementation Phases

[To be filled during planning]
EOF
fi

# Output result
if [[ "$JSON_OUTPUT" == "true" ]]; then
    cat << EOF
{
  "BRANCH": "${BRANCH}",
  "FEATURE_NUMBER": ${FEATURE_NUMBER},
  "SHORT_NAME": "${SHORT_NAME}",
  "SPECS_DIR": "${SPECS_DIR}",
  "FEATURE_SPEC": "${FEATURE_SPEC}",
  "IMPL_PLAN": "${IMPL_PLAN}"
}
EOF
else
    echo "Branch: ${BRANCH}"
    echo "Spec: ${FEATURE_SPEC}"
    echo "Plan: ${IMPL_PLAN}"
fi
