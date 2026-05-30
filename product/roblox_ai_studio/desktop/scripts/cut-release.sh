#!/usr/bin/env bash

set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
DESKTOP_DIR="$(dirname "$DIR")"
cd "$DESKTOP_DIR"

VERSION=$(node -p "require('./package.json').version" | tr -d '\r')
EXPECTED_TAG="desktop-v$VERSION"

if [ "$1" = "--prod" ]; then
  echo "Cutting commercial prod release for $VERSION..."
  export PLAYRO_RELEASE_CHANNEL=prod
else
  echo "Cutting test release for $VERSION..."
  export PLAYRO_RELEASE_CHANNEL=test
  EXPECTED_TAG="$EXPECTED_TAG-test"
fi

echo "1. Validating package layout and build..."
npm run verify:packaged

echo "2. Generating manifest and release notes..."
npm run release:manifest
npm run release:notes

echo "3. Running sell-readiness gate..."
npm run release:sell-check

echo "--------------------------------------------------------"
echo "RELEASE READY: $EXPECTED_TAG"
echo "--------------------------------------------------------"
echo "To publish this release to GitHub:"
echo ""
echo "  cd product/roblox_ai_studio/desktop"
echo "  gh release create \"$EXPECTED_TAG\" \\"
echo "    --title \"Playro v$VERSION\" \\"
echo "    --notes-file release/RELEASE_NOTES_v$VERSION.md \\"
echo "    \"dist/Playro Setup $VERSION.exe\" \\"
echo "    \"dist/Playro $VERSION.exe\" \\"
echo "    \"dist/release-manifest-v$VERSION.json\""
echo ""
echo "If this is a pre-release, append '--prerelease' to the gh command."
echo "If gh is not installed, manually create $EXPECTED_TAG on GitHub and upload the 3 files."
