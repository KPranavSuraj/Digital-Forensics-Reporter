# 📦 Sample Disk Images for Testing

This folder contains test disk images for the two forensic cases included in the Digital Forensics Reporter application.

---

## 📋 AVAILABLE TEST DISK IMAGES

### **Operation: Dark Web Case**

These are raw disk images from a dark web marketplace investigation:

| Format | File | Size | Purpose |
|--------|------|------|---------|
| **DD** | `operation_dark_web.dd` | 5 MB | Standard raw disk dump |
| **IMG** | `operation_dark_web.img` | 5 MB | Generic image format |
| **RAW** | `operation_dark_web.raw` | 5 MB | Raw sector data |
| **E01** | `operation_dark_web.E01` | 5 MB | EnCase format |

**Case Details:**
- Suspect: TOR marketplace operator
- Evidence: Compromised laptop hard drive
- Key findings in XML/CSV/JSON/LOG files also provided

---

### **Operation: Insider Threat Case**

These are disk images from a corporate espionage investigation:

| Format | File | Size | Purpose |
|--------|------|------|---------|
| **DD** | `operation_insider_threat.dd` | 5 MB | Standard raw disk dump |
| **IMG** | `operation_insider_threat.img` | 5 MB | Generic image format |
| **RAW** | `operation_insider_threat.raw` | 5 MB | Raw sector data |
| **E01** | `operation_insider_threat.E01` | 5 MB | EnCase format |

**Case Details:**
- Suspect: Disgruntled employee
- Evidence: Desktop computer hard drive
- Key findings in XML/CSV/JSON/LOG files also provided

---

## 🚀 HOW TO USE

### **Via Web Interface**

1. **Start the application**
   ```bash
   cd backend
   python main.py
   ```

2. **Open browser**
   ```
   http://localhost:8000
   ```

3. **Upload a disk image**
   - Click "💾 Disk Images" tab
   - Drag or select any `.dd`, `.img`, `.raw`, or `.E01` file
   - Click "⚡ Analyze Disk Image"
   - Wait for analysis to complete
   - View the forensic report

### **Via Command Line**

```bash
# Upload disk image
curl -X POST http://localhost:8000/api/upload \
  -F "file=@operation_dark_web.dd" \
  -F "case_name=Dark Web Investigation" \
  -F "analyst_name=John Doe" \
  -F "case_number=DW-2024-001"

# Get job ID from response
# Then process
curl -X POST http://localhost:8000/api/process/{job_id}

# Check status
curl http://localhost:8000/api/status/{job_id}

# Download report
curl http://localhost:8000/api/report/{job_id} > report.pdf
```

### **Using Test Script**

```bash
# From project root
python test_disk_image_upload.py
```

This will:
1. Create a test disk image
2. Upload it
3. Process it
4. Verify pytsk3 is working

---

## 📊 TEST SCENARIOS

### **Scenario 1: Test All Formats**

Upload each format separately to verify they're all recognized:

```bash
# Test DD format
curl -X POST http://localhost:8000/api/upload \
  -F "file=@operation_dark_web.dd" \
  -F "case_name=Test DD" \
  -F "analyst_name=Tester"

# Test IMG format
curl -X POST http://localhost:8000/api/upload \
  -F "file=@operation_dark_web.img" \
  -F "case_name=Test IMG" \
  -F "analyst_name=Tester"

# Test RAW format
curl -X POST http://localhost:8000/api/upload \
  -F "file=@operation_dark_web.raw" \
  -F "case_name=Test RAW" \
  -F "analyst_name=Tester"

# Test E01 format
curl -X POST http://localhost:8000/api/upload \
  -F "file=@operation_dark_web.E01" \
  -F "case_name=Test E01" \
  -F "analyst_name=Tester"
```

### **Scenario 2: Test Both Cases**

1. Upload dark web case disk image
2. Generate report
3. Query with AI
4. Export results
5. Upload insider threat case
6. Repeat

### **Scenario 3: Mixed Evidence**

1. Upload `operation_dark_web.xml` (artifact)
2. Upload `operation_dark_web.dd` (disk image) to same case
3. Cross-reference findings
4. Generate combined report

---

## 🔍 WHAT'S IN THESE IMAGES

**Format:** Raw disk images (minimal test data)  
**Filesystem:** Basic structure for pytsk3 recognition  
**Size:** 5 MB each (quick for testing)  
**Purpose:** Test pytsk3 integration and disk image analysis workflow

### **What pytsk3 Will Detect:**
- ✅ Disk image format recognition
- ✅ Filesystem type detection
- ✅ File system structure parsing
- ✅ Volume discovery
- ✅ Unallocated space identification

### **Limitations (These Are Test Images):**
- ⚠️ No actual files inside
- ⚠️ No real forensic data
- ⚠️ Not real suspect evidence
- ⚠️ Use for testing only

---

## ✅ EXPECTED RESULTS

When you upload these disk images, the application should:

1. ✅ **Upload successful**
   - Response: `"file_type": "disk_image"`
   - Job created successfully

2. ✅ **Processing**
   - pytsk3 analyzes the image
   - Filesystem detected
   - File listings extracted

3. ✅ **Report generation**
   - PDF created with findings
   - Timeline analysis included
   - File summaries provided

4. ✅ **AI analysis ready**
   - Query the findings
   - Ask questions about the case
   - Get AI-powered insights

---

## 📋 FILE MANIFEST

```
sample_data/
├── operation_dark_web.dd      ← Dark Web case, DD format
├── operation_dark_web.img     ← Dark Web case, IMG format
├── operation_dark_web.raw     ← Dark Web case, RAW format
├── operation_dark_web.E01     ← Dark Web case, E01 format
├── operation_dark_web.xml     ← Dark Web case artifact
├── operation_dark_web.csv     ← Dark Web case artifact
├── operation_dark_web.json    ← Dark Web case artifact
├── operation_dark_web.log     ← Dark Web case artifact
│
├── operation_insider_threat.dd      ← Insider Threat case, DD format
├── operation_insider_threat.img     ← Insider Threat case, IMG format
├── operation_insider_threat.raw     ← Insider Threat case, RAW format
├── operation_insider_threat.E01     ← Insider Threat case, E01 format
├── operation_insider_threat.xml     ← Insider Threat case artifact
├── operation_insider_threat.csv     ← Insider Threat case artifact
├── operation_insider_threat.json    ← Insider Threat case artifact
├── operation_insider_threat.log     ← Insider Threat case artifact
│
└── [Media files and other samples]
```

---

## 🧪 QUICK TEST

1. **Start server**
   ```bash
   cd backend
   python main.py
   ```

2. **Upload test image**
   ```bash
   curl -X POST http://localhost:8000/api/upload \
     -F "file=@sample_data/operation_dark_web.dd" \
     -F "case_name=Quick Test" \
     -F "analyst_name=Tester"
   ```

3. **Check response**
   - Should show: `"file_type": "disk_image"`
   - Should show: Job ID created
   - pytsk3 is working! ✅

---

## 🎯 USE CASES

### **Development & Testing**
- Verify pytsk3 integration
- Test disk image upload workflow
- Validate file format support
- Check report generation

### **Training**
- Demo forensic analysis
- Show disk image processing
- Explain pytsk3 capabilities
- Train new analysts

### **Proof of Concept**
- Show client capabilities
- Demonstrate features
- Validate requirements
- Test performance

---

## ⚠️ IMPORTANT NOTES

1. **These are test images**
   - Not real forensic evidence
   - Minimal content
   - For testing only

2. **For real forensic work**
   - Use actual suspect images
   - Follow chain of custody
   - Maintain write-blocking
   - Document all analysis

3. **Format compatibility**
   - `.dd` - Standard raw format
   - `.img` - Generic image format
   - `.raw` - Raw sector data
   - `.E01` - EnCase format

---

## 📝 TESTING CHECKLIST

Before deploying to production, verify:

- [ ] Can upload .dd files
- [ ] Can upload .img files
- [ ] Can upload .raw files
- [ ] Can upload .E01 files
- [ ] pytsk3 detects disk images
- [ ] Reports generate correctly
- [ ] Both cases work
- [ ] AI analysis works
- [ ] Mixed artifacts work

---

## 🎓 LEARNING PATH

1. **Start Simple**
   - Upload one disk image
   - View the report
   - Understand the output

2. **Test All Formats**
   - Try each format
   - Verify they all work
   - Understand format differences

3. **Try Both Cases**
   - Dark Web case
   - Insider Threat case
   - Compare approaches

4. **Advanced**
   - Upload both artifacts and disk images
   - Cross-reference findings
   - Generate comprehensive reports
   - Use AI to analyze findings

---

## 🚀 READY TO TEST

These disk images are ready to use with the forensics application!

1. Extract the ZIP
2. Start the backend: `python backend/main.py`
3. Open the web interface: `http://localhost:8000`
4. Switch to "💾 Disk Images" tab
5. Upload any of these `.dd`, `.img`, `.raw`, or `.E01` files
6. Watch pytsk3 analyze the disk image
7. Generate and review the forensic report

---

**Version**: 1.0.0  
**Date**: 2025-04-25  
**Status**: Ready for Testing  

**Happy forensic analyzing! 🔍**
