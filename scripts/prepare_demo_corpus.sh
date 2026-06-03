#!/usr/bin/env bash
set -euo pipefail

rm -rf state sandbox usage.json
mkdir -p state sandbox
cp -R demo_corpus/papers sandbox/papers
cp -R demo_corpus/custom sandbox/corpus

echo "Prepared demo sandbox:"
find sandbox -maxdepth 2 -type f | sort
