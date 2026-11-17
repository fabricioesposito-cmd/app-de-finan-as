#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
mkdir -p work
swiftc -module-cache-path work/swift-cache scripts/pdf_ocr.swift -o work/pdf-ocr
printf 'OCR local pronto.\n'
