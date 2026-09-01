#!/bin/sh

set -eu

if [ "$#" -ne 2 ]; then
    echo "Usage: $0 /path/to/ch341eeprom NEW_OUTPUT_DIRECTORY" >&2
    exit 1
fi

programmer=$1
output_dir=$2

if [ ! -x "$programmer" ]; then
    echo "ERROR: Programmer is not executable: $programmer" >&2
    exit 1
fi

if [ -e "$output_dir" ]; then
    echo "ERROR: Output path already exists: $output_dir" >&2
    exit 1
fi

mkdir -p "$output_dir"

check_size() {
    file=$1
    size=$(wc -c < "$file" | tr -d ' ')
    if [ "$size" -ne 16384 ]; then
        echo "ERROR: $file is $size bytes; expected 16384." >&2
        exit 2
    fi
}

index=1
while [ "$index" -le 3 ]; do
    output="$output_dir/read-0$index.bin"
    echo "Reading copy $index of 3 at the tool's standard speed..."
    "$programmer" -v -s 24c128 -r "$output"
    check_size "$output"
    index=$((index + 1))
done

echo "SHA-256:"
shasum -a 256 "$output_dir"/read-*.bin

if ! cmp -s "$output_dir/read-01.bin" "$output_dir/read-02.bin" || \
   ! cmp -s "$output_dir/read-01.bin" "$output_dir/read-03.bin"; then
    echo "ERROR: The three reads differ. Preserve them and do not write this chip." >&2
    exit 3
fi

chmod 444 "$output_dir"/read-*.bin
echo "SUCCESS: Three identical 16 KiB reads were preserved in $output_dir"
