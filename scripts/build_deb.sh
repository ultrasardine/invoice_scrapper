#!/usr/bin/env bash
set -euo pipefail

APP_NAME="InvoiceScrapper"
PKG_NAME="invoice-scrapper"
VERSION="${1:-}"
ARCH="amd64"

if [[ -z "$VERSION" ]]; then
  echo "Usage: $0 <version>" >&2
  exit 1
fi

BIN_PATH="dist/linux/${APP_NAME}"
if [[ ! -f "$BIN_PATH" ]]; then
  echo "Expected binary not found at ${BIN_PATH}" >&2
  exit 1
fi

WORK_ROOT="dist/linux-deb"
PKG_ROOT="${WORK_ROOT}/pkgroot"
OUT_FILE="${WORK_ROOT}/${PKG_NAME}_${VERSION}_${ARCH}.deb"

rm -rf "$PKG_ROOT"
mkdir -p "${PKG_ROOT}/opt/${APP_NAME}" "${PKG_ROOT}/usr/bin" "${PKG_ROOT}/DEBIAN"

cp "$BIN_PATH" "${PKG_ROOT}/opt/${APP_NAME}/${APP_NAME}"
chmod 755 "${PKG_ROOT}/opt/${APP_NAME}/${APP_NAME}"
ln -sf "/opt/${APP_NAME}/${APP_NAME}" "${PKG_ROOT}/usr/bin/invoicescrapper"

cat > "${PKG_ROOT}/DEBIAN/control" <<EOF
Package: ${PKG_NAME}
Version: ${VERSION}
Section: utils
Priority: optional
Architecture: ${ARCH}
Maintainer: Invoice Scrapper <maintainer@example.com>
Description: Desktop app to extract invoice data from Portuguese PDFs and export to Excel.
EOF

dpkg-deb --build "$PKG_ROOT" "$OUT_FILE"
echo "$OUT_FILE"

