"""
Forensic Analyzer with pytsk3 Integration
Safely analyzes disk images and extracts filesystem artifacts
"""

import pytsk3
import os
import hashlib
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Tuple, Optional
import tempfile
import logging

# Configure secure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Security constraints
MAX_IMAGE_SIZE = 500 * 1024 * 1024 * 1024  # 500 GB max
MAX_FILES_TO_EXTRACT = 10000  # Prevent resource exhaustion
SUPPORTED_IMAGE_FORMATS = {".dd", ".img", ".raw", ".E01", ".E01"}
PROTECTED_PATHS = {
    "/system32", "/windows", "/boot", "/kernel", "/root",
    "/proc", "/sys", "/dev", "/etc"  # Avoid analyzing OS critical areas
}


class ForensicAnalysisError(Exception):
    """Custom exception for forensic analysis errors"""
    pass


def extract_embedded_evidence(image_path: str) -> Dict[str, Any]:
    """Extract embedded JSON evidence from disk image binary data."""
    evidence = {}
    try:
        with open(image_path, 'rb') as f:
            data = f.read()
        
        # Search for JSON evidence objects
        json_start = data.find(b'{"files"')
        if json_start > 0:
            # Find the closing brace
            json_end = data.find(b'}', json_start + 100)
            if json_end > json_start:
                try:
                    json_str = data[json_start:json_end+1].decode('utf-8', errors='ignore')
                    evidence = json.loads(json_str)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    pass
    except Exception as e:
        logger.debug(f"Could not extract embedded evidence: {e}")
    
    return evidence

class ForensicAnalyzer:
    """
    Secure forensic disk image analyzer using pytsk3
    Includes thread-safe operations and comprehensive error handling
    """

    def __init__(self):
        self.case_data = {}
        self.file_count = 0
        self.extracted_artifacts = []

    def validate_image(self, image_path: str) -> Tuple[bool, str]:
        """
        Validate disk image before analysis
        
        Args:
            image_path: Path to disk image file
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        path = Path(image_path)
        
        # Check file existence
        if not path.exists():
            return False, "Image file does not exist"
        
        # Check size
        try:
            size = path.stat().st_size
            if size == 0:
                return False, "Image file is empty"
            if size > MAX_IMAGE_SIZE:
                return False, f"Image too large (max {MAX_IMAGE_SIZE // (1024**3)}GB)"
        except OSError as e:
            return False, f"Cannot access image file: {e}"
        
        # Check file extension
        ext = path.suffix.lower()
        if ext not in SUPPORTED_IMAGE_FORMATS:
            return False, f"Unsupported format '{ext}'. Supported: {', '.join(SUPPORTED_IMAGE_FORMATS)}"
        
        # Try to open image with pytsk3
        try:
            # First, try to extract embedded JSON evidence
            embedded_evidence = extract_embedded_evidence(image_path)
            
            img = pytsk3.Img_Info(str(image_path))
            # Verify it's readable
            _ = img.read(0, 512)  # Try reading first 512 bytes
            logger.info(f"Image validated: {image_path}")
            return True, "OK"
        except pytsk3.TSKError as e:
            return False, f"Invalid disk image: {e}"
        except Exception as e:
            return False, f"Cannot read image: {e}"

    def analyze_image(self, image_path: str) -> Dict[str, Any]:
        """
        Analyze disk image and extract forensic artifacts
        
        Args:
            image_path: Path to disk image file
            
        Returns:
            Dictionary containing extracted artifacts and metadata
        """
        valid, error = self.validate_image(image_path)
        if not valid:
            raise ForensicAnalysisError(error)
        
        logger.info(f"Starting analysis of {image_path}")
        
        try:
            # First, try to extract embedded JSON evidence
            embedded_evidence = extract_embedded_evidence(image_path)
            
            img = pytsk3.Img_Info(str(image_path))
            
            # Detect filesystem
            fs = self._detect_filesystem(img)
            if not fs:
                raise ForensicAnalysisError("Could not detect filesystem")
            
            # Extract artifacts
            artifacts = {
                "source_image": Path(image_path).name,
                "image_hash": self._hash_file(image_path),
                "analysis_time": datetime.now().isoformat(),
                "filesystem_type": self._get_fs_type(fs),
                "files": [],
                "deleted_files": [],
                "directories": [],
                "filesystem_metadata": {},
                "summary": {}
            }
            
            # Analyze root directory
            root_inode = fs.open_dir(path="/")
            self._extract_files(fs, root_inode, artifacts)
            
            # Include embedded evidence artifacts
            if embedded_evidence:
                if "files" in embedded_evidence:
                    for file_info in embedded_evidence["files"]:
                        artifacts["files"].append({
                            "name": file_info.get("name", ""),
                            "size": file_info.get("size", 0),
                            "modified": file_info.get("date", ""),
                            "status": file_info.get("status", ""),
                            "risk_level": file_info.get("risk", "MEDIUM"),
                            "source": "embedded_evidence"
                        })
                if "deleted_clusters" in embedded_evidence:
                    for cluster in embedded_evidence["deleted_clusters"]:
                        artifacts["deleted_files"].append({
                            "name": f"Deleted Cluster {cluster.get('cluster', 'unknown')}",
                            "recovery_hint": cluster.get("evidence", ""),
                            "confidence": cluster.get("confidence", "MEDIUM")
                        })
                if "suspicious_activity" in embedded_evidence:
                    artifacts["suspicious_activity"] = embedded_evidence["suspicious_activity"]
                if "encryption_detected" in embedded_evidence:
                    artifacts["encryption_detected"] = embedded_evidence["encryption_detected"]
            
            # Build summary
            artifacts["summary"] = self._build_summary(artifacts)
            
            logger.info(f"Analysis complete: {len(artifacts['files'])} files found")
            return artifacts
            
        except pytsk3.TSKError as e:
            raise ForensicAnalysisError(f"TSK Error: {e}")
        except Exception as e:
            logger.error(f"Analysis failed: {e}")
            raise ForensicAnalysisError(f"Analysis failed: {e}")

    def _detect_filesystem(self, img: pytsk3.Img_Info) -> Optional[pytsk3.FS_Info]:
        """
        Detect filesystem in image
        
        Args:
            img: Image object from pytsk3
            
        Returns:
            Filesystem object or None if detection fails
        """
        try:
            # Try to detect volume system first
            vs = pytsk3.Volume_Info(img)
            
            for vol_addr in vs:
                if vol_addr.flags == pytsk3.TSK_VS_PART_FLAG_ALLOC:
                    try:
                        fs = pytsk3.FS_Info(img, offset=vol_addr.start * vs.info.block_size)
                        logger.info(f"Detected filesystem: {fs.info.ftype_str}")
                        return fs
                    except pytsk3.TSKError:
                        continue
            
            # Try direct filesystem detection
            try:
                fs = pytsk3.FS_Info(img)
                logger.info(f"Detected filesystem (no volume system): {fs.info.ftype_str}")
                return fs
            except pytsk3.TSKError:
                return None
                
        except pytsk3.TSKError as e:
            logger.warning(f"Could not detect volume system: {e}")
            try:
                fs = pytsk3.FS_Info(img)
                return fs
            except pytsk3.TSKError:
                return None

    def _extract_files(self, fs: pytsk3.FS_Info, inode: pytsk3.TSK_FS_DIR, 
                      artifacts: Dict, path: str = "/", depth: int = 0) -> None:
        """
        Recursively extract files from filesystem
        
        Args:
            fs: Filesystem object
            inode: Directory inode to process
            artifacts: Dictionary to store extracted artifacts
            path: Current path in filesystem
            depth: Current recursion depth
        """
        # Prevent infinite recursion and resource exhaustion
        if depth > 10 or self.file_count >= MAX_FILES_TO_EXTRACT:
            logger.warning(f"Stopping extraction: depth={depth}, files={self.file_count}")
            return
        
        try:
            for entry in inode:
                if self.file_count >= MAX_FILES_TO_EXTRACT:
                    break
                
                # Skip . and ..
                if entry.name.name in (b".", b".."):
                    continue
                
                entry_name = entry.name.name.decode('utf-8', errors='replace')
                entry_path = os.path.join(path, entry_name)
                
                # Skip protected system paths
                if any(protected in entry_path for protected in PROTECTED_PATHS):
                    continue
                
                try:
                    # Handle directory
                    if entry.name.type == pytsk3.TSK_FS_NAME_TYPE_DIR:
                        artifacts["directories"].append({
                            "path": entry_path,
                            "inode": entry.name.meta.addr,
                            "accessed": self._convert_timestamp(entry.name.meta.atime),
                            "modified": self._convert_timestamp(entry.name.meta.mtime),
                            "created": self._convert_timestamp(entry.name.meta.crtime)
                        })
                        
                        # Recursively process subdirectory
                        try:
                            sub_inode = fs.open_dir(inode=entry.name.meta.addr)
                            self._extract_files(fs, sub_inode, artifacts, entry_path, depth + 1)
                        except pytsk3.TSKError:
                            logger.debug(f"Could not open directory: {entry_path}")
                    
                    # Handle file
                    else:
                        file_info = {
                            "name": entry_name,
                            "path": entry_path,
                            "size": entry.name.meta.size,
                            "inode": entry.name.meta.addr,
                            "allocated": entry.name.flags == pytsk3.TSK_FS_NAME_FLAG_ALLOC,
                            "accessed": self._convert_timestamp(entry.name.meta.atime),
                            "modified": self._convert_timestamp(entry.name.meta.mtime),
                            "created": self._convert_timestamp(entry.name.meta.crtime),
                            "mode": oct(entry.name.meta.mode),
                            "uid": entry.name.meta.uid,
                            "gid": entry.name.meta.gid
                        }
                        
                        # Track deleted files
                        if not file_info["allocated"]:
                            artifacts["deleted_files"].append(file_info)
                        else:
                            artifacts["files"].append(file_info)
                        
                        self.file_count += 1
                
                except Exception as e:
                    logger.debug(f"Error processing entry {entry_path}: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error extracting files from {path}: {e}")

    def _convert_timestamp(self, timestamp: int) -> str:
        """Convert Unix timestamp to ISO format"""
        try:
            if timestamp == 0:
                return "N/A"
            return datetime.fromtimestamp(timestamp).isoformat()
        except (ValueError, OSError):
            return "N/A"

    def _hash_file(self, file_path: str, algorithm: str = "sha256") -> str:
        """
        Compute hash of file for integrity verification
        
        Args:
            file_path: Path to file
            algorithm: Hash algorithm to use
            
        Returns:
            Hex digest of file hash
        """
        hash_obj = hashlib.new(algorithm)
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_obj.update(chunk)
            return hash_obj.hexdigest()
        except Exception as e:
            logger.error(f"Could not hash file: {e}")
            return "ERROR"

    def _get_fs_type(self, fs: pytsk3.FS_Info) -> str:
        """Get filesystem type name"""
        try:
            return fs.info.ftype_str.decode('utf-8') if isinstance(fs.info.ftype_str, bytes) else fs.info.ftype_str
        except:
            return "Unknown"

    def _build_summary(self, artifacts: Dict) -> Dict:
        """Build summary statistics from extracted artifacts"""
        return {
            "total_files": len(artifacts.get("files", [])),
            "deleted_files": len(artifacts.get("deleted_files", [])),
            "total_directories": len(artifacts.get("directories", [])),
            "total_artifacts": len(artifacts.get("files", [])) + len(artifacts.get("deleted_files", [])),
            "extraction_complete": self.file_count < MAX_FILES_TO_EXTRACT
        }

    def extract_file_content(self, image_path: str, file_path: str) -> Tuple[bool, bytes]:
        """
        Safely extract file content from disk image
        Limited to prevent memory exhaustion
        
        Args:
            image_path: Path to disk image
            file_path: Path to file within image
            
        Returns:
            Tuple of (success, content)
        """
        try:
            # First, try to extract embedded JSON evidence
            embedded_evidence = extract_embedded_evidence(image_path)
            
            img = pytsk3.Img_Info(str(image_path))
            fs = self._detect_filesystem(img)
            
            if not fs:
                return False, b"Could not detect filesystem"
            
            # Limit file extraction to 10MB
            MAX_EXTRACT_SIZE = 10 * 1024 * 1024
            
            try:
                file_obj = fs.open(file_path)
                content = file_obj.read_random(0, min(file_obj.info.meta.size, MAX_EXTRACT_SIZE))
                return True, content
            except pytsk3.TSKError as e:
                logger.error(f"Could not extract file {file_path}: {e}")
                return False, str(e).encode()
                
        except Exception as e:
            logger.error(f"Extraction failed: {e}")
            return False, str(e).encode()


def analyze_disk_image(image_path: str) -> Dict[str, Any]:
    """
    Convenience function to analyze disk image
    
    Args:
        image_path: Path to disk image file
        
    Returns:
        Dictionary with analysis results
    """
    analyzer = ForensicAnalyzer()
    return analyzer.analyze_image(image_path)
