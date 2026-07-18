# SETUP VERIFICATION & DISK IMAGE UPLOAD TEST

## ✅ What Should Be Present

After extracting the ZIP, verify you have these files in `backend/`:

```
✓ main.py                      - FastAPI server (UPDATED for disk images)
✓ autopsy_parser.py            - Parser (UPDATED with parse_disk_image)
✓ forensic_analyzer.py         - NEW: pytsk3 wrapper
✓ rag_engine.py
✓ report_generator.py
✓ requirements.txt              - UPDATED with pytsk3
✓ .env.example
```

---

## 🔧 Installation Checklist

### Step 1: Install Dependencies
```bash
cd backend
pip install -r requirements.txt
```

**Verify pytsk3 installed:**
```bash
python -c "import pytsk3; print('✓ pytsk3 installed:', pytsk3.__version__)"
```

### Step 2: Configure API Keys
```bash
cp .env.example .env
# Edit .env and add your OpenAI or Groq API keys
# OPENAI_API_KEY=sk-...
# or
# GROQ_API_KEY=gsk_...
```

### Step 3: Start Server
```bash
python main.py
```

You should see:
```
INFO:     Application startup complete
INFO:     Uvicorn running on http://0.0.0.0:8000
```

---

## ✅ Upload a Disk Image - Complete Test

### Test 1: Upload a Disk Image (.dd format)

```bash
# Create a small test image (optional - use real .dd if available)
# dd if=/dev/zero of=test.dd bs=1M count=10

# Upload
curl -X POST http://localhost:8000/api/upload \
  -F "file=@test.dd" \
  -F "case_name=Test Case" \
  -F "analyst_name=Tester" \
  -F "case_number=TEST-001" \
  -F "department=Lab"
```

**Expected Response:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "uploaded",
  "file_type": "disk_image",
  "message": "File uploaded successfully"
}
```

### Test 2: Process the Disk Image

```bash
# Get the job_id from above response
JOB_ID="550e8400-e29b-41d4-a716-446655440000"

# Process
curl -X POST http://localhost:8000/api/process/$JOB_ID
```

**Expected Response:**
```json
{
  "job_id": "550e8400-...",
  "status": "processing"
}
```

### Test 3: Check Processing Status

```bash
curl http://localhost:8000/api/status/$JOB_ID
```

**Expected Response (while processing):**
```json
{
  "id": "550e8400-...",
  "status": "parsing",
  "created_at": "2025-04-25T...",
  "is_disk_image": true,
  "progress": 25
}
```

**When completed:**
```json
{
  "id": "550e8400-...",
  "status": "completed",
  "report_path": "/path/to/report_*.pdf",
  "is_disk_image": true
}
```

### Test 4: Download Report

```bash
curl http://localhost:8000/api/report/$JOB_ID > report.pdf
echo "Report downloaded: report.pdf"
```

---

## 🧪 Test with Sample Data

The `sample_data/` folder contains test files. Try uploading:

### Test Traditional Artifact (Should Still Work)
```bash
curl -X POST http://localhost:8000/api/upload \
  -F "file=@sample_data/operation_dark_web.xml" \
  -F "case_name=Sample Case" \
  -F "analyst_name=Tester"
```

### Test Disk Image (NEW)
If you have a real `.dd` file:
```bash
curl -X POST http://localhost:8000/api/upload \
  -F "file=@your_image.dd" \
  -F "case_name=Real Case" \
  -F "analyst_name=Tester"
```

---

## 🔍 Troubleshooting

### Error: "Method Not Allowed"
This usually means the file extension isn't recognized. Check:
1. File extension is lowercase: `.dd` not `.DD`
2. Extension is in allowed list (.dd, .img, .raw, .E01)
3. Content-Type is correct (should auto-detect)

**Fix:**
```bash
# Verify file extension
ls -la your_file.dd

# Try with explicit format
curl -X POST http://localhost:8000/api/upload \
  -F "file=@your_file.dd;type=application/octet-stream" \
  -F "case_name=Test"
```

### Error: "pytsk3 not found"
```bash
pip install pytsk3
python -c "import pytsk3; print('OK')"
```

### Error: "libtsk-dev not installed" (Linux)
```bash
sudo apt-get install libtsk-dev
```

### Error: "Failed to determine filesystem type"
Disk image might be:
- Corrupted or invalid format
- Not a real disk image
- Empty file

**Verify:**
```bash
# Check file integrity
file your_image.dd

# Check size
ls -lh your_image.dd
```

### Server Won't Start
Check port 8000 is available:
```bash
# Try different port
python main.py --port 8001

# Or kill existing process
lsof -i :8000
kill -9 <PID>
```

---

## ✅ Verification Checklist

Run these to verify everything is working:

```bash
# 1. Check Python version
python --version              # Should be 3.8+

# 2. Check pytsk3
python -c "import pytsk3; print('✓ pytsk3 OK')"

# 3. Check API responses
curl http://localhost:8000/

# 4. Check upload endpoint
curl -X POST http://localhost:8000/api/upload \
  -F "file=@test.txt" \
  -F "case_name=Test" \
  -F "analyst_name=Test"    # Should return job_id, even for .txt

# 5. Test with disk image
# curl -X POST http://localhost:8000/api/upload \
#   -F "file=@test.dd" \
#   -F "case_name=Test" \
#   -F "analyst_name=Test"    # Should return job_id with file_type: "disk_image"
```

---

## 🎯 What Should Work Now

After proper setup:

✅ Upload `.dd` files (raw disk images)
✅ Upload `.img` files (standard images)
✅ Upload `.raw` files (raw images)
✅ Upload `.E01` files (EnCase format)
✅ Automatic filesystem detection
✅ File extraction from disk images
✅ Deleted file detection
✅ Report generation
✅ AI analysis via RAG engine
✅ All original features (XML/CSV/JSON)

---

## 📊 Data Flow for Disk Images

```
1. Upload disk image (.dd, .img, .raw, .E01)
        ↓
2. API validates extension & file size
        ↓
3. File stored in job directory
        ↓
4. process endpoint called
        ↓
5. autopsy_parser.parse() detects disk image
        ↓
6. ForensicAnalyzer (pytsk3) opens image
        ↓
7. Filesystem auto-detected
        ↓
8. Files extracted (allocated + deleted)
        ↓
9. Results normalized to artifact format
        ↓
10. RAG engine indexes artifacts
        ↓
11. Report generator creates PDF
        ↓
12. Report ready for download
```

---

## 🔐 Security Verification

Verify security features:

```bash
# 1. Check .env file (should have secrets)
cat backend/.env       # Should have API keys

# 2. Check file permissions
ls -la backend/*.py    # Should be readable

# 3. Verify read-only mode
# (The code only READS images, never modifies)
# Check forensic_analyzer.py line: pytsk3.Img_Info(str(image_path))
# This opens in read-only mode

# 4. Check audit logging
# Monitor the server logs during upload/process
```

---

## ✨ Expected Log Output

When you upload a disk image and process it, server logs should show:

```
INFO: PYTSK3_INTEGRATION - Analyzing disk image
INFO: Validation passed
INFO: Opening image: test.dd
INFO: Detecting filesystem...
INFO: Filesystem: NTFS
INFO: Extracting files...
INFO: Found XX artifacts
INFO: Analysis complete
```

---

## 🎯 Common Issues & Solutions

| Issue | Solution |
|-------|----------|
| "unsupported type" | Check file extension: `.dd` not `.DD` |
| "Method Not Allowed" | Endpoint exists, check HTTP method is POST |
| pytsk3 import error | Run: `pip install pytsk3` |
| "Invalid disk image" | Image file might be corrupted |
| Port 8000 in use | Use different port: `python main.py --port 8001` |
| API key error | Edit `.env` with valid OpenAI/Groq key |
| Analysis very slow | Normal for large images (~1 min per 1GB) |

---

## 📝 Next Steps

1. ✅ Extract ZIP file
2. ✅ Install dependencies: `pip install -r backend/requirements.txt`
3. ✅ Copy & edit `.env.example` → `.env`
4. ✅ Start server: `python backend/main.py`
5. ✅ Test traditional upload (XML/CSV)
6. ✅ Test disk image upload (.dd file)
7. ✅ Download and view PDF report
8. ✅ Query with AI

---

## 🆘 Still Having Issues?

If you get "Method Not Allowed" when uploading disk images:

1. **Verify the file has correct extension:**
   ```bash
   ls -la *.dd *.img *.raw 2>/dev/null || echo "No disk images found"
   ```

2. **Verify API is running:**
   ```bash
   curl http://localhost:8000/
   # Should return HTML page or JSON response
   ```

3. **Check server logs for detailed errors:**
   ```bash
   # Server will print errors to console
   # Look for "FileValidationError", "pytsk3", etc.
   ```

4. **Test with curl verbose mode:**
   ```bash
   curl -v -X POST http://localhost:8000/api/upload \
     -F "file=@test.dd" \
     -F "case_name=Test" \
     -F "analyst_name=Test"
   ```

---

**Version**: 1.0.0  
**Status**: Ready to Test  
**Last Updated**: 2025-04-25

**If everything is in place and you're still having issues, check the server console for detailed error messages!**
