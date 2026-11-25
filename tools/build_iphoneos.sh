#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
build=build/iphoneos
output=out/iphoneos

if [[ -e "$output" ]]; then
  printf 'Choose a clean checkout or move the previous %s directory.\n' "$output" >&2
  exit 1
fi

xcodebuild -version
xcrun --sdk iphoneos --show-sdk-path
cmake -S . -B "$build" -G Ninja \
  -DCMAKE_SYSTEM_NAME=iOS \
  -DCMAKE_OSX_SYSROOT=iphoneos \
  -DCMAKE_OSX_ARCHITECTURES=arm64 \
  -DCMAKE_OSX_DEPLOYMENT_TARGET=16.3 \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_XCODE_ATTRIBUTE_CODE_SIGNING_ALLOWED=NO
cmake --build "$build" --parallel 2
bundle="$build/PhoneOSProbe.app"
mkdir -p "$output"
python3 -u tools/inspect_macho.py "$bundle" | tee "$output/macho-inspection.txt"

app="$output/Payload/PhoneOSProbe.app"
mkdir -p "$app/Frameworks"
cp -p "$bundle/PhoneOSProbe" "$bundle/Info.plist" "$app/"
for name in ProbeBase ProbePlugin; do
  framework="$name.framework"
  mkdir "$app/Frameworks/$framework"
  cp -p "$bundle/Frameworks/$framework/$name" "$bundle/Frameworks/$framework/Info.plist" \
    "$app/Frameworks/$framework/"
done
ipa="$output/PhoneOSProbe-unsigned.ipa"
ditto -c -k --norsrc --keepParent "$output/Payload" "$ipa"
python3 -u tools/inspect_ipa.py "$ipa" "$bundle" | tee "$output/ipa-inspection.txt"
