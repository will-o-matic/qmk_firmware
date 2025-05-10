#!/usr/bin/env python3
"""
QMK Combo Extractor for keymap-drawer

This script extracts combo definitions from a QMK keymap.c file and
outputs them in the format required by keymap-drawer.
"""

import re
import sys
import argparse
from typing import Dict, List, Tuple, Optional


def parse_combos(keymap_content: str) -> List[Tuple[str, List[str], str]]:
    """
    Parse combo definitions from keymap.c content.
    
    Args:
        keymap_content: The content of the keymap.c file
        
    Returns:
        A list of tuples containing (combo_name, [key1, key2, ...], result_key)
    """
    # Find combo variable definitions
    combo_var_pattern = re.compile(
        r'const\s+uint16_t\s+PROGMEM\s+(\w+)_combo\[\]\s*=\s*{([^}]+)}',
        re.MULTILINE
    )
    
    # Find combo array entries
    combo_array_pattern = re.compile(
        r'\[(\w+)\]\s*=\s*COMBO\((\w+)_combo,\s*([^)]+)\)',
        re.MULTILINE
    )
    
    # Extract combo variable definitions
    combo_vars = {}
    for match in combo_var_pattern.finditer(keymap_content):
        var_name = match.group(1)
        keys_str = match.group(2)
        # Extract keys, remove COMBO_END
        keys = [k.strip() for k in keys_str.split(',') if 'COMBO_END' not in k]
        combo_vars[var_name] = keys
    
    # Extract combo array entries
    combos = []
    for match in combo_array_pattern.finditer(keymap_content):
        combo_name = match.group(1)
        var_name = match.group(2)
        result_key = match.group(3).strip()
        
        if var_name in combo_vars:
            keys = combo_vars[var_name]
            combos.append((combo_name, keys, result_key))
    
    return combos


def clean_key_name(key: str) -> str:
    """
    Clean QMK key names to match keymap-drawer format.
    
    Args:
        key: QMK key name (e.g., KC_W)
        
    Returns:
        Cleaned key name for keymap-drawer (e.g., W)
    """
    # Special case for complex keycodes with parentheses
    if '(' in key and not key.endswith(')'):
        key = key + ')'
    
    # Handle special composite keycodes first
    special_cases = {
        'KC_QUOT': "'",
        'S(KC_QUOT)': '"',
        'S(KC_MINS)': '_',
        'CW_TOGG': 'Caps',
        'LARR': '->',
        'FARR': '=>',
        'BARR': '<-',
        'EPIP': '|>',
        'VIMS': ':w'
    }
    
    for k, v in special_cases.items():
        if key == k:
            return v
    
    # Remove common prefixes
    prefixes = ['KC_', 'QK_', 'MO_', 'LT_', 'OSM_']
    for prefix in prefixes:
        if key.startswith(prefix):
            key = key[len(prefix):]
    
    # Handle special cases
    key_map = {
        'COMM': ',',
        'DOT': '.',
        'SLSH': '/',
        'QUOT': "'",
        'LBRC': '[',
        'RBRC': ']',
        'SCLN': ';',
        'MINS': '-',
        'EQL': '=',
        'BSLS': '\\',
        'GRV': '`',
        'TAB': 'Tab'
    }
    
    # For complex keycodes like S(KC_QUOT), process them specially
    if '(' in key:
        # Extract the outer function and inner key
        match = re.match(r'([^(]+)\(([^)]+)\)', key)
        if match:
            func, inner_key = match.groups()
            # Clean the inner key
            inner_key_cleaned = inner_key
            for prefix in prefixes:
                if inner_key.startswith(prefix):
                    inner_key_cleaned = inner_key[len(prefix):]
            
            if inner_key_cleaned in key_map:
                inner_key_cleaned = key_map[inner_key_cleaned]
            
            return f"{func}({inner_key_cleaned})"
    
    if key in key_map:
        return key_map[key]
    
    return key


def yaml_escape(value: str) -> str:
    """
    Escape special characters for YAML output.
    
    Args:
        value: String to escape
        
    Returns:
        Escaped string for YAML
    """
    # Characters that need to be quoted in YAML
    special_chars = [',', '-', ':', '[', ']', '{', '}', '&', '*', '!', '|', '>', "'", '"', '%', '@', '`']
    
    if any(char in value for char in special_chars) or value.strip() == '':
        # Use single quotes and escape any single quotes in the value
        return f"'{value.replace("'", "''")}'"
    
    return value


def format_for_keymap_drawer(combos: List[Tuple[str, List[str], str]]) -> str:
    """
    Format the parsed combos for keymap-drawer.
    
    Args:
        combos: List of parsed combo tuples
        
    Returns:
        Formatted string for keymap-drawer
    """
    output = ["combos:"]
    
    for combo_name, keys, result_key in combos:
        # Clean up key names for keymap-drawer format
        clean_keys = [clean_key_name(k) for k in keys]
        clean_result = clean_key_name(result_key)
        
        # Escape special characters for YAML
        escaped_keys = [yaml_escape(k) for k in clean_keys]
        escaped_result = yaml_escape(clean_result)
        
        # Format according to keymap-drawer spec
        combo_line = f"  - tk: [{', '.join(escaped_keys)}]"
        combo_line += f"\n    key: {escaped_result}"
        combo_line += f"\n    layers: [Base]"  # Assuming all combos are on the Base layer
        output.append(combo_line)
    
    return "\n".join(output)


def main():
    """
    Main function to parse command-line arguments and process the keymap file.
    """
    parser = argparse.ArgumentParser(
        description="Extract combos from QMK keymap.c for keymap-drawer"
    )
    parser.add_argument(
        "keymap_file", 
        help="Path to the keymap.c file"
    )
    parser.add_argument(
        "-o", "--output", 
        help="Output file (default: stdout)"
    )
    parser.add_argument(
        "-l", "--layers",
        default="Base",
        help="Comma-separated list of layers for the combos (default: Base)"
    )
    
    args = parser.parse_args()
    
    try:
        with open(args.keymap_file, 'r', encoding='utf-8') as file:
            keymap_content = file.read()
    except IOError as e:
        print(f"Error reading keymap file: {e}", file=sys.stderr)
        sys.exit(1)
    
    combos = parse_combos(keymap_content)
    
    if not combos:
        print("No combos found in the keymap file.", file=sys.stderr)
        sys.exit(0)
    
    formatted_output = format_for_keymap_drawer(combos)
    
    if args.output:
        try:
            with open(args.output, 'w', encoding='utf-8') as file:
                file.write(formatted_output)
            print(f"Combo definitions written to {args.output}")
        except IOError as e:
            print(f"Error writing to output file: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        print(formatted_output)


if __name__ == "__main__":
    main()