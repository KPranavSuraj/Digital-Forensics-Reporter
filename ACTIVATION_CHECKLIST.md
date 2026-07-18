# ✅ PYTSK3 ACTIVATION CHECKLIST

Follow these steps to activate and verify pytsk3 disk image support.

---

## 📋 Pre-Check

### 1. Verify Files Exist

```bash
# In the backend directory, verify these files exist:
ls -la backend/main.py                    # Main API
ls -la backend/autopsy_parser.py          # Parser with disk image support
ls -la backend/forensic_analyzer.py       # pytsk3 wrapper
ls -la backend/requirements.txt           # Dependencies
ls -la backend/.env.example               # Config template
```

All should exist and show file size > 0.

### 2. Verify Python Version

```bash
python --version      # Should be 3.8 or newer
```

If you have Python 2 or very old Python 3, upgrade first.

### 3. Install System Dependencies (One-time)

**Linux (Ubuntu/Debian):**
```bash
sudo apt-get update
sudo apt-get install libtsk-dev
```

**macOS:**
```bash
brew install sleuthkit
```

**Windows:**
No additional system dependencies needed.

---

## 🚀 Activation Steps

### Step 1: Install Python Dependencies

```bash
cd backend
pip install -r requirements.txt
```

This installs:
- fastapi
- uvicorn
- pytsk3 ← **KEY FOR DISK IMAGES**
- openai/groq (for AI)
- reportlab (for PDF)
- And others

**Verify pytsk3 installed:**
```bash
python -c "import pytsk3; print('✓ pytsk3 version:', pytsk3.__version__)"
```

If you see an error, run:
```bash
pip install pytsk3
```

### Step 2: Create Configuration File

```bash
cp .env.example .env
```

Now edit `.env` and add your API keys:
```bash
# Add ONE of these:
OPENAI_API_KEY=sk-...          # For OpenAI/ChatGPT
# OR
GROQ_API_KEY=gsk_...           # For Groq (faster)
```

### Step 3: Start the Server

```bash
python main.py
```

You should see:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete
```

Server is now ready for disk image uploads!

### Step 4: Verify Disk Image Support is Active

In a new terminal, run:

```bash
# Check if upload endpoint accepts disk images
curl -X OPTIONS http://localhost:8000/api/upload -v
```

Or just try uploading:

```bash
# Create a small test image
dd if=/dev/zero of=test.dd bs=1M count=5

# Upload it
curl -X POST http://localhost:8000/api/upload \
  -F "file=@test.dd" \
  -F "case_name=Test" \
  -F "analyst_name=Admin"
```

**Success response:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "uploaded",
  "file_type": "disk_image",
  "message": "File uploaded successfully"
}
```

**If you see file_type: "disk_image" → PYTSK3 IS ACTIVE! ✓**

---

## 🔍 Verification Steps

### Verify 1: Check Code is Present

```bash
# Should find parse_disk_image method
grep -n "def parse_disk_image" backend/autopsy_parser.py
# Output: 102:    def parse_disk_image(self, file_path: str) -> Dict[str, Any]:

# Should find ForensicAnalyzer class
grep -n "class ForensicAnalyzer" backend/forensic_analyzer.py
# Output: 21:class ForensicAnalyzer:

# Should find disk image in allowed extensions
grep -n "E01.*Disk image" backend/main.py
# Output: 875:        ".dd", ".img", ".raw", ".E01"  # Disk image formats
```

All three should return results. If any are missing, the feature isn't installed.

### Verify 2: Check pytsk3 Can Be Imported

```bash
python -c "
import sys
sys.path.insert(0, 'backend')
try:
    from forensic_analyzer import ForensicAnalyzer
    print('✓ ForensicAnalyzer imported')
    analyzer = ForensicAnalyzer()
    print('✓ ForensicAnalyzer instantiated')
    print('✓ PYTSK3 INTEGRATION ACTIVE!')
except Exception as e:
    print(f'✗ Error: {e}')
    print('  Run: pip install pytsk3')
"
```

Should see:
```
✓ ForensicAnalyzer imported
✓ ForensicAnalyzer instantiated
✓ PYTSK3 INTEGRATION ACTIVE!
```

### Verify 3: Check Upload Endpoint

```bash
python -c "
import sys
sys.path.insert(0, 'backend')
from main import app

# Find upload endpoint
for route in app.routes:
    if '/api/upload' in str(route):
        print(f'✓ Found: {route}')
        if 'POST' in str(route.methods):
            print('✓ Accepts POST method')
        if '.dd' in open('backend/main.py').read():
            print('✓ .dd extension supported')
"
```

Should see:
```
✓ Found: POST /api/upload
✓ Accepts POST method
✓ .dd extension supported
```

---

## 🧪 Test Disk Image Upload

### Test 1: Quick Test

```bash
# Use the included test script
python test_disk_image_upload.py
```

This will:
1. Create a test disk image
2. Upload it
3. Process it
4. Show results

### Test 2: Manual Test

```bash
# Create small test image (10 MB)
dd if=/dev/zero of=test.dd bs=1M count=10

# Upload
curl -X POST http://localhost:8000/api/upload \
  -F "file=@test.dd" \
  -F "case_name=My Test" \
  -F "analyst_name=Tester" \
  -F "case_number=TEST-001" \
  -F "department=Lab"

# Save response to file
curl -s -X POST http://localhost:8000/api/upload \
  -F "file=@test.dd" \
  -F "case_name=My Test" \
  -F "analyst_name=Tester" > response.json

# Check response
cat response.json | python -m json.tool
```

**Look for:**
```json
{
  "job_id": "some-uuid",
  "file_type": "disk_image",
  "status": "uploaded"
}
```

If `file_type` is `disk_image` → **PYTSK3 IS WORKING! ✓**

---

## 📊 What Should Work Now

After activation, you should be able to:

✅ Upload `.dd` files (raw disk images)
✅ Upload `.img` files (standard images)
✅ Upload `.raw` files (raw images)
✅ Upload `.E01` files (EnCase format)
✅ Upload traditional artifacts (XML/CSV/JSON) - still works
✅ Get automatic filesystem detection
✅ Extract files from disk images
✅ Detect deleted files
✅ Generate forensic reports
✅ Query with AI

---

## ❌ If Something Doesn't Work

### Error: "ModuleNotFoundError: No module named 'pytsk3'"

**Solution:**
```bash
pip install pytsk3
python -c "import pytsk3; print('OK')"
```

### Error: "Method Not Allowed" (405)

**Solution:**
1. Verify endpoint is POST: `@app.post("/api/upload")`
2. Check file extension is lowercase: `.dd` not `.DD`
3. Verify file extension is in allowed list
4. See FIX_METHOD_NOT_ALLOWED.md for detailed troubleshooting

### Error: "libtsk-dev not installed"

**Solution:**
```bash
# Linux
sudo apt-get install libtsk-dev

# macOS
brew install sleuthkit
```

### Error: pytsk3 installation fails

**Solution:**
```bash
# Install system dependencies first
# (see "Install System Dependencies" above)

# Then install pytsk3
pip install pytsk3

# If still failing, try:
pip install --upgrade pytsk3
```

---

## ✅ Final Checklist

Before using disk images, verify:

- [ ] Python 3.8+ installed
- [ ] System dependencies installed (libtsk-dev on Linux)
- [ ] `pip install -r backend/requirements.txt` completed
- [ ] `import pytsk3` works in Python
- [ ] `.env` file created with API keys
- [ ] Server running: `python backend/main.py`
- [ ] Endpoint responds to requests
- [ ] Test upload works

---

## 🎉 Success Indicators

You'll know pytsk3 is working when:

1. ✓ Server starts without pytsk3 errors
2. ✓ Test script reports: "PYTSK3 INTEGRATION WORKING!"
3. ✓ Upload response includes: `"file_type": "disk_image"`
4. ✓ Server logs show filesystem detection
5. ✓ Report includes file listings

---

## 📚 Additional Resources

- **Setup & Test**: See `SETUP_AND_TEST.md`
- **Troubleshooting**: See `FIX_METHOD_NOT_ALLOWED.md`
- **Complete Guide**: See `COMPLETE_QUICKSTART.md`
- **Technical Details**: See `PYTSK3_INTEGRATION_GUIDE.md`

---

## 🎯 Next Steps

1. ✅ Follow activation steps above
2. ✅ Run verification checks
3. ✅ Test with `test_disk_image_upload.py`
4. ✅ Upload your own disk images
5. ✅ Download PDF reports

---

**Status**: ✅ Ready to Activate  
**Time to Complete**: ~10 minutes  
**Version**: 1.0.0

**Once all checks pass, you're ready to analyze disk images!**
