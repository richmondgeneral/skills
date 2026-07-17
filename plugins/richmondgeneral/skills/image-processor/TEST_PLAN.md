# image-processor Test Plan

## Prerequisites

1. **API Keys configured** in `~/.env`:
   - `GEMINI_API_KEY` - Required for generation/editing
   - `NANO_BANANA_API_KEY` - Required for background removal
   - `REMOVE_BG_API_KEY` - Optional (paid fallback)

2. **Full Disk Access** granted to Terminal (System Settings > Privacy & Security)

3. **Test images** available:
   - A product photo with busy background
   - A portrait photo
   - Photos.app has at least 10 photos

## Test Cases

### 1. Model Status Check

```bash
cd ${CLAUDE_PLUGIN_ROOT}/skills/image-processor
uv run --project ${CLAUDE_PLUGIN_ROOT} python scripts/status.py
```

**Expected**: Shows health status for all models (NanaBananaModel, Gemini25FlashModel, RemoveBgModel, GeminiImageModel)

---

### 2. Background Removal

#### 2.1 Basic removal
```bash
uv run --project ${CLAUDE_PLUGIN_ROOT} python scripts/process.py /path/to/test.jpg
```
**Expected**: Creates `test-nobg.png` in same directory

#### 2.2 Custom output path
```bash
uv run --project ${CLAUDE_PLUGIN_ROOT} python scripts/process.py /path/to/test.jpg --output /tmp/result.png
```
**Expected**: Creates `/tmp/result.png`

#### 2.3 Quality modes
```bash
uv run --project ${CLAUDE_PLUGIN_ROOT} python scripts/process.py /path/to/test.jpg --quality premium --output /tmp/premium.png
```
**Expected**: Uses highest quality model available

#### 2.4 JSON output
```bash
uv run --project ${CLAUDE_PLUGIN_ROOT} python scripts/process.py /path/to/test.jpg --json
```
**Expected**: Returns JSON with success, model, output_path, confidence, processing_time

---

### 3. Image Generation

#### 3.1 Basic generation
```bash
uv run --project ${CLAUDE_PLUGIN_ROOT} python scripts/generate.py \
  --prompt "A vintage typewriter on a wooden desk, soft lighting" \
  --output /tmp/typewriter.png
```
**Expected**: Creates `/tmp/typewriter.png` with generated image

#### 3.2 With style reference
```bash
uv run --project ${CLAUDE_PLUGIN_ROOT} python scripts/generate.py \
  --prompt "Apply this vintage style to a mountain landscape" \
  --reference /path/to/style.jpg \
  --output /tmp/styled.png
```
**Expected**: Creates image with style from reference

#### 3.3 Pro quality
```bash
uv run --project ${CLAUDE_PLUGIN_ROOT} python scripts/generate.py \
  --prompt "Professional product photography of ceramic mug, 4K" \
  --quality pro \
  --output /tmp/mug.png
```
**Expected**: Uses Nano Banana Pro model (gemini-3-pro-image)

---

### 4. Image Editing

#### 4.1 Basic edit
```bash
uv run --project ${CLAUDE_PLUGIN_ROOT} python scripts/edit.py \
  --input /path/to/photo.jpg \
  --instruction "Remove the background and add a subtle shadow" \
  --output /tmp/edited.png
```
**Expected**: Creates edited image

#### 4.2 Style change
```bash
uv run --project ${CLAUDE_PLUGIN_ROOT} python scripts/edit.py \
  --input /path/to/landscape.jpg \
  --instruction "Change to sunset lighting with warm orange tones" \
  --output /tmp/sunset.png
```
**Expected**: Applies lighting change

#### 4.3 With reference
```bash
uv run --project ${CLAUDE_PLUGIN_ROOT} python scripts/edit.py \
  --input /path/to/subject.jpg \
  --instruction "Place this subject in the reference background" \
  --reference /path/to/background.jpg \
  --output /tmp/composite.png
```
**Expected**: Composites subject into background

---

### 5. Photos.app Access

#### 5.1 Library stats
```bash
uv run --project ${CLAUDE_PLUGIN_ROOT} python scripts/photos.py --stats
```
**Expected**: Shows total photos, videos, favorites, albums count

#### 5.2 List recent photos
```bash
uv run --project ${CLAUDE_PLUGIN_ROOT} python scripts/photos.py --recent 5
```
**Expected**: Lists 5 most recent photos with filename, dimensions, date

#### 5.3 List albums
```bash
uv run --project ${CLAUDE_PLUGIN_ROOT} python scripts/photos.py --albums
```
**Expected**: Lists album names with photo counts

#### 5.4 List favorites
```bash
uv run --project ${CLAUDE_PLUGIN_ROOT} python scripts/photos.py --favorites
```
**Expected**: Lists favorited photos

#### 5.5 Search by filename
```bash
uv run --project ${CLAUDE_PLUGIN_ROOT} python scripts/photos.py --search "IMG_%"
```
**Expected**: Lists photos matching pattern

#### 5.6 Date range filter
```bash
uv run --project ${CLAUDE_PLUGIN_ROOT} python scripts/photos.py --since 2025-12-01 --limit 10
```
**Expected**: Lists photos from Dec 1, 2025 onwards

#### 5.7 Get photo info
```bash
# First get a UUID from --recent
UUID=$(uv run --project ${CLAUDE_PLUGIN_ROOT} python scripts/photos.py --recent 1 --json | python3 -c "import sys,json; print(json.load(sys.stdin)[0]['uuid'])")
uv run --project ${CLAUDE_PLUGIN_ROOT} python scripts/photos.py --info "$UUID"
```
**Expected**: Shows detailed photo info including file path

#### 5.8 Copy photo
```bash
uv run --project ${CLAUDE_PLUGIN_ROOT} python scripts/photos.py --copy "$UUID" --output /tmp/copied.jpg
```
**Expected**: Copies photo to /tmp/copied.jpg

#### 5.9 JSON output
```bash
uv run --project ${CLAUDE_PLUGIN_ROOT} python scripts/photos.py --recent 3 --json
```
**Expected**: Returns JSON array with photo objects

---

### 6. Integration Tests

#### 6.1 Photos → Background Removal
```bash
# Get recent photo and process it
UUID=$(uv run --project ${CLAUDE_PLUGIN_ROOT} python scripts/photos.py --recent 1 --json | python3 -c "import sys,json; print(json.load(sys.stdin)[0]['uuid'])")
uv run --project ${CLAUDE_PLUGIN_ROOT} python scripts/photos.py --copy "$UUID" --output /tmp/from-photos.jpg
uv run --project ${CLAUDE_PLUGIN_ROOT} python scripts/process.py /tmp/from-photos.jpg --output /tmp/from-photos-nobg.png
```
**Expected**: Successfully removes background from Photos library image

#### 6.2 Generate → Edit chain
```bash
# Generate base, then refine
uv run --project ${CLAUDE_PLUGIN_ROOT} python scripts/generate.py \
  --prompt "Minimalist logo design, cream background" \
  --output /tmp/logo-base.png

uv run --project ${CLAUDE_PLUGIN_ROOT} python scripts/edit.py \
  --input /tmp/logo-base.png \
  --instruction "Add gold metallic finish and subtle emboss effect" \
  --output /tmp/logo-final.png
```
**Expected**: Both operations succeed, final image shows refinements

---

### 7. Error Handling

#### 7.1 Missing input file
```bash
uv run --project ${CLAUDE_PLUGIN_ROOT} python scripts/process.py /nonexistent/file.jpg
```
**Expected**: Error message, exit code 1

#### 7.2 Missing API key
```bash
GEMINI_API_KEY= uv run --project ${CLAUDE_PLUGIN_ROOT} python scripts/generate.py \
  --prompt "test" --output /tmp/test.png
```
**Expected**: Error about missing API key

#### 7.3 Invalid photo UUID
```bash
uv run --project ${CLAUDE_PLUGIN_ROOT} python scripts/photos.py --copy "invalid-uuid" --output /tmp/test.jpg
```
**Expected**: Error message about photo not found

#### 7.4 Photos.app not accessible
```bash
# Test with non-existent library
uv run --project ${CLAUDE_PLUGIN_ROOT} python scripts/photos.py --library /nonexistent/path --stats
```
**Expected**: Error about library not found

---

## Performance Benchmarks

| Operation | Target Time | Notes |
|-----------|-------------|-------|
| Status check | < 1s | No API calls |
| Background removal | < 15s | Depends on model |
| Image generation | < 30s | Pro mode may be slower |
| Image editing | < 30s | With references adds time |
| Photos list | < 2s | SQLite query |
| Photos copy | < 5s | Depends on file size |

---

## Checklist

- [ ] All API keys configured
- [ ] Full Disk Access granted
- [ ] Status check passes
- [ ] Background removal works
- [ ] Image generation works
- [ ] Image editing works
- [ ] Photos.app access works
- [ ] Integration tests pass
- [ ] Error handling works correctly
