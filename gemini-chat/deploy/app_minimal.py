#!/usr/bin/env python3
"""
Gemini Chat Web UI - Production background removal
"""
import os
import gradio as gr
from models import TaskConfig, RemoveBgModel

# Load API key
remove_bg_key = os.getenv('REMOVE_BG_API_KEY')

if not remove_bg_key:
    print("⚠️  REMOVE_BG_API_KEY not set")

# Initialize remove.bg model
model = None
try:
    model = RemoveBgModel()
    if model.health_check():
        print("✓ remove.bg loaded")
    else:
        print("⚠️  remove.bg health check failed")
except Exception as e:
    print(f"❌ Failed to load remove.bg: {e}")

def process_image(image):
    """Process image with remove.bg"""
    if not model:
        return None, "❌ remove.bg not available - check API key", "", ""
    
    if image is None:
        return None, "No image uploaded", "", ""
    
    try:
        # Create task
        task = TaskConfig(
            task_type='remove-bg',
            quality_mode='high',
            prefer_free=False
        )
        
        # Process
        result = model.process_image(image, task)
        
        if result.success:
            cost = f'${result.cost:.4f}' if result.cost > 0 else 'Free'
            return (
                result.output_path,
                f"✓ Success",
                f"{result.processing_time:.1f}s",
                cost
            )
        else:
            return None, f"Error: {result.error}", "", ""
    except Exception as e:
        return None, f"Error: {str(e)}", "", ""

# Simple UI
with gr.Blocks(title="Background Removal") as demo:
    gr.Markdown("# 🍌 AI Background Removal\nUpload an image to remove its background.")
    
    with gr.Row():
        with gr.Column():
            input_img = gr.Image(label="📸 Upload Image", type="filepath")
            btn = gr.Button("🚀 Remove Background", variant="primary")
        
        with gr.Column():
            output_img = gr.Image(label="✓ Result", type="filepath")
            status = gr.Textbox(label="Status")
            time = gr.Textbox(label="Time")
            cost = gr.Textbox(label="Cost")
    
    btn.click(
        fn=process_image,
        inputs=input_img,
        outputs=[output_img, status, time, cost]
    )

if __name__ == "__main__":
    print("🚀 Starting Background Removal")
    demo.launch(server_name="0.0.0.0", server_port=7860)
