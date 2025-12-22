#!/usr/bin/env python3
"""
Gemini Chat - Multi-model auto image processor.

Smart routing across Nano Banana Pro, Gemini 2.5 Flash, and remove.bg.
"""
import sys
import argparse
from pathlib import Path

from models import TaskConfig, NanaBananaModel, Gemini25FlashModel, RemoveBgModel
from router import ModelRouter


def setup_models():
    """Initialize all available models."""
    models = []
    
    # Try to initialize each model
    try:
        nano = NanaBananaModel()
        if nano.health_check():
            models.append(nano)
    except Exception as e:
        print(f"⚠️  Nano Banana Pro unavailable: {e}", file=sys.stderr)
    
    try:
        gemini25 = Gemini25FlashModel()
        if gemini25.health_check():
            models.append(gemini25)
    except Exception as e:
        print(f"⚠️  Gemini 2.5 Flash unavailable: {e}", file=sys.stderr)
    
    try:
        removebg = RemoveBgModel()
        if removebg.health_check():
            models.append(removebg)
    except Exception as e:
        print(f"⚠️  remove.bg unavailable: {e}", file=sys.stderr)
    
    if not models:
        print("❌ No models available. Check API keys:", file=sys.stderr)
        print("  - NANO_BANANA_API_KEY", file=sys.stderr)
        print("  - GEMINI_API_KEY", file=sys.stderr)
        print("  - REMOVE_BG_API_KEY (optional)", file=sys.stderr)
        sys.exit(1)
    
    return models


def cmd_process(args):
    """Process a single image."""
    # Setup
    models = setup_models()
    router = ModelRouter(models, prefer_free=args.prefer == 'free')
    
    # Create task config
    task_config = TaskConfig(
        task_type=args.task,
        quality_mode=args.quality,
        output_path=args.output,
        output_format=args.format,
        prefer_free=(args.prefer == 'free')
    )
    
    # Auto-select model if not specified
    if args.model == 'auto':
        print("🤖 Analyzing task...")
        model = router.select_model(task_config)
        if not model:
            print(f"❌ No suitable model found for task: {args.task}")
            return 1
        print(f"✓ Selected: {model.__class__.__name__}")
    else:
        # Find specific model
        model_map = {
            'nano-banana': NanaBananaModel,
            'gemini25': Gemini25FlashModel,
            'removebg': RemoveBgModel
        }
        model_class = model_map.get(args.model)
        if not model_class:
            print(f"❌ Unknown model: {args.model}")
            return 1
        
        model = next((m for m in models if isinstance(m, model_class)), None)
        if not model:
            print(f"❌ Model not available: {args.model}")
            return 1
    
    # Process image
    print(f"🍌 Processing {args.image}...")
    result = model.process_image(args.image, task_config)
    
    # Output result
    if result.success:
        print(result)
        return 0
    else:
        print(f"❌ {result.error}")
        return 1


def cmd_status(args):
    """Show model status."""
    models = setup_models()
    router = ModelRouter(models)
    
    status = router.get_model_status()
    
    print("Model Health:")
    for name, info in status.items():
        health = "✓" if info['healthy'] else "❌"
        caps = info['capabilities']
        stats = info['stats']
        
        print(f"  {health} {name}")
        print(f"     Quality: {caps['quality_score']:.1%} | "
              f"Avg Time: {caps['avg_time']:.1f}s | "
              f"Cost: {caps['cost']}")
        
        if stats['calls'] > 0:
            print(f"     Calls: {stats['calls']} | "
                  f"Success: {stats['success_rate']:.1%} | "
                  f"Total Cost: ${stats['total_cost']:.2f}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Gemini Chat - Multi-model auto image processor"
    )
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    
    # Process command
    process_parser = subparsers.add_parser('process', help='Process a single image')
    process_parser.add_argument('image', help='Input image path')
    process_parser.add_argument('--task', default='remove-bg', 
                                choices=['remove-bg', 'analyze', 'enhance'],
                                help='Processing task (default: remove-bg)')
    process_parser.add_argument('--quality', default='high',
                                choices=['low', 'medium', 'high', 'premium'],
                                help='Quality level (default: high)')
    process_parser.add_argument('--model', default='auto',
                                choices=['auto', 'nano-banana', 'gemini25', 'removebg'],
                                help='Model to use (default: auto)')
    process_parser.add_argument('--prefer', default='free',
                                choices=['free', 'fast', 'quality'],
                                help='Preference (default: free)')
    process_parser.add_argument('--output', help='Output path')
    process_parser.add_argument('--format', default='png',
                                help='Output format (default: png)')
    
    # Status command
    status_parser = subparsers.add_parser('status', help='Show model status')
    
    # Parse args
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    # Run command
    if args.command == 'process':
        return cmd_process(args)
    elif args.command == 'status':
        return cmd_status(args)
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
