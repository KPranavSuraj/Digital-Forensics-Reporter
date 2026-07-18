#!/usr/bin/env python3
"""
Example Usage Scripts - pytsk3 Integration
Demonstrates safe and secure usage of the enhanced forensics reporter
"""

import sys
import json
import requests
from pathlib import Path
from datetime import datetime

# Configuration
API_URL = "http://localhost:8000"
TIMEOUT = 300  # 5 minutes

print("=" * 70)
print("Digital Forensics Reporter - pytsk3 Integration Examples")
print("=" * 70)


# ============================================================================
# EXAMPLE 1: Upload and Analyze a Disk Image
# ============================================================================

def example_1_disk_image_analysis():
    """
    Example 1: Upload and analyze a disk image (DD format)
    
    This example demonstrates:
    - Uploading a disk image
    - Monitoring analysis progress
    - Downloading the forensic report
    """
    print("\n[EXAMPLE 1] Disk Image Analysis")
    print("-" * 70)
    
    image_path = "evidence/suspect_drive.dd"
    
    if not Path(image_path).exists():
        print(f"⚠️  Test image not found: {image_path}")
        print("   To run this example:")
        print("   1. Provide a disk image (DD, IMG, RAW, or E01 format)")
        print("   2. Place it in 'evidence/' directory")
        return
    
    try:
        print(f"1. Uploading disk image: {image_path}")
        
        with open(image_path, 'rb') as f:
            files = {'file': f}
            data = {
                'case_name': 'Digital Evidence - Case ABC-2025-001',
                'case_number': 'ABC-2025-001',
                'analyst_name': 'Detective Smith',
                'department': 'Digital Forensics Lab',
                'analysis_mode': 'detailed'
            }
            
            response = requests.post(
                f"{API_URL}/api/upload",
                files=files,
                data=data,
                timeout=TIMEOUT
            )
        
        if response.status_code != 200:
            print(f"   ❌ Upload failed: {response.text}")
            return
        
        result = response.json()
        job_id = result['job_id']
        file_type = result.get('file_type', 'unknown')
        
        print(f"   ✓ Upload successful!")
        print(f"   Job ID: {job_id}")
        print(f"   File Type: {file_type}")
        
        print(f"\n2. Starting analysis...")
        response = requests.post(
            f"{API_URL}/api/process/{job_id}",
            timeout=TIMEOUT
        )
        
        if response.status_code != 200:
            print(f"   ❌ Processing failed: {response.text}")
            return
        
        print(f"   ✓ Analysis started")
        
        print(f"\n3. Monitoring progress...")
        max_wait = 60  # seconds
        poll_interval = 5
        elapsed = 0
        
        while elapsed < max_wait:
            response = requests.get(
                f"{API_URL}/api/status/{job_id}",
                timeout=TIMEOUT
            )
            status = response.json()
            current_status = status.get('status', 'unknown')
            
            print(f"   Status: {current_status}", end='\r')
            
            if current_status == 'completed':
                print(f"   Status: ✓ COMPLETED")
                break
            elif current_status == 'error':
                print(f"   Status: ❌ ERROR")
                print(f"   Error: {status.get('error', 'Unknown')}")
                return
            
            elapsed += poll_interval
            import time
            time.sleep(poll_interval)
        
        if current_status != 'completed':
            print(f"   ⚠️  Analysis timeout")
            return
        
        print(f"\n4. Downloading forensic report...")
        response = requests.get(
            f"{API_URL}/api/report/{job_id}",
            timeout=TIMEOUT
        )
        
        if response.status_code == 200:
            report_path = f"report_{job_id}.pdf"
            with open(report_path, 'wb') as f:
                f.write(response.content)
            print(f"   ✓ Report saved: {report_path}")
        else:
            print(f"   ❌ Report download failed: {response.text}")
        
        print(f"\n5. Getting case preview...")
        response = requests.get(
            f"{API_URL}/api/preview-report/{job_id}",
            timeout=TIMEOUT
        )
        
        if response.status_code == 200:
            preview = response.json()
            summary = preview.get('summary', {})
            
            print(f"   Case Summary:")
            print(f"   - Total Artifacts: {summary.get('total_artifacts', 0)}")
            print(f"   - Suspicious Events: {summary.get('suspicious_events', 0)}")
            print(f"   - Media Items: {summary.get('media_count', 0)}")
        
        print(f"\n✅ Example 1 Complete!")
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Request error: {e}")
    except Exception as e:
        print(f"❌ Error: {e}")


# ============================================================================
# EXAMPLE 2: Upload Traditional Forensic Artifacts (XML/CSV)
# ============================================================================

def example_2_artifact_analysis():
    """
    Example 2: Upload and analyze traditional forensic artifacts
    
    This example demonstrates:
    - Uploading Autopsy XML/CSV exports
    - Analyzing extracted artifacts
    - Querying with AI RAG engine
    """
    print("\n[EXAMPLE 2] Traditional Artifact Analysis")
    print("-" * 70)
    
    artifact_path = "artifacts/autopsy_report.xml"
    
    if not Path(artifact_path).exists():
        print(f"⚠️  Artifact file not found: {artifact_path}")
        print("   To run this example:")
        print("   1. Export case from Autopsy as XML")
        print("   2. Place it in 'artifacts/' directory")
        return
    
    try:
        print(f"1. Uploading forensic artifacts: {artifact_path}")
        
        with open(artifact_path, 'rb') as f:
            files = {'file': f}
            data = {
                'case_name': 'Network Breach Investigation',
                'case_number': 'NET-2025-042',
                'analyst_name': 'Forensic Analyst Johnson',
                'department': 'Cyber Crimes Unit',
                'analysis_mode': 'detailed'
            }
            
            response = requests.post(
                f"{API_URL}/api/upload",
                files=files,
                data=data,
                timeout=TIMEOUT
            )
        
        if response.status_code != 200:
            print(f"   ❌ Upload failed: {response.text}")
            return
        
        result = response.json()
        job_id = result['job_id']
        
        print(f"   ✓ Upload successful!")
        print(f"   Job ID: {job_id}")
        
        print(f"\n2. Processing artifacts...")
        response = requests.post(
            f"{API_URL}/api/process/{job_id}",
            timeout=TIMEOUT
        )
        
        if response.status_code != 200:
            print(f"   ❌ Processing failed: {response.text}")
            return
        
        print(f"   ✓ Processing started")
        
        # Wait for completion
        print(f"\n3. Waiting for analysis completion...")
        import time
        for i in range(12):  # Wait up to 60 seconds
            response = requests.get(f"{API_URL}/api/status/{job_id}")
            status = response.json()
            
            if status['status'] == 'completed':
                print(f"   ✓ Analysis complete!")
                break
            elif status['status'] == 'error':
                print(f"   ❌ Analysis failed: {status.get('error')}")
                return
            
            time.sleep(5)
        
        print(f"\n✅ Example 2 Complete!")
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Request error: {e}")
    except Exception as e:
        print(f"❌ Error: {e}")


# ============================================================================
# EXAMPLE 3: Query Analysis Results with AI
# ============================================================================

def example_3_ai_query(job_id: str):
    """
    Example 3: Query analysis results using AI RAG engine
    
    This example demonstrates:
    - Querying processed cases
    - Using AI for intelligent analysis
    - Getting forensic insights
    """
    print("\n[EXAMPLE 3] AI-Powered Forensic Query")
    print("-" * 70)
    
    if not job_id:
        print("⚠️  Please provide a job_id from a completed analysis")
        return
    
    try:
        print(f"1. Checking case status...")
        response = requests.get(f"{API_URL}/api/status/{job_id}")
        
        if response.status_code != 200:
            print(f"   ❌ Case not found: {job_id}")
            return
        
        status = response.json()
        
        if status['status'] != 'completed':
            print(f"   ❌ Case not ready. Status: {status['status']}")
            return
        
        print(f"   ✓ Case is ready for analysis")
        
        print(f"\n2. Querying case with AI...")
        
        queries = [
            "What suspicious web browsing activity was found?",
            "Were any deleted files recovered?",
            "What USB devices were connected?",
            "Which programs were recently installed?",
            "What is the timeline of suspicious events?"
        ]
        
        for question in queries:
            print(f"\n   Q: {question}")
            
            response = requests.post(
                f"{API_URL}/api/query/{job_id}",
                json={
                    "question": question,
                    "session_token": ""  # Add actual token if using sessions
                },
                timeout=TIMEOUT
            )
            
            if response.status_code == 200:
                result = response.json()
                answer = result.get('answer', 'No answer generated')
                print(f"   A: {answer[:200]}...")
            else:
                print(f"   ❌ Query failed: {response.text}")
        
        print(f"\n✅ Example 3 Complete!")
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Request error: {e}")
    except Exception as e:
        print(f"❌ Error: {e}")


# ============================================================================
# EXAMPLE 4: Direct pytsk3 Usage
# ============================================================================

def example_4_direct_analysis():
    """
    Example 4: Direct pytsk3 analysis without API
    
    This example demonstrates:
    - Using ForensicAnalyzer directly
    - Safe image validation
    - Raw filesystem artifact extraction
    """
    print("\n[EXAMPLE 4] Direct pytsk3 Filesystem Analysis")
    print("-" * 70)
    
    try:
        from forensic_analyzer import ForensicAnalyzer, ForensicAnalysisError
        
        image_path = "evidence/test_image.dd"
        
        if not Path(image_path).exists():
            print(f"⚠️  Test image not found: {image_path}")
            return
        
        print(f"1. Validating image: {image_path}")
        analyzer = ForensicAnalyzer()
        
        is_valid, error = analyzer.validate_image(image_path)
        
        if not is_valid:
            print(f"   ❌ Validation failed: {error}")
            return
        
        print(f"   ✓ Image validation successful")
        
        print(f"\n2. Analyzing filesystem...")
        
        try:
            results = analyzer.analyze_image(image_path)
            
            summary = results.get('summary', {})
            print(f"\n   Filesystem Analysis Results:")
            print(f"   - Filesystem Type: {results.get('filesystem_type')}")
            print(f"   - Total Files: {summary.get('total_files', 0)}")
            print(f"   - Deleted Files: {summary.get('deleted_files', 0)}")
            print(f"   - Total Directories: {summary.get('total_directories', 0)}")
            
            print(f"\n   Recent Files:")
            for file_info in results.get('files', [])[:5]:
                print(f"   - {file_info.get('path', 'N/A')}")
                print(f"     Modified: {file_info.get('modified', 'N/A')}")
            
            print(f"\n   ✓ Analysis complete")
            
        except ForensicAnalysisError as e:
            print(f"   ❌ Analysis failed: {e}")
        
        print(f"\n✅ Example 4 Complete!")
        
    except ImportError:
        print("⚠️  pytsk3 not installed")
        print("   Install with: pip install pytsk3")
    except Exception as e:
        print(f"❌ Error: {e}")


# ============================================================================
# EXAMPLE 5: Batch Analysis
# ============================================================================

def example_5_batch_analysis():
    """
    Example 5: Batch processing multiple evidence files
    
    This example demonstrates:
    - Processing multiple cases in sequence
    - Error recovery
    - Results aggregation
    """
    print("\n[EXAMPLE 5] Batch Evidence Processing")
    print("-" * 70)
    
    evidence_files = [
        ("evidence/case1.dd", "Case-2025-001", "Analyst A"),
        ("evidence/case2.csv", "Case-2025-002", "Analyst B"),
        ("evidence/case3.xml", "Case-2025-003", "Analyst C"),
    ]
    
    results = []
    
    for evidence_path, case_num, analyst in evidence_files:
        if not Path(evidence_path).exists():
            print(f"⚠️  Skipping: {evidence_path} (not found)")
            continue
        
        try:
            print(f"\nProcessing: {evidence_path}")
            
            with open(evidence_path, 'rb') as f:
                files = {'file': f}
                data = {
                    'case_name': f'Batch Case {case_num}',
                    'case_number': case_num,
                    'analyst_name': analyst,
                    'department': 'Batch Processing Lab'
                }
                
                response = requests.post(
                    f"{API_URL}/api/upload",
                    files=files,
                    data=data,
                    timeout=TIMEOUT
                )
            
            if response.status_code == 200:
                result = response.json()
                results.append({
                    'file': evidence_path,
                    'job_id': result['job_id'],
                    'status': 'uploaded'
                })
                print(f"✓ Job {result['job_id']}")
            else:
                results.append({
                    'file': evidence_path,
                    'status': 'failed',
                    'error': response.text
                })
                print(f"❌ Upload failed")
        
        except Exception as e:
            results.append({
                'file': evidence_path,
                'status': 'error',
                'error': str(e)
            })
            print(f"❌ Error: {e}")
    
    # Summary
    print(f"\n{'='*70}")
    print(f"Batch Processing Summary:")
    print(f"{'='*70}")
    
    uploaded = len([r for r in results if r['status'] == 'uploaded'])
    failed = len([r for r in results if r['status'] in ['failed', 'error']])
    
    print(f"Successfully uploaded: {uploaded}")
    print(f"Failed uploads: {failed}")
    print(f"\nJob IDs for monitoring:")
    
    for r in results:
        if 'job_id' in r:
            print(f"  {r['job_id']}")
    
    print(f"\n✅ Example 5 Complete!")


# ============================================================================
# Main Menu
# ============================================================================

def main():
    print("\nAvailable Examples:")
    print("1. Disk Image Analysis")
    print("2. Traditional Artifact Analysis")
    print("3. AI-Powered Query (requires completed case)")
    print("4. Direct pytsk3 Analysis")
    print("5. Batch Processing")
    print("0. Exit")
    
    print("\nNote: Ensure the API is running on http://localhost:8000")
    
    try:
        choice = input("\nSelect example (0-5): ").strip()
        
        if choice == '1':
            example_1_disk_image_analysis()
        elif choice == '2':
            example_2_artifact_analysis()
        elif choice == '3':
            job_id = input("Enter job ID: ").strip()
            example_3_ai_query(job_id)
        elif choice == '4':
            example_4_direct_analysis()
        elif choice == '5':
            example_5_batch_analysis()
        elif choice == '0':
            print("Exiting...")
            sys.exit(0)
        else:
            print("Invalid choice!")
    
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
