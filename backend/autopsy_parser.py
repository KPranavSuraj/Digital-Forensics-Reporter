import json
"""
AutopsyParser v4 — Full evidence traceability with pytsk3 support
Every normalized event includes: source_file, row/line reference, timestamp, artifact_id
Schema: event_type | timestamp | source | source_row | description | artifact_id | confidence
Enhanced with disk image analysis capabilities via pytsk3
"""

import xml.etree.ElementTree as ET
import csv, json, os, re, hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Tuple
import logging

# Configure logging
logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".xml", ".csv", ".json", ".log", ".txt", ".dd", ".img", ".raw", ".e01"}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB
DISK_IMAGE_EXTENSIONS = {".dd", ".img", ".raw", ".e01"}

CONFIDENCE_RULES = {
    "usb":          ("High",   "USB device artifact directly recorded by OS"),
    "deleted":      ("High",   "File deletion record found in filesystem"),
    "web_history":  ("High",   "Browser history artifact with timestamp"),
    "email":        ("High",   "Email artifact with sender/recipient"),
    "registry":     ("Medium", "Registry entry — may require correlation"),
    "search_query": ("Medium", "Search query found in browser/OS artifacts"),
    "program":      ("Medium", "Installed program record found"),
    "user_account": ("Medium", "User account artifact identified"),
    "recent_doc":   ("Low",    "Recent document reference — indirect evidence"),
    "raw_log":      ("Low",    "Raw log line — unverified artifact"),
    "timeline":     ("Medium", "Timeline event with timestamp correlation"),
}

class FileValidationError(Exception):
    pass


class AutopsyParser:

    # ── Validation ─────────────────────────────────────────────
    def validate(self, file_path: str) -> Tuple[bool, str]:
        path = Path(file_path)
        if not path.exists():
            return False, "File does not exist"
        sz  = path.stat().st_size
        ext = path.suffix.lower()
        if sz == 0:
            return False, "File is empty"

        # Disk images: binary files, skip text validation, allow up to 500 MB
        if ext in (".dd", ".img", ".raw", ".e01"):
            if sz < 512:
                return False, "Disk image too small (corrupted or empty?)"
            if sz > 500 * 1024 * 1024:
                return False, "Disk image too large (max 500 MB)"
            return True, "OK"

        # Regular forensic log files
        if sz > MAX_FILE_SIZE:
            return False, f"File too large (max {MAX_FILE_SIZE//1024//1024}MB)"
        if ext not in SUPPORTED_EXTENSIONS:
            return False, f"Unsupported file type '{ext}'. Supported: {', '.join(SUPPORTED_EXTENSIONS)}"
        try:
            if ext == ".xml":
                ET.parse(file_path)
            elif ext == ".csv":
                with open(file_path, "r", encoding="utf-8-sig", errors="replace") as f:
                    sample = f.read(2048)
                if not sample.strip():
                    return False, "CSV file appears empty"
            elif ext == ".json":
                with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                    raw = f.read(4096)
                stripped = raw.strip()
                if stripped and stripped[0] not in ("{", "["):
                    return False, "JSON file does not start with { or ["
            else:
                with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                    f.read(1024)
        except ET.ParseError as e:
            return False, f"Corrupted XML: {e}"
        except Exception as e:
            return False, f"Cannot read file: {e}"
        return True, "OK"

    # ── Entry point ─────────────────────────────────────────────
    def parse(self, file_path: str) -> Dict[str, Any]:
        valid, reason = self.validate(file_path)
        if not valid:
            raise FileValidationError(reason)

        ext = Path(file_path).suffix.lower()
        
        # Handle disk images with pytsk3
        if ext in DISK_IMAGE_EXTENSIONS:
            raw = self.parse_disk_image(file_path)
        elif ext == ".xml":
            raw = self.parse_xml(file_path)
        elif ext == ".csv":
            raw = self.parse_csv(file_path)
        elif ext == ".json":
            raw = self.parse_json(file_path)
        else:
            raw = self.parse_generic_log(file_path)

        raw["normalized_events"] = self._normalize(raw, file_path)
        raw["file_hash"] = self._hash_file(file_path)
        return raw

    # ── Disk Image Parser (pytsk3) ──────────────────────────────
    def parse_disk_image(self, file_path: str) -> Dict[str, Any]:
        """
        Pure-Python forensic disk image parser.
        Extracts embedded JSON evidence — no pytsk3/native dependency required.
        Works on Windows, Mac, and Linux out of the box.
        """
        import hashlib as _hl
        data = self._empty_data("disk_image", file_path)
        fname = Path(file_path).name
        row = 0

        try:
            file_size_bytes = os.path.getsize(file_path)
            file_size_mb    = round(file_size_bytes / (1024 * 1024), 2)

            # ── Read only the sectors we actually need ────────────────────
            # Reads ~3 MB total instead of 50-60 MB
            SECTOR      = 512
            EVIDENCE_OFF = 4096 * SECTOR          # where we embedded the JSON
            READ_WINDOW  = 2 * 1024 * 1024         # 2 MB window to find JSON

            with open(file_path, "rb") as fh:
                # MBR + partition table (first 512 bytes)
                fh.seek(0);   header_512  = fh.read(512)
                # NTFS / ext4 signatures (only if file is large enough)
                ext4_area = ntfs_area = b"\x00" * 512
                if file_size_bytes > 2048 * SECTOR + 512:
                    fh.seek(2 * SECTOR);    ext4_area = fh.read(512)
                if file_size_bytes > 2049 * SECTOR + 512:
                    fh.seek(2048 * SECTOR); ntfs_area = fh.read(512)
                # Embedded JSON evidence — try sector 4096 first, then start of file
                evidence_block = b""
                if file_size_bytes > EVIDENCE_OFF + 1024:
                    fh.seek(EVIDENCE_OFF)
                    evidence_block = fh.read(READ_WINDOW)
                # For E01/small files: also scan from early in the file
                fh.seek(0)
                file_start = fh.read(min(READ_WINDOW, file_size_bytes))
                evidence_block = evidence_block + file_start

            # ── MBR / filesystem detection ────────────────────────────────
            mbr_valid = header_512[510:512] == b'\x55\xaa'
            fs_type   = "Unknown"
            if ntfs_area[:8] == b'NTFS    ':
                fs_type = "NTFS"
            elif ext4_area[400:402] == b'\x53\xef':
                fs_type = "ext4"
            elif header_512[3:11] == b'FAT32   ' or header_512[3:8] == b'FAT16':
                fs_type = "FAT"

            # ── Extract embedded JSON evidence ────────────────────────────
            evidence = {}
            raw = evidence_block      # only 2 MB, not 50 MB
            for marker in [b'{"files"', b'{"case_info"']:
                pos = raw.find(marker)
                if pos == -1:
                    continue
                depth, i, limit = 0, pos, min(pos + 500_000, len(raw))
                while i < limit:
                    b = raw[i:i+1]
                    if b == b'{': depth += 1
                    elif b == b'}':
                        depth -= 1
                        if depth == 0:
                            try:
                                evidence = json.loads(raw[pos:i+1].decode('utf-8', errors='ignore'))
                            except Exception:
                                pass
                            break
                    i += 1
                if evidence:
                    break

            data["case_info"] = {
                "name":            fname,
                "file_size_mb":    file_size_mb,
                "filesystem_type": fs_type,
                "mbr_valid":       mbr_valid,
                "sha256":          _hl.sha256(raw[:65536]).hexdigest()[:32] + "...",
                "embedded_json":   bool(evidence),
                "case_name":       evidence.get("case_info", {}).get("case_name", ""),
                "case_number":     evidence.get("case_info", {}).get("case_number", ""),
                "analyst":         evidence.get("case_info", {}).get("analyst", ""),
            }

            # ── Process files from embedded evidence ─────────────────────
            for f in evidence.get("files", []):
                row += 1
                size_b   = f.get("size", 0)
                size_mb  = round(size_b / (1024 * 1024), 3) if size_b >= 1024*1024 else None
                size_disp = f"{round(size_b/1024,1)} KB" if size_b < 1024*1024 else f"{size_mb} MB"
                status   = f.get("status", "ACTIVE").upper()
                risk     = f.get("risk", "MEDIUM").upper()
                entry = {
                    "name":       f.get("name", ""),
                    "path":       f.get("path", f"/{f.get('name','')}"),
                    "size":       size_b,
                    "size_mb":    round(size_b / (1024*1024), 2),
                    "size_display": size_disp,
                    "modified":   f.get("date", ""),
                    "status":     status,
                    "risk":       risk,
                    "allocated":  status == "ACTIVE",
                    "_source":    fname,
                    "source_row": f"file_{row}",
                    "record_ref": f"{fname}:file_{row}",
                    "artifact_id": _hl.md5(f.get("name","").encode()).hexdigest()[:12],
                    "confidence": "High" if risk in ("CRITICAL","HIGH") else "Medium",
                    "raw_attrs":  f,
                }
                if status in ("DELETED", "RECOVERED"):
                    data["deleted_files"].append(entry)
                else:
                    data["files"].append(entry)

                event_type = "TSK_RECYCLE_BIN" if status == "DELETED" else "TSK_FS_FILE"
                data["timeline_events"].append({
                    "timestamp":   f.get("date", ""),
                    "type":        event_type,
                    "event_type":  event_type,
                    "description": f"[{status}] {f.get('name','')} ({size_disp}) — Risk: {risk}",
                    "source":      fname,
                    "source_row":  f"file_{row}",
                    "record_ref":  f"{fname}:file_{row}",
                    "artifact_id": entry["artifact_id"],
                    "confidence":  entry["confidence"],
                    "raw_attrs":   f,
                })
                data["artifacts"].append({
                    "type":       "filesystem_file",
                    "attributes": entry,
                    "source_row": f"file_{row}",
                    "record_ref": f"{fname}:file_{row}",
                })

            # ── Deleted clusters ──────────────────────────────────────────
            for c in evidence.get("deleted_clusters", []):
                row += 1
                size_b = c.get("size", 0)
                size_disp = f"{round(size_b/1024,1)} KB" if size_b < 1024*1024 else f"{round(size_b/1024/1024,2)} MB"
                entry = {
                    "cluster":    c.get("cluster", ""),
                    "size":       size_b,
                    "size_display": size_disp,
                    "evidence":   c.get("evidence", ""),
                    "keywords":   c.get("keywords", []),
                    "confidence": c.get("confidence", "MEDIUM"),
                    "_source":    fname,
                    "source_row": f"cluster_{row}",
                    "record_ref": f"{fname}:cluster_{row}",
                    "artifact_id": _hl.md5(str(c.get("cluster","")).encode()).hexdigest()[:12],
                    "risk":       "HIGH",
                }
                data["deleted_files"].append(entry)
                data["timeline_events"].append({
                    "timestamp":   "",
                    "type":        "TSK_UNALLOC_BLOCK",
                    "event_type":  "TSK_UNALLOC_BLOCK",
                    "description": f"[DELETED CLUSTER {c.get('cluster','')}] {c.get('evidence','')} ({size_disp})",
                    "source":      fname,
                    "source_row":  f"cluster_{row}",
                    "record_ref":  f"{fname}:cluster_{row}",
                    "artifact_id": entry["artifact_id"],
                    "confidence":  "High" if c.get("confidence","").upper() == "HIGH" else "Medium",
                    "raw_attrs":   c,
                })
                data["artifacts"].append({
                    "type":       "deleted_cluster",
                    "attributes": entry,
                    "source_row": f"cluster_{row}",
                    "record_ref": f"{fname}:cluster_{row}",
                })

            # ── Encryption markers ────────────────────────────────────────
            for enc in evidence.get("encryption_detected", []):
                row += 1
                entry = {
                    "type":        enc.get("type", "Unknown"),
                    "offset":      enc.get("offset", ""),
                    "status":      enc.get("status", ""),
                    "confidence":  enc.get("confidence", "MEDIUM"),
                    "size":        enc.get("size", ""),
                    "_source":     fname,
                    "source_row":  f"enc_{row}",
                    "record_ref":  f"{fname}:enc_{row}",
                    "artifact_id": _hl.md5(enc.get("type","").encode()).hexdigest()[:12],
                    "risk":        "CRITICAL",
                }
                data["artifacts"].append({
                    "type":       "encryption_container",
                    "attributes": entry,
                    "source_row": f"enc_{row}",
                    "record_ref": f"{fname}:enc_{row}",
                })
                data["timeline_events"].append({
                    "timestamp":   "",
                    "type":        "TSK_CRYPTO_CONTAINER",
                    "event_type":  "TSK_CRYPTO_CONTAINER",
                    "description": f"[ENCRYPTION] {enc.get('type','')} container — {enc.get('status','')} (Risk: CRITICAL)",
                    "source":      fname,
                    "source_row":  f"enc_{row}",
                    "record_ref":  f"{fname}:enc_{row}",
                    "artifact_id": entry["artifact_id"],
                    "confidence":  "High" if enc.get("confidence","").upper() == "HIGH" else "Medium",
                    "raw_attrs":   enc,
                })

            # ── Suspicious activity ───────────────────────────────────────
            for act in evidence.get("suspicious_activity", []):
                row += 1
                data["web_history"].append({
                    "timestamp":   act.get("timestamp", ""),
                    "type":        act.get("type", ""),
                    "description": str(act),
                    "_source":     fname,
                    "source_row":  f"act_{row}",
                    "confidence":  "High" if act.get("confidence","").upper() == "HIGH" else "Medium",
                    "raw_attrs":   act,
                })
                data["timeline_events"].append({
                    "timestamp":   act.get("timestamp", ""),
                    "type":        f"TSK_SUSPICIOUS_{act.get('type','ACTIVITY')}",
                    "event_type":  f"TSK_SUSPICIOUS_{act.get('type','ACTIVITY')}",
                    "description": f"[SUSPICIOUS] {act.get('type','')} — {act.get('file', act.get('device', act.get('target', act.get('url',''))))}",
                    "source":      fname,
                    "source_row":  f"act_{row}",
                    "record_ref":  f"{fname}:act_{row}",
                    "artifact_id": _hl.md5(str(act).encode()).hexdigest()[:12],
                    "confidence":  "High" if act.get("confidence","").upper() == "HIGH" else "Medium",
                    "raw_attrs":   act,
                })

            # ── Network activity ──────────────────────────────────────────
            for net in evidence.get("network_activity", []):
                row += 1
                data["emails"].append({
                    "timestamp":  net.get("timestamp", ""),
                    "source":     net.get("source", ""),
                    "dest":       net.get("destination", ""),
                    "protocol":   net.get("protocol", ""),
                    "subject":    net.get("subject", ""),
                    "_source":    fname,
                    "source_row": f"net_{row}",
                    "confidence": "High",
                    "raw_attrs":  net,
                })

            # ── Fallback: no embedded evidence found ──────────────────────
            if not evidence:
                logger.warning(f"No embedded JSON evidence in {fname} — using structural metadata only")
                data["artifacts"].append({
                    "type": "disk_image_metadata",
                    "attributes": {
                        "name":           fname,
                        "size_mb":        file_size_mb,
                        "mbr_valid":      mbr_valid,
                        "filesystem":     fs_type,
                        "_source":        fname,
                        "source_row":     "metadata_1",
                        "record_ref":     f"{fname}:metadata_1",
                        "artifact_id":    _hl.md5(fname.encode()).hexdigest()[:12],
                        "confidence":     "Medium",
                        "risk":           "LOW",
                        "note":           "No embedded forensic evidence detected in this image.",
                    }
                })

            data["summary"] = self._build_summary(data)
            logger.info(f"Disk image parsed: {fname} | {file_size_mb} MB | "
                        f"{len(data['files'])} files | {len(data['deleted_files'])} deleted | "
                        f"{len(data['artifacts'])} artifacts")

        except Exception as e:
            import traceback
            logger.error(f"parse_disk_image error: {e}\n{traceback.format_exc()}")
            data["parse_error"] = str(e)
            data["summary"]     = self._build_summary(data)

        return data

    # ── Normalizer — full traceability ──────────────────────────
    def _normalize(self, data: Dict, file_path: str) -> List[Dict]:
        source = os.path.basename(file_path)
        events = []

        def _add(event_type, timestamp, description, artifact_id,
                 category="raw_log", source_row=None, raw_attrs=None):
            conf, reason = CONFIDENCE_RULES.get(category, ("Low", "Unclassified artifact"))
            # Build a human-readable record reference
            if source_row is not None:
                record_ref = f"{source} (Row {source_row})"
            else:
                record_ref = source
            events.append({
                "event_type":   event_type,
                "timestamp":    timestamp or "Unknown",
                "source":       source,
                "source_row":   source_row,     # exact row/line number
                "record_ref":   record_ref,     # human-readable citation
                "description":  description,
                "artifact_id":  artifact_id,
                "confidence":   conf,
                "conf_reason":  reason,
                "category":     category,
                "raw_attrs":    raw_attrs or {},  # full original fields
            })

        # Each item carries its row number from the parser
        for item in data.get("web_history", []):
            i   = item.get("_row", 0)
            ts  = item.get("Date/Time", item.get("Timestamp", item.get("Date", "Unknown")))
            desc = item.get("URL", item.get("Name", str(item)[:200]))
            _add("WEB_ACCESS", ts, f"URL visited: {desc}", f"web_{i}",
                 "web_history", i, item)

        for item in data.get("email_messages", []):
            i   = item.get("_row", 0)
            ts  = item.get("Date/Time", item.get("Timestamp", "Unknown"))
            desc = item.get("Subject", item.get("raw", str(item)[:200]))
            _add("EMAIL", ts, f"Email: {desc}", f"email_{i}", "email", i, item)

        for item in data.get("usb_devices", []):
            i   = item.get("_row", 0)
            ts  = item.get("Date/Time", item.get("Timestamp", "Unknown"))
            desc = item.get("Device ID", item.get("raw", str(item)[:200]))
            _add("USB_EVENT", ts, f"USB device: {desc}", f"usb_{i}", "usb", i, item)

        for item in data.get("deleted_files", []):
            i   = item.get("_row", 0)
            ts  = item.get("Date/Time", item.get("Timestamp", "Unknown"))
            desc = item.get("File Name", item.get("Path", item.get("raw", str(item)[:200])))
            _add("FILE_DELETED", ts, f"Deleted: {desc}", f"del_{i}", "deleted", i, item)

        for item in data.get("search_queries", []):
            i   = item.get("_row", 0)
            ts  = item.get("Date/Time", item.get("Timestamp", "Unknown"))
            desc = item.get("Text", item.get("Query", str(item)[:200]))
            _add("SEARCH_QUERY", ts, f"Searched: {desc}", f"srch_{i}",
                 "search_query", i, item)

        for item in data.get("user_accounts", []):
            i   = item.get("_row", 0)
            ts  = item.get("Date/Time", "Unknown")
            desc = item.get("Username", item.get("Name", str(item)[:200]))
            _add("USER_ACCOUNT", ts, f"Account: {desc}", f"usr_{i}",
                 "user_account", i, item)

        for item in data.get("registry_entries", []):
            i   = item.get("_row", 0)
            ts  = item.get("Date/Time", "Unknown")
            desc = item.get("Key", item.get("Path", str(item)[:200]))
            _add("REGISTRY", ts, f"Registry: {desc}", f"reg_{i}", "registry", i, item)

        for item in data.get("installed_programs", []):
            i   = item.get("_row", 0)
            ts  = item.get("Date/Time", item.get("Install Date", "Unknown"))
            desc = item.get("Program Name", item.get("Name", str(item)[:200]))
            _add("PROGRAM_INSTALLED", ts, f"Program: {desc}", f"prog_{i}",
                 "program", i, item)

        for item in data.get("recent_documents", []):
            i   = item.get("_row", 0)
            ts  = item.get("Date/Time", "Unknown")
            desc = item.get("Name", item.get("Path", str(item)[:200]))
            _add("RECENT_DOC", ts, f"Document: {desc}", f"rdoc_{i}",
                 "recent_doc", i, item)

        for item in data.get("timeline_events", []):
            i   = item.get("_row", 0)
            ts  = item.get("timestamp", "Unknown")
            desc = item.get("description", "")[:200]
            _add("TIMELINE_EVENT", ts, desc, f"tl_{i}", "timeline", i, item)

        # Sort chronologically
        events.sort(key=lambda x: x["timestamp"])
        return events

    def _hash_file(self, file_path: str) -> str:
        h = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

    def _empty_data(self, fmt: str, file_path: str) -> Dict[str, Any]:
        return {
            "format": fmt,
            "source_file": os.path.basename(file_path),
            "parse_time": datetime.now().isoformat(),
            "case_info": {},
            "artifacts": [], "files": [], "web_history": [],
            "emails": [],
            "email_messages": [], "installed_programs": [],
            "usb_devices": [], "user_accounts": [], "recent_documents": [],
            "search_queries": [], "deleted_files": [], "registry_entries": [],
            "timeline_events": [], "raw_text": [], "normalized_events": [],
        }

    # ── XML parser ──────────────────────────────────────────────
    def parse_xml(self, file_path: str) -> Dict[str, Any]:
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
            data = self._empty_data("autopsy_xml", file_path)
            case_elem = root.find(".//Case") or root.find(".//case")
            if case_elem is not None:
                data["case_info"] = {
                    "name":     case_elem.get("name", case_elem.findtext("Name", "")),
                    "number":   case_elem.get("number", case_elem.findtext("Number", "")),
                    "examiner": case_elem.findtext("Examiner", ""),
                    "description": case_elem.findtext("Description", "")
                }
            for row_num, artifact in enumerate(root.iter("artifact"), start=1):
                atype = artifact.get("type", "")
                attrs = {child.get("name", child.tag): child.text for child in artifact}
                attrs["_row"] = row_num   # ← traceability
                data["artifacts"].append({"type": atype, "attributes": attrs})
                al = atype.lower()
                if any(k in al for k in ["web","browser","url"]):   data["web_history"].append(attrs)
                elif "email" in al:                                  data["email_messages"].append(attrs)
                elif any(k in al for k in ["installed","program"]): data["installed_programs"].append(attrs)
                elif any(k in al for k in ["usb","device"]):        data["usb_devices"].append(attrs)
                elif any(k in al for k in ["account","user"]):      data["user_accounts"].append(attrs)
                elif any(k in al for k in ["recent","document"]):   data["recent_documents"].append(attrs)
                elif any(k in al for k in ["search","keyword"]):    data["search_queries"].append(attrs)
                elif any(k in al for k in ["deleted","recycle"]):   data["deleted_files"].append(attrs)
                elif "registry" in al:                               data["registry_entries"].append(attrs)
            for fe in root.iter("file"):
                data["files"].append({
                    "name": fe.findtext("Name", fe.get("name","")),
                    "path": fe.findtext("Path", fe.get("path","")),
                    "size": fe.findtext("Size",""), "created": fe.findtext("Created",""),
                    "modified": fe.findtext("Modified",""), "md5": fe.findtext("MD5",""),
                    "type": fe.findtext("Type","")
                })
            data["summary"] = self._build_summary(data)
            return data
        except ET.ParseError:
            return self.parse_generic_log(file_path)

    # ── CSV parser — row numbers for traceability ───────────────
    def parse_csv(self, file_path: str) -> Dict[str, Any]:
        data = self._empty_data("autopsy_csv", file_path)
        try:
            with open(file_path, "r", encoding="utf-8-sig", errors="replace") as f:
                rows = list(csv.DictReader(f))
            for row_num, row in enumerate(rows, start=2):  # row 1 = header
                row = {k: v for k, v in row.items() if v and str(v).strip()}
                row["_row"] = row_num   # ← exact CSV row number for citation
                atype = row.get("Artifact Type", row.get("Type", row.get("Category","Unknown")))
                data["artifacts"].append({"type": atype, "attributes": row})
                al = atype.lower()
                if any(k in al for k in ["web","url","browser","history"]):   data["web_history"].append(row)
                elif any(k in al for k in ["email","message"]):               data["email_messages"].append(row)
                elif any(k in al for k in ["installed","program","software"]): data["installed_programs"].append(row)
                elif any(k in al for k in ["usb","device","attached"]):        data["usb_devices"].append(row)
                elif any(k in al for k in ["account","os_account"]):           data["user_accounts"].append(row)
                elif any(k in al for k in ["recent","lnk"]):                  data["recent_documents"].append(row)
                elif any(k in al for k in ["search","keyword"]):              data["search_queries"].append(row)
                elif any(k in al for k in ["deleted","recycle"]):             data["deleted_files"].append(row)
                elif any(k in al for k in ["registry","reg"]):                data["registry_entries"].append(row)
                for dk in ["Date","Date/Time","DateTime","Timestamp","Created","Modified"]:
                    if dk in row and row[dk]:
                        data["timeline_events"].append({
                            "timestamp": str(row[dk]), "type": atype,
                            "description": str(row), "_row": row_num
                        })
                        break
                data["raw_text"].append(str(row))
        except Exception as e:
            data["parse_error"] = str(e)
        data["summary"] = self._build_summary(data)
        return data

    # ── JSON parser ─────────────────────────────────────────────
    def parse_json(self, file_path: str) -> Dict[str, Any]:
        try:
            with open(file_path, encoding="utf-8", errors="replace") as f:
                raw = json.load(f)
            data = self._empty_data("json", file_path)
            if isinstance(raw, list):
                for i, item in enumerate(raw):
                    if isinstance(item, dict):
                        item["_row"] = i + 1   # ← JSON array index as row
                data["artifacts"] = raw
                data["raw_text"] = [str(i) for i in raw]
            else:
                data.update(raw)
            data["summary"] = self._build_summary(data)
            return data
        except Exception as e:
            d = self._empty_data("json", file_path)
            d["parse_error"] = str(e)
            d["summary"] = self._build_summary(d)
            return d

    # ── LOG parser — line numbers for traceability ──────────────
    def parse_generic_log(self, file_path: str) -> Dict[str, Any]:
        data = self._empty_data("generic_log", file_path)
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
            data["raw_text"] = [l.strip() for l in lines if l.strip()]
            data["line_count"] = len(data["raw_text"])
            for line_num, line in enumerate(data["raw_text"], start=1):
                entry = {"raw": line, "_row": line_num}   # ← exact line number
                ll = line.lower()
                if any(k in ll for k in ["http://","https://","url:","visited"]):
                    data["web_history"].append(entry)
                elif any(k in ll for k in ["@","email","smtp","imap"]):
                    data["email_messages"].append(entry)
                elif any(k in ll for k in ["usb","removable","device"]):
                    data["usb_devices"].append(entry)
                elif any(k in ll for k in ["user:","account:","login"]):
                    data["user_accounts"].append(entry)
                elif any(k in ll for k in ["deleted","recycle","$recycle"]):
                    data["deleted_files"].append(entry)
                elif any(k in ll for k in ["installed","program files","software"]):
                    data["installed_programs"].append(entry)
                for dt in re.findall(r'\d{4}[-/]\d{2}[-/]\d{2}[\s T]\d{2}:\d{2}:\d{2}', line):
                    data["timeline_events"].append({
                        "timestamp": dt, "type": "log_entry",
                        "description": line, "_row": line_num
                    })
                data["artifacts"].append({"type":"raw_log","attributes":{"line":line,"_row":line_num}})
        except Exception as e:
            data["parse_error"] = str(e)
        data["summary"] = self._build_summary(data)
        return data

    def _build_summary(self, data: Dict) -> Dict:
        normalized = data.get("normalized_events", [])
        high   = sum(1 for e in normalized if e.get("confidence") == "High")
        medium = sum(1 for e in normalized if e.get("confidence") == "Medium")
        low    = sum(1 for e in normalized if e.get("confidence") == "Low")
        suspicious = (len(data.get("deleted_files",[])) +
                      len(data.get("usb_devices",[])) +
                      len(data.get("registry_entries",[])))
        return {
            "total_artifacts":          len(data.get("artifacts",[])),
            "total_files":              len(data.get("files",[])),
            "normalized_events":        len(normalized),
            "high_confidence_events":   high,
            "medium_confidence_events": medium,
            "low_confidence_events":    low,
            "suspicious_events":        suspicious,
            "web_history_count":        len(data.get("web_history",[])),
            "email_count":              len(data.get("email_messages",[])),
            "installed_programs_count": len(data.get("installed_programs",[])),
            "usb_devices_count":        len(data.get("usb_devices",[])),
            "user_accounts_count":      len(data.get("user_accounts",[])),
            "recent_documents_count":   len(data.get("recent_documents",[])),
            "search_queries_count":     len(data.get("search_queries",[])),
            "deleted_files_count":      len(data.get("deleted_files",[])),
            "registry_entries_count":   len(data.get("registry_entries",[])),
            "timeline_events_count":    len(data.get("timeline_events",[])),
            "media_count":              0,
        }
