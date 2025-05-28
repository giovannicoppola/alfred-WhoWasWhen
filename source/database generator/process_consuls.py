#!/usr/bin/env python3
"""
Process consuls.tsv file to assign ruler IDs according to specific rules.

This script reads consuls.tsv and creates consuls_IDs.tsv with the following logic:
1. If ruler ID is empty, consul doesn't end with Roman numerals, and unique = x: assign new progressive ruler ID starting at 1016
2. If ruler ID is empty, consul ends with Roman numerals, and unique = x: add "inconsistent" to notes
3. If ruler ID is empty, consul ends with Roman numerals, and unique = n: find previous consul without numerals and use their ruler ID and wikipedia link
4. If ruler ID is empty, consul doesn't end with Roman numerals, and unique = n: add "inconsistent" to notes
"""

import csv
import re
import sys

def has_roman_numeral_suffix(name):
    """Check if a name ends with Roman numerals like ' I', ' II', ' III', etc."""
    # Pattern to match Roman numerals at the end of a string
    # Matches patterns like " I", " II", " III", " IV", " V", etc.
    pattern = r' [IVX]+$'
    return bool(re.search(pattern, name))

def get_base_name(name):
    """Get the base name without Roman numeral suffix."""
    # Remove Roman numeral suffix to get base name
    pattern = r' [IVX]+$'
    return re.sub(pattern, '', name)

def process_consuls_file(input_filename, output_filename):
    """Process the consuls TSV file according to the specified rules."""
    
    # Track assigned ruler IDs
    next_ruler_id = 1016
    
    # Dictionary to store base name -> ruler info mapping
    base_name_to_ruler = {}
    
    # Store all rows for processing
    rows = []
    
    # Read the input file
    with open(input_filename, 'r', encoding='utf-8') as infile:
        # Use tab as delimiter
        reader = csv.DictReader(infile, delimiter='\t')
        
        # Store all rows for processing
        for row in reader:
            rows.append(row)
    
    # Process each row
    for i, row in enumerate(rows):
        consul = row['consul'].strip()
        unique = row['Unique'].strip().lower()
        ruler_id = row['Ruler ID'].strip()
        wikipedia_link = row['wikipedia link'].strip()
        notes = row['notes'].strip()
        
        # Skip if ruler ID is already filled
        if ruler_id:
            # If this is a unique consul without Roman numerals, store for future reference
            if unique == 'x' and not has_roman_numeral_suffix(consul):
                base_name_to_ruler[consul] = {
                    'ruler_id': ruler_id,
                    'wikipedia_link': wikipedia_link
                }
            continue
        
        # Process based on the rules
        has_numerals = has_roman_numeral_suffix(consul)
        
        if unique == 'x':  # Unique = x
            if not has_numerals:
                # Rule 1: Assign new progressive ruler ID
                row['Ruler ID'] = str(next_ruler_id)
                # Store this for future reference
                base_name_to_ruler[consul] = {
                    'ruler_id': str(next_ruler_id),
                    'wikipedia_link': wikipedia_link
                }
                next_ruler_id += 1
                print(f"Assigned ruler ID {row['Ruler ID']} to {consul}")
            else:
                # Rule 2: Add "inconsistent" to notes
                if notes:
                    row['notes'] = notes + '; inconsistent'
                else:
                    row['notes'] = 'inconsistent'
                print(f"Added 'inconsistent' to notes for {consul}")
        
        else:  # unique = n
            if has_numerals:
                # Rule 3: Find previous consul without Roman numerals
                base_name = get_base_name(consul)
                
                if base_name in base_name_to_ruler:
                    # Found matching base name
                    previous_ruler = base_name_to_ruler[base_name]
                    row['Ruler ID'] = previous_ruler['ruler_id']
                    
                    # Handle wikipedia link
                    if wikipedia_link and wikipedia_link != previous_ruler['wikipedia_link']:
                        # Current wikipedia link doesn't match
                        if notes:
                            row['notes'] = notes + '; inconsistent wikipedia'
                        else:
                            row['notes'] = 'inconsistent wikipedia'
                        # Keep current wikipedia link
                    else:
                        # Use previous wikipedia link if current is empty or matches
                        row['wikipedia link'] = previous_ruler['wikipedia_link']
                    
                    print(f"Assigned ruler ID {row['Ruler ID']} to {consul} (from {base_name})")
                else:
                    # No matching base name found - this shouldn't happen normally
                    if notes:
                        row['notes'] = notes + '; inconsistent - no base name found'
                    else:
                        row['notes'] = 'inconsistent - no base name found'
                    print(f"Warning: No base name found for {consul} (base: {base_name})")
            else:
                # Rule 4: Add "inconsistent" to notes
                if notes:
                    row['notes'] = notes + '; inconsistent'
                else:
                    row['notes'] = 'inconsistent'
                print(f"Added 'inconsistent' to notes for {consul} (unique=n, no numerals)")
    
    # Write the output file
    with open(output_filename, 'w', encoding='utf-8', newline='') as outfile:
        if rows:
            fieldnames = rows[0].keys()
            writer = csv.DictWriter(outfile, fieldnames=fieldnames, delimiter='\t')
            writer.writeheader()
            writer.writerows(rows)
    
    print(f"\nProcessing complete. Output written to {output_filename}")
    print(f"Next available ruler ID: {next_ruler_id}")

def main():
    """Main function to run the processing."""
    input_filename = 'consuls.tsv'
    output_filename = 'consuls_IDs.tsv'
    
    try:
        process_consuls_file(input_filename, output_filename)
    except FileNotFoundError:
        print(f"Error: File {input_filename} not found.")
        sys.exit(1)
    except Exception as e:
        print(f"Error processing file: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 