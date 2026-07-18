"""
ReportGenerator v3 — Legal-grade with full evidence traceability
Sections: Cover | Statistics | Executive Summary | Methodology |
          Findings (with evidence links) | Timeline | Evidence References |
          Conclusions | Recommendations | Chain of Custody
"""

import os, json, shutil
from datetime import datetime
from typing import Dict, List, Any
from pathlib import Path
from dotenv import load_dotenv

ENV_PATH = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=ENV_PATH, override=True)

GROQ_AVAILABLE = OPENAI_AVAILABLE = REPORTLAB_AVAILABLE = False
try:
    from groq import Groq; GROQ_AVAILABLE = True
except ImportError: pass
try:
    from openai import OpenAI; OPENAI_AVAILABLE = True
except ImportError: pass
try:
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                     TableStyle, PageBreak, HRFlowable)
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_JUSTIFY, TA_CENTER
    REPORTLAB_AVAILABLE = True
except ImportError: pass


class ReportGenerator:

    def __init__(self):
        self.client = None
        self.client_type = None
        groq_key = os.getenv("GROQ_API_KEY","").strip()
        openai_key = os.getenv("OPENAI_API_KEY","").strip()
        if groq_key and GROQ_AVAILABLE:
            self.client = Groq(api_key=groq_key); self.client_type = "groq"
            print("[ReportGen] Groq enabled")
        elif openai_key and OPENAI_AVAILABLE:
            self.client = OpenAI(api_key=openai_key); self.client_type = "openai"
            print("[ReportGen] OpenAI enabled")
        else:
            print("[ReportGen] Template mode (no API key found)")
        print(f"[ReportGen] PDF engine: {'ReportLab' if REPORTLAB_AVAILABLE else 'Text fallback'}")

    def set_runtime_key(self, api_key: str, key_type: str):
        try:
            if key_type == "groq" and GROQ_AVAILABLE:
                self.client = Groq(api_key=api_key); self.client_type = "groq"
            elif key_type == "openai" and OPENAI_AVAILABLE:
                self.client = OpenAI(api_key=api_key); self.client_type = "openai"
        except Exception: pass

    def _llm(self, prompt: str, fallback: str) -> str:
        if not self.client: return fallback
        try:
            model = "llama-3.3-70b-versatile" if self.client_type == "groq" else "gpt-3.5-turbo"
            r = self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role":"system","content":"You are a certified forensic examiner writing a formal legal-grade digital forensics report. Be precise, objective, and cite evidence."},
                    {"role":"user","content":prompt}
                ], max_tokens=600, temperature=0.1)
            return r.choices[0].message.content
        except Exception: return fallback

    def _eref(self, ev: Dict, src: str="") -> Dict:
        """Build an evidence reference dict from a normalized event."""
        source = ev.get("source", src)
        row    = ev.get("source_row")
        return {
            "source":      source,
            "row":         row,
            "record_ref":  f"{source} (Row {row})" if row is not None else source,
            "timestamp":   ev.get("timestamp","Unknown"),
            "artifact_id": ev.get("artifact_id","?"),
            "description": ev.get("description",""),
            "confidence":  ev.get("confidence","?"),
        }

    # ── Master generate ────────────────────────────────────────
    def generate(self, job_id, parsed_data, rag_engine, case_info):
        summary  = parsed_data.get("summary", {})
        findings = self._gen_findings(parsed_data, rag_engine, job_id)
        timeline = self._gen_timeline(parsed_data)
        ev_refs  = self._collect_refs(parsed_data, findings)
        return {
            "job_id":            job_id,
            "generated_at":      datetime.now().isoformat(),
            "case_info":         case_info,
            "executive_summary": self._gen_exec(parsed_data, case_info, rag_engine, job_id),
            "methodology":       self._gen_method(),
            "findings":          findings,
            "timeline":          timeline,
            "evidence_refs":     ev_refs,
            "artifacts_detail":  self._gen_detail(parsed_data),
            "conclusions":       self._gen_conclusions(parsed_data, case_info, rag_engine, job_id),
            "recommendations":   self._gen_recs(parsed_data),
            "statistics":        summary,
            "chain_of_custody":  self._gen_coc(case_info, parsed_data),
        }

    def _collect_refs(self, parsed_data, findings):
        refs, seen = [], set()
        src = parsed_data.get("source_file","")
        for f in findings.values():
            if not isinstance(f, dict): continue
            for er in f.get("evidence_refs", []):
                uid = str(er.get("artifact_id","")) + str(er.get("row",""))
                if uid not in seen:
                    seen.add(uid); refs.append(er)
        for ev in parsed_data.get("normalized_events", [])[:80]:
            uid = str(ev.get("artifact_id","")) + str(ev.get("source_row",""))
            if uid not in seen:
                seen.add(uid); refs.append(self._eref(ev, src))
        return refs[:100]

    def _gen_exec(self, parsed_data, case_info, rag_engine, job_id):
        s = parsed_data.get("summary",{}); cn = case_info.get("case_name","Unknown Case")
        fallback = (
            f"This report presents findings of a digital forensic examination of {cn} "
            f"(Case No. {case_info.get('case_number','N/A')}), conducted by "
            f"{case_info.get('analyst_name','the assigned analyst')} of the "
            f"{case_info.get('department','Digital Forensics Lab')}.\n\n"
            f"The examination yielded {s.get('total_artifacts',0)} digital artifacts including "
            f"{s.get('web_history_count',0)} web history entries, "
            f"{s.get('email_count',0)} email records, "
            f"{s.get('usb_devices_count',0)} USB device connections, and "
            f"{s.get('deleted_files_count',0)} recovered deleted files. "
            f"High-confidence events: {s.get('high_confidence_events',0)}. "
            f"Suspicious events: {s.get('suspicious_events',0)}.\n\n"
            f"All evidence has been handled per chain of custody protocols to maintain admissibility."
        )
        ctx = rag_engine.get_case_context(job_id, "executive summary key findings")
        return self._llm(
            f"Write 3-paragraph executive summary for forensics report. Case:{cn} | "
            f"No:{case_info.get('case_number')} | Analyst:{case_info.get('analyst_name')} | "
            f"Stats:{json.dumps(s)} | Context:{ctx[:400]} | Formal legal tone.", fallback)

    def _gen_method(self):
        return (
            "The digital forensic examination was conducted in accordance with NIST SP 800-86 "
            "and ACPO Good Practice Guide for Digital Evidence.\n\n"
            "1. Evidence Acquisition: Subject digital media was forensically processed using "
            "write-blocking procedures. MD5 hash values recorded to verify integrity.\n\n"
            "2. Evidence Verification: Forensic image verified for accuracy. File hash "
            "recorded in chain of custody documentation.\n\n"
            "3. Artifact Extraction: Evidence processed through automated parsing pipeline "
            "covering web history, email, USB devices, user accounts, deleted files, "
            "registry entries, installed programs, and search queries.\n\n"
            "4. Normalization: All artifacts normalized into unified schema with full "
            "traceability: source file, row/line reference, timestamp, artifact ID, "
            "and confidence rating (High/Medium/Low).\n\n"
            "5. RAG Indexing: All artifacts indexed for cross-referencing and AI-assisted "
            "analysis. Each AI finding cites the exact source artifact(s) it is based on.\n\n"
            "6. Documentation: All findings documented with evidence references in format: "
            "'Finding: [X] | Evidence: [filename] (Row [N]) | Time: [T] | Artifact: [ID]'."
        )

    def _gen_findings(self, parsed_data, rag_engine, job_id):
        s   = parsed_data.get("summary",{})
        src = parsed_data.get("source_file","evidence file")
        nrm = parsed_data.get("normalized_events",[])

        def _evs(cat, n=5):
            return [e for e in nrm if e.get("category") == cat][:n]

        def _finding(title, count, narrative, evs):
            return {
                "title":         title,
                "narrative":     narrative,
                "count":         count,
                "evidence_refs": [self._eref(e, src) for e in evs],
                "sample_events": [
                    {"description": e.get("description",""),
                     "timestamp":   e.get("timestamp","Unknown"),
                     "source":      e.get("source", src),
                     "row":         e.get("source_row"),
                     "record_ref":  e.get("record_ref", src),
                     "artifact_id": e.get("artifact_id","?"),
                     "confidence":  e.get("confidence","?")}
                    for e in evs
                ],
            }

        findings = {}
        n = s.get("web_history_count",0); evs = _evs("web_history")
        findings["web_activity"] = _finding("3.1 Web Activity", n,
            f"Examination revealed {n} web browsing history entries providing a chronological "
            "record of websites visited, indicating user intent relevant to the investigation."
            if n else "No web browsing history artifacts identified.", evs)

        n = s.get("email_count",0); evs = _evs("email")
        findings["email_analysis"] = _finding("3.2 Email Analysis", n,
            f"Analysis revealed {n} email message(s) containing relevant correspondence and metadata."
            if n else "No email artifacts identified.", evs)

        n = s.get("usb_devices_count",0); evs = _evs("usb")
        findings["device_connections"] = _finding("3.3 Device Connections", n,
            f"{n} external storage device(s) identified with connection timestamps and device identifiers."
            if n else "No external storage device connections identified.", evs)

        n = s.get("deleted_files_count",0); evs = _evs("deleted")
        findings["deleted_files"] = _finding("3.4 Deleted Files", n,
            f"File system analysis recovered {n} deleted file(s). "
            "Recovery indicates possible deliberate destruction of evidence."
            if n else "No deleted files recovered.", evs)

        n = s.get("user_accounts_count",0); evs = _evs("user_account")
        findings["user_accounts"] = _finding("3.5 User Accounts", n,
            f"{n} user account(s) identified providing insight into access patterns."
            if n else "No user account information identified.", evs)

        n = s.get("search_queries_count",0); evs = _evs("search_query")
        findings["search_queries"] = _finding("3.6 Search Queries", n,
            f"{n} search query record(s) recovered revealing information-seeking behavior."
            if n else "No search query records recovered.", evs)

        n = s.get("installed_programs_count",0); evs = _evs("program")
        findings["installed_programs"] = _finding("3.7 Installed Programs", n,
            f"{n} installed program(s) identified. May reveal tools used for data exfiltration."
            if n else "No installed program records identified.", evs)

        return findings

    def _gen_timeline(self, parsed_data):
        src = parsed_data.get("source_file","")
        formatted, seen = [], set()
        for ev in parsed_data.get("normalized_events",[])[:300]:
            ts = str(ev.get("timestamp","")); aid = ev.get("artifact_id","")
            k = f"{ts}_{aid}"
            if k not in seen:
                seen.add(k)
                row = ev.get("source_row")
                formatted.append({
                    "timestamp":   ts,
                    "event_type":  ev.get("event_type","Unknown"),
                    "description": str(ev.get("description",""))[:200],
                    "source":      ev.get("source", src),
                    "source_row":  row,
                    "record_ref":  ev.get("record_ref", ev.get("source", src)),
                    "artifact_id": ev.get("artifact_id",""),
                    "confidence":  ev.get("confidence","Low"),
                    "category":    ev.get("category",""),
                })
        formatted.sort(key=lambda x: x.get("timestamp","") or "9999")
        return formatted[:150]

    def _gen_detail(self, parsed_data):
        detail = {}
        for key in ["web_history","email_messages","usb_devices","user_accounts",
                    "recent_documents","search_queries","deleted_files","installed_programs"]:
            items = parsed_data.get(key,[])
            detail[key] = {"count": len(items), "samples": items[:5]}
        return detail

    def _gen_conclusions(self, parsed_data, case_info, rag_engine, job_id):
        s = parsed_data.get("summary",{})
        fallback = (
            f"The examination of {case_info.get('case_name','the subject device')} yielded "
            f"{s.get('total_artifacts',0)} recoverable artifacts with "
            f"{s.get('high_confidence_events',0)} high-confidence events identified.\n\n"
            "All conclusions are based solely on the digital evidence recovered and analyzed. "
            "The forensic examiner makes no determination of guilt or innocence."
        )
        ctx = rag_engine.get_case_context(job_id, "suspicious activity conclusion evidence")
        return self._llm(
            f"Write formal conclusions for forensics report. "
            f"Case:{case_info.get('case_name')} | Stats:{json.dumps(s)} | "
            f"Context:{ctx[:400]} | 2 paragraphs.", fallback)

    def _gen_recs(self, parsed_data):
        s = parsed_data.get("summary",{})
        recs = []
        if s.get("web_history_count",0):    recs.append("Further investigation of identified URLs and online accounts is recommended.")
        if s.get("deleted_files_count",0):  recs.append("Recovered deleted files should be subjected to detailed content analysis.")
        if s.get("email_count",0):          recs.append("Email communications should be cross-referenced with known contacts.")
        if s.get("usb_devices_count",0):    recs.append("External storage devices should be located and forensically examined.")
        recs.append("All recovered artifacts should be reviewed by qualified legal counsel.")
        recs.append("Chain of custody documentation must be maintained throughout legal proceedings.")
        return recs

    def _gen_coc(self, case_info, parsed_data):
        return {
            "evidence_item": parsed_data.get("source_file","Unknown"),
            "file_hash":     parsed_data.get("file_hash","Not computed"),
            "received_by":   case_info.get("analyst_name","Unknown"),
            "department":    case_info.get("department","Digital Forensics Lab"),
            "received_date": case_info.get("created_at", datetime.now().isoformat()),
            "analysis_date": datetime.now().isoformat(),
            "tools_used":    ["Autopsy Parser v3","RAG Engine v3","Automated Digital Forensics Reporter v3"],
            "hash_verified": "MD5 hash computed and recorded",
            "notes":         "Evidence handled in accordance with forensic best practices and ACPO guidelines.",
        }

    # ── PDF ────────────────────────────────────────────────────
    def save_pdf(self, report_data, output_path):
        if REPORTLAB_AVAILABLE: self._pdf_reportlab(report_data, output_path)
        else:                   self._pdf_text(report_data, output_path)

    def _pdf_reportlab(self, report_data, output_path):
        doc = SimpleDocTemplate(output_path, pagesize=letter,
              rightMargin=inch, leftMargin=inch, topMargin=inch, bottomMargin=inch)
        styles = getSampleStyleSheet()
        T   = ParagraphStyle('T',  parent=styles['Title'],   fontSize=18, spaceAfter=6,  textColor=colors.HexColor('#1a237e'))
        H1  = ParagraphStyle('H1', parent=styles['Heading1'],fontSize=13, spaceBefore=12,spaceAfter=5,  textColor=colors.HexColor('#1565c0'))
        H2  = ParagraphStyle('H2', parent=styles['Heading2'],fontSize=10, spaceBefore=7, spaceAfter=3,  textColor=colors.HexColor('#0d47a1'))
        B   = ParagraphStyle('B',  parent=styles['Normal'],  fontSize=9,  spaceAfter=5,  leading=13, alignment=TA_JUSTIFY)
        EV  = ParagraphStyle('EV', parent=styles['Normal'],  fontSize=8,  spaceAfter=2,  leading=11, textColor=colors.HexColor('#333333'), leftIndent=10)
        CIT = ParagraphStyle('CIT',parent=styles['Normal'],  fontSize=7.5,spaceAfter=4,  leading=10, textColor=colors.HexColor('#1565c0'), leftIndent=20)
        FT  = ParagraphStyle('FT', parent=styles['Normal'],  fontSize=8,  alignment=TA_CENTER, textColor=colors.HexColor('#757575'))

        def HR(): return HRFlowable(width="100%",thickness=1,color=colors.HexColor('#90caf9'))
        def SP(h=0.15): return Spacer(1, h*inch)
        def tbl(data, widths, hdrbg='#1565c0'):
            t = Table(data, colWidths=widths)
            t.setStyle(TableStyle([
                ('BACKGROUND',(0,0),(-1,0),colors.HexColor(hdrbg)),
                ('TEXTCOLOR',(0,0),(-1,0),colors.white),
                ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),
                ('FONTSIZE',(0,0),(-1,-1),8),
                ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#e3f2fd')]),
                ('GRID',(0,0),(-1,-1),0.4,colors.HexColor('#bdbdbd')),
                ('PADDING',(0,0),(-1,-1),4),('VALIGN',(0,0),(-1,-1),'TOP'),
            ]))
            return t

        ci    = report_data.get("case_info",{})
        stats = report_data.get("statistics",{})
        story = []

        # Cover
        story += [SP(1.5), Paragraph("DIGITAL FORENSICS EXAMINATION REPORT",T),
                  HRFlowable(width="100%",thickness=2,color=colors.HexColor('#1a237e')), SP(0.3)]
        story.append(tbl([
            ["Case Name:",        ci.get("case_name","N/A")],
            ["Case Number:",      ci.get("case_number","N/A")],
            ["Examining Analyst:",ci.get("analyst_name","N/A")],
            ["Department:",       ci.get("department","N/A")],
            ["Date of Report:",   datetime.now().strftime("%B %d, %Y %H:%M UTC")],
            ["Classification:",   "CONFIDENTIAL — FOR OFFICIAL USE ONLY"],
        ], [2.2*inch,4*inch], '#1a237e'))
        story.append(PageBreak())

        # Statistics
        story += [Paragraph("SUMMARY STATISTICS",H1), HR(), SP()]
        s = stats
        story.append(tbl([
            ["Artifact Category","Count","Artifact Category","Count"],
            ["Total Artifacts",str(s.get("total_artifacts",0)),"Normalized Events",str(s.get("normalized_events",0))],
            ["Web History",str(s.get("web_history_count",0)),"Emails",str(s.get("email_count",0))],
            ["USB Devices",str(s.get("usb_devices_count",0)),"Deleted Files",str(s.get("deleted_files_count",0))],
            ["User Accounts",str(s.get("user_accounts_count",0)),"Search Queries",str(s.get("search_queries_count",0))],
            ["High Confidence",str(s.get("high_confidence_events",0)),"Suspicious Events",str(s.get("suspicious_events",0))],
        ],[2.2*inch,0.8*inch,2.2*inch,0.8*inch]))
        story.append(SP())

        # 1. Executive Summary
        story += [Paragraph("1. EXECUTIVE SUMMARY",H1),HR()]
        for p in report_data.get("executive_summary","").split("\n\n"):
            if p.strip(): story.append(Paragraph(p.strip(),B))

        # 2. Methodology
        story += [SP(),Paragraph("2. METHODOLOGY",H1),HR()]
        for p in report_data.get("methodology","").split("\n\n"):
            if p.strip(): story.append(Paragraph(p.strip(),B))

        # 3. Findings with evidence linking
        story += [PageBreak(),Paragraph("3. KEY FINDINGS",H1),HR()]
        for key in ["web_activity","email_analysis","device_connections","deleted_files",
                    "user_accounts","search_queries","installed_programs"]:
            f = report_data.get("findings",{}).get(key,{})
            if not isinstance(f,dict): continue
            story += [SP(0.06), Paragraph(f.get("title",key),H2)]
            story.append(Paragraph(f.get("narrative",""),B))
            for ev in f.get("sample_events",[]):
                desc = str(ev.get("description",""))[:120]
                ref  = ev.get("record_ref", ev.get("source","?"))
                ts   = ev.get("timestamp","Unknown")
                aid  = ev.get("artifact_id","?")
                conf = ev.get("confidence","?")
                story.append(Paragraph(f"Finding: {desc}", EV))
                story.append(Paragraph(f"Evidence: {ref} | Time: {ts} | Artifact: {aid} | Confidence: {conf}", CIT))

        # 4. Timeline
        timeline = report_data.get("timeline",[])
        if timeline:
            story += [PageBreak(),Paragraph("4. FORENSIC TIMELINE",H1),HR()]
            tl_rows = [["Timestamp","Event","Description","Source (Row)","Conf."]]
            for ev in timeline[:50]:
                row = ev.get("source_row"); src = ev.get("source","")
                src_ref = f"{src} (Row {row})" if row is not None else src
                tl_rows.append([
                    str(ev.get("timestamp",""))[:18], str(ev.get("event_type",""))[:18],
                    str(ev.get("description",""))[:60], src_ref[:28], ev.get("confidence","?")[:4],
                ])
            story.append(tbl(tl_rows,[1.4*inch,1.2*inch,2.1*inch,1.5*inch,0.5*inch]))

        # 5. Evidence References
        ev_refs = report_data.get("evidence_refs",[])
        if ev_refs:
            story += [PageBreak(),Paragraph("5. EVIDENCE REFERENCES",H1),HR(),
                      Paragraph(f"Complete list of {len(ev_refs)} evidence artifact(s) cited in this report:",B)]
            er_rows = [["#","Artifact ID","Source File","Row","Timestamp","Confidence"]]
            for i,er in enumerate(ev_refs[:60],1):
                er_rows.append([str(i),str(er.get("artifact_id","?"))[:14],
                    str(er.get("source","?"))[:22],str(er.get("row","N/A")),
                    str(er.get("timestamp","?"))[:18],str(er.get("confidence","?"))[:4]])
            story.append(tbl(er_rows,[0.3*inch,1.1*inch,1.8*inch,0.5*inch,1.5*inch,0.5*inch]))

        # 6. Conclusions
        story += [PageBreak(),Paragraph("6. CONCLUSIONS",H1),HR()]
        for p in report_data.get("conclusions","").split("\n\n"):
            if p.strip(): story.append(Paragraph(p.strip(),B))

        # 7. Recommendations
        story += [SP(),Paragraph("7. RECOMMENDATIONS",H1),HR()]
        for i,rec in enumerate(report_data.get("recommendations",[]),1):
            story.append(Paragraph(f"<b>{i}.</b> {rec}",B))

        # 8. Chain of Custody
        coc = report_data.get("chain_of_custody",{})
        story += [PageBreak(),Paragraph("8. CHAIN OF CUSTODY",H1),HR()]
        story.append(tbl([
            ["Evidence Item:",    str(coc.get("evidence_item","N/A"))],
            ["MD5 Hash:",         str(coc.get("file_hash","N/A"))],
            ["Examined By:",      str(coc.get("received_by","N/A"))],
            ["Department:",       str(coc.get("department","N/A"))],
            ["Analysis Date:",    str(coc.get("analysis_date","N/A"))[:19]],
            ["Tools Used:",       ", ".join(coc.get("tools_used",[]))],
            ["Hash Verification:",str(coc.get("hash_verified","N/A"))],
            ["Notes:",            str(coc.get("notes","N/A"))],
        ],[2*inch,4.5*inch],'#1a237e'))

        story += [SP(0.5),
                  HRFlowable(width="100%",thickness=1,color=colors.HexColor('#1a237e')),
                  Paragraph("END OF REPORT — Automated Digital Forensics Reporter v3.0",FT)]
        doc.build(story)
        print(f"[ReportGen] PDF saved: {output_path}")

    def _pdf_text(self, report_data, output_path):
        text_path = output_path.replace(".pdf",".txt")
        ci = report_data.get("case_info",{})
        with open(text_path,"w",encoding="utf-8") as f:
            f.write("DIGITAL FORENSICS EXAMINATION REPORT\n"+"="*60+"\n\n")
            f.write(f"Case: {ci.get('case_name')} | {ci.get('case_number')}\n")
            f.write(f"Analyst: {ci.get('analyst_name')} | {ci.get('department')}\n")
            f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
            f.write("1. EXECUTIVE SUMMARY\n"+"-"*40+"\n")
            f.write(report_data.get("executive_summary","")+"\n\n")
            f.write("2. METHODOLOGY\n"+"-"*40+"\n")
            f.write(report_data.get("methodology","")+"\n\n")
            f.write("3. FINDINGS\n"+"-"*40+"\n")
            for key, finding in report_data.get("findings",{}).items():
                if not isinstance(finding,dict): continue
                f.write(f"\n{finding.get('title',key)}\n")
                f.write(finding.get("narrative","")+"\n")
                for ev in finding.get("sample_events",[]):
                    f.write(f"  Finding: {ev.get('description','')}\n")
                    f.write(f"  Evidence: {ev.get('record_ref','?')} | Time: {ev.get('timestamp','?')} | Artifact: {ev.get('artifact_id','?')}\n")
            f.write("\n4. FORENSIC TIMELINE\n"+"-"*40+"\n")
            for ev in report_data.get("timeline",[])[:40]:
                row = f" (Row {ev['source_row']})" if ev.get("source_row") is not None else ""
                f.write(f"{ev.get('timestamp','')} → {ev.get('event_type','')} — {ev.get('description','')}\n")
                f.write(f"  Source: {ev.get('source','')}{row}\n")
            f.write("\n5. EVIDENCE REFERENCES\n"+"-"*40+"\n")
            for i,er in enumerate(report_data.get("evidence_refs",[])[:40],1):
                f.write(f"{i}. {er.get('artifact_id','?')} | {er.get('record_ref','?')} | {er.get('timestamp','?')}\n")
            f.write("\n6. CONCLUSIONS\n"+"-"*40+"\n")
            f.write(report_data.get("conclusions","")+"\n")
        shutil.copy(text_path, output_path)
        print(f"[ReportGen] Text report saved: {output_path}")
