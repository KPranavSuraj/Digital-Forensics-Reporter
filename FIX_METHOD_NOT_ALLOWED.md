# 🔧 FIX: "Method Not Allowed" Error When Uploading Disk Images

## 🎯 The Problem

When you try to upload a disk image (.dd, .img, .raw, .E01), you get:
```json
{"detail":"Method Not Allowed"}
```

This means the API endpoint exists but it's not accepting your request method.

---

## ✅ Complete Solution

### Step 1: Verify the Code is Correct

**Check that main.py has the POST endpoint:**
```bash
grep -n "@app.post(\"/api/upload\")" backend/main.py
```

Should show:
```
852:@app.post("/api/upload")
```

**Check that allowed_exts includes disk images:**
```bash
grep -A 5 "allowed_exts = {" backend/main.py
```

Should show:
```python
allowed_exts = {
    ".xml", ".csv", ".json", ".log", ".txt",
    ".jpg", ".jpeg", ".png", ".mp4", ".avi", ".mov",
    ".mp3", ".wav", ".aac", ".m4a",
    ".dd", ".img", ".raw", ".E01"  # Disk image formats
}
```

**Check that autopsy_parser has parse_disk_image:**
```bash
grep -n "def parse_disk_image" backend/autopsy_parser.py
```

Should show:
```
102:    def parse_disk_image(self, file_path: str) -> Dict[str, Any]:
```

**Check that forensic_analyzer.py exists:**
```bash
ls -la backend/forensic_analyzer.py
```

Should show the file exists and is readable.

### Step 2: Verify Dependencies Are Installed

```bash
# Check Python version
python --version                    # Should be 3.8+

# Check pytsk3
python -c "import pytsk3; print('✓ pytsk3:', pytsk3.__version__)"

# Check other dependencies
python -c "import fastapi; print('✓ fastapi')"
python -c "import uvicorn; print('✓ uvicorn')"
```

If pytsk3 is missing:
```bash
pip install pytsk3
```

### Step 3: Test the Upload Endpoint

**Use the test script:**
```bash
python test_disk_image_upload.py
```

This will:
1. Create a small test disk image
2. Upload it to the API
3. Check the response
4. Process it
5. Check the status

**OR test manually with curl:**
```bash
# Test traditional artifact (should work)
curl -X POST http://localhost:8000/api/upload \
  -F "file=@sample.xml" \
  -F "case_name=Test" \
  -F "analyst_name=Tester"

# Test disk image
curl -X POST http://localhost:8000/api/upload \
  -F "file=@test.dd" \
  -F "case_name=Test" \
  -F "analyst_name=Tester"
```

---

## 🔍 Troubleshooting the "Method Not Allowed" Error

### Common Cause 1: File Extension Not Lowercase

**Problem:** Uploading `test.DD` instead of `test.dd`

**Fix:**
```bash
# Check your file extension
ls -la test.*

# Rename if needed
mv test.DD test.dd

# Then upload
curl -X POST http://localhost:8000/api/upload \
  -F "file=@test.dd" \
  -F "case_name=Test"
```

### Common Cause 2: Wrong HTTP Method

**Problem:** Using GET instead of POST

**Wrong:**
```bash
curl http://localhost:8000/api/upload \
  -F "file=@test.dd"
```

**Correct:**
```bash
curl -X POST http://localhost:8000/api/upload \
  -F "file=@test.dd" \
  -F "case_name=Test"
```

### Common Cause 3: File Extension Not Recognized

**Problem:** File extension is not in the allowed list

**Fix:**
Verify in main.py that your extension is in `allowed_exts`:
```python
allowed_exts = {
    ".xml", ".csv", ".json", ".log", ".txt",
    ".jpg", ".jpeg", ".png", ".mp4", ".avi", ".mov",
    ".mp3", ".wav", ".aac", ".m4a",
    ".dd", ".img", ".raw", ".E01"  # Your extension should be here
}
```

If your extension is missing, add it:
```python
allowed_exts = {
    # ... existing ...
    ".dd", ".img", ".raw", ".E01", ".your_ext"  # Add here
}
```

### Common Cause 4: pytsk3 Not Installed

**Problem:** When AutopsyParser tries to use ForensicAnalyzer, pytsk3 isn't available

**Fix:**
```bash
pip install pytsk3

# Verify
python -c "import pytsk3; print('OK')"
```

### Common Cause 5: Server Not Reloaded

**Problem:** You made code changes but didn't restart the server

**Fix:**
```bash
# Stop the server (Ctrl+C)

# Restart
python backend/main.py
```

### Common Cause 6: Wrong API Endpoint

**Problem:** Using old endpoint path

**Wrong:**
```bash
curl -X POST http://localhost:8000/upload    # Missing /api
curl -X POST http://localhost:8000/file/upload
```

**Correct:**
```bash
curl -X POST http://localhost:8000/api/upload
```

---

## 🧪 Step-by-Step Verification Test

Run these commands in order to verify everything:

### 1. Verify Server is Running
```bash
curl http://localhost:8000/
```
Should return HTML page or JSON response (not "Method Not Allowed")

### 2. Verify Python Modules
```bash
python -c "
import sys
sys.path.insert(0, 'backend')
from main import app
from autopsy_parser import AutopsyParser
from forensic_analyzer import ForensicAnalyzer
print('✓ All modules imported successfully')
"
```

### 3. Verify Endpoint Exists
```bash
python -c "
import sys
sys.path.insert(0, 'backend')
from main import app

# List all routes
for route in app.routes:
    if 'upload' in str(route):
        print(f'Found: {route.methods} {route.path}')
"
```

Should show:
```
Found: {'POST'} /api/upload
```

### 4. Verify File Support
```bash
python -c "
import sys
sys.path.insert(0, 'backend')

# Check if disk image extensions are supported
allowed_exts = {
    '.xml', '.csv', '.json', '.log', '.txt',
    '.jpg', '.jpeg', '.png', '.mp4', '.avi', '.mov',
    '.mp3', '.wav', '.aac', '.m4a',
    '.dd', '.img', '.raw', '.E01'
}

for ext in ['.dd', '.img', '.raw', '.E01']:
    if ext in allowed_exts:
        print(f'✓ {ext} is supported')
    else:
        print(f'✗ {ext} is NOT supported')
"
```

### 5. Test Upload with Verbose Output
```bash
# Create a test file
dd if=/dev/zero of=test.dd bs=1M count=1

# Upload with verbose output
curl -v -X POST http://localhost:8000/api/upload \
  -F "file=@test.dd" \
  -F "case_name=Test" \
  -F "analyst_name=Tester" \
  -F "case_number=TEST-001" \
  2>&1 | grep -E "^< HTTP|^> POST|Method|detail"
```

---

## 📝 Complete Working Example

### Full Setup Process

```bash
# 1. Extract ZIP
unzip Digital-Forensics-Reporter-Complete.zip
cd Digital-Forensics-Reporter-Complete

# 2. Install dependencies
cd backend
pip install -r requirements.txt

# 3. Configure
cp .env.example .env
# Edit .env and add your API keys

# 4. Verify installation
python -c "import pytsk3; print('pytsk3 OK')"
python -c "import fastapi; print('fastapi OK')"

# 5. Start server (in separate terminal)
python main.py

# 6. Create test disk image (in another terminal)
dd if=/dev/zero of=test.dd bs=1M count=10

# 7. Upload
curl -X POST http://localhost:8000/api/upload \
  -F "file=@test.dd" \
  -F "case_name=Test Disk Image" \
  -F "analyst_name=Admin" \
  -F "case_number=TEST-001" \
  -F "department=Lab"

# 8. Check response
# Should show: {"job_id": "...", "file_type": "disk_image", ...}

# 9. Get job_id from response and process
JOB_ID="your_job_id_here"
curl -X POST http://localhost:8000/api/process/$JOB_ID

# 10. Check status
curl http://localhost:8000/api/status/$JOB_ID

# 11. Download report when ready
curl http://localhost:8000/api/report/$JOB_ID > report.pdf
```

---

## 🚀 If All Else Fails

### Reset and Rebuild

```bash
# 1. Stop the server (Ctrl+C)

# 2. Clean up
cd backend
rm -rf __pycache__ .pytest_cache

# 3. Reinstall dependencies fresh
pip uninstall -y pytsk3 fastapi uvicorn pydantic python-multipart
pip install -r requirements.txt

# 4. Verify pytsk3
python -c "import pytsk3; print(pytsk3.__version__)"

# 5. Restart server
python main.py

# 6. Test again
python ../test_disk_image_upload.py
```

### Check Server Logs

Look at the server output (where you ran `python main.py`) for error messages:

```
ERROR - Exception in ASGI application
ERROR - pytsk3 module not found
ERROR - ForensicAnalyzer initialization failed
```

These will tell you exactly what's wrong.

---

## ✅ Success Indicators

When disk image upload is working, you should see:

**In curl response:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "uploaded",
  "file_type": "disk_image",
  "message": "File uploaded successfully"
}
```

**In server logs:**
```
INFO: PYTSK3_INTEGRATION - Analyzing disk image
INFO: Validation passed
INFO: Filesystem detected
```

---

## 📞 Still Stuck?

### Debug Information to Gather

```bash
# 1. Python version
python --version

# 2. pytsk3 version
python -c "import pytsk3; print(pytsk3.__version__)"

# 3. FastAPI version
python -c "import fastapi; print(fastapi.__version__)"

# 4. File being uploaded
file test.dd

# 5. Server logs
# (output from python main.py - copy/paste any errors)

# 6. curl response headers
curl -v -X POST http://localhost:8000/api/upload \
  -F "file=@test.dd" 2>&1 | head -30
```

### Create an Issue Report

If you're still having trouble, provide:
1. Output of `python --version`
2. Output of `python -c "import pytsk3; print(pytsk3.__version__)"`
3. Full curl command you're using
4. Full curl response
5. Server logs (copy/paste the error)
6. File extension of your disk image

---

## 🎯 Quick Checklist

Before submitting a bug report, verify:

- [ ] Python 3.8+ installed
- [ ] pytsk3 installed: `pip install pytsk3`
- [ ] All dependencies installed: `pip install -r backend/requirements.txt`
- [ ] Server running: `python backend/main.py`
- [ ] File has correct extension (.dd, .img, .raw, or .E01)
- [ ] File extension is LOWERCASE
- [ ] Using POST method: `curl -X POST ...`
- [ ] Endpoint is correct: `/api/upload`
- [ ] API keys configured in `.env`
- [ ] No spaces or special chars in file paths

---

**Version**: 1.0.0  
**Status**: Troubleshooting Guide  
**Last Updated**: 2025-04-25

**Once verified, run the test script to confirm everything works!**
