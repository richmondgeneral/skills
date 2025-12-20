# Hugging Face Spaces Deployment Guide

## 📋 Pre-Deployment

All files are ready in `/tmp/gemini-chat-deploy/`:
- ✅ app.py (updated for HF secrets)
- ✅ models/ directory
- ✅ router.py
- ✅ requirements.txt
- ✅ README.md (with Space metadata)

## 🚀 Deployment Steps

### Step 1: Create Hugging Face Space (2 minutes)

1. Go to https://huggingface.co/spaces
2. Click "Create new Space"
3. Fill in:
   - **Name:** `gemini-chat`
   - **License:** MIT
   - **SDK:** Gradio
   - **Visibility:** Public
   - **Hardware:** CPU basic (free)
4. Click "Create Space"

### Step 2: Get Your Space Repository URL

After creation, you'll see:
```
https://huggingface.co/spaces/YOUR_USERNAME/gemini-chat
```

Clone URL will be:
```
https://huggingface.co/spaces/YOUR_USERNAME/gemini-chat.git
```

### Step 3: Clone and Deploy (3 minutes)

```bash
# Clone your new Space
git clone https://huggingface.co/spaces/YOUR_USERNAME/gemini-chat
cd gemini-chat

# Copy deployment files
cp -r /tmp/gemini-chat-deploy/* .

# Commit and push
git add .
git commit -m "Deploy Gemini Chat Web UI

- Multi-model background removal
- Nano Banana Pro (Gemini 3)
- Gemini 2.5 Flash
- Auto model selection

Co-Authored-By: Warp <agent@warp.dev>"

git push
```

### Step 4: Configure Secrets (2 minutes)

1. Go to your Space page
2. Click "Settings" (gear icon)
3. Scroll to "Repository secrets"
4. Add three secrets:

**Secret 1:**
- Name: `NANO_BANANA_API_KEY`
- Value: `AIzaSyAvjBCoEKfsaOEni94y2Q93fWakndF5zGM`

**Secret 2:**
- Name: `GEMINI_API_KEY`
- Value: [Your Gemini API key]

**Secret 3 (Optional):**
- Name: `REMOVE_BG_API_KEY`
- Value: [Your remove.bg key, if you have one]

### Step 5: Wait for Build (2-3 minutes)

The Space will automatically:
1. Install dependencies from requirements.txt
2. Load your app.py
3. Start Gradio server
4. Generate public URL

Watch the "Logs" tab for build progress.

### Step 6: Test Your Deployment

Once built, your app will be live at:
```
https://huggingface.co/spaces/YOUR_USERNAME/gemini-chat
```

**Test checklist:**
- [ ] UI loads
- [ ] Image upload works
- [ ] Model dropdown functional
- [ ] "🚀 Remove Background" processes image
- [ ] Results display with confidence/time/cost
- [ ] No API key errors in logs

## 🔧 Troubleshooting

### "API key not found" errors
- Go to Space Settings → Repository secrets
- Verify secret names match exactly:
  - `NANO_BANANA_API_KEY`
  - `GEMINI_API_KEY`
  - `REMOVE_BG_API_KEY`
- Restart Space after adding secrets

### Build fails
- Check "Logs" tab for errors
- Verify requirements.txt has correct package names
- Ensure all model files copied correctly

### Gradio version mismatch
- Update requirements.txt to specific version
- Change `gradio>=4.0.0` to `gradio==4.0.0` if needed

## 📊 Post-Deployment

After successful deployment:

1. **Update Linear TVM-84:**
   - Mark as Done
   - Add public URL in comment
   
2. **Update README in skills repo:**
   ```bash
   cd ~/skills/gemini-chat
   # Add to README.md:
   # **Live Demo:** https://huggingface.co/spaces/YOUR_USERNAME/gemini-chat
   ```

3. **Share the link:**
   - Test with team
   - Get feedback
   - Monitor usage in HF dashboard

## 💡 Tips

- **Free tier limits:** 2 CPU cores, 16GB RAM, 50GB storage
- **Auto-scaling:** HF handles traffic automatically
- **Monitoring:** Check Space "Analytics" tab for usage
- **Updates:** Just `git push` to your Space repo to update

## 📞 Support

If you encounter issues:
- Check HF Spaces docs: https://huggingface.co/docs/hub/spaces
- View Space logs for errors
- Restart Space from Settings if needed

---

**Ready to deploy?** Follow the steps above! ⬆️
