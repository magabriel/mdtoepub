#!/bin/bash
set -uo pipefail

# bump_version.sh — Update version across all project files and create git tag.
#
# Usage:
#   ./bump_version.sh          # Interactive mode
#   ./bump_version.sh 1.4.0    # Use specified version

PYPROJECT="pyproject.toml"
METAINFO="data/com.github.mdtoepub.metainfo.xml"
VERSION_PY="mdtoepub/_version.py"

# ── Read current version ──────────────────────────────────────────────

get_current_version() {
    grep '^version' "$PYPROJECT" | head -1 | cut -d'"' -f2
}

CURRENT=$(get_current_version)
echo "Current version: $CURRENT"

# ── Parse SemVer components ───────────────────────────────────────────

IFS='.' read -r MAJOR MINOR PATCH <<< "$CURRENT"

# ── Propose alternatives ──────────────────────────────────────────────

propose_versions() {
    local maj=$1 min=$2 pat=$3
    echo ""
    echo "Proposed versions (Semantic Versioning):"
    echo "  1) $maj.$min.$((pat + 1))   (PATCH — bug fixes)"
    echo "  2) $maj.$((min + 1)).0   (MINOR — new features, backwards-compatible)"
    echo "  3) $((maj + 1)).0.0   (MAJOR — breaking changes)"
}

# ── Validate version ──────────────────────────────────────────────────

version_gt() {
    # Returns 0 (true) if $1 > $2
    local IFS='.'
    local -a v1=($1) v2=($2)
    for i in 0 1 2; do
        local a=${v1[$i]:-0} b=${v2[$i]:-0}
        if (( a > b )); then return 0; fi
        if (( a < b )); then return 1; fi
    done
    return 1
}

validate_version() {
    local ver=$1
    if ! [[ "$ver" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        echo "ERROR: Invalid version format '$ver'. Expected MAJOR.MINOR.PATCH (e.g. 1.4.0)"
        return 1
    fi
    if ! version_gt "$ver" "$CURRENT"; then
        echo "WARNING: Version '$ver' is not greater than current '$CURRENT'."
        read -rp "Continue anyway? [y/N] " yn
        if [[ "$yn" != [yY] ]]; then
            return 1
        fi
    fi
    return 0
}

# ── Get target version ────────────────────────────────────────────────

if [[ -n "${1:-}" ]]; then
    NEW_VERSION="$1"
else
    propose_versions "$MAJOR" "$MINOR" "$PATCH"
    echo ""
    read -rp "Enter new version (or number 1-3): " choice
    case "$choice" in
        1) NEW_VERSION="$MAJOR.$MINOR.$((PATCH + 1))" ;;
        2) NEW_VERSION="$MAJOR.$((MINOR + 1)).0" ;;
        3) NEW_VERSION="$((MAJOR + 1)).0.0" ;;
        *) NEW_VERSION="$choice" ;;
    esac
fi

validate_version "$NEW_VERSION" || exit 1

echo ""
echo "Bumping version: $CURRENT → $NEW_VERSION"
echo ""

# ── Update pyproject.toml ─────────────────────────────────────────────

sed -i "s|^version = \"$CURRENT\"|version = \"$NEW_VERSION\"|" "$PYPROJECT"
echo "  ✓ $PYPROJECT"

# ── Update metainfo.xml ──────────────────────────────────────────────

TODAY=$(date +%Y-%m-%d)
sed -i "s|<release version=\"$CURRENT\" date=\"[^\"]*\"|<release version=\"$NEW_VERSION\" date=\"$TODAY\"|" "$METAINFO"
echo "  ✓ $METAINFO"

# ── Update _version.py ──────────────────────────────────────────────

echo "__version__ = \"$NEW_VERSION\"" > "$VERSION_PY"
echo "  ✓ $VERSION_PY"

# ── Run tests ─────────────────────────────────────────────────────────

echo ""
echo "Running tests..."
if python3 -m pytest tests/ -x -q 2>&1; then
    echo "  ✓ Tests passed"
else
    echo "  ✗ Tests FAILED — reverting changes"
    git checkout -- "$PYPROJECT" "$METAINFO"
    git checkout -- "$VERSION_PY" 2>/dev/null || true
    exit 1
fi

# ── Git commit and tag ────────────────────────────────────────────────

echo ""
read -rp "Commit and tag v$NEW_VERSION? [Y/n] " yn
if [[ "$yn" == [nN] ]]; then
    echo "Changes saved but not committed."
    exit 0
fi

git add "$PYPROJECT" "$METAINFO" "$VERSION_PY"
git commit -m "Bump version to $NEW_VERSION"
git tag -a "v$NEW_VERSION" -m "v$NEW_VERSION"
echo ""
echo "  ✓ Committed and tagged v$NEW_VERSION"
echo ""

read -rp "Push branch and tag to origin? [Y/n] " yn_push
if [[ "$yn_push" != [nN] ]]; then
    git push origin HEAD
    git push origin "v$NEW_VERSION"
    echo ""
    echo "  ✓ Pushed branch and tag v$NEW_VERSION to origin"
    echo ""
else
    echo "  Skipped push. To push manually later:"
    echo "    git push origin HEAD"
    echo "    git push origin v$NEW_VERSION"
    echo ""
fi

echo "Next steps:"
echo "  ./build.sh all          # Build flatpak bundle"
echo "  ./build.sh install-local # Install locally"
