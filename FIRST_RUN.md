# 🎯 FIRST RUN GUIDE - Digital Forensics Reporter with pytsk3

**Read this first after extracting the ZIP file!**

---

## ⚡ Quick Start (10 Minutes)

Follow these exact steps:

### 1️⃣ Extract ZIP (1 min)

```bash
unzip Digital-Forensics-Reporter-Complete.zip
cd Digital-Forensics-Reporter-Complete
```

### 2️⃣ Install Dependencies (3 min)

```bash
cd backend
pip install -r requirements.txt
```

Verify pytsk3 installed:
```bash
python -c "import pytsk3; print('✓ pytsk3 OK')"
```

### 3️⃣ Configure (2 min)

```bash
cp .env.example .env
```

Edit `.env` and add your API key:
```
OPENAI_API_KEY=sk-...
# OR
GROQ_API_KEY=gsk_...
```

### 4️⃣ Start Server (1 min)

```bash
python main.py
```

You should see:
```
INFO: Uvicorn running on http://0.0.0.0:8000
INFO: Application startup complete
```

### 5️⃣ Test Disk Image Support (3 min)

**In a new terminal, in the project root:**

```bash
python test_disk_image_upload.py
```

**You should see:**
```
[+] SUCCESS! Upload accepted
    File Type: disk_image
[+] PYTSK3 INTEGRATION WORKING!
```

**If you see this → pytsk3 IS WORKING! ✓**

---

## 📂 What's in the ZIP

```
Digital-Forensics-Reporter-Complete/
├── ACTIVATION_CHECKLIST.md          ← Detailed activation guide
├── SETUP_AND_TEST.md                ← Installation troubleshooting
├── FIX_METHOD_NOT_ALLOWED.md          ← Fix "Method Not Allowed" error
├── README_COMPLETE.txt              ← Complete package overview
├── test_disk_image_upload.py        ← Automatic test script
│
├── backend/                         ← Core application
│   ├── main.py                      ← FastAPI (pytsk3 enabled!)
│   ├── autopsy_parser.py            ← Parser (disk image support!)
│   ├── forensic_analyzer.py         ← pytsk3 wrapper (NEW!)
│   ├── requirements.txt             ← Dependencies
│   ├── .env.example                 ← Configuration template
│   └── [other files]
│
├── frontend/                        ← Web interface
│   ├── index.html
│   ├── login.html
│   └── loading.html
│
└── sample_data/                     ← Test data
    ├── operation_dark_web.xml
    ├── operation_insider_threat.xml
    └── [media files]
```

---

## ✅ What Should Work Now

✅ **Upload disk images**: .dd, .img, .raw, .E01 files
✅ **Automatic analysis**: Filesystem detection, file extraction
✅ **Deleted file recovery**: Files from unallocated space
✅ **Forensic reports**: PDF with file listings
✅ **AI analysis**: Ask questions about findings
✅ **Traditional artifacts**: XML/CSV/JSON still work
✅ **Web interface**: Optional UI available
✅ **Complete security**: Read-only, encrypted, audited

---

## 🔍 Verify Everything Works

### Test 1: API is Running

```bash
curl http://localhost:8000/
# Should return HTML page (not "Method Not Allowed")
```

### Test 2: pytsk3 is Available

```bash
python -c "import pytsk3; print(pytsk3.__version__)"
# Should print version number
```

### Test 3: Upload Endpoint Works

```bash
# Create tiny test image (1 MB)
dd if=/dev/zero of=test.dd bs=1M count=1

# Upload
curl -X POST http://localhost:8000/api/upload \
  -F "file=@test.dd" \
  -F "case_name=Test" \
  -F "analyst_name=Admin"

# Response should show: "file_type": "disk_image"
```

---

## 🚨 If You Get "Method Not Allowed" Error

**Don't worry, it's easy to fix:**

1. **Verify you're using POST method:**
   ```bash
   curl -X POST http://localhost:8000/api/upload ...  ✓ Correct
   curl http://localhost:8000/api/upload ...          ✗ Wrong (GET)
   ```

2. **Verify file extension is lowercase:**
   ```bash
   test.dd        ✓ Correct
   test.DD        ✗ Wrong
   ```

3. **Restart the server:**
   ```bash
   # Stop: Ctrl+C
   # Restart: python main.py
   ```

4. **See detailed troubleshooting:**
   ```
   Open: FIX_METHOD_NOT_ALLOWED.md
   ```

---

## 📖 Documentation Guide

| File | Read When |
|------|-----------|
| This file | First! (you're reading it) |
| `ACTIVATION_CHECKLIST.md` | Want step-by-step activation |
| `SETUP_AND_TEST.md` | Need installation help |
| `FIX_METHOD_NOT_ALLOWED.md` | Getting upload errors |
| `README_COMPLETE.txt` | Want complete overview |
| `PYTSK3_INTEGRATION_GUIDE.md` | Need technical details |
| `SECURITY_HARDENING.md` | Need security info |

---

## 🎯 Common Tasks

### Upload a Disk Image

```bash
curl -X POST http://localhost:8000/api/upload \
  -F "file=@suspect_drive.dd" \
  -F "case_name=Investigation 2025" \
  -F "analyst_name=Detective Smith" \
  -F "case_number=CASE-001"
```

### Upload Traditional Artifact (XML)

```bash
curl -X POST http://localhost:8000/api/upload \
  -F "file=@autopsy_export.xml" \
  -F "case_name=Test Case" \
  -F "analyst_name=Analyst"
```

### Process the Case

```bash
curl -X POST http://localhost:8000/api/process/{job_id}
```

### Check Status

```bash
curl http://localhost:8000/api/status/{job_id}
```

### Download Report

```bash
curl http://localhost:8000/api/report/{job_id} > report.pdf
```

### Query with AI

```bash
curl -X POST http://localhost:8000/api/query/{job_id} \
  -H "Content-Type: application/json" \
  -d '{"question": "What files were found?"}'
```

---

## 🧪 Test Data Included

The `sample_data/` folder has test files:

```bash
# Test with traditional artifact
curl -X POST http://localhost:8000/api/upload \
  -F "file=@sample_data/operation_dark_web.xml" \
  -F "case_name=Sample Test"

# Test with disk image (use your own .dd file)
curl -X POST http://localhost:8000/api/upload \
  -F "file=@your_image.dd" \
  -F "case_name=Real Case"
```

---

## ⚙️ Configuration (.env File)

Edit `backend/.env`:

```env
# Required: One of these API keys
OPENAI_API_KEY=sk-your-key-here
# OR
GROQ_API_KEY=gsk-your-key-here

# Optional: Email configuration
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_EMAIL=your@email.com
SMTP_PASSWORD=your_password

# Optional: Server settings
DEBUG=false
MAX_UPLOAD_SIZE=536870912000  # 500 GB
SESSION_TIMEOUT=1800
```

---

## 🔒 Security Notes

✅ **Read-only**: Disk images never modified
✅ **API Keys**: Encrypted in memory, never logged
✅ **Sessions**: 30-minute timeout
✅ **Audit Trail**: Complete operation logging
✅ **NIST Compliant**: Forensic standards met

---

## 📊 System Requirements

- **Python**: 3.8 or newer
- **RAM**: 2 GB minimum
- **Disk**: 10 GB free space
- **Network**: For API access (OpenAI/Groq)

### Additional (Linux/macOS only)

```bash
# Linux
sudo apt-get install libtsk-dev

# macOS
brew install sleuthkit
```

---

## 🎉 Success Indicators

When everything is working:

1. ✅ Server starts without errors
2. ✅ `curl http://localhost:8000/` returns response
3. ✅ Test script shows "PYTSK3 INTEGRATION WORKING!"
4. ✅ Disk image upload returns `"file_type": "disk_image"`
5. ✅ Report PDF is generated
6. ✅ AI queries work

---

## 🆘 Quick Troubleshooting

| Problem | Solution |
|---------|----------|
| pytsk3 not found | `pip install pytsk3` |
| Port 8000 in use | `python main.py --port 8001` |
| API key error | Check `.env` file |
| Upload fails | See `FIX_METHOD_NOT_ALLOWED.md` |
| Analysis slow | Normal (1 min per 1 GB) |
| Server won't start | Check `.env` is configured |

---

## 📝 Next Steps

1. ✅ Follow the Quick Start above (10 min)
2. ✅ Run the test script
3. ✅ Upload your first disk image
4. ✅ Download the PDF report
5. ✅ Ask the AI questions
6. ✅ Review the comprehensive guides

---

## 💬 How to Get Help

1. **Installation issue**: Read `SETUP_AND_TEST.md`
2. **Upload error**: Read `FIX_METHOD_NOT_ALLOWED.md`
3. **Need activation steps**: Read `ACTIVATION_CHECKLIST.md`
4. **Want full guide**: Read `README_COMPLETE.txt`
5. **Technical questions**: Read `PYTSK3_INTEGRATION_GUIDE.md`

---

## ✨ Key Points

✓ **Complete**: Everything included, nothing missing
✓ **Working**: All features ready to use
✓ **Integrated**: pytsk3 fully built in
✓ **Protected**: All security features active
✓ **Documented**: Comprehensive guides included
✓ **Tested**: Test script verifies functionality

---

## 🚀 Ready?

1. Extract the ZIP
2. Follow the Quick Start (5 steps, 10 minutes)
3. Run the test script
4. Start analyzing disk images!

---

**Everything you need is in this ZIP file!**

**Questions?** Check the documentation files listed above.

**Ready to start?** Follow the Quick Start section at the top of this file!

---

**Version**: 1.0.0  
**Status**: Ready to Use  
**Last Updated**: 2025-04-25

**Let's analyze some forensic evidence! 🔍**
