# 🔍 Digital Forensics Report Generator

An AI-powered Digital Forensics Report Generator that automates the analysis of forensic evidence and generates structured investigation reports from digital artifacts.

This project is designed to reduce the time forensic analysts spend manually reviewing evidence and writing reports by combining digital forensic analysis with AI-assisted report generation.

---

## 🚀 Features

- 📁 Upload forensic evidence files
- 💾 Support for forensic disk images
  - `.dd`
  - `.img`
  - `.E01`
  - `.raw`
- 📄 Parse forensic logs and extracted artifacts
- 🤖 AI-generated investigation reports
- 📑 Export reports in PDF format
- 🧠 Retrieval-Augmented Generation (RAG) support
- 🗄️ MySQL database integration
- 🔐 Secure authentication system
- 🌐 Modern web interface

---

# 🛠 Tech Stack

### Frontend
- HTML5
- CSS3
- JavaScript

### Backend
- Python
- FastAPI
- Pytsk3
- MySQL

### AI
- OpenAI API / Groq API
- RAG (Retrieval-Augmented Generation)

---

# 📂 Project Structure

```
Digital-Forensics-Reporter
│
├── frontend/
│   ├── index.html
│   ├── login.html
│   └── loading.html
│
├── backend/
│   ├── main.py
│   ├── forensic_analyzer.py
│   ├── report_generator.py
│   ├── rag_engine.py
│   ├── autopsy_parser.py
│   ├── database.py
│   ├── requirements.txt
│   └── .env.example
│
├── sample_data/
├── SETUP_MYSQL.sql
└── README.md
```

---

# ⚙️ Installation

## 1. Clone the repository

```bash
git clone https://github.com/KPranavSuraj/Digital-Forensics-Reporter.git
cd Digital-Forensics-Reporter
```

---

## 2. Create a virtual environment

Windows

```bash
python -m venv venv
venv\Scripts\activate
```

Linux/macOS

```bash
python3 -m venv venv
source venv/bin/activate
```

---

## 3. Install dependencies

```bash
pip install -r backend/requirements.txt
```

---

## 4. Configure environment variables

Copy

```
backend/.env.example
```

to

```
backend/.env
```

Fill in your:

- Database credentials
- API keys
- Secret keys

> **Important:** Never commit your `.env` file to GitHub.

---

## 5. Configure MySQL

Run

```
SETUP_MYSQL.sql
```

to create the required database and tables.

---

## 6. Start the backend

```bash
cd backend
python main.py
```

---

## 7. Open the frontend

Open

```
frontend/index.html
```

or serve it using a local web server.

---

# 📸 Screenshots

Add screenshots here after deployment.

Example:

```
screenshots/
├── login.png
├── dashboard.png
├── upload.png
└── generated-report.png
```

---

# 📑 Workflow

1. User uploads forensic evidence.
2. System validates supported file types.
3. Evidence is parsed and analyzed.
4. AI summarizes findings.
5. RAG enriches the generated report.
6. PDF investigation report is generated.

---

# 📁 Supported Evidence Types

- Disk Images (.dd, .img, .raw, .E01)
- Log Files
- Images
- Audio
- Video
- Documents

---

# 🔒 Security

- Environment variables stored separately
- Database credentials protected
- Input validation
- Secure file uploads

---

# 📈 Future Improvements

- Docker deployment
- User management
- Case management dashboard
- OCR for scanned evidence
- Timeline visualization
- Chain-of-custody tracking
- Cloud deployment

---

# 🤝 Contributing

Contributions are welcome.

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Open a Pull Request

---

# 📄 License

This project is intended for educational and research purposes.

---

# 👨‍💻 Author

**Pranav Suraj**

- GitHub: https://github.com/KPranavSuraj
- LinkedIn: https://www.linkedin.com/in/pranavsuraj-kondaveeti-608850378/

---

⭐ If you found this project useful, consider giving it a star! 
