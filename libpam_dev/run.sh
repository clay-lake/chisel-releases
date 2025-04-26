#!/bin/bash

# Set the output directory for the root filesystem
OUTPUT_DIR="$(dirname "$0")"

function rel_find() {
    local dir="$1"
    shift

    pushd "$dir" > /dev/null 
    find . "$@"

    popd > /dev/null 
}

echo "Creating baseline rootfs..."
if test -d "$OUTPUT_DIR/baseline"
then
    echo "Directory baseline rootfs already exists. Skipping creation."
else
    mkdir -p $_
    chisel cut --release "ubuntu-24.10" --root "$_" libpam-runtime_config 
fi

echo "Creating Current rootfs..."
rm -rf "$OUTPUT_DIR/current"
mkdir -p $_
chisel cut --release "$OUTPUT_DIR/.." --root "$_" libpam-runtime_config 

echo "Comparing rootfs structure..."
if diff <(rel_find "$OUTPUT_DIR/baseline") <(rel_find "$OUTPUT_DIR/current")
then
    echo "Pass: rootfs structure match."
else
    echo "Fail: rootfs differences found."
    exit 1
fi

echo "Comparing rootfs content..."
for file in $(rel_find "$OUTPUT_DIR/current" -type f)
do
    echo "Checking file: $file"
    if ! diff "$OUTPUT_DIR/baseline/$file" "$OUTPUT_DIR/current/$file"
    then
        echo "Fail: $file differs."
        exit 1
    fi
done
echo "Pass: rootfs content matches."