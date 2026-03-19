"""
=============================================================
  Word Frequency Analyzer สำหรับนักแปล
  ─────────────────────────────────────
  วิเคราะห์คำที่ใช้บ่อยในเอกสาร .txt / .docx
  รองรับ stopwords ภาษาอังกฤษ | แสดง bar chart | export CSV
=============================================================
"""

import re
import io
import collections

import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

# ─── ติดตั้ง dependency เพิ่มเติมหากยังไม่มี ───────────────────────────────
try:
    from docx import Document
except ImportError:
    import subprocess, sys
    subprocess.check_call([sys.executable, "-m", "pip", "install", "python-docx"])
    from docx import Document

# ─── Stopwords ภาษาอังกฤษ (เพิ่มเติมได้ใน sidebar) ──────────────────────────
DEFAULT_STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "if", "in", "on", "at", "to",
    "for", "of", "with", "by", "from", "up", "about", "into", "through",
    "is", "are", "was", "were", "be", "been", "being", "have", "has",
    "had", "do", "does", "did", "will", "would", "could", "should",
    "may", "might", "shall", "can", "need", "dare", "ought",
    "i", "me", "my", "we", "our", "you", "your", "he", "she", "it",
    "his", "her", "its", "they", "them", "their", "this", "that",
    "these", "those", "who", "which", "what", "how", "when", "where",
    "not", "no", "nor", "so", "yet", "both", "either", "neither",
    "as", "such", "while", "than", "then", "also", "just", "more",
    "s", "t", "re", "ve", "ll", "d", "m",   # contractions ที่ถูกตัด apostrophe
}

# ═══════════════════════════════════════════════════════════════════
#  PAGE CONFIG
# ═══════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="Word Frequency Analyzer",
    page_icon="📖",
    layout="wide",
)

# ─── Custom CSS ──────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* ── หน้าหลัก ── */
html, body, [data-testid="stAppViewContainer"] {
    background: #0f1117;
    color: #e8e3d9;
}
[data-testid="stSidebar"] {
    background: #16191f;
    border-right: 1px solid #2a2d35;
}

/* ── Typography ── */
h1 { font-family: 'Georgia', serif; letter-spacing: -1px; }
h2, h3 { font-family: 'Georgia', serif; }

/* ── Metric cards ── */
[data-testid="metric-container"] {
    background: #1c1f29;
    border: 1px solid #2e3240;
    border-radius: 10px;
    padding: 16px 20px;
}

/* ── Upload zone ── */
[data-testid="stFileUploader"] {
    border: 2px dashed #4a5568;
    border-radius: 12px;
    padding: 8px;
    background: #13151d;
    transition: border-color 0.2s;
}
[data-testid="stFileUploader"]:hover { border-color: #e8b84b; }

/* ── Download button ── */
.stDownloadButton > button {
    background: linear-gradient(135deg, #e8b84b, #c9922a) !important;
    color: #0f1117 !important;
    font-weight: 700 !important;
    border: none !important;
    border-radius: 8px !important;
    padding: 0.5rem 1.4rem !important;
    font-size: 0.95rem !important;
    transition: opacity 0.2s !important;
}
.stDownloadButton > button:hover { opacity: 0.85 !important; }

/* ── Divider ── */
hr { border-color: #2a2d35 !important; }

/* ── Info / success boxes ── */
[data-testid="stAlert"] { border-radius: 10px; }
</style>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════
#  HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════

def extract_text_from_txt(file_bytes: bytes) -> str:
    """อ่าน plain-text จาก .txt (ลอง utf-8 → latin-1 fallback)"""
    try:
        return file_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return file_bytes.decode("latin-1")


def extract_text_from_docx(file_bytes: bytes) -> str:
    """อ่านข้อความทุก paragraph จาก .docx"""
    doc = Document(io.BytesIO(file_bytes))
    return "\n".join(para.text for para in doc.paragraphs)


def tokenize(text: str) -> list[str]:
    """
    แปลงข้อความเป็น token:
    - lowercase ทั้งหมด
    - เก็บเฉพาะตัวอักษรภาษาอังกฤษ (a-z) → ตัดตัวเลข / สัญลักษณ์ออก
    """
    text = text.lower()
    tokens = re.findall(r"[a-z]+", text)
    return tokens


def count_words(tokens: list[str], stopwords: set, min_len: int = 2) -> pd.DataFrame:
    """
    นับความถี่คำ หลังจากกรอง stopwords และคำที่สั้นเกินไป
    คืนค่า DataFrame ที่เรียงจากมากไปน้อย
    """
    filtered = [
        w for w in tokens
        if w not in stopwords and len(w) >= min_len
    ]
    counter = collections.Counter(filtered)
    df = pd.DataFrame(counter.most_common(), columns=["คำ", "จำนวนครั้ง"])
    df.index = df.index + 1          # เริ่ม index ที่ 1
    return df


def plot_bar_chart(df: pd.DataFrame, top_n: int, color_accent: str) -> plt.Figure:
    """
    วาด horizontal bar chart สำหรับ top N คำ
    ใช้โทนสีมืด เข้ากับ dark theme ของ app
    """
    data = df.head(top_n).iloc[::-1]   # กลับด้านให้บาร์ที่สูงสุดอยู่บนสุด

    fig, ax = plt.subplots(figsize=(10, max(5, top_n * 0.35)))
    fig.patch.set_facecolor("#1c1f29")
    ax.set_facecolor("#1c1f29")

    # ─── วาด gradient bars โดยใช้สีหลักเป็น gradient อ่อน → เข้ม ───
    bars = ax.barh(
        data["คำ"],
        data["จำนวนครั้ง"],
        color=color_accent,
        edgecolor="none",
        height=0.65,
    )

    # ─── แสดงตัวเลขที่ปลายแต่ละบาร์ ───
    for bar in bars:
        width = bar.get_width()
        ax.text(
            width + max(data["จำนวนครั้ง"]) * 0.01,
            bar.get_y() + bar.get_height() / 2,
            f"{int(width):,}",
            va="center", ha="left",
            fontsize=9, color="#c8c2b4",
        )

    # ─── Styling แกนและกริด ───
    ax.tick_params(colors="#c8c2b4", labelsize=11)
    ax.xaxis.label.set_color("#c8c2b4")
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.axvline(0, color="#3a3d4a", linewidth=1)
    ax.grid(axis="x", color="#2a2d35", linewidth=0.7, linestyle="--")
    ax.set_xlabel("จำนวนครั้งที่ปรากฏ", color="#9a9488", fontsize=11, labelpad=10)
    ax.set_title(
        f"Top {top_n} คำที่ใช้บ่อยที่สุด",
        color="#e8e3d9", fontsize=14, fontweight="bold", pad=16,
    )

    plt.tight_layout()
    return fig


# ═══════════════════════════════════════════════════════════════════
#  SIDEBAR – การตั้งค่า
# ═══════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("## ⚙️ การตั้งค่า")
    st.divider()

    # ── จำนวน top N คำ ──
    top_n = st.slider(
        "จำนวนคำที่แสดง (Top N)",
        min_value=5, max_value=50, value=30, step=5,
    )

    # ── ความยาวคำขั้นต่ำ ──
    min_len = st.slider(
        "ความยาวคำขั้นต่ำ (ตัวอักษร)",
        min_value=1, max_value=6, value=2,
        help="กรองคำที่สั้นเกินไปออก เช่น ตั้งค่า 3 จะตัดคำ 2 ตัวอักษรออก",
    )

    # ── สีแผนภูมิ ──
    st.markdown("**สีแผนภูมิ**")
    chart_color = st.color_picker("เลือกสี", value="#e8b84b")

    st.divider()

    # ── Stopwords เพิ่มเติม ──
    st.markdown("**เพิ่ม Stopwords เอง**")
    extra_sw_input = st.text_area(
        "คั่นด้วยช่องว่างหรือขึ้นบรรทัดใหม่",
        placeholder="e.g. said mr mrs also",
        height=100,
    )
    extra_stopwords = set(extra_sw_input.lower().split())

    # ── สรุป stopwords ทั้งหมด ──
    all_stopwords = DEFAULT_STOPWORDS | extra_stopwords
    st.caption(f"Stopwords ที่ใช้งานอยู่: **{len(all_stopwords)}** คำ")

    st.divider()
    st.caption("📖 Word Frequency Analyzer v1.0\nสร้างเพื่อนักแปลโดยเฉพาะ")


# ═══════════════════════════════════════════════════════════════════
#  HEADER
# ═══════════════════════════════════════════════════════════════════
st.markdown("""
<div style='padding: 1.5rem 0 0.5rem 0;'>
  <h1 style='margin:0; font-size:2.2rem; color:#e8e3d9;'>
    📖 Word Frequency Analyzer
  </h1>
  <p style='color:#9a9488; margin:0.4rem 0 0 0; font-size:1.05rem;'>
    วิเคราะห์คำที่ใช้บ่อยในเอกสาร — สำหรับนักแปลและนักภาษาศาสตร์
  </p>
</div>
""", unsafe_allow_html=True)

st.divider()

# ═══════════════════════════════════════════════════════════════════
#  FILE UPLOAD SECTION
# ═══════════════════════════════════════════════════════════════════
st.markdown("### 📂 อัปโหลดเอกสาร")
st.caption("รองรับไฟล์ .txt และ .docx (Word Document)")

uploaded_file = st.file_uploader(
    label="วางไฟล์ที่นี่หรือคลิกเพื่อเลือก",
    type=["txt", "docx"],
    label_visibility="collapsed",
)

# ═══════════════════════════════════════════════════════════════════
#  MAIN PROCESSING
# ═══════════════════════════════════════════════════════════════════
if uploaded_file is not None:

    # ─── 1. อ่านไฟล์และดึงข้อความ ───────────────────────────────────
    file_bytes = uploaded_file.read()
    ext = uploaded_file.name.rsplit(".", 1)[-1].lower()

    with st.spinner("กำลังอ่านเอกสาร..."):
        if ext == "txt":
            raw_text = extract_text_from_txt(file_bytes)
        elif ext == "docx":
            raw_text = extract_text_from_docx(file_bytes)
        else:
            st.error("รองรับเฉพาะไฟล์ .txt และ .docx เท่านั้น")
            st.stop()

    # ─── 2. Tokenize และนับคำ ─────────────────────────────────────────
    with st.spinner("กำลังวิเคราะห์คำ..."):
        tokens = tokenize(raw_text)
        df_all = count_words(tokens, all_stopwords, min_len)

    # ─── 3. แสดง Metric summary ───────────────────────────────────────
    st.divider()
    st.markdown("### 📊 ภาพรวมเอกสาร")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("📄 ชื่อไฟล์", uploaded_file.name)
    col2.metric("🔤 คำทั้งหมด (raw)", f"{len(tokens):,}")
    col3.metric("✂️ หลังกรอง stopwords", f"{df_all['จำนวนครั้ง'].sum():,}")
    col4.metric("🗂️ คำไม่ซ้ำกัน", f"{len(df_all):,}")

    # ─── 4. แสดง Bar Chart ────────────────────────────────────────────
    st.divider()
    st.markdown(f"### 📈 Top {top_n} คำที่ใช้บ่อยที่สุด")

    if df_all.empty:
        st.warning("ไม่พบคำในเอกสาร หรือทุกคำถูกกรองออกโดย stopwords")
    else:
        fig = plot_bar_chart(df_all, top_n, chart_color)
        st.pyplot(fig)
        plt.close(fig)

    # ─── 5. แสดงตาราง Top N ──────────────────────────────────────────
    st.divider()
    st.markdown("### 📋 ตารางผลลัพธ์")

    df_display = df_all.head(top_n).copy()
    df_display["สัดส่วน (%)"] = (
        df_display["จำนวนครั้ง"] / df_display["จำนวนครั้ง"].sum() * 100
    ).round(2)

    # แสดง progress bar เพื่อให้อ่านง่ายขึ้น (Streamlit built-in)
    st.dataframe(
        df_display,
        use_container_width=True,
        column_config={
            "จำนวนครั้ง": st.column_config.ProgressColumn(
                "จำนวนครั้ง",
                min_value=0,
                max_value=int(df_display["จำนวนครั้ง"].max()),
                format="%d",
            ),
            "สัดส่วน (%)": st.column_config.NumberColumn(format="%.2f%%"),
        },
        height=420,
    )

    # ─── 6. ปุ่ม Download CSV ─────────────────────────────────────────
    st.divider()
    st.markdown("### 💾 ดาวน์โหลดผลลัพธ์")

    # เตรียม CSV ทั้งหมด (ไม่ใช่แค่ top_n)
    csv_bytes = df_all.to_csv(index=True, encoding="utf-8-sig").encode("utf-8-sig")
    base_name = uploaded_file.name.rsplit(".", 1)[0]

    col_dl1, col_dl2 = st.columns([1, 3])
    with col_dl1:
        st.download_button(
            label="⬇️ ดาวน์โหลด CSV (คำทั้งหมด)",
            data=csv_bytes,
            file_name=f"{base_name}_word_freq.csv",
            mime="text/csv",
        )
    with col_dl2:
        st.caption(
            f"ไฟล์ CSV จะมี **{len(df_all):,}** แถว (คำที่ไม่ซ้ำทั้งหมด)"
            f" พร้อมคอลัมน์: ลำดับ, คำ, จำนวนครั้ง, สัดส่วน (%)"
        )

    # ─── 7. แสดง preview ข้อความต้นฉบับ (ยุบได้) ────────────────────
    with st.expander("🔍 ดูข้อความต้นฉบับ (Preview)"):
        preview = raw_text[:3000] + ("..." if len(raw_text) > 3000 else "")
        st.text_area("ข้อความ", preview, height=250, disabled=True)

else:
    # ─── ยังไม่มีไฟล์ → แสดง placeholder ──────────────────────────
    st.markdown("""
    <div style='
        text-align:center;
        padding: 3rem 2rem;
        background: #13151d;
        border: 1px dashed #2e3240;
        border-radius: 16px;
        margin-top: 1.5rem;
    '>
        <div style='font-size:3rem; margin-bottom:1rem;'>📄</div>
        <h3 style='color:#c8c2b4; margin:0 0 0.5rem 0;'>ยังไม่มีเอกสาร</h3>
        <p style='color:#6b6860; margin:0;'>
            อัปโหลดไฟล์ .txt หรือ .docx เพื่อเริ่มวิเคราะห์<br>
            ปรับแต่งการตั้งค่าได้ที่แถบด้านซ้าย
        </p>
    </div>
    """, unsafe_allow_html=True)
