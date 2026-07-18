# 🔍 Forensic Disk Images Summary

## Overview
Complete forensic disk images for both investigation cases with comprehensive embedded evidence data.

---

## **📁 Insider Threat Case (CY-2024-0089)**
**Suspect**: John Doe | **Analyst**: Agent M. Rodriguez

### Available Formats
| Format | File Size | Type |
|--------|-----------|------|
| **DD** | 50 MB | Raw sector dump |
| **IMG** | 50 MB | Generic image format |
| **RAW** | 50 MB | Raw binary data |
| **E01** | 20 MB | EnCase format |

### Embedded Evidence
✅ **7 Suspicious Files**:
- `Q4_2024_Strategy_CONFIDENTIAL.docx` (45 KB) — **DELETED** — Confidential corporate strategy
- `client_database_master.mdb` (512 KB) — **DELETED** — Client sensitive data
- `john_doe_personal_notes.txt` (8 KB) — **RECOVERED** — Personal observations
- `mega_upload_batch.zip` (100 KB) — **DELETED** — Exfiltration evidence
- `usb_transfer_log.csv` (4 KB) — **ACTIVE** — USB device activity
- `browser_history.dat` (32 KB) — **ACTIVE** — Web browsing traces
- `gmail_cache.db` (16 KB) — **ACTIVE** — Email communication cache

✅ **Deleted Clusters** (3):
- Q4 Strategy partial recovery (4 KB, HIGH confidence)
- Database index fragments (8 KB, HIGH confidence)
- Deleted email headers (2 KB, MEDIUM confidence)

✅ **Suspicious Activities** (5):
- File deletion: `client_database_master.mdb` — 2024-03-15 10:32:44
- USB device mounted: SanDisk Ultra (Serial: 4C530001200115119007)
- Cloud upload to MEGA.nz — 2024-03-15 09:23:11
- Browser history: mega.nz/upload, competitor-corp.com/careers
- Email to recruiter at competing company

✅ **Network Activity**:
- Email to `recruiter@competitor.com` with 512 KB attachment (2024-03-14)
- ProtonMail communication with backup database (2024-03-15)

---

## **📁 Dark Web Case (CY-2024-0090)**
**Suspect**: Alex R | **Analyst**: Agent K. Patel

### Available Formats
| Format | File Size | Type |
|--------|-----------|------|
| **DD** | 60 MB | Raw sector dump |
| **IMG** | 60 MB | Generic image format |
| **RAW** | 60 MB | Raw binary data |
| **E01** | 25 MB | EnCase format |

### Embedded Evidence
✅ **6 Suspicious Files**:
- `tor_browser.exe` (8 MB) — **ACTIVE** — Anonymous browsing tool
- `veracrypt_container.img` (2 MB) — **ACTIVE** — Encrypted volume (2 GB)
- `electrum_wallet.dat` (64 KB) — **ACTIVE** — Monero cryptocurrency wallet
- `transaction_history_xmr.csv` (100 KB) — **DELETED** — Monero transaction records
- `vendor_contacts_darkweb.txt` (8 KB) — **DELETED** — Darknet vendor contacts
- `marketplace_logs.db` (512 KB) — **RECOVERED** — Marketplace transaction logs

✅ **Deleted Clusters** (3):
- Transaction data fragments (4 KB, HIGH confidence)
- Contact list recovery (8 KB, HIGH confidence)
- Encrypted payload header (2 KB, MEDIUM confidence)

✅ **Encryption Detected** (2):
- VeraCrypt active container (2 GB, HIGH confidence)
- TrueCrypt encrypted volume (1 GB, MEDIUM confidence)

✅ **Suspicious Activities** (4):
- Tor Browser installation — 2024-03-28
- Cryptocurrency wallet (Monero/Electrum)
- VeraCrypt encryption container
- Darknet marketplace access

✅ **Network Activity**:
- Tor .onion domain connection (darknetlive.com)
- ProtonMail to Tutanota communication: "Package confirmed - XMR payment received"

---

## **📊 Evidence Summary**

### **Insider Threat**
| Category | Count | Risk Level |
|----------|-------|-----------|
| CRITICAL artifacts | 2 | 🔴 CRITICAL |
| HIGH artifacts | 3 | 🟠 HIGH |
| Deleted files | 3 | 🟠 HIGH |
| Total evidence items | 15 | Mixed |

### **Dark Web**
| Category | Count | Risk Level |
|----------|-------|-----------|
| CRITICAL artifacts | 3 | 🔴 CRITICAL |
| HIGH artifacts | 3 | 🟠 HIGH |
| Encrypted volumes | 2 | 🔴 CRITICAL |
| Total evidence items | 16 | Mixed |

---

## **🛠️ How to Use**

### **Upload Any Format**
```
1. Click "Upload Evidence" in the web interface
2. Select any disk image:
   - insider_threat_forensic_image.dd
   - insider_threat_forensic_image.E01
   - dark_web_forensic_image.raw
   - etc.
3. Fill case details
4. Click "Analyze"
5. Results display in Artifacts tab
```

### **What You'll See**
✅ All 6-7 files extracted with metadata
✅ Deleted clusters with recovery hints
✅ Suspicious activities flagged
✅ Risk levels (CRITICAL, HIGH, MEDIUM)
✅ Confidence scores (HIGH, MEDIUM, LOW)
✅ Timeline of all events
✅ Network activity correlated

---

## **File Integrity**

All disk images contain:
- ✅ Valid MBR (Master Boot Record)
- ✅ Partition tables (NTFS, ext4)
- ✅ Filesystem headers
- ✅ Embedded JSON evidence (at sector 4096)
- ✅ File signature markers
- ✅ Deleted cluster indicators
- ✅ Multiple evidence formats (for redundancy)

### **Verification**
```bash
# Check image structure
file insider_threat_forensic_image.dd
# Output: data (MBR boot sector, standard)

# Verify embedded evidence
strings insider_threat_forensic_image.dd | grep "Q4_2024"
# Found!
```

---

## **Forensic Analysis Features**

### **Insider Threat Analysis**
- Data exfiltration detection
- Confidential document tracking
- USB device activity correlation
- Email communication analysis
- Competitor research indicators
- Timeline reconstruction

### **Dark Web Analysis**
- Tor/VPN usage detection
- Cryptocurrency wallet tracking
- Encryption container identification
- Darknet marketplace evidence
- Transaction history recovery
- Vendor contact extraction

---

## **Size Breakdown**

```
Total Disk Images: 275 MB
├── Insider Threat (170 MB)
│   ├── DD (50 MB) + IMG (50 MB) + RAW (50 MB) + E01 (20 MB)
└── Dark Web (205 MB)
    ├── DD (60 MB) + IMG (60 MB) + RAW (60 MB) + E01 (25 MB)
```

---

## **Next Steps**

1. **Extract ZIP** → unzip Digital-Forensics-Reporter-Complete.zip
2. **Start Backend** → double-click START.bat
3. **Login** → Use your credentials (admin/analyst/viewer)
4. **Upload Image** → Select any .dd, .img, .raw, or .e01 file
5. **Analyze** → System extracts and displays evidence
6. **Review** → Check Artifacts, Findings, Timeline, Media tabs

---

**Version**: 1.0  
**Embedded Evidence**: Comprehensive forensic datasets  
**Status**: ✅ Ready for Analysis
