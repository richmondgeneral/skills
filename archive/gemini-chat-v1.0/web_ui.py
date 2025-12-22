#!/usr/bin/env python3
"""
Gemini Chat Web UI - Beautiful interface for AI background removal.
"""
import gradio as gr
from models import TaskConfig, NanaBananaModel, Gemini25FlashModel, RemoveBgModel
from router import ModelRouter

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
    exit(1)

router = ModelRouter(models)

def process_image(image_path, model_choice, quality_mode):
    """Process image and return result."""
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
                type="filepath",
                label="📸 Upload Image",
                height=400
            )
            
            model_choice = gr.Dropdown(
                choices=["auto", "nano-banana", "gemini25", "removebg"],
                value="auto",
                label="🤖 Model",
                info="Auto selects best free model (Nano Banana Pro)"
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
                height=400
            )
            
            with gr.Row():
                confidence = gr.Textbox(
                    label="Confidence",
                    interactive=False
                )
                time = gr.Textbox(
                    label="Time",
                    interactive=False
                )
                cost = gr.Textbox(
                    label="Cost",
                    interactive=False
                )
    
    # Connect event
    process_btn.click(
        fn=process_image,
        inputs=[input_img, model_choice, quality_mode],
        outputs=[output_img, confidence, time, cost]
    )
    
    gr.Markdown("""
    ---
    **Models:**
    - 🍌 **Nano Banana Pro** (Gemini 3): 98% confidence, ~8s, free
    - **Gemini 2.5 Flash**: 95% confidence, ~8s, free
    - **remove.bg**: Premium quality, ~3s, $0.009/image
    """)

if __name__ == "__main__":
    print("\n🚀 Starting Gemini Chat Web UI...")
    print(f"📊 Loaded {len(models)} models")
    print("🌐 Opening browser at http://localhost:7860\n")
    
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        theme=gr.themes.Soft(primary_hue="purple")
    )
