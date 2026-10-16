#!/usr/bin/env python3
"""Materialize independently installable platform skills into an empty output directory."""
import argparse
from pathlib import Path
import sys
from skill_sources import materialize

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--platform', choices=('gpt', 'grok'))
    args = parser.parse_args()
    try:
        entries = materialize(args.root, args.output, args.platform)
    except (ValueError, OSError) as exc:
        print(f'Build failed: {exc}', file=sys.stderr)
        return 1
    print('Built: ' + ', '.join(f'{p}/{n}' for p, n in entries))
    return 0

if __name__ == '__main__':
    sys.exit(main())
