import hashlib
import random
import streamlit as st
from groq import Groq
from fpdf import FPDF
import json
import re
import time
import os
import io
import html


# ── Groq setup ──────────────────────────────────────────────────────────────
def resolve_groq_key() -> str:
    # 1. Try Streamlit secrets first (the .toml file)
    try:
        key = st.secrets.get("GROQ_API_KEY", "")
        if key: return key
    except Exception:
        pass
        
    # 2. Fallback to Environment Variables (for local testing)
    env_key = os.environ.get("GROQ_API_KEY", "")
    if env_key: return env_key
    
    # 3. Last resort: the sidebar input
    return st.session_state.get("groq_api_key", "")


# Models available on Groq Free Tier (April 2026)
SUPPORTED_GROQ_MODELS = [
    "llama-3.3-70b-versatile", # High quality, 1k requests/day
    "llama-3.1-8b-instant",    # Insanely fast, 14.4k requests/day
    "llama-4-scout-17b"        # Newest efficiency model
]

def call_groq(prompt: str, model: str = "llama-3.3-70b-versatile") -> str:
    api_key = resolve_groq_key()
    if not api_key:
        raise ValueError("no_key")

    client = Groq(api_key=api_key)
    
    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            model=model,
            temperature=0.5, # Lower is better for resume tailoring
        )
        return chat_completion.choices[0].message.content
    except Exception as e:
        # Groq headers return x-ratelimit-remaining-requests
        # Use this to debug if you hit the 1,000/day limit
        raise Exception(f"Groq API Error: {e}")

def create_pdf(text_content, company, first_name, last_name, doc_type):
    # Standardize naming
    clean_company = company.strip().replace(" ", "_") if company else "Company"
    filename = f"{clean_company}_{first_name}_{last_name}_{doc_type}.pdf"
    
    pdf = FPDF()
    pdf.add_page()
    
    # Header: Name and Title
    pdf.set_font("Helvetica", 'B', 16)
    pdf.cell(0, 10, f"{first_name} {last_name}".upper(), ln=True, align='C')
    
    pdf.set_font("Helvetica", 'I', 10)
    pdf.cell(0, 10, f"Application for {company} - {doc_type}", ln=True, align='C')
    pdf.ln(5)
    
    # Body Content
    pdf.set_font("Helvetica", size=11)
    
    # fpdf2 handles multi-line text well with multi_cell
    # We encode/decode to handle special characters gracefully
    clean_text = text_content.encode('latin-1', 'replace').decode('latin-1')
    pdf.multi_cell(0, 7, clean_text)
    
    # Return as bytes for Streamlit download button
    pdf_bytes = pdf.output(dest='S')
    if isinstance(pdf_bytes, str):
        pdf_bytes = pdf_bytes.encode('latin-1')
    elif isinstance(pdf_bytes, memoryview):
        pdf_bytes = pdf_bytes.tobytes()
    elif isinstance(pdf_bytes, bytearray):
        pdf_bytes = bytes(pdf_bytes)
    if not isinstance(pdf_bytes, bytes):
        raise RuntimeError(
            "PDF creation returned unsupported binary data format. "
            f"Got: {type(pdf_bytes).__name__}"
        )
    return pdf_bytes, filename

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="ResumeAI – Smart Resume Tailoring",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&family=Sora:wght@400;600;700&display=swap');

/* ── Root & body ── */
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

/* ── Hide default Streamlit chrome ── */
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding-top: 1.5rem; padding-bottom: 3rem; max-width: 1100px; }

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background: #0f1117;
    border-right: 1px solid #1e2130;
}
[data-testid="stSidebar"] * { color: #c8cfe8 !important; }
[data-testid="stSidebar"] .sidebar-logo {
    font-family: 'Sora', sans-serif;
    font-size: 1.4rem;
    font-weight: 700;
    color: #fff !important;
    letter-spacing: -0.5px;
    margin-bottom: 0.25rem;
}
[data-testid="stSidebar"] .sidebar-tagline {
    font-size: 0.78rem;
    color: #6272a4 !important;
    margin-bottom: 2rem;
}
[data-testid="stSidebar"] hr { border-color: #1e2130 !important; margin: 1.2rem 0; }
[data-testid="stSidebar"] .sidebar-section-label {
    font-size: 0.7rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #6272a4 !important;
    margin-bottom: 0.5rem;
}
[data-testid="stSidebar"] .stRadio label { font-size: 0.88rem !important; }

/* ── Step nav pills ── */
.step-nav {
    display: flex;
    gap: 10px;
    margin-bottom: 1.8rem;
    flex-wrap: wrap;
}
.step-pill {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 7px 16px;
    border-radius: 99px;
    font-size: 0.83rem;
    font-weight: 500;
    border: 1.5px solid transparent;
    cursor: default;
    white-space: nowrap;
}
.step-pill.active {
    background: #1a1d2e;
    border-color: #4f5cff;
    color: #7c87ff;
}
.step-pill.done {
    background: #0d1f16;
    border-color: #1d6b3b;
    color: #3dba6f;
}
.step-pill.inactive {
    background: #0f1117;
    border-color: #1e2130;
    color: #3a3f5c;
}
.step-num {
    width: 20px; height: 20px;
    border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: 0.7rem; font-weight: 700;
    background: currentColor;
    flex-shrink: 0;
}
.step-num span { color: #0f1117; }

/* ── Section headings ── */
.section-heading {
    font-family: 'Sora', sans-serif;
    font-size: 1.35rem;
    font-weight: 700;
    color: #e8eaf6;
    margin-bottom: 0.25rem;
}
.section-sub {
    font-size: 0.85rem;
    color: #6272a4;
    margin-bottom: 1.5rem;
}

/* ── Cards ── */
.card {
    background: #161822;
    border: 1px solid #1e2130;
    border-radius: 12px;
    padding: 1.4rem 1.6rem;
    margin-bottom: 1rem;
}
.card-title {
    font-size: 0.78rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.07em;
    color: #6272a4;
    margin-bottom: 0.75rem;
}

/* ── Keyword pills ── */
.kw-grid { display: flex; flex-wrap: wrap; gap: 7px; margin-top: 4px; }
.kw { 
    font-size: 0.78rem; 
    padding: 4px 11px; 
    border-radius: 99px; 
    font-weight: 500;
    border: 1px solid;
}
.kw-hard   { background: #0d1a35; color: #6ba3ff; border-color: #1e3a6e; }
.kw-soft   { background: #0d2218; color: #4dcc85; border-color: #1a5236; }
.kw-ats    { background: #2a1f05; color: #f0a930; border-color: #5a3f0a; }
.kw-miss   { background: #2a0d0d; color: #ff6b6b; border-color: #5a1a1a; }

/* ── Match score bar ── */
.score-wrap { margin-top: 0.4rem; }
.score-bar-bg {
    height: 8px;
    background: #1e2130;
    border-radius: 99px;
    overflow: hidden;
    margin-bottom: 5px;
}
.score-bar-fill {
    height: 100%;
    border-radius: 99px;
    transition: width 0.6s ease;
}
.score-label {
    font-size: 0.8rem;
    color: #6272a4;
}

/* ── Textarea / input overrides ── */
textarea, .stTextArea textarea {
    background: #0d0f18 !important;
    border: 1px solid #1e2130 !important;
    border-radius: 8px !important;
    color: #c8cfe8 !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 0.87rem !important;
    line-height: 1.65 !important;
}
textarea:focus, .stTextArea textarea:focus {
    border-color: #4f5cff !important;
    box-shadow: 0 0 0 2px rgba(79,92,255,0.18) !important;
}

/* ── Buttons ── */
.stButton > button {
    background: linear-gradient(135deg, #4f5cff, #7c4dff) !important;
    color: #fff !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    font-size: 0.88rem !important;
    padding: 0.5rem 1.4rem !important;
    transition: opacity 0.15s !important;
}
.stButton > button:hover { opacity: 0.88 !important; }
.stButton > button[kind="secondary"] {
    background: #161822 !important;
    border: 1px solid #1e2130 !important;
    color: #c8cfe8 !important;
}

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {
    gap: 4px;
    background: #0d0f18;
    border-radius: 10px;
    padding: 4px;
    border: 1px solid #1e2130;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 7px;
    color: #6272a4;
    font-size: 0.85rem;
    padding: 6px 18px;
}
.stTabs [aria-selected="true"] {
    background: #161822;
    color: #e8eaf6;
}
.stTabs [data-baseweb="tab-highlight"] { display: none; }
.stTabs [data-baseweb="tab-border"] { display: none; }

/* ── Output text area ── */
.output-area {
    background: #0d0f18;
    border: 1px solid #1e2130;
    border-radius: 10px;
    padding: 1.2rem 1.4rem;
    font-size: 0.85rem;
    line-height: 1.8;
    color: #c8cfe8;
    white-space: pre-wrap;
    min-height: 260px;
    font-family: 'Inter', sans-serif;
}

/* ── Upload area ── */
[data-testid="stFileUploader"] {
    background: #0d0f18;
    border: 1.5px dashed #1e2130;
    border-radius: 10px;
    padding: 0.5rem;
}
[data-testid="stFileUploader"]:hover { border-color: #4f5cff; }

/* ── Info/success/warning callouts ── */
.callout {
    padding: 10px 14px;
    border-radius: 8px;
    font-size: 0.83rem;
    margin-bottom: 1rem;
    display: flex;
    align-items: flex-start;
    gap: 10px;
}
.callout-info    { background: #0d1a35; border-left: 3px solid #4f5cff; color: #6ba3ff; }
.callout-success { background: #0d2218; border-left: 3px solid #3dba6f; color: #4dcc85; }
.callout-warn    { background: #2a1f05; border-left: 3px solid #f0a930; color: #f0a930; }

/* ── Metric tiles ── */
.metric-tile {
    background: #161822;
    border: 1px solid #1e2130;
    border-radius: 10px;
    padding: 1rem 1.2rem;
    text-align: center;
}
.metric-num {
    font-family: 'Sora', sans-serif;
    font-size: 1.8rem;
    font-weight: 700;
    color: #e8eaf6;
}
.metric-label {
    font-size: 0.75rem;
    color: #6272a4;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin-top: 2px;
}

/* ── Select/radio ── */
.stSelectbox > div > div, .stRadio > div {
    background: #0d0f18 !important;
    border-color: #1e2130 !important;
    color: #c8cfe8 !important;
}
</style>
""", unsafe_allow_html=True)

# ── Session state defaults ─────────────────────────────────────────────────────
defaults = {
    "step": 1,
    "resume_text": "",
    "job_text": "",
    "keywords": {
        "hard_skills": [],
        "soft_skills": [],
        "ats_phrases": [],
        "missing": [],
        "match_score": 0,
    },
    "tailored_resume": "",
    "cover_letter": "",
    "tone": "Professional",
    "length": "Standard (1 page)",
    "include_cover": True,
    "company_name": "",
    "first_name": "",
    "last_name": "",
    "full_name": "",
    "model": "llama-3.1-8b-instant", # Change default model
    "groq_api_key": "",                 # New key storage
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown('<div class="sidebar-logo">📄 ResumeAI</div>', unsafe_allow_html=True)
    st.markdown('<div class="sidebar-tagline">ATS-optimized resumes in seconds</div>', unsafe_allow_html=True)
    st.markdown('<hr>', unsafe_allow_html=True)

    st.markdown('<div class="sidebar-section-label">Output settings</div>', unsafe_allow_html=True)
    st.session_state.tone = st.selectbox(
        "Writing tone",
        ["Professional", "Conversational", "Technical", "Executive"],
        index=["Professional", "Conversational", "Technical", "Executive"].index(st.session_state.tone),
    )
    st.session_state.length = st.selectbox(
        "Resume length",
        ["Concise (½ page)", "Standard (1 page)", "Detailed (2 pages)"],
        index=["Concise (½ page)", "Standard (1 page)", "Detailed (2 pages)"].index(st.session_state.length),
    )
    st.session_state.include_cover = st.toggle("Generate cover letter", value=st.session_state.include_cover)

    st.markdown('<div class="sidebar-section-label">Groq API key</div>', unsafe_allow_html=True)
    groq_key_input = st.text_input(
        "Groq API key",
        value=st.session_state.get("groq_api_key", ""),
        type="password",
        placeholder="gsk_...",
        label_visibility="collapsed"
)
    st.session_state["groq_api_key"] = groq_key_input

    st.markdown('<hr>', unsafe_allow_html=True)
    st.markdown('<div class="sidebar-section-label">Export format</div>', unsafe_allow_html=True)
    export_fmt = st.radio("Format", ["Plain text", "Markdown", "PDF-ready HTML"], label_visibility="collapsed")

    st.markdown('<hr>', unsafe_allow_html=True)
    st.markdown('<div class="sidebar-section-label">Groq key status</div>', unsafe_allow_html=True)
    if resolve_groq_key():
        st.markdown('<span style="font-size:0.75rem;color:#3dba6f">✓ Groq key ready</span>', unsafe_allow_html=True)
    else:
        st.markdown('<span style="font-size:0.75rem;color:#ff6b6b">⚠ No Groq key set</span>', unsafe_allow_html=True)

    st.markdown('<hr>', unsafe_allow_html=True)
    st.markdown('<div class="sidebar-section-label">About</div>', unsafe_allow_html=True)
    st.markdown(
        '<span style="font-size:0.78rem; color:#3a3f5c"> Powered by: J.O.S.H. AI. '
        'JOSH AI can make mistakes. Please use with caution.</span>',
        unsafe_allow_html=True,
    )

# ── Step nav ───────────────────────────────────────────────────────────────────
def step_pill(num, label, current):
    if num < current:
        cls = "done"
        icon = "✓"
    elif num == current:
        cls = "active"
        icon = str(num)
    else:
        cls = "inactive"
        icon = str(num)
    return f'<div class="step-pill {cls}"><div class="step-num"><span>{icon}</span></div>{label}</div>'

steps = ["Resume input", "Job posting", "Keywords", "Results"]
pills = "".join(step_pill(i + 1, s, st.session_state.step) for i, s in enumerate(steps))
st.markdown(f'<div class="step-nav">{pills}</div>', unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════
# STEP 1 — Resume input
# ═══════════════════════════════════════════════════════════════
if st.session_state.step == 1:
    st.markdown('<div class="section-heading">Your resume</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-sub">Upload a file or paste your experience directly</div>', unsafe_allow_html=True)

    tab_upload, tab_paste, tab_form = st.tabs(["📎 Upload file", "📋 Paste text", "✏️ Fill form"])

    with tab_upload:
        uploaded = st.file_uploader(
            "Drop your resume here",
            type=["pdf", "docx", "txt"],
            label_visibility="collapsed",
        )
        if uploaded:
            st.markdown(
                f'<div class="callout callout-success">✓ &nbsp;<strong>{uploaded.name}</strong> uploaded successfully</div>',
                unsafe_allow_html=True,
            )

    with tab_paste:
        resume_paste = st.text_area(
            "Paste resume content",
            value=st.session_state.resume_text,
            height=260,
            placeholder="Paste your full resume text here — work experience, skills, education, achievements...",
            label_visibility="collapsed",
        )
        st.session_state.resume_text = resume_paste

    with tab_form:
        st.markdown('<div class="card"><div class="card-title">Personal info</div>', unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            full_name = st.text_input("Full name", value=st.session_state.full_name, placeholder="Jon Doe")
            st.session_state.full_name = full_name
            name_parts = full_name.strip().split(None, 1)
            st.session_state.first_name = name_parts[0] if name_parts else ""
            st.session_state.last_name = name_parts[1] if len(name_parts) > 1 else ""
            st.text_input("Email", placeholder="jon@example.com")
        with c2:
            st.text_input("Location", placeholder="Surrey, BC")
            st.text_input("LinkedIn / Portfolio", placeholder="linkedin.com/in/...")
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="card"><div class="card-title">Work experience</div>', unsafe_allow_html=True)
        st.text_area(
            "Experience",
            height=120,
            placeholder="Job title | Company | Dates\n– Bullet point achievement...\n– Another achievement...",
            label_visibility="collapsed",
        )
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="card"><div class="card-title">Skills & education</div>', unsafe_allow_html=True)
        c3, c4 = st.columns(2)
        with c3:
            st.text_area("Skills", height=90, placeholder="Python, AWS, SQL, Git...", label_visibility="collapsed")
        with c4:
            st.text_area("Education", height=90, placeholder="Degree | School | Year", label_visibility="collapsed")
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("Continue to job posting →", type="primary", use_container_width=False):
        st.session_state.step = 2
        st.rerun()


# ═══════════════════════════════════════════════════════════════
# STEP 2 — Job posting
# ═══════════════════════════════════════════════════════════════
elif st.session_state.step == 2:
    st.markdown('<div class="section-heading">Job posting</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-sub">Paste the full job description — the more detail, the better the keyword match</div>', unsafe_allow_html=True)

    st.markdown('<div class="card"><div class="card-title">Job details (optional)</div>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    with c1:
        company_name = st.text_input("Company name", value=st.session_state.company_name, placeholder="Acme Corp")
        st.session_state.company_name = company_name
    with c2:
        st.text_input("Role title", placeholder="Senior Backend Engineer")
    with c3:
        st.selectbox("Seniority", ["Junior", "Mid-level", "Senior", "Lead", "Manager", "Director"])
    st.markdown('</div>', unsafe_allow_html=True)

    job_text = st.text_area(
        "Full job description",
        value=st.session_state.job_text,
        height=320,
        placeholder="Paste the complete job posting here — requirements, responsibilities, qualifications, tech stack...",
        label_visibility="collapsed",
    )
    st.session_state.job_text = job_text

    st.markdown(
        '<div class="callout callout-info">💡 Include the full posting including "nice to have" sections — '
        'ATS systems often score on these too.</div>',
        unsafe_allow_html=True,
    )

    col_back, col_fwd, _ = st.columns([1, 1.5, 4])
    with col_back:
        if st.button("← Back", use_container_width=True):
            st.session_state.step = 1
            st.rerun()
    with col_fwd:
        if st.button("Extract keywords →", type="primary", use_container_width=True):
            if not st.session_state.resume_text and not st.session_state.job_text:
                st.warning("Please fill in your resume and the job posting.")
            else:
                with st.spinner("Extracting keywords..."):
                    prompt = f"""Analyze this resume against the job posting and return ONLY a valid JSON object. No markdown, no backticks, no explanation. IMPORTANT: Return ONLY the text of the resume itself. 
                                Do not include any introductions, notes, warnings, or feedback about the candidate's fit. 
                                The output should start immediately with the Resume content and end immediately after the final section.

Resume:
{st.session_state.resume_text}

Job posting:
{st.session_state.job_text}

Return exactly this structure:
{{"hard_skills":["skill1","skill2"],"soft_skills":["skill1"],"ats_phrases":["exact phrase from posting"],"missing":["required skill not in resume"],"match_score":62}}

Rules:
- hard_skills: technical/tool skills from the posting that ARE already in the resume
- soft_skills: interpersonal/behavioral skills from the posting that ARE in the resume
- ats_phrases: exact multi-word phrases from the posting (3-6 items)
- missing: required skills/tools from the posting that are NOT in the resume
- match_score: integer 0-100 representing current resume-to-posting match"""
                    try:
                        raw = call_groq(prompt)
                        clean = re.sub(r"```json|```", "", raw).strip()
                        st.session_state.keywords = json.loads(clean)
                        st.session_state.step = 3
                        st.rerun()
                    except ValueError:
                        st.error("Please enter your Groq API key in the sidebar first.")
                    except json.JSONDecodeError:
                        st.error("Groq returned unexpected output. Try again — this sometimes happens on the free tier.")
                    except Exception as e:
                        st.error(f"API error: {e}")


# ═══════════════════════════════════════════════════════════════
# STEP 3 — Keywords
# ═══════════════════════════════════════════════════════════════
elif st.session_state.step == 3:
    st.markdown('<div class="section-heading">Keyword analysis</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-sub">Extracted from the job posting and compared against your resume</div>', unsafe_allow_html=True)

    kw = st.session_state.keywords
    score = kw["match_score"]

    # Metric tiles
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.markdown(f'<div class="metric-tile"><div class="metric-num">{score}%</div><div class="metric-label">ATS match</div></div>', unsafe_allow_html=True)
    with m2:
        st.markdown(f'<div class="metric-tile"><div class="metric-num">{len(kw["hard_skills"])}</div><div class="metric-label">Hard skills</div></div>', unsafe_allow_html=True)
    with m3:
        st.markdown(f'<div class="metric-tile"><div class="metric-num">{len(kw["ats_phrases"])}</div><div class="metric-label">ATS phrases</div></div>', unsafe_allow_html=True)
    with m4:
        st.markdown(f'<div class="metric-tile"><div class="metric-num" style="color:#ff6b6b">{len(kw["missing"])}</div><div class="metric-label">Missing keywords</div></div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Score bar
    bar_color = "#3dba6f" if score >= 70 else "#f0a930" if score >= 40 else "#ff6b6b"
    st.markdown(
        f'<div class="score-wrap">'
        f'<div class="score-bar-bg"><div class="score-bar-fill" style="width:{score}%; background:{bar_color}"></div></div>'
        f'<div class="score-label">Your resume currently matches <strong style="color:#c8cfe8">{score}%</strong> of keywords. '
        f'Tailoring typically brings this to <strong style="color:#3dba6f">85–95%</strong>.</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    st.markdown("<br>", unsafe_allow_html=True)

    # Keyword breakdown
    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="card-title">✓ Hard skills found</div>', unsafe_allow_html=True)
        pills = " ".join(f'<span class="kw kw-hard">{k}</span>' for k in kw["hard_skills"])
        st.markdown(f'<div class="kw-grid">{pills}</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="card-title">✓ Soft skills found</div>', unsafe_allow_html=True)
        pills = " ".join(f'<span class="kw kw-soft">{k}</span>' for k in kw["soft_skills"])
        st.markdown(f'<div class="kw-grid">{pills}</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with col_b:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="card-title">⚡ ATS phrases to include</div>', unsafe_allow_html=True)
        pills = " ".join(f'<span class="kw kw-ats">{k}</span>' for k in kw["ats_phrases"])
        st.markdown(f'<div class="kw-grid">{pills}</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="card-title">✗ Missing keywords</div>', unsafe_allow_html=True)
        pills = " ".join(f'<span class="kw kw-miss">{k}</span>' for k in kw["missing"])
        st.markdown(f'<div class="kw-grid">{pills}</div>', unsafe_allow_html=True)
        st.markdown(
            '<p style="font-size:0.78rem;color:#6272a4;margin-top:10px">'
            'These will be woven in naturally during tailoring.</p>',
            unsafe_allow_html=True,
        )
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    col_back, col_fwd, _ = st.columns([1, 2, 3])
    with col_back:
        if st.button("← Back", use_container_width=True):
            st.session_state.step = 2
            st.rerun()
    with col_fwd:
        label = "Tailor resume + cover letter →" if st.session_state.include_cover else "Tailor resume →"
        if st.button(label, type="primary", use_container_width=True):
            kw = st.session_state.keywords
            all_keywords = kw["hard_skills"] + kw["soft_skills"] + kw["ats_phrases"] + kw["missing"]

            prompt_intro = f"Rewrite the resume below to naturally incorporate these keywords: {', '.join(all_keywords)}."
            prompt_base = f"""{prompt_intro}

Tone: {st.session_state.tone}. Length: {st.session_state.length}.

RESUME RULES

TASK:
Rewrite the resume to improve clarity, professionalism, and alignment with the job description.

========================
INPUT VALIDATION (ABSOLUTE PRIORITY — FINAL GATE)
=================================================

Evaluate inputs BEFORE generating any content.

INVALID INPUT CONDITIONS:

* Resume contains no real personal data (work experience, education, or skills)
* Job posting is nonsensical, unrelated text, or not a real role description
* Inputs appear to be random phrases, questions, or test data

IF INPUT IS INVALID:
Output EXACTLY:
Insufficient or invalid input to generate a resume and cover letter.

Then STOP. Do not generate anything else. Do not explain.

========================
STRICT RULES
============

* Preserve all original facts exactly as stated
* Do not add any new skills, tools, technologies, or responsibilities
* Do not increase seniority, impact, or expertise
* Do not imply knowledge of concepts not explicitly present in the resume
* Maintain original level of certainty (e.g., basic, tried, some experience)
* Only include keywords if they are explicitly supported by the resume

========================
ANTI-HALLUCINATION (CRITICAL)
=============================

* NO CONCEPT ESCALATION: Do not convert simple tasks into advanced concepts (e.g., “created a website” must not become “digital transformation”)
* Do not introduce tools, frameworks, or methodologies not explicitly present
* Do not mirror job posting requirements unless explicitly supported by resume content

========================
TRANSFORMATIONS ALLOWED
=======================

* Rewording for clarity
* Improving grammar and tone
* Grouping related ideas
* Using professional but accurate language

========================
TRANSFORMATIONS NOT ALLOWED
===========================

* Adding strategic, leadership, or technical experience
* Inferring tools, frameworks, or methodologies
* Generalizing tasks into business impact

========================
FACTUAL ACCURACY
================

* No fabricated achievements, metrics, or outcomes
* No exaggeration of responsibilities or impact
* Every bullet must be directly supported by the resume

========================
OUTPUT FORMAT
=============

Plain text only
Use: SUMMARY, EXPERIENCE, SKILLS, EDUCATION

========================
CONSISTENCY RULE
================

Do not introduce new concepts or terminology during regeneration.




Original resume:
{st.session_state.resume_text}

Job posting context:
{st.session_state.job_text}
"""

            if st.session_state.include_cover:
                combined_prompt = f"""{prompt_base}

Additionally, write a concise 3-paragraph cover letter for this job application.

Tone: {st.session_state.tone}. Keep it under 500 words.

COVER LETTER RULES

TASK:
Generate a concise, professional 3-paragraph cover letter based strictly on the resume and job posting.

========================
INPUT VALIDATION (ABSOLUTE PRIORITY — FINAL GATE)
=================================================

Evaluate inputs BEFORE generating any content.

INVALID INPUT CONDITIONS:

* Resume contains no real personal data (work experience, education, or skills)
* Job posting is nonsensical, unrelated text, or not a real role description
* Inputs appear to be random phrases, questions, or test data

IF INPUT IS INVALID:
Output EXACTLY:
Insufficient or invalid input to generate a resume and cover letter.

Then STOP. Do not generate anything else. Do not explain.

========================
STRUCTURE (MANDATORY)
=====================

* Paragraph 1: Role and company introduction with professional tone
* Paragraph 2: 2–3 concrete experiences directly from the resume
* Paragraph 3: Brief closing with call to action
* No repetition across paragraphs

========================
FACTUAL ACCURACY (CRITICAL)
===========================

* Do not invent achievements, metrics, tools, or outcomes
* Do not exaggerate responsibilities or impact
* Every claim must be directly supported by the resume
* Do not imply leadership, strategy, or technical expertise unless explicitly stated
* Do not mirror job posting requirements unless supported by the resume

========================
ANTI-HALLUCINATION
==================

* Do not introduce advanced concepts (e.g., data analytics, agile, digital transformation, strategy) unless explicitly present in the resume
* Do not upgrade basic experience into advanced domains

========================
TONE & STYLE
============

* Maintain a positive, professional, and grounded tone
* Do not include self-criticism or limitations
* Do not explicitly state lack of experience
* Use confident, neutral language for past experience
* Use reserved language only for future growth (e.g., “interested in developing…”)

========================
LANGUAGE QUALITY
================

* Avoid generic filler (e.g., “highly motivated,” “passion for innovation”)
* Avoid repetition of ideas or phrases
* Each sentence must serve a clear purpose
* Prefer specific actions over vague statements
* Paragraph 2 must include at least two concrete actions from the resume

========================
SIGN-OFF RULE (STRICT)
======================

End with a professional closing (Sincerely, or Best regards,).

Include name and phone number only if BOTH are explicitly present in the resume.
Otherwise output ONLY the closing line.

Do not add explanations or extra text.

========================
CONSISTENCY RULE
================

Do not introduce new concepts, terminology, or structure on regeneration.


Separate the output with these exact markers:
===TAILORED RESUME===
<your resume text here>
===COVER LETTER===
<your cover letter here>
"""
                with st.spinner("Tailoring your resume and cover letter..."):
                    try:
                        combined = call_groq(combined_prompt)
                        if "===TAILORED RESUME===" in combined and "===COVER LETTER===" in combined:
                            resume_part = combined.split("===TAILORED RESUME===", 1)[1].split("===COVER LETTER===", 1)[0].strip()
                            cover_part = combined.split("===COVER LETTER===", 1)[1].strip()
                            st.session_state.tailored_resume = resume_part
                            st.session_state.cover_letter = cover_part
                        else:
                            st.session_state.tailored_resume = combined
                            st.session_state.cover_letter = ""
                    except ValueError:
                        st.error("Please enter your Groq API key in the sidebar first.")
                        st.stop()
                    except Exception as e:
                        st.error(f"Resume tailoring error: {e}")
                        st.stop()
            else:
                with st.spinner("Tailoring your resume..."):
                    try:
                        st.session_state.tailored_resume = call_groq(prompt_base)
                    except ValueError:
                        st.error("Please enter your Groq API key in the sidebar first.")
                        st.stop()
                    except Exception as e:
                        st.error(f"Resume tailoring error: {e}")
                        st.stop()

            st.session_state.step = 4
            st.rerun()


# ═══════════════════════════════════════════════════════════════
# STEP 4 — Results
# ═══════════════════════════════════════════════════════════════
elif st.session_state.step == 4:
    st.markdown('<div class="section-heading">Your tailored documents</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-sub">Optimized for ATS and the specific job posting</div>', unsafe_allow_html=True)

    st.markdown(
        f'<div class="callout callout-success">✓ &nbsp;Resume tailored — estimated ATS score improved from '
        f'<strong>{st.session_state.keywords.get("match_score", "—")}%</strong> to '
        f'<strong style="color:#3dba6f">~90%+</strong></div>',
        unsafe_allow_html=True,
    )

    tabs = ["📄 Tailored resume", "✉️ Cover letter"] if st.session_state.include_cover else ["📄 Tailored resume"]
    tab_objects = st.tabs(tabs)

    with tab_objects[0]:
        st.markdown("<br>", unsafe_allow_html=True)
        c_score, c_copy, c_regen, _ = st.columns([1.2, 0.8, 0.8, 3])
        with c_score:
            st.markdown(
                '<div style="background:#0d2218;border:1px solid #1a5236;border-radius:8px;padding:8px 14px;'
                'text-align:center"><div style="font-size:1.3rem;font-weight:700;color:#3dba6f">91%</div>'
                '<div style="font-size:0.7rem;color:#4dcc85">ATS match</div></div>',
                unsafe_allow_html=True,
            )
        with c_copy:
            st.download_button("Copy text", data=st.session_state.tailored_resume, file_name="resume.txt", mime="text/plain", key="copy_resume")
        with c_regen:
            if st.button("Regenerate", key="regen_resume"):
                with st.spinner("Regenerating..."):
                    kw = st.session_state.keywords
                    all_keywords = kw["hard_skills"] + kw["soft_skills"] + kw["ats_phrases"] + kw["missing"]
                    prompt = f"""Rewrite this resume with a slightly different structure, incorporating these keywords: {", ".join(all_keywords)}.
Tone: {st.session_state.tone}. Length: {st.session_state.length}. Plain text only, ATS-friendly sections.
Resume: {st.session_state.resume_text}
Job posting: {st.session_state.job_text}"""
                    try:
                            st.session_state.tailored_resume = call_groq(prompt)
                    except ValueError:
                        st.error("Please enter your Groq API key in the sidebar first.")
                    except Exception as e:
                        st.error(f"Error: {e}")

        st.markdown("<br>", unsafe_allow_html=True)
        edited = st.text_area(
            "Tailored resume",
            value=st.session_state.tailored_resume,
            height=400,
            label_visibility="collapsed",
        )
        st.session_state.tailored_resume = edited

        st.markdown("<br>", unsafe_allow_html=True)
        try:
            resume_pdf, resume_filename = create_pdf(
                st.session_state.tailored_resume,
                st.session_state.company_name,
                st.session_state.first_name,
                st.session_state.last_name,
                "Resume",
            )
        except RuntimeError as e:
            st.error(str(e))
            resume_pdf = None
            resume_filename = None

        dl1, dl2 = st.columns([1.2, 1.2])
        with dl1:
            st.download_button(
                "⬇ Download .txt",
                data=st.session_state.tailored_resume,
                file_name="tailored_resume.txt",
                mime="text/plain",
                use_container_width=True,
            )
        with dl2:
            if resume_pdf is not None:
                st.download_button(
                    label="⬇️ Download .pdf",
                    data=io.BytesIO(resume_pdf),
                    file_name=resume_filename,
                    mime="application/pdf",
                    use_container_width=True,
                )

    if st.session_state.include_cover and len(tab_objects) > 1:
        with tab_objects[1]:
            st.markdown("<br>", unsafe_allow_html=True)
            c_tone, c_copy2, c_regen2, _ = st.columns([1.8, 0.8, 0.8, 2.5])
            with c_tone:
                st.selectbox(
                    "Tone",
                    ["Professional", "Enthusiastic", "Concise", "Executive"],
                    label_visibility="collapsed",
                    key="cover_tone",
                )
            with c_copy2:
                st.download_button("Copy text", data=st.session_state.cover_letter, file_name="cover_letter.txt", mime="text/plain", key="copy_cover")
            with c_regen2:
                if st.button("Regenerate", key="regen_cover"):
                    with st.spinner("Regenerating..."):
                        tone = st.session_state.get("cover_tone", st.session_state.tone)
                        prompt = f"""Write a fresh 3-paragraph cover letter. Tone: {tone}. Under 220 words.
Paragraph 1: strong opening referencing the role. Paragraph 2: 2-3 concrete achievements matching the job. Paragraph 3: brief closing.
Use keywords from the posting naturally. Extract name from resume. Plain text only.
Resume: {st.session_state.tailored_resume}
Job posting: {st.session_state.job_text}"""
                        try:
                            st.session_state.cover_letter = call_groq(prompt)
                            st.rerun()
                        except ValueError:
                            st.error("Please enter your Groq API key in the sidebar first.")
                        except Exception as e:
                            st.error(f"Error: {e}")

            st.markdown("<br>", unsafe_allow_html=True)
            edited_cover = st.text_area(
                "Cover letter",
                value=st.session_state.cover_letter,
                height=340,
                label_visibility="collapsed",
            )
            st.session_state.cover_letter = edited_cover

            try:
                cover_pdf, cover_filename = create_pdf(
                    st.session_state.cover_letter,
                    st.session_state.company_name,
                    st.session_state.first_name,
                    st.session_state.last_name,
                    "Coverletter",
                )
            except RuntimeError as e:
                st.error(str(e))
                cover_pdf = None
                cover_filename = None

            dl4, dl5 = st.columns([1.2, 1.2])
            with dl4:
                st.download_button(
                    "⬇ Download .txt",
                    data=st.session_state.cover_letter,
                    file_name="cover_letter.txt",
                    mime="text/plain",
                    key="dl_cover_txt",
                    use_container_width=True,
                )
            with dl5:
                if cover_pdf is not None:
                    st.download_button(
                        label="⬇️ Download .pdf",
                        data=io.BytesIO(cover_pdf),
                        file_name=cover_filename,
                        mime="application/pdf",
                        use_container_width=True,
                    )

    st.markdown("<br>", unsafe_allow_html=True)

    col_back, col_new, _ = st.columns([1, 1.5, 4])
    with col_back:
        if st.button("← Back", use_container_width=True):
            st.session_state.step = 3
            st.rerun()
    with col_new:
        if st.button("Start new application", use_container_width=True):
            for k, v in defaults.items():
                st.session_state[k] = v
            st.rerun()

