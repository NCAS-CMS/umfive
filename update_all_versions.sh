#!/bin/bash

# Starting file and version
current_file="umfive/data/STASH_to_CF.txt"
prev_v="10.2"

echo "Starting batch update..."

# Loop through major versions 10 to 14
for major in {10..14}; do
    # Loop through minor versions 0 to 9
    for minor in {0..9}; do

        # Skip versions before 10.3
        if [[ "$major" -eq 10 && "$minor" -lt 3 ]]; then
            continue
        fi

        new_v="${major}.${minor}"
        stashmaster="STASHmaster/vn${new_v}/STASHmaster_A"
        output_file="STASH_to_CF_vn${new_v}.txt"

        # Check if the STASHmaster file exists for this version
        if [[ -f "$stashmaster" ]]; then
	    echo ""
            echo "Processing version $new_v (Previous: $prev_v)..."
	    echo ""

            python3 update_stash_to_cf.py \
                --stashmaster "$stashmaster" \
                --stash-to-cf "$current_file" \
                --prev-version "$prev_v" \
                --new-version "$new_v" \
                --output "$output_file" \
                --skip-version-check

            # Update pointers for the next iteration
            current_file="$output_file"
            prev_v="$new_v"
        else
            echo "Skipping version $new_v (STASHmaster file not found)"
        fi

        # Stop once we reach 14.1
        if [[ "$major" -eq 14 && "$minor" -eq 1 ]]; then
            break 2
        fi
    done
done

echo "Finished! The final updated file is: $current_file"
