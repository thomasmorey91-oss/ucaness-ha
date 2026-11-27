#!/bin/sh
# Détourage automatique de la photo du véhicule (carte custom:ucaness-vehicle-card), facultatif.
#
# Télécharge dans dashboard/www/ucaness/detourage/ :
#   - u2netp.onnx (4,6 Mo) : modèle U²-Net réduit, licence Apache-2.0 (https://github.com/xuebinqin/U-2-Net),
#     copie publiée par le projet rembg (https://github.com/danielgatis/rembg) ;
#   - onnxruntime-web 1.31.1 (≈ 15 Mo), licence MIT (https://github.com/microsoft/onnxruntime).
# Chaque fichier est vérifié par son empreinte SHA-256. Copier ensuite le dossier www/ucaness/detourage/
# dans /config/www/ucaness/detourage/ du Home Assistant.
#
# Le détourage tourne dans le navigateur : la photo n'est envoyée qu'à Home Assistant.
# Sans ces fichiers, la carte propose un détourage simple (fond uni).
set -eu
cd "$(dirname "$0")/../.."
DEST=dashboard/www/ucaness/detourage
mkdir -p "$DEST"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

verifier() {   # fichier empreinte
  echo "$2  $1" | sha256sum -c - >/dev/null || { echo "Empreinte incorrecte : $1" >&2; exit 1; }
}

curl -fsSL -o "$TMP/u2netp.onnx" https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2netp.onnx
verifier "$TMP/u2netp.onnx" 309c8469258dda742793dce0ebea8e6dd393174f89934733ecc8b14c76f4ddd8

curl -fsSL -o "$TMP/ort.tgz" https://registry.npmjs.org/onnxruntime-web/-/onnxruntime-web-1.31.1.tgz
tar -xzf "$TMP/ort.tgz" -C "$TMP" package/dist/ort.wasm.min.mjs package/dist/ort-wasm-simd-threaded.mjs \
  package/dist/ort-wasm-simd-threaded.wasm
verifier "$TMP/package/dist/ort.wasm.min.mjs" c21d9c326d453a4a61398270c804d5979e118540597cb0c07f7b3d64e6098234
verifier "$TMP/package/dist/ort-wasm-simd-threaded.mjs" 30ed0b5cd1182ede931fea448afb567d4dc705ec957af09f108a2be5f770dac3
verifier "$TMP/package/dist/ort-wasm-simd-threaded.wasm" 4b884c203b0fa48d057be3332c65513ff85aa3c5bddd6946acc0fab7ecda001d

cp "$TMP/u2netp.onnx" "$TMP"/package/dist/ort.wasm.min.mjs "$TMP"/package/dist/ort-wasm-simd-threaded.mjs \
  "$TMP"/package/dist/ort-wasm-simd-threaded.wasm "$DEST/"
printf '%s\n' "onnxruntime-web 1.31.1 : © Microsoft Corporation, licence MIT, https://github.com/microsoft/onnxruntime/blob/main/LICENSE" > "$DEST/LICENCE-onnxruntime.txt"
printf '%s\n' "u2netp.onnx : U²-Net (Qin et al., 2020), licence Apache-2.0, https://github.com/xuebinqin/U-2-Net" > "$DEST/LICENCE-u2netp.txt"
echo "Détourage installé dans $DEST ($(du -sh "$DEST" | cut -f1))."
