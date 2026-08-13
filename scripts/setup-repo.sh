#!/bin/sh
# malosound — one-time setup for a fresh clone (macOS / Linux side of the rig).
# Windows: scripts/setup-repo.ps1
#
# Git does not version core.hooksPath, so the pre-commit hook has to be switched
# on once per clone, on every machine.

set -eu
cd "$(dirname "$0")/.."

printf '\nmalosound — repo setup\n\n'

git config core.hooksPath .githooks
chmod +x .githooks/* 2>/dev/null || true
printf '  [ok]   pre-commit hook enabled (core.hooksPath = .githooks)\n'
printf '         Blocks unfrozen .amxd, audio bytes, and >20 MB files.\n'

git config core.autocrlf false
printf '  [ok]   core.autocrlf = false (.gitattributes decides)\n'

if git config user.name >/dev/null && git config user.email >/dev/null; then
    printf '  [ok]   identity: %s <%s>\n' "$(git config user.name)" "$(git config user.email)"
else
    printf '  [warn] git user.name / user.email not set\n'
fi

for tool in cmake node; do
    if command -v "$tool" >/dev/null 2>&1; then
        printf '  [ok]   %s found\n' "$tool"
    else
        printf '  [warn] %s not found\n' "$tool"
    fi
done

printf '\n  Building the analysis core:\n'
printf '      cmake -S dsp -B dsp/build && cmake --build dsp/build\n'
printf '      ctest --test-dir dsp/build --output-on-failure\n'

printf '\ndone. Next: docs/START_HERE.md\n\n'
