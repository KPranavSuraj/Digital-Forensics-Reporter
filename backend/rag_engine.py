"""
RAG Engine v3 — Evidence-backed with full traceability citations
Every chunk and every AI response includes: source file, row/line, timestamp, artifact_id
"""

import os, json
from typing import Dict, List, Any
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

ENV_PATH = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=ENV_PATH, override=True)

GROQ_AVAILABLE = False
OPENAI_AVAILABLE = False
try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    pass
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    pass

SYSTEM_PROMPT = """You are a certified digital forensics analyst. Follow these strict rules:

1. ONLY use forensic evidence from the context. No assumptions, no external knowledge.
2. Every finding MUST cite the evidence in this exact format:
   FINDING: [what was found]
   SOURCE: [filename] | Line/Row [number] | [timestamp]
   ARTIFACT ID: [artifact_id]
   CONFIDENCE: [High/Medium/Low] — [reason]
   ---
3. If the evidence doesn't answer the question, say: "Insufficient evidence in provided data."
4. Never speculate. Only state what the artifacts directly show."""


class ForensicsRAGEngine:

    def __init__(self):
        self.client = None
        self.client_type = None
        self.case_data_store: Dict[str, Any] = {}
        groq_key = os.getenv("GROQ_API_KEY", "").strip()
        openai_key = os.getenv("OPENAI_API_KEY", "").strip()
        if groq_key and GROQ_AVAILABLE:
            self.client = Groq(api_key=groq_key)
            self.client_type = "groq"
            print("[RAG] Groq initialized")
        elif openai_key and OPENAI_AVAILABLE:
            self.client = OpenAI(api_key=openai_key)
            self.client_type = "openai"
            print("[RAG] OpenAI initialized")
        else:
            print(f"[RAG] No API key — keyword mode. .env at: {ENV_PATH}")

    def set_runtime_key(self, api_key: str, key_type: str):
        try:
            if key_type == "groq" and GROQ_AVAILABLE:
                self.client = Groq(api_key=api_key)
                self.client_type = "groq"
            elif key_type == "openai" and OPENAI_AVAILABLE:
                self.client = OpenAI(api_key=api_key)
                self.client_type = "openai"
        except Exception:
            pass

    def index_case(self, job_id: str, parsed_data: Dict) -> None:
        chunks = self._create_chunks(parsed_data)
        self.case_data_store[job_id] = {
            "chunks": chunks,
            "parsed_data": parsed_data,
            "indexed_at": datetime.now().isoformat()
        }
        print(f"[RAG] Indexed {len(chunks)} chunks for job {job_id}")

    def _create_chunks(self, parsed_data: Dict) -> List[Dict]:
        """Build chunks with full traceability metadata on every entry."""
        chunks: List[Dict] = []
        source = parsed_data.get("source_file", "unknown")

        # Summary chunk
        if parsed_data.get("summary"):
            chunks.append({
                "id": "summary", "type": "summary", "confidence": "High",
                "timestamp": parsed_data.get("parse_time", ""),
                "source": source, "source_row": None,
                "record_ref": source,
                "artifact_id": "summary",
                "text": (f"CASE SUMMARY | source={source} | "
                         f"{json.dumps(parsed_data['summary'])}"),
            })

        # Normalized events — each has full traceability already
        for ev in parsed_data.get("normalized_events", [])[:400]:
            row = ev.get("source_row")
            row_str = f"Row {row}" if row else "N/A"
            chunks.append({
                "id":          ev["artifact_id"],
                "type":        ev["category"],
                "confidence":  ev["confidence"],
                "timestamp":   ev["timestamp"],
                "source":      ev["source"],
                "source_row":  row,
                "record_ref":  ev.get("record_ref", ev["source"]),
                "artifact_id": ev["artifact_id"],
                "text": (
                    f"[{ev['event_type']}] {ev['description']} | "
                    f"source={ev['source']} | {row_str} | "
                    f"timestamp={ev['timestamp']} | "
                    f"artifact_id={ev['artifact_id']} | "
                    f"confidence={ev['confidence']}"
                ),
            })

        # Fallback raw chunks if normalized is sparse
        if len(chunks) <= 2:
            def _raw_chunk(prefix, items, cat, conf):
                for i, item in enumerate(items[:30]):
                    row = item.get("_row", i)
                    chunks.append({
                        "id": f"{prefix}_{i}", "type": cat, "confidence": conf,
                        "timestamp": "Unknown", "source": source,
                        "source_row": row,
                        "record_ref": f"{source} (Row {row})" if row else source,
                        "artifact_id": f"{prefix}_{i}",
                        "text": f"[{cat.upper()}] {json.dumps(item)} | source={source} | Row {row}",
                    })
            _raw_chunk("web",  parsed_data.get("web_history",[]),    "web_history", "High")
            _raw_chunk("del",  parsed_data.get("deleted_files",[]),  "deleted",     "High")
            _raw_chunk("usb",  parsed_data.get("usb_devices",[]),    "usb",         "High")
            raw = parsed_data.get("raw_text", [])
            for i in range(0, min(len(raw), 100), 5):
                chunks.append({
                    "id": f"raw_{i}", "type": "raw_log", "confidence": "Low",
                    "timestamp": "Unknown", "source": source,
                    "source_row": i + 1,
                    "record_ref": f"{source} (Lines {i+1}-{i+5})",
                    "artifact_id": f"raw_{i}",
                    "text": " | ".join(raw[i:i+5]),
                })
        return chunks

    def _retrieve(self, job_id: str, question: str, top_k: int = 8) -> List[Dict]:
        chunks = self.case_data_store.get(job_id, {}).get("chunks", [])
        if not chunks:
            return []
        kws = set(w for w in question.lower().split() if len(w) > 2)
        BOOST = {"High": 3, "Medium": 1, "Low": 0}
        scored = []
        for c in chunks:
            score = sum(1 for kw in kws if kw in c["text"].lower())
            score += BOOST.get(c.get("confidence", "Low"), 0)
            if score > 0:
                scored.append((score, c))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [c for _, c in scored[:top_k]] or chunks[:top_k]

    def query(self, job_id: str, question: str, top_k: int = 8) -> str:
        if job_id not in self.case_data_store:
            return "Case data not found. Please process a forensic log first."
        chunks = self._retrieve(job_id, question, top_k)
        context = "\n\n".join(c["text"] for c in chunks)
        if self.client:
            return self._llm_answer(question, context, chunks)
        return self._keyword_answer(question, chunks)

    def _llm_answer(self, question: str, context: str, chunks: List[Dict]) -> str:
        try:
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": (
                    f"FORENSIC EVIDENCE (with traceability):\n{context[:4000]}\n\n"
                    f"QUESTION: {question}\n\n"
                    f"Provide findings with exact source citations (filename, row/line, timestamp)."
                )}
            ]
            model = "llama-3.3-70b-versatile" if self.client_type == "groq" else "gpt-3.5-turbo"
            resp = self.client.chat.completions.create(
                model=model, messages=messages, max_tokens=900, temperature=0.1)
            return resp.choices[0].message.content
        except Exception as e:
            return f"AI error: {e}"

    def _keyword_answer(self, question: str, chunks: List[Dict]) -> str:
        if not chunks:
            return ("No relevant forensic data found.\n\n"
                    "Using limited mode (no API key) — add a Groq key via 🔑 API KEY.")
        lines = []
        for c in chunks:
            conf      = c.get("confidence", "?")
            ts        = c.get("timestamp", "Unknown")
            ref       = c.get("record_ref", c.get("source", "Unknown"))
            aid       = c.get("artifact_id", "?")
            text      = c["text"][:250]
            lines.append(
                f"[{c['type'].upper()}] {text}\n"
                f"  ↳ Source: {ref} | Time: {ts} | Artifact: {aid} | Confidence: {conf}"
            )
        return (
            f"Evidence-based results for '{question}':\n\n"
            + "\n\n".join(lines)
            + "\n\n─────────────────────────────────────\n"
            "Using limited mode (no API key) — AI analysis disabled.\n"
            "Add a Groq key via 🔑 API KEY for full AI-powered responses."
        )

    def get_case_context(self, job_id: str, topic: str) -> str:
        if job_id not in self.case_data_store:
            return ""
        return "\n".join(c["text"] for c in self._retrieve(job_id, topic, top_k=8))
