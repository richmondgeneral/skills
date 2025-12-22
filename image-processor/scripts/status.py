#!/usr/bin/env python3
"""
Model status CLI.

Usage:
  python status.py
  python status.py --json
"""
import argparse
import sys
import os

# Add lib to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))

from router import create_default_router


def main():
    parser = argparse.ArgumentParser(description='Check model status')
    parser.add_argument('--json', action='store_true', help='Output JSON')

    args = parser.parse_args()

    router = create_default_router()
    status = router.get_model_status()

    if args.json:
        import json
        print(json.dumps(status, indent=2))
    else:
        print("Model Health:\n")
        for model_name, info in status.items():
            health = "OK" if info['healthy'] else "NO API KEY"
            caps = info['capabilities']
            tasks = ', '.join(caps['tasks'])
            cost = 'Free' if caps['cost'] == 'free' else f"${caps['cost_per_image']}/img"

            print(f"  {model_name}")
            print(f"    Status: {health}")
            print(f"    Tasks: {tasks}")
            print(f"    Quality: {caps['quality_score']:.0%} | Avg Time: {caps['avg_time']:.1f}s | Cost: {cost}")
            print()


if __name__ == '__main__':
    main()
