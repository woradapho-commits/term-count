"""
=============================================================
  Word Frequency Analyzer สำหรับนักแปล
  ─────────────────────────────────────
  วิเคราะห์คำที่ใช้บ่อยในเอกสาร .txt / .docx
  รองรับ stopwords ภาษาอังกฤษ | แสดง bar chart | export CSV
  v2.0 – เพิ่ม Part-of-Speech (POS) tagging
=============================================================
"""

import re
import io
import collections

import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from docx import Document
import nltk
from nltk import pos_tag

import urllib.request
import matplotlib.font_manager as fm
import os

# ─── โหลด Font ภาษาไทย (Sarabun) สำหรับ matplotlib ────────────────────────
@st.cache_resource
def setup_thai_font():
    font_path = "/tmp/Sarabun-Regular.ttf"
    if not os.path.exists(font_path):
        url = "https://github.com/google/fonts/raw/main/ofl/sarabun/Sarabun-Regular.ttf"
        try:
            urllib.request.urlretrieve(url, font_path)
        except Exception:
            return None
    try:
        fm.fontManager.addfont(font_path)
        prop = fm.FontProperties(fname=font_path)
        plt.rcParams["font.family"] = prop.get_name()
        return prop.get_name()
    except Exception:
        return None

THAI_FONT_NAME = setup_thai_font()

def apply_thai_font(ax, title_size=14, label_size=11, tick_size=11):
    """ตั้ง font ภาษาไทยให้ทุก text element ใน Axes"""
    if THAI_FONT_NAME is None:
        return
    fp = fm.FontProperties(family=THAI_FONT_NAME)
    for item in ([ax.title, ax.xaxis.label, ax.yaxis.label]
                 + ax.get_xticklabels() + ax.get_yticklabels()):
        item.set_fontproperties(fp)


# ─── ดาวน์โหลด NLTK data ที่จำเป็น ─────────────────────────────────────────
@st.cache_resource
def download_nltk_data():
    for pkg in ["averaged_perceptron_tagger", "averaged_perceptron_tagger_eng", "punkt", "punkt_tab"]:
        try:
            nltk.download(pkg, quiet=True)
        except Exception:
            pass

download_nltk_data()

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

# ─── แมปรหัส Penn Treebank POS → ชื่อภาษาไทย + สีที่ใช้แสดง ───────────────
POS_MAP = {
    # Nouns
    "NN":  ("Noun (นาม)",        "#4e9af1"),
    "NNS": ("Noun (นาม)",        "#4e9af1"),
    "NNP": ("Proper Noun (ชื่อเฉพาะ)", "#74b9f5"),
    "NNPS":("Proper Noun (ชื่อเฉพาะ)", "#74b9f5"),
    # Verbs
    "VB":  ("Verb (กริยา)",      "#56c47a"),
    "VBD": ("Verb (กริยา)",      "#56c47a"),
    "VBG": ("Verb (กริยา)",      "#56c47a"),
    "VBN": ("Verb (กริยา)",      "#56c47a"),
    "VBP": ("Verb (กริยา)",      "#56c47a"),
    "VBZ": ("Verb (กริยา)",      "#56c47a"),
    # Adjectives
    "JJ":  ("Adjective (คุณศัพท์)", "#e8b84b"),
    "JJR": ("Adjective (คุณศัพท์)", "#e8b84b"),
    "JJS": ("Adjective (คุณศัพท์)", "#e8b84b"),
    # Adverbs
    "RB":  ("Adverb (กริยาวิเศษณ์)", "#e06c9f"),
    "RBR": ("Adverb (กริยาวิเศษณ์)", "#e06c9f"),
    "RBS": ("Adverb (กริยาวิเศษณ์)", "#e06c9f"),
    # Others
    "CD":  ("Numeral (ตัวเลข)",  "#a29bfe"),
    "FW":  ("Foreign Word",      "#fd7e52"),
}

def get_pos_label(tag: str) -> tuple[str, str]:
    """คืนค่า (ชื่อ POS ภาษาไทย, รหัสสี) — ถ้าไม่รู้จักใช้ 'Other'"""
    return POS_MAP.get(tag, ("Other", "#636e72"))


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
html, body, [data-testid="stAppViewContainer"] {
    background: #0f1117;
    color: #e8e3d9;
}
[data-testid="stSidebar"] {
    background: #16191f;
    border-right: 1px solid #2a2d35;
}
h1 { font-family: 'Georgia', serif; letter-spacing: -1px; }
h2, h3 { font-family: 'Georgia', serif; }
[data-testid="metric-container"] {
    background: #1c1f29;
    border: 1px solid #2e3240;
    border-radius: 10px;
    padding: 16px 20px;
}
[data-testid="stFileUploader"] {
    border: 2px dashed #4a5568;
    border-radius: 12px;
    padding: 8px;
    background: #13151d;
    transition: border-color 0.2s;
}
[data-testid="stFileUploader"]:hover { border-color: #e8b84b; }
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
hr { border-color: #2a2d35 !important; }
[data-testid="stAlert"] { border-radius: 10px; }

/* POS badge chips */
.pos-badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 20px;
    font-size: 0.78rem;
    font-weight: 600;
    margin: 2px;
}
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
    - เก็บเฉพาะตัวอักษรภาษาอังกฤษ (a-z)
    """
    text = text.lower()
    tokens = re.findall(r"[a-z]+", text)
    return tokens


@st.cache_data(show_spinner=False)
def tag_pos_for_words(word_list: tuple[str]) -> dict[str, str]:
    """
    รับ tuple ของคำที่ไม่ซ้ำ → คืน dict {word: pos_label}
    ใช้ NLTK pos_tag บนประโยคตัวอย่าง เพื่อประสิทธิภาพที่ดีขึ้น
    Cache ผลลัพธ์ไว้เพื่อไม่ต้องประมวลซ้ำ
    """
    if not word_list:
        return {}
    # pos_tag ทำงานได้ดีกว่าเมื่อรับเป็น sequence ต่อเนื่อง
    tagged = pos_tag(list(word_list))
    return {word: tag for word, tag in tagged}


def count_words_with_pos(
    tokens: list[str],
    stopwords: set,
    min_len: int = 2,
) -> pd.DataFrame:
    """
    นับความถี่คำ + แท็ก POS แต่ละคำ
    คืนค่า DataFrame: คำ | จำนวนครั้ง | POS Tag | หมวดหมู่ | สี
    """
    filtered = [w for w in tokens if w not in stopwords and len(w) >= min_len]
    counter = collections.Counter(filtered)

    # POS tag เฉพาะคำที่ไม่ซ้ำ (เร็วกว่า tag ทุก token)
    unique_words = tuple(counter.keys())
    pos_dict = tag_pos_for_words(unique_words)

    rows = []
    for word, count in counter.most_common():
        raw_tag = pos_dict.get(word, "NN")
        label, color = get_pos_label(raw_tag)
        rows.append({
            "คำ": word,
            "จำนวนครั้ง": count,
            "POS Tag": raw_tag,
            "หมวดหมู่": label,
            "สี": color,
        })

    df = pd.DataFrame(rows)
    df.index = df.index + 1
    return df


def plot_bar_chart(df: pd.DataFrame, top_n: int, color_by_pos: bool, default_color: str) -> plt.Figure:
    """
    วาด horizontal bar chart สำหรับ top N คำ
    color_by_pos=True → ระบายสีตามหมวด POS | False → ใช้สีเดียว
    """
    data = df.head(top_n).iloc[::-1]

    fig, ax = plt.subplots(figsize=(10, max(5, top_n * 0.35)))
    fig.patch.set_facecolor("#1c1f29")
    ax.set_facecolor("#1c1f29")

    bar_colors = data["สี"].tolist() if color_by_pos else [default_color] * len(data)

    bars = ax.barh(
        data["คำ"],
        data["จำนวนครั้ง"],
        color=bar_colors,
        edgecolor="none",
        height=0.65,
    )

    for bar in bars:
        width = bar.get_width()
        ax.text(
            width + max(data["จำนวนครั้ง"]) * 0.01,
            bar.get_y() + bar.get_height() / 2,
            f"{int(width):,}",
            va="center", ha="left",
            fontsize=9, color="#c8c2b4",
        )

    ax.tick_params(colors="#c8c2b4", labelsize=11)
    ax.xaxis.label.set_color("#c8c2b4")
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.axvline(0, color="#3a3d4a", linewidth=1)
    ax.grid(axis="x", color="#2a2d35", linewidth=0.7, linestyle="--")

    # ─── ตั้งค่า font ภาษาไทย ───
    if THAI_FONT_NAME:
        fp = fm.FontProperties(family=THAI_FONT_NAME)
        fp_bold = fm.FontProperties(family=THAI_FONT_NAME, weight="bold")
        ax.set_xlabel("จำนวนครั้งที่ปรากฏ", color="#9a9488", fontsize=11, labelpad=10)
        ax.xaxis.label.set_fontproperties(fp)
        ax.xaxis.label.set_color("#9a9488")
        ax.set_title(f"Top {top_n} คำที่ใช้บ่อยที่สุด", color="#e8e3d9", fontsize=14, pad=16)
        ax.title.set_fontproperties(fp_bold)
        ax.title.set_color("#e8e3d9")
        for lbl in ax.get_yticklabels():
            lbl.set_fontproperties(fp)
            lbl.set_color("#c8c2b4")
    else:
        ax.set_xlabel("จำนวนครั้งที่ปรากฏ", color="#9a9488", fontsize=11, labelpad=10)
        ax.set_title(f"Top {top_n} คำที่ใช้บ่อยที่สุด", color="#e8e3d9", fontsize=14, fontweight="bold", pad=16)

    # ─── Legend สำหรับ POS ───
    if color_by_pos:
        seen = {}
        for _, row in data.iterrows():
            if row["หมวดหมู่"] not in seen:
                seen[row["หมวดหมู่"]] = row["สี"]
        patches = [mpatches.Patch(color=c, label=l) for l, c in seen.items()]
        legend = ax.legend(
            handles=patches,
            loc="lower right",
            framealpha=0.15,
            labelcolor="#c8c2b4",
            fontsize=9,
            facecolor="#1c1f29",
            edgecolor="#3a3d4a",
        )
        if THAI_FONT_NAME:
            fp_leg = fm.FontProperties(family=THAI_FONT_NAME, size=9)
            for text in legend.get_texts():
                text.set_fontproperties(fp_leg)
                text.set_color("#c8c2b4")

    plt.tight_layout()
    return fig


def plot_pos_pie(df: pd.DataFrame) -> plt.Figure:
    """วาด donut chart สัดส่วนแต่ละ POS หมวดหมู่"""
    pos_counts = (
        df.groupby(["หมวดหมู่", "สี"])["จำนวนครั้ง"]
        .sum()
        .reset_index()
        .sort_values("จำนวนครั้ง", ascending=False)
    )

    fig, ax = plt.subplots(figsize=(7, 5))
    fig.patch.set_facecolor("#1c1f29")
    ax.set_facecolor("#1c1f29")

    wedges, texts, autotexts = ax.pie(
        pos_counts["จำนวนครั้ง"],
        labels=pos_counts["หมวดหมู่"],
        colors=pos_counts["สี"],
        autopct="%1.1f%%",
        startangle=140,
        wedgeprops={"width": 0.55, "edgecolor": "#1c1f29", "linewidth": 2},
        pctdistance=0.75,
    )

    # ─── ตั้งค่า font ภาษาไทยสำหรับ label และ title ───
    if THAI_FONT_NAME:
        fp = fm.FontProperties(family=THAI_FONT_NAME, size=9)
        fp_bold = fm.FontProperties(family=THAI_FONT_NAME, weight="bold", size=13)
        for t in texts:
            t.set_fontproperties(fp)
            t.set_color("#c8c2b4")
        for at in autotexts:
            at.set_fontsize(8)
            at.set_color("#0f1117")
            at.set_fontweight("bold")
        ax.set_title(
            "สัดส่วน Part of Speech (ตามจำนวนครั้ง)",
            color="#e8e3d9", fontsize=13, pad=14,
        )
        ax.title.set_fontproperties(fp_bold)
        ax.title.set_color("#e8e3d9")
    else:
        for t in texts:
            t.set_color("#c8c2b4")
            t.set_fontsize(9)
        for at in autotexts:
            at.set_color("#0f1117")
            at.set_fontsize(8)
            at.set_fontweight("bold")
        ax.set_title(
            "สัดส่วน Part of Speech (ตามจำนวนครั้ง)",
            color="#e8e3d9", fontsize=13, fontweight="bold", pad=14,
        )

    plt.tight_layout()
    return fig


# ═══════════════════════════════════════════════════════════════════
#  SIDEBAR – การตั้งค่า
# ═══════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("## ⚙️ การตั้งค่า")
    st.divider()

    top_n = st.slider("จำนวนคำที่แสดง (Top N)", min_value=5, max_value=50, value=30, step=5)
    min_len = st.slider(
        "ความยาวคำขั้นต่ำ (ตัวอักษร)", min_value=1, max_value=6, value=2,
        help="กรองคำที่สั้นเกินไปออก",
    )

    st.markdown("**สีแผนภูมิ (เมื่อปิดโหมด POS)**")
    chart_color = st.color_picker("เลือกสี", value="#e8b84b")

    # ── ตัวเลือก POS ──
    st.divider()
    st.markdown("**🏷️ Part-of-Speech (POS)**")
    color_by_pos = st.toggle("ระบายสีแผนภูมิตาม POS", value=True)

    # ── กรอง POS ที่ต้องการแสดง ──
    all_pos_labels = sorted({v[0] for v in POS_MAP.values()} | {"Other"})
    selected_pos = st.multiselect(
        "แสดงเฉพาะหมวด POS",
        options=all_pos_labels,
        default=all_pos_labels,
        help="เลือกหมวดที่ต้องการดูในตารางและกราฟ",
    )

    st.divider()
    st.markdown("**เพิ่ม Stopwords เอง**")
    extra_sw_input = st.text_area(
        "คั่นด้วยช่องว่างหรือขึ้นบรรทัดใหม่",
        placeholder="e.g. said mr mrs also",
        height=100,
    )
    extra_stopwords = set(extra_sw_input.lower().split())
    all_stopwords = DEFAULT_STOPWORDS | extra_stopwords
    st.caption(f"Stopwords ที่ใช้งานอยู่: **{len(all_stopwords)}** คำ")

    st.divider()
    st.caption("📖 Word Frequency Analyzer v2.0\nสร้างเพื่อนักแปลโดยเฉพาะ")


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

    # ─── 1. อ่านไฟล์ ──────────────────────────────────────────────
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

    # ─── 2. Tokenize + นับคำ + POS tag ───────────────────────────
    with st.spinner("กำลังวิเคราะห์คำและจัดหมวดหมู่ POS..."):
        tokens = tokenize(raw_text)
        df_all = count_words_with_pos(tokens, all_stopwords, min_len)

    # ─── 3. กรองตาม POS ที่เลือกใน sidebar ──────────────────────
    df_filtered = df_all[df_all["หมวดหมู่"].isin(selected_pos)].copy()

    # ─── 4. Metrics ────────────────────────────────────────────────
    st.divider()
    st.markdown("### 📊 ภาพรวมเอกสาร")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("📄 ชื่อไฟล์", uploaded_file.name)
    col2.metric("🔤 คำทั้งหมด (raw)", f"{len(tokens):,}")
    col3.metric("✂️ หลังกรอง stopwords", f"{df_all['จำนวนครั้ง'].sum():,}")
    col4.metric("🗂️ คำไม่ซ้ำกัน", f"{len(df_all):,}")

    # ─── 5. POS Summary badges ─────────────────────────────────────
    st.divider()
    st.markdown("### 🏷️ สรุปหมวดหมู่ Part of Speech")

    pos_total = (
        df_all.groupby(["หมวดหมู่", "สี"])["จำนวนครั้ง"]
        .sum()
        .reset_index()
        .rename(columns={"จำนวนครั้ง": "total"})
    )
    pos_wcount = (
        df_all.groupby("หมวดหมู่")["คำ"]
        .count()
        .reset_index()
        .rename(columns={"คำ": "word_count"})
    )
    pos_summary = pos_total.merge(pos_wcount, on="หมวดหมู่").sort_values("total", ascending=False)

    # แสดง badge chips
    badge_html = ""
    for _, row in pos_summary.iterrows():
        color = row["สี"]
        label = row["หมวดหมู่"]
        total = int(row["total"])
        wcount = int(row["word_count"])
        badge_html += (
            f"<span class='pos-badge' style='background:{color}22; "
            f"color:{color}; border:1px solid {color}55;'>"
            f"{label} — {total:,} ครั้ง ({wcount} คำ)</span>"
        )
    st.markdown(badge_html, unsafe_allow_html=True)

    # Donut chart สัดส่วน POS
    fig_pie = plot_pos_pie(df_all)
    st.pyplot(fig_pie)
    plt.close(fig_pie)

    # ─── 6. Bar Chart ──────────────────────────────────────────────
    st.divider()
    st.markdown(f"### 📈 Top {top_n} คำที่ใช้บ่อยที่สุด")

    if df_filtered.empty:
        st.warning("ไม่พบคำในหมวด POS ที่เลือก หรือทุกคำถูกกรองออกโดย stopwords")
    else:
        fig = plot_bar_chart(df_filtered, top_n, color_by_pos, chart_color)
        st.pyplot(fig)
        plt.close(fig)

    # ─── 7. ตารางผลลัพธ์ พร้อม POS ────────────────────────────────
    st.divider()
    st.markdown("### 📋 ตารางผลลัพธ์")

    # tab แยกตาม POS / ภาพรวม
    tab_all, tab_noun, tab_verb, tab_adj, tab_adv = st.tabs([
        "ทั้งหมด", "🔵 Noun", "🟢 Verb", "🟡 Adjective", "🩷 Adverb"
    ])

    def render_table(data: pd.DataFrame):
        display = data.head(top_n).copy()
        display["สัดส่วน (%)"] = (
            display["จำนวนครั้ง"] / df_all["จำนวนครั้ง"].sum() * 100
        ).round(2)
        st.dataframe(
            display[["คำ", "จำนวนครั้ง", "หมวดหมู่", "POS Tag", "สัดส่วน (%)"]],
            use_container_width=True,
            column_config={
                "จำนวนครั้ง": st.column_config.ProgressColumn(
                    "จำนวนครั้ง",
                    min_value=0,
                    max_value=int(df_all["จำนวนครั้ง"].max()),
                    format="%d",
                ),
                "สัดส่วน (%)": st.column_config.NumberColumn(format="%.2f%%"),
            },
            height=420,
        )

    with tab_all:
        render_table(df_filtered)

    for tab, keyword in [
        (tab_noun, "Noun"),
        (tab_verb, "Verb"),
        (tab_adj, "Adjective"),
        (tab_adv, "Adverb"),
    ]:
        with tab:
            sub = df_all[df_all["หมวดหมู่"].str.contains(keyword)]
            if sub.empty:
                st.info(f"ไม่พบคำในหมวด {keyword}")
            else:
                render_table(sub)

    # ─── 8. ปุ่ม Download CSV ─────────────────────────────────────
    st.divider()
    st.markdown("### 💾 ดาวน์โหลดผลลัพธ์")

    # CSV รวม POS column ด้วย
    export_df = df_all[["คำ", "จำนวนครั้ง", "หมวดหมู่", "POS Tag"]].copy()
    export_df["สัดส่วน (%)"] = (
        export_df["จำนวนครั้ง"] / export_df["จำนวนครั้ง"].sum() * 100
    ).round(2)
    csv_bytes = export_df.to_csv(index=True, encoding="utf-8-sig").encode("utf-8-sig")
    base_name = uploaded_file.name.rsplit(".", 1)[0]

    col_dl1, col_dl2 = st.columns([1, 3])
    with col_dl1:
        st.download_button(
            label="⬇️ ดาวน์โหลด CSV (คำทั้งหมด + POS)",
            data=csv_bytes,
            file_name=f"{base_name}_word_freq_pos.csv",
            mime="text/csv",
        )
    with col_dl2:
        st.caption(
            f"ไฟล์ CSV จะมี **{len(export_df):,}** แถว "
            f"พร้อมคอลัมน์: ลำดับ, คำ, จำนวนครั้ง, หมวดหมู่, POS Tag, สัดส่วน (%)"
        )

    # ─── 9. Preview ข้อความต้นฉบับ ───────────────────────────────
    with st.expander("🔍 ดูข้อความต้นฉบับ (Preview)"):
        preview = raw_text[:3000] + ("..." if len(raw_text) > 3000 else "")
        st.text_area("ข้อความ", preview, height=250, disabled=True)

else:
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
