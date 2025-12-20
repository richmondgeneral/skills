#!/usr/bin/env python3
"""
AI Background Removal - Production
Uses remove.bg API for professional results
"""
import os
import requests
import time
import gradio as gr
from pathlib import Path

REMOVE_BG_API_KEY = os.getenv('REMOVE_BG_API_KEY', '')

def remove_background(image_path):
    """Remove background using remove.bg API"""
    if not REMOVE_BG_API_KEY:
        return None, "❌ API key not configured", "", ""
    
    if not image_path:
        return None, "No image uploaded", "", ""
    
    start_time = time.time()
    
    try:
        # Call remove.bg API
        with open(image_path, 'rb') as f:
            response = requests.post(
                'https://api.remove.bg/v1.0/removebg',
                files={'image_file': f},
                data={'size': 'auto'},
                headers={'X-Api-Key': REMOVE_BG_API_KEY},
                timeout=30
            )
        
        if response.status_code == 200:
            # Save result
            input_path = Path(image_path)
            output_path = str(input_path.parent / f"{input_path.stem}-nobg.png")
            with open(output_path, 'wb') as out:
                out.write(response.content)
            
            processing_time = time.time() - start_time
            return (
                output_path,
                "✓ Success",
                f"{processing_time:.1f}s",
                "$0.009"
            )
        else:
            return None, f"Error: {response.status_code} - {response.text[:100]}", "", ""
            
    except Exception as e:
        return None, f"Error: {str(e)}", "", ""

# Build UI
with gr.Blocks(title="AI Background Removal") as demo:
    gr.Markdown("""
    # 🍌 AI Background Removal
    **Production quality background removal powered by remove.bg**
    
    Upload an image and remove its background instantly!
    """)
    
    with gr.Row():
        with gr.Column():
            input_img = gr.Image(label="📸 Upload Image", type="filepath")
            btn = gr.Button("🚀 Remove Background", variant="primary", size="lg")
        
        with gr.Column():
            output_img = gr.Image(label="✓ Result", type="filepath")
            with gr.Row():
                status = gr.Textbox(label="Status", value="")
                time_taken = gr.Textbox(label="Time", value="")
                cost = gr.Textbox(label="Cost", value="")
    
    btn.click(
        fn=remove_background,
        inputs=[input_img],
        outputs=[output_img, status, time_taken, cost]
    )
    
    gr.Markdown("""
    ---
    **Powered by remove.bg** | Cost: $0.009 per image | Speed: ~3 seconds
    """)

if __name__ == "__main__":
    if REMOVE_BG_API_KEY:
        print("✓ remove.bg API key configured")
    else:
        print("⚠️  REMOVE_BG_API_KEY not set in environment")
    
    print("🚀 Launching AI Background Removal")
    demo.launch(server_name="0.0.0.0", server_port=7860)
