#!/usr/bin/env python3
"""
AI catalog-image cleanup / inpaint CLI.

One universal prompt produces a clean storefront-ready catalog photo from
any source image. Damage is preserved by default (documentary truth for
appraisal/provenance); --fix-damage swaps in restoration; --both produces
two outputs side-by-side.

Examples:
  clean.py -i photo.jpg -o cleaned.jpg                    # default: preserve damage
  clean.py -i photo.jpg -o cleaned.jpg --fix-damage       # restoration mode
  clean.py -i photo.jpg -o cleaned.jpg --both             # two outputs (-preserved/-fixed)
  clean.py -i photo.jpg -o cleaned.jpg --pro              # gemini-3-pro-image-preview (~$2.13)
  clean.py -i photo.jpg -o cleaned.jpg --remove "the dust on the rim"

Prompt sections live in ../lib/cleanup_prompts.md so the (future) Cowork
Cloudinary path can read the same prompt verbatim.
"""
import argparse
import json
import os
import re
import shutil
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))

from PIL import Image  # noqa: E402

from models import TaskConfig  # noqa: E402
from router import create_default_router  # noqa: E402


PROMPTS_FILE = Path(__file__).resolve().parent.parent / 'lib' / 'cleanup_prompts.md'
MODEL_PRO = "gemini-3-pro-image-preview"
DEFAULT_MAX_LONG_EDGE = 2048


def maybe_downscale(input_path: Path, max_long_edge: int = DEFAULT_MAX_LONG_EDGE) -> Path:
    """Downscale source to max_long_edge if larger; return new (or original) path.

    Gemini downsamples to ~2048px internally anyway, so pre-shrinking trims
    upload time and input tokens without changing output quality. A value of
    0 disables downscaling entirely.
    """
    if max_long_edge <= 0:
        return input_path
    with Image.open(input_path) as im:
        w, h = im.size
        if max(w, h) <= max_long_edge:
            return input_path
        scale = max_long_edge / max(w, h)
        new_w = round(w * scale)
        new_h = round(h * scale)
        resized = im.resize((new_w, new_h), Image.LANCZOS)
        ext = input_path.suffix or '.png'
        tmp = Path(tempfile.gettempdir()) / f"{input_path.stem}-ds{max_long_edge}{ext}"
        save_kwargs = {}
        if ext.lower() in ('.jpg', '.jpeg'):
            save_kwargs['quality'] = 95
            if resized.mode in ('RGBA', 'P'):
                resized = resized.convert('RGB')
        resized.save(tmp, **save_kwargs)
        return tmp


def _read_size(path: Path) -> tuple[int, int]:
    with Image.open(path) as im:
        return im.size


def load_sections():
    """Parse cleanup_prompts.md into {section_name: body}.

    Format: H2 headings mark section boundaries. Body = lines between this
    H2 and the next. Block comments (lines starting with '<!--') are stripped.
    """
    if not PROMPTS_FILE.exists():
        raise SystemExit(f"prompts file missing: {PROMPTS_FILE}")

    sections = {}
    current = None
    buf = []
    in_block = False
    for line in PROMPTS_FILE.read_text(encoding='utf-8').splitlines():
        stripped = line.lstrip()
        if in_block:
            if '-->' in stripped:
                in_block = False
            continue
        if stripped.startswith('<!--'):
            if '-->' not in stripped:
                in_block = True
            continue
        m = re.match(r'^##\s+(\S.*?)\s*$', line)
        if m:
            if current is not None:
                sections[current] = '\n'.join(buf).strip()
            current = m.group(1).strip()
            buf = []
        elif current is not None:
            buf.append(line)
    if current is not None:
        sections[current] = '\n'.join(buf).strip()
    return sections


def build_prompt(sections, fix_damage: bool, extra: str = "") -> str:
    """Compose final prompt: base + damage clause [+ extra]."""
    base = sections.get('base')
    damage = sections.get('damage-fix' if fix_damage else 'damage-preserve')
    if not base or not damage:
        raise SystemExit("cleanup_prompts.md missing 'base' or damage sections")
    parts = [base, damage]
    if extra:
        parts.append(f"Additional direction: {extra}")
    return "\n\n".join(parts)


def run_one(input_path: Path, output_path: Path, instruction: str,
            quality: str, verbose: bool) -> dict:
    """Single cleanup call. Returns dict with success/model/time/output/error."""
    task_config = TaskConfig.for_edit(
        instruction=instruction,
        output_path=str(output_path),
        quality=quality,
        references=[],
    )
    router = create_default_router()
    if verbose:
        print(f"  → {output_path.name}  (model: "
              f"{os.environ.get('GEMINI_IMAGE_MODEL', 'flash-default')})",
              file=sys.stderr)
    t0 = time.time()
    result = router.process(str(input_path), task_config)
    elapsed = time.time() - t0
    return {
        'success': result.success,
        'model': result.model_used,
        'output_path': result.output_path,
        'processing_time': elapsed,
        'error': result.error if not result.success else None,
    }


def with_suffix(path: Path, suffix: str) -> Path:
    """foo.jpg + 'preserved' -> foo-preserved.jpg"""
    return path.with_name(f"{path.stem}-{suffix}{path.suffix}")


def main():
    parser = argparse.ArgumentParser(
        description="AI catalog-image cleanup (Gemini).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument('--input', '-i', required=True, help='Input image path')
    parser.add_argument('--output', '-o', required=True,
                        help='Output image path (with --both: produces -preserved/-fixed variants)')
    parser.add_argument('--fix-damage', action='store_true',
                        help='Repair visible damage as part of cleanup (default: preserve)')
    parser.add_argument('--both', action='store_true',
                        help='Produce both preserved-damage and damage-fixed versions')
    parser.add_argument('--pro', action='store_true',
                        help='Use gemini-3-pro-image-preview (~$2.13/call vs ~$0.57)')
    parser.add_argument('--remove', '-r', dest='extra',
                        help='Freeform additional direction appended to the prompt')
    parser.add_argument('--quality', '-q', default='auto',
                        choices=['auto', 'fast', 'pro'])
    parser.add_argument('--max-long-edge', type=int, default=DEFAULT_MAX_LONG_EDGE,
                        metavar='N',
                        help=f'Downscale input so long edge ≤ N before sending to Gemini '
                             f'(default: {DEFAULT_MAX_LONG_EDGE}; 0 disables). Gemini downsamples '
                             f'to ~2048 internally, so pre-shrinking cuts upload time without '
                             f'affecting output quality.')
    parser.add_argument('--no-downscale', action='store_true',
                        help='Alias for --max-long-edge 0')
    parser.add_argument('--json', action='store_true', help='Emit JSON result')
    parser.add_argument('--verbose', '-v', action='store_true')
    args = parser.parse_args()

    if args.both and args.fix_damage:
        parser.error('--both already produces both versions; --fix-damage is redundant')

    if not os.path.exists(args.input):
        print(f"Error: input image not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    sections = load_sections()
    if args.pro:
        os.environ['GEMINI_IMAGE_MODEL'] = MODEL_PRO

    max_long_edge = 0 if args.no_downscale else args.max_long_edge
    source_path = Path(args.input)
    orig_w, orig_h = _read_size(source_path)
    effective_input = maybe_downscale(source_path, max_long_edge=max_long_edge)
    if effective_input != source_path:
        ds_w, ds_h = _read_size(effective_input)
        downscaled_to = f"{ds_w}x{ds_h}"
        pct = round((ds_w * ds_h - orig_w * orig_h) / (orig_w * orig_h) * 100)
    else:
        ds_w = ds_h = None
        downscaled_to = None
        pct = 0

    output_path = Path(args.output)
    runs = []

    if args.both:
        preserved_path = with_suffix(output_path, 'preserved')
        fixed_path = with_suffix(output_path, 'fixed')
        runs.append(('preserved', preserved_path, False))
        runs.append(('fixed', fixed_path, True))
    else:
        runs.append(('single', output_path, args.fix_damage))

    if args.verbose:
        print(f"Input: {args.input}", file=sys.stderr)
        if downscaled_to:
            print(f"Scale: downscaled {orig_w}x{orig_h} → {ds_w}x{ds_h} ({pct}%)",
                  file=sys.stderr)
        elif max_long_edge > 0:
            print(f"Scale: source ≤ {max_long_edge}px, no downscale", file=sys.stderr)
        else:
            print("Scale: downscaling disabled", file=sys.stderr)
        print(f"Mode:  {'both' if args.both else ('fix-damage' if args.fix_damage else 'preserve-damage')}",
              file=sys.stderr)
        print(f"Model: {'pro (gemini-3-pro-image-preview)' if args.pro else 'flash (gemini-3.1-flash-image-preview)'}",
              file=sys.stderr)
        if args.extra:
            print(f"Extra: {args.extra}", file=sys.stderr)

    results = []
    for tag, out_path, fix in runs:
        instruction = build_prompt(sections, fix_damage=fix, extra=args.extra or "")
        if args.verbose:
            print(f"\n[{tag}] processing...", file=sys.stderr)
        r = run_one(effective_input, out_path, instruction, args.quality, args.verbose)
        r['variant'] = tag
        r['downscaled_to'] = downscaled_to
        results.append(r)
        if not r['success']:
            break  # don't run --both's second pass if first failed

    overall_ok = all(r['success'] for r in results)

    if args.json:
        payload = {
            'success': overall_ok,
            'mode': 'both' if args.both else ('fix-damage' if args.fix_damage else 'preserve-damage'),
            'model_class': 'pro' if args.pro else 'flash',
            'input_image': args.input,
            'results': results,
        }
        print(json.dumps(payload, indent=2))
    else:
        for r in results:
            label = r['variant']
            if r['success']:
                print(f"  [{label}] {r['output_path']}  "
                      f"({r['model']}, {r['processing_time']:.1f}s)")
            else:
                print(f"  [{label}] FAILED: {r['error']}", file=sys.stderr)

    sys.exit(0 if overall_ok else 1)


if __name__ == '__main__':
    main()
