#!/usr/bin/env python3
"""
Gemini Chat Web UI - Beautiful interface for AI background removal.
Optimized for Hugging Face Spaces deployment.
"""
import os
import gradio as gr

from models import TaskConfig, NanaBananaModel, Gemini25FlashModel, RemoveBgModel
from router import ModelRouter

# Load secrets from Hugging Face Spaces
# These will be set in Space Settings → Repository secrets
if not os.getenv('NANO_BANANA_API_KEY'):
    print("⚠️  NANO_BANANA_API_KEY not set in Space secrets")
if not os.getenv('GEMINI_API_KEY'):
    print("⚠️  GEMINI_API_KEY not set in Space secrets")
if not os.getenv('REMOVE_BG_API_KEY'):
    print("ℹ️  REMOVE_BG_API_KEY not set (optional)")

# Initialize models
models = []
try:
    nano = NanaBananaModel()
    if nano.health_check():
        models.append(nano)
        print("✓ Nano Banana Pro loaded")
except Exception as e:
    print(f"⚠️  Nano Banana Pro unavailable: {e}")

try:
    gemini25 = Gemini25FlashModel()
    if gemini25.health_check():
        models.append(gemini25)
        print("✓ Gemini 2.5 Flash loaded")
except Exception as e:
    print(f"⚠️  Gemini 2.5 Flash unavailable: {e}")

try:
    removebg = RemoveBgModel()
    if removebg.health_check():
        models.append(removebg)
        print("✓ remove.bg loaded")
except Exception as e:
    print(f"⚠️  remove.bg unavailable: {e}")

if not models:
    print("❌ No models available. Check API keys:")
    print("  - NANO_BANANA_API_KEY")
    print("  - GEMINI_API_KEY")
    print("  - REMOVE_BG_API_KEY (optional)")
    # Don't exit on HF Spaces, show error in UI instead

router = ModelRouter(models) if models else None

def process_image(image_path, model_choice, quality_mode):
    """Process image and return result."""
    if not models:
        return None, "❌ No models available - check API keys in Space settings", "0s", "N/A"
    
    if not image_path:
        return None, "No image uploaded", "0s", "Free"
    
    # Create task config
    task = TaskConfig(
        task_type='remove-bg',
        quality_mode=quality_mode.lower(),
        prefer_free=True
    )
    
    # Select model
    if model_choice == 'auto':
        # Auto now prefers remove.bg for quality
        model_map = {
            'removebg': RemoveBgModel,
            'nano-banana': NanaBananaModel,
            'gemini25': Gemini25FlashModel,
        }
        # Try remove.bg first, fallback to free models
        model = next((m for m in models if isinstance(m, RemoveBgModel)), None)
        if not model:
            model = router.select_model(task)
        if not model:
            return None, "No suitable model found", "0s", "Free"
    else:
        model_map = {
            'nano-banana': NanaBananaModel,
            'gemini25': Gemini25FlashModel,
            'removebg': RemoveBgModel
        }
        model_class = model_map.get(model_choice)
        model = next((m for m in models if isinstance(m, model_class)), None)
        
        if not model:
            return None, f"Model {model_choice} not available", "0s", "Free"
    
    # Process
    result = model.process_image(image_path, task)
    
    if result.success:
        cost = 'Free' if result.cost == 0 else f'${result.cost:.4f}'
        return (
            result.output_path,
            f"{result.confidence:.1%}",
            f"{result.processing_time:.1f}s",
            cost
        )
    else:
        return None, f"Error: {result.error}", "0s", "Free"

# Build UI
with gr.Blocks() as demo:
    gr.Markdown("""
    # 🍌 Gemini Chat
    **AI-Powered Background Removal**
    
    Upload an image, select a model, and remove the background instantly!
    """)
    
    with gr.Row():
        with gr.Column():
            input_img = gr.Image(
                label="📸 Upload Image",
                type="filepath",
                height=400
            )
            
            model_choice = gr.Dropdown(
                choices=["removebg", "auto", "nano-banana", "gemini25"],
                value="removebg",
                label="🤖 Model",
                info="remove.bg selected for production quality ($0.009/image)"
            )
            
            quality_mode = gr.Radio(
                choices=["High", "Premium"],
                value="High",
                label="✨ Quality Mode"
            )
            
            process_btn = gr.Button(
                "🚀 Remove Background",
                variant="primary",
                size="lg"
            )
        
        with gr.Column():
            output_img = gr.Image(
                label="✓ Processed Image",
                type="filepath",
                height=400
            )
            
            with gr.Row():
                confidence = gr.Textbox(label="Confidence")
                time = gr.Textbox(label="Time")
                cost = gr.Textbox(label="Cost")
    
    # Connect event
    process_btn.click(
        fn=process_image,
        inputs=[input_img, model_choice, quality_mode],
        outputs=[output_img, confidence, time, cost]
    )
    
    gr.Markdown("""
    ---
    **Models:**
    - **remove.bg** (Default): Production quality, ~3s, $0.009/image
    - 🍌 **Nano Banana Pro** (Experimental): Free, ~8s, bounding box only
    - **Gemini 2.5 Flash** (Experimental): Free, ~8s, bounding box only
    
    **Source:** [GitHub](https://github.com/richmondgeneral/skills/tree/main/gemini-chat)
    """)

if __name__ == "__main__":
    print("\n🚀 Starting Gemini Chat Web UI...")
    print(f"📊 Loaded {len(models)} models")
    print("🌐 Launching on Hugging Face Spaces\n")
    
    # HF Spaces configuration
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        show_error=True
    )
