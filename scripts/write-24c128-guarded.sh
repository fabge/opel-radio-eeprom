#!/bin/sh

set -eu

if [ "$#" -ne 4 ]; then
    echo "Usage: $0 /path/to/ch341eeprom EXPECTED_CURRENT_IMAGE TARGET_IMAGE NEW_RECORD_DIRECTORY" >&2
    exit 1
fi

programmer=$1
expected_current=$2
target=$3
record_dir=$4

if [ ! -x "$programmer" ]; then
    echo "ERROR: Programmer is not executable: $programmer" >&2
    exit 1
fi

check_size() {
    file=$1
    label=$2
    if [ ! -f "$file" ]; then
        echo "ERROR: Missing $label: $file" >&2
        exit 1
    fi
    size=$(wc -c < "$file" | tr -d ' ')
    if [ "$size" -ne 16384 ]; then
        echo "ERROR: $label is $size bytes; expected 16384." >&2
        exit 1
    fi
}

check_size "$expected_current" "expected current image"
check_size "$target" "target image"

if [ -e "$record_dir" ]; then
    echo "ERROR: Record path already exists: $record_dir" >&2
    exit 1
fi

mkdir -p "$record_dir"
expected_record="$record_dir/expected-current.bin"
target_record="$record_dir/intended-target.bin"
prewrite="$record_dir/prewrite-read.bin"
readback1="$record_dir/postwrite-read-01.bin"
readback2="$record_dir/postwrite-read-02.bin"

cp "$expected_current" "$expected_record"
cp "$target" "$target_record"
chmod 444 "$expected_record" "$target_record"

if cmp -s "$expected_record" "$target_record"; then
    echo "ERROR: Expected-current and target images are identical; no write is needed." >&2
    exit 1
fi

echo "Reading the seated chip before any write..."
"$programmer" -v -s 24c128 -r "$prewrite"
check_size "$prewrite" "pre-write read"

if ! cmp -s "$prewrite" "$expected_record"; then
    echo "ERROR: The seated chip does not exactly match the expected current image." >&2
    echo "No write was performed. Preserve: $prewrite" >&2
    exit 2
fi

echo "Verified current image SHA-256: $(shasum -a 256 "$prewrite" | awk '{print $1}')"
echo "Target image SHA-256:           $(shasum -a 256 "$target_record" | awk '{print $1}')"
echo "Review the selected images and physical chip identity now."
printf "Type WRITE VERIFIED 24C128 to authorize the complete-chip write: "
IFS= read -r confirmation
if [ "$confirmation" != "WRITE VERIFIED 24C128" ]; then
    echo "Cancelled. No write was performed."
    exit 1
fi

"$programmer" -v -s 24c128 -w "$target_record"

echo "Reading back copy 1 of 2..."
"$programmer" -v -s 24c128 -r "$readback1"
check_size "$readback1" "first readback"

echo "Reading back copy 2 of 2..."
"$programmer" -v -s 24c128 -r "$readback2"
check_size "$readback2" "second readback"

if ! cmp -s "$target_record" "$readback1" || \
   ! cmp -s "$target_record" "$readback2" || \
   ! cmp -s "$readback1" "$readback2"; then
    echo "ERROR: Post-write verification failed. Preserve $record_dir and do not install the chip." >&2
    exit 3
fi

chmod 444 "$prewrite" "$readback1" "$readback2"
echo "SUCCESS: Two complete readbacks match the target image exactly."
echo "Records: $record_dir"
