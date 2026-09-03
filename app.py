import streamlit as st
import pandas as pd
from PIL import Image, ImageDraw, ImageFont, ImageOps
from streamlit_image_coordinates import streamlit_image_coordinates
import sqlite3
import json
import uuid
import io
import os
import shutil
from datetime import datetime

# =========================================================
# 학교 시설물 현장조사 시스템 V4
# - 정기안전점검 우선
# - 기존학교 / 신규학교
# - 전회 손상 비교
# - 신규손상 / 양호 / 외부 / 부대시설
# - 도면 위치 수정
# - 손상 복사
# - 사진 자동 연결 및 6장 사진첩
# - 손상물량표 / 조사망도 / 사진첩 / 결과자료 Excel
# - SQLite + 파일 저장
# =========================================================

st.set_page_config(
    page_title="학교 시설물 현장조사 V4",
    page_icon="🏫",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# -------------------------
# CSS: 현장 스마트폰 최적화
# -------------------------
st.markdown("""
<style>
html, body, [class*="css"] { font-family: sans-serif; }
.block-container { padding-top: .7rem; padding-bottom: 4rem; max-width: 1100px; }
.stButton > button {
    min-height: 48px;
    border-radius: 10px;
    font-weight: 700;
    width: 100%;
}
div[data-testid="stHorizontalBlock"] { gap: .45rem; }
.small-note { color:#666; font-size:.86rem; }
.big-title { font-size:1.35rem; font-weight:800; margin-bottom:.2rem; }
.status-card {
    padding:12px 14px; border:1px solid #ddd; border-radius:12px;
    background:#fafafa; margin-bottom:8px;
}
.damage-card {
    padding:10px 12px; border:1px solid #ddd; border-radius:12px;
    margin:6px 0;
}
</style>
""", unsafe_allow_html=True)

BASE = Path("field_data")
PHOTO_DIR = BASE / "photos"
PLAN_DIR = BASE / "plans"
BASE.mkdir(exist_ok=True)
PHOTO_DIR.mkdir(exist_ok=True)
PLAN_DIR.mkdir(exist_ok=True)
DB_PATH = BASE / "inspection.db"

# =========================================================
# DB
# =========================================================
def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = db()
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS projects (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        inspection_year TEXT,
        inspection_type TEXT,
        mode TEXT,
        created_at TEXT
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS floors (
        id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL,
        floor_name TEXT NOT NULL,
        plan_path TEXT,
        sort_order INTEGER DEFAULT 0
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS defects (
        id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL,
        floor_id TEXT NOT NULL,
        display_no INTEGER,
        source TEXT,
        status TEXT,
        location TEXT,
        member TEXT,
        defect_type TEXT,
        crack_width REAL,
        crack_length REAL,
        damage_width REAL,
        damage_height REAL,
        count_ea INTEGER,
        cause TEXT,
        x REAL,
        y REAL,
        photo_no TEXT,
        note TEXT,
        created_at TEXT,
        updated_at TEXT
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS photos (
        id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL,
        floor_id TEXT,
        defect_id TEXT,
        photo_no INTEGER,
        category TEXT,
        path TEXT,
        caption TEXT,
        taken_at TEXT
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS check_items (
        id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL,
        category TEXT,
        item TEXT,
        result TEXT,
        opinion TEXT,
        photo_id TEXT,
        updated_at TEXT
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS facilities (
        id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL,
        category TEXT,
        item TEXT,
        result TEXT,
        location TEXT,
        opinion TEXT,
        photo_id TEXT,
        updated_at TEXT
    )
    """)
    conn.commit()
    conn.close()

init_db()

# =========================================================
# DB helpers
# =========================================================
def uid(prefix=""):
    return prefix + uuid.uuid4().hex[:10]

def now():
    return datetime.now().isoformat(timespec="seconds")

def q(sql, params=(), fetch=False):
    conn = db()
    cur = conn.cursor()
    cur.execute(sql, params)
    rows = cur.fetchall() if fetch else None
    conn.commit()
    conn.close()
    return rows

def project_rows():
    return q("SELECT * FROM projects ORDER BY created_at DESC", fetch=True)

def floor_rows(project_id):
    return q("SELECT * FROM floors WHERE project_id=? ORDER BY sort_order, floor_name", (project_id,), fetch=True)

def defect_rows(project_id, floor_id=None):
    if floor_id:
        return q("""
            SELECT * FROM defects
            WHERE project_id=? AND floor_id=?
            ORDER BY display_no, created_at
        """, (project_id, floor_id), fetch=True)
    return q("""
        SELECT * FROM defects WHERE project_id=?
        ORDER BY floor_id, display_no, created_at
    """, (project_id,), fetch=True)

def photo_rows(project_id, floor_id=None):
    if floor_id:
        return q("""
            SELECT * FROM photos WHERE project_id=? AND floor_id=?
            ORDER BY photo_no
        """, (project_id, floor_id), fetch=True)
    return q("SELECT * FROM photos WHERE project_id=? ORDER BY photo_no", (project_id,), fetch=True)

def get_floor(floor_id):
    rows = q("SELECT * FROM floors WHERE id=?", (floor_id,), fetch=True)
    return rows[0] if rows else None

def get_defect(defect_id):
    rows = q("SELECT * FROM defects WHERE id=?", (defect_id,), fetch=True)
    return rows[0] if rows else None

def next_display_no(project_id, floor_id):
    rows = q("SELECT COALESCE(MAX(display_no),0)+1 AS n FROM defects WHERE project_id=? AND floor_id=?",
             (project_id, floor_id), fetch=True)
    return int(rows[0]["n"])

def next_photo_no(project_id):
    rows = q("SELECT COALESCE(MAX(photo_no),0)+1 AS n FROM photos WHERE project_id=?",
             (project_id,), fetch=True)
    return int(rows[0]["n"])

# =========================================================
# Image helpers
# =========================================================
def load_font(size=22):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "C:/Windows/Fonts/malgun.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
    ]
    for p in candidates:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()

def normalize_image(uploaded):
    im = Image.open(uploaded)
    im = ImageOps.exif_transpose(im).convert("RGB")
    # 보고서용 원본은 지나치게 키우지 않되, 가로 사진을 우선
    max_w = 1600
    if im.width > max_w:
        ratio = max_w / im.width
        im = im.resize((max_w, int(im.height * ratio)))
    return im

def save_uploaded_photo(uploaded, project_id, photo_no):
    im = normalize_image(uploaded)
    path = PHOTO_DIR / f"{project_id}_{photo_no:03d}.jpg"
    im.save(path, "JPEG", quality=88, optimize=True)
    return str(path)

def marked_plan(floor_row, project_id, selected_id=None):
    if not floor_row or not floor_row["plan_path"] or not os.path.exists(floor_row["plan_path"]):
        return None
    im = Image.open(floor_row["plan_path"]).convert("RGB")
    draw = ImageDraw.Draw(im)
    font = load_font(max(16, int(min(im.size) / 45)))
    rows = defect_rows(project_id, floor_row["id"])
    for i, d in enumerate(rows, 1):
        if d["x"] is None or d["y"] is None:
            continue
        x, y = float(d["x"]), float(d["y"])
        r = max(10, int(min(im.size) / 120))
        # 선택된 손상은 외곽 원으로 강조
        if d["id"] == selected_id:
            draw.ellipse((x-r-5, y-r-5, x+r+5, y+r+5), outline="blue", width=5)
        draw.ellipse((x-r, y-r, x+r, y+r), fill="white", outline="red", width=3)
        label = str(d["display_no"])
        draw.text((x+r+4, y-r), label, fill="red", font=font)
    return im

def image_bytes(im, fmt="PNG"):
    bio = io.BytesIO()
    im.save(bio, format=fmt)
    bio.seek(0)
    return bio

# =========================================================
# Session state
# =========================================================
defaults = {
    "project_id": None,
    "floor_id": None,
    "selected_defect_id": None,
    "move_mode": False,
    "copy_source_id": None,
    "last_photo_id": None,
    "message": "",
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# =========================================================
# Header
# =========================================================
st.markdown('<div class="big-title">🏫 학교 시설물 현장조사 시스템 V4</div>', unsafe_allow_html=True)
st.caption("정기안전점검 현장용 · 기존/신규학교 · 손상망도 · 물량표 · 사진첩 · 외부/부대시설")

# =========================================================
# 0. 프로젝트 선택 / 생성
# =========================================================
projects = project_rows()

with st.expander("① 학교 / 조사 프로젝트", expanded=st.session_state.project_id is None):
    if projects:
        names = [f'{p["name"]} · {p["inspection_year"]} · {p["mode"]}' for p in projects]
        idx = 0
        if st.session_state.project_id:
            for i, p in enumerate(projects):
                if p["id"] == st.session_state.project_id:
                    idx = i
        chosen = st.selectbox("기존 프로젝트", names, index=idx)
        selected_project = projects[names.index(chosen)]
        if st.button("이 프로젝트 사용", key="use_project"):
            st.session_state.project_id = selected_project["id"]
            st.session_state.floor_id = None
            st.session_state.selected_defect_id = None
            st.rerun()

    st.divider()
    st.write("새 학교 조사 시작")
    c1, c2 = st.columns(2)
    with c1:
        new_name = st.text_input("학교명", placeholder="예: ○○초등학교")
        year = st.text_input("점검연도", value=str(datetime.now().year))
    with c2:
        mode = st.radio("조사 구분", ["기존학교(전회자료 있음)", "신규학교"], horizontal=False)
        itype = st.selectbox("점검종류", ["정기안전점검", "정밀안전점검(추후 확장)", "정밀안전진단(추후 확장)"])
    if st.button("새 프로젝트 만들기", type="primary", key="create_project"):
        if not new_name.strip():
            st.error("학교명을 입력하세요.")
        else:
            pid = uid("PRJ_")
            q("""INSERT INTO projects(id,name,inspection_year,inspection_type,mode,created_at)
                 VALUES(?,?,?,?,?,?)""",
              (pid, new_name.strip(), year, itype, mode.split("(")[0], now()))
            st.session_state.project_id = pid
            st.session_state.floor_id = None
            st.success("프로젝트를 만들었습니다.")
            st.rerun()

if not st.session_state.project_id:
    st.info("위에서 기존 프로젝트를 선택하거나 새 프로젝트를 만드세요.")
    st.stop()

project = q("SELECT * FROM projects WHERE id=?", (st.session_state.project_id,), fetch=True)[0]

# =========================================================
# 1. 층/도면 관리
# =========================================================
st.markdown(f"### {project['name']} · {project['inspection_year']}년 {project['inspection_type']}")

with st.expander("② 층 / 도면 등록", expanded=not bool(floor_rows(project["id"]))):
    existing_floors = floor_rows(project["id"])
    if existing_floors:
        floor_names = [f["floor_name"] for f in existing_floors]
        chosen_floor = st.selectbox("현재 층", floor_names)
        current = next(f for f in existing_floors if f["floor_name"] == chosen_floor)
        st.session_state.floor_id = current["id"]

        st.markdown(
            "📐 **도면 파일 첨부** — 컴퓨터에서 도면 파일을 아래 업로더 영역으로 **마우스로 끌어다 놓기** 하거나 클릭해서 선택하세요."
        )
        new_plan = st.file_uploader(
            "📂 도면을 여기에 끌어다 놓거나 클릭해서 선택",
            type=["png","jpg","jpeg","webp"],
            key=f"plan_{current['id']}"
        )
        if new_plan is not None:
            im = normalize_image(new_plan)
            p = PLAN_DIR / f"{project['id']}_{current['id']}.png"
            im.save(p, "PNG")
            q("UPDATE floors SET plan_path=? WHERE id=?", (str(p), current["id"]))
            st.success("도면을 저장했습니다.")
            st.rerun()
    else:
        st.info("옥상, 5층, 4층 … 순서로 층을 등록하세요.")
        c1, c2 = st.columns(2)
        with c1:
            floor_name = st.text_input("층 이름", placeholder="예: 5층")
        with c2:
            sort_order = st.number_input("정렬순서", min_value=0, value=1, step=1)
        st.markdown(
            "📐 **도면 파일 첨부** — 컴퓨터에서 도면 파일을 아래 업로더 영역으로 **마우스로 끌어다 놓기** 하거나 클릭해서 선택하세요."
        )
        plan = st.file_uploader(
            "📂 도면을 여기에 끌어다 놓거나 클릭해서 선택",
            type=["png","jpg","jpeg","webp"],
            key="first_plan"
        )
        if st.button("층 등록", type="primary"):
            if not floor_name.strip():
                st.error("층 이름을 입력하세요.")
            else:
                fid = uid("FLR_")
                plan_path = None
                if plan:
                    im = normalize_image(plan)
                    p = PLAN_DIR / f"{project['id']}_{fid}.png"
                    im.save(p, "PNG")
                    plan_path = str(p)
                q("INSERT INTO floors(id,project_id,floor_name,plan_path,sort_order) VALUES(?,?,?,?,?)",
                  (fid, project["id"], floor_name.strip(), plan_path, int(sort_order)))
                st.session_state.floor_id = fid
                st.success("층을 등록했습니다.")
                st.rerun()

# ensure floor
floors = floor_rows(project["id"])
if not floors:
    st.warning("먼저 층과 도면을 등록하세요.")
    st.stop()

if st.session_state.floor_id not in [f["id"] for f in floors]:
    st.session_state.floor_id = floors[0]["id"]

# =========================================================
# Main floor selector
# =========================================================
floor_labels = [f["floor_name"] for f in floors]
current_idx = [f["id"] for f in floors].index(st.session_state.floor_id)
chosen_label = st.selectbox("현재 조사층", floor_labels, index=current_idx)
st.session_state.floor_id = next(f["id"] for f in floors if f["floor_name"] == chosen_label)
floor = get_floor(st.session_state.floor_id)

# =========================================================
# 3. 진행현황
# =========================================================
all_defects = defect_rows(project["id"], floor["id"])
all_photos = photo_rows(project["id"], floor["id"])
st.markdown("### 조사 현황")
a,b,c,d = st.columns(4)
a.metric("손상", len(all_defects))
b.metric("사진", len(all_photos))
c.metric("도면", "완료" if floor["plan_path"] and os.path.exists(floor["plan_path"]) else "미등록")
d.metric("층", floor["floor_name"])

# =========================================================
# 4. 도면 / 위치
# =========================================================
st.markdown("### ③ 도면 위치")
if floor["plan_path"] and os.path.exists(floor["plan_path"]):
    plan_im = Image.open(floor["plan_path"]).convert("RGB")
    display = plan_im.copy()
    draw = ImageDraw.Draw(display)
    font = load_font(max(14, int(min(display.size) / 50)))
    rows = defect_rows(project["id"], floor["id"])
    for d in rows:
        if d["x"] is None or d["y"] is None:
            continue
        x,y = float(d["x"]),float(d["y"])
        r=max(8,int(min(display.size)/140))
        if d["id"] == st.session_state.selected_defect_id:
            draw.ellipse((x-r-4,y-r-4,x+r+4,y+r+4), outline="blue", width=4)
        draw.ellipse((x-r,y-r,x+r,y+r), fill="white", outline="red", width=2)
        draw.text((x+r+3,y-r), str(d["display_no"]), fill="red", font=font)

    st.caption("위치 수정: 아래에서 손상을 선택한 뒤 [📍 위치수정]을 누르고 도면의 새 위치를 터치하세요.")
    max_width = 850
    clicked = streamlit_image_coordinates(
        display,
        key=f"coord_{project['id']}_{floor['id']}_{st.session_state.move_mode}_{st.session_state.selected_defect_id}",
        width=max_width
    )
    if clicked:
        # streamlit_image_coordinates는 표시 이미지 좌표를 반환하므로 원본 좌표로 환산
        sx = plan_im.width / display.width
        sy = plan_im.height / display.height
        ox = clicked["x"] * sx
        oy = clicked["y"] * sy

        if st.session_state.move_mode and st.session_state.selected_defect_id:
            q("UPDATE defects SET x=?, y=?, updated_at=? WHERE id=?",
              (ox, oy, now(), st.session_state.selected_defect_id))
            st.session_state.move_mode = False
            st.session_state.message = "위치를 수정했습니다."
            st.rerun()
        elif st.session_state.copy_source_id:
            source = get_defect(st.session_state.copy_source_id)
            if source:
                did = uid("DEF_")
                no = next_display_no(project["id"], floor["id"])
                q("""INSERT INTO defects
                (id,project_id,floor_id,display_no,source,status,location,member,defect_type,
                 crack_width,crack_length,damage_width,damage_height,count_ea,cause,x,y,photo_no,note,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (did,project["id"],floor["id"],no,"복사","신규",source["location"],source["member"],source["defect_type"],
                 source["crack_width"],source["crack_length"],source["damage_width"],source["damage_height"],
                 source["count_ea"],source["cause"],ox,oy,None,"복사 후 위치만 변경",now(),now()))
                st.session_state.copy_source_id = None
                st.session_state.selected_defect_id = did
                st.success(f"{no}번 신규손상을 복사했습니다.")
                st.rerun()
        else:
            # 일반 터치: 새 손상 입력 화면으로 좌표 저장
            st.session_state.pending_xy = (ox, oy)
            st.info(f"도면 위치 지정 완료: X={ox:.0f}, Y={oy:.0f}. 아래 신규손상 정보를 입력하세요.")

else:
    st.warning("현재 층의 도면이 없습니다. 위의 '층 / 도면 등록'에서 등록하세요.")

# =========================================================
# 5. 손상 목록 + 조작
# =========================================================
st.markdown("### ④ 손상 관리")

rows = defect_rows(project["id"], floor["id"])
if rows:
    for d in rows:
        title = f'{d["display_no"]}번 · {d["status"]} · {d["location"] or "-"} · {d["member"] or "-"} · {d["defect_type"] or "-"}'
        with st.container(border=True):
            st.write(title)
            c1,c2,c3,c4 = st.columns(4)
            if c1.button("선택", key=f"sel_{d['id']}"):
                st.session_state.selected_defect_id = d["id"]
                st.session_state.move_mode = False
                st.rerun()
            if c2.button("📍 위치수정", key=f"move_{d['id']}"):
                st.session_state.selected_defect_id = d["id"]
                st.session_state.move_mode = True
                st.info(f'{d["display_no"]}번을 선택했습니다. 도면에서 새 위치를 터치하세요.')
                st.rerun()
            if c3.button("📋 복사", key=f"copy_{d['id']}"):
                st.session_state.copy_source_id = d["id"]
                st.session_state.move_mode = False
                st.info("도면에서 새 위치를 터치하세요.")
                st.rerun()
            if c4.button("✏️ 수정", key=f"edit_{d['id']}"):
                st.session_state.selected_defect_id = d["id"]
                st.session_state.edit_mode = True
                st.rerun()
else:
    st.info("현재 층에 등록된 손상이 없습니다.")

if st.session_state.get("move_mode"):
    st.warning("📍 위치수정 모드입니다. 도면에서 마커를 옮길 새 위치를 터치하세요.")

# =========================================================
# 6. 신규손상 입력
# =========================================================
st.markdown("### ⑤ 신규손상 등록")

pending = st.session_state.get("pending_xy", None)
if pending:
    st.success(f"도면 위치가 지정되었습니다. X={pending[0]:.0f}, Y={pending[1]:.0f}")

presets = {
    "일반": ("벽체","도장들뜸",""),
    "균열": ("벽체","일반균열(수직)",""),
    "누수/습기": ("천장","누수흔적","우수유입등"),
    "박리/박락": ("벽체","박락",""),
    "철근노출": ("보","철근노출",""),
    "상태양호": ("","상태양호",""),
}
preset = st.radio("빠른 유형", list(presets.keys()), horizontal=True)
pmember, ptype, pcause = presets[preset]

c1,c2,c3 = st.columns(3)
with c1:
    location = st.text_input("발생위치", placeholder="예: 복도, 계단실")
    member = st.text_input("부재", value=pmember)
with c2:
    defect_type = st.text_input("유형 및 형상", value=ptype)
    cause = st.text_input("발생원인", value=pcause)
with c3:
    status = st.selectbox("상태", ["신규","기존-유지","기존-확대","기존-축소","보수완료"])
    count_ea = st.number_input("개소(EA)", min_value=1, value=1, step=1)

c1,c2,c3,c4 = st.columns(4)
with c1:
    crack_width = st.number_input("균열폭(mm)", min_value=0.0, value=0.0, step=0.1, format="%.1f")
with c2:
    crack_length = st.number_input("균열길이(m)", min_value=0.0, value=0.0, step=0.1, format="%.1f")
with c3:
    damage_width = st.number_input("손상가로(m)", min_value=0.0, value=0.0, step=0.1, format="%.1f")
with c4:
    damage_height = st.number_input("손상세로(m)", min_value=0.0, value=0.0, step=0.1, format="%.1f")

note = st.text_area("비고 / 현장 메모", height=70)

cam_photo = st.camera_input(
    "📷 현장에서 바로 촬영",
    key=f"cam_{project['id']}_{floor['id']}_{len(rows)}"
)
photo_upload = st.file_uploader(
    "🖼️ 갤러리에서 사진 선택",
    type=["jpg","jpeg","png","webp"],
    key=f"damage_photo_{project['id']}_{floor['id']}_{len(rows)}"
)
photo_source = cam_photo if cam_photo is not None else photo_upload

c1,c2,c3 = st.columns(3)
if c1.button("💾 손상 저장", type="primary", key="save_damage"):
    if not pending:
        st.error("먼저 도면에서 손상 위치를 터치하세요.")
    else:
        did = uid("DEF_")
        no = next_display_no(project["id"], floor["id"])
        q("""INSERT INTO defects
        (id,project_id,floor_id,display_no,source,status,location,member,defect_type,
         crack_width,crack_length,damage_width,damage_height,count_ea,cause,x,y,photo_no,note,created_at,updated_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (did,project["id"],floor["id"],no,"신규",status,location,member,defect_type,
         crack_width or None,crack_length or None,damage_width or None,damage_height or None,
         int(count_ea),cause,pending[0],pending[1],None,note,now(),now()))

        if photo_source:
            pn = next_photo_no(project["id"])
            path = save_uploaded_photo(photo_upload, project["id"], pn)
            caption = f'{floor["floor_name"]} {location} {member} {defect_type}'.strip()
            phid = uid("PHT_")
            q("""INSERT INTO photos(id,project_id,floor_id,defect_id,photo_no,category,path,caption,taken_at)
                 VALUES(?,?,?,?,?,?,?,?,?)""",
              (phid,project["id"],floor["id"],did,pn,"손상",path,caption,now()))
            q("UPDATE defects SET photo_no=?, updated_at=? WHERE id=?", (str(pn),now(),did))
            st.session_state.last_photo_id = phid

        st.session_state.pending_xy = None
        st.session_state.selected_defect_id = did
        st.success(f"{no}번 손상을 저장했습니다.")
        st.rerun()

if c2.button("📷 사진만 추가", key="photo_only"):
    st.session_state.photo_add_mode = True

if c3.button("↺ 입력 초기화", key="clear_input"):
    st.session_state.pending_xy = None
    st.rerun()

# =========================================================
# 7. 선택 손상 상세 수정
# =========================================================
selected = get_defect(st.session_state.selected_defect_id) if st.session_state.selected_defect_id else None
if selected and st.session_state.get("edit_mode"):
    st.markdown("### ⑥ 선택 손상 수정")
    st.info(f'{selected["display_no"]}번 손상을 수정합니다.')
    c1,c2 = st.columns(2)
    with c1:
        eloc = st.text_input("위치", value=selected["location"] or "", key="eloc")
        emember = st.text_input("부재", value=selected["member"] or "", key="emember")
        etype = st.text_input("유형 및 형상", value=selected["defect_type"] or "", key="etype")
        ecause = st.text_input("발생원인", value=selected["cause"] or "", key="ecause")
    with c2:
        estatus = st.selectbox("상태", ["신규","기존-유지","기존-확대","기존-축소","보수완료"],
                               index=["신규","기존-유지","기존-확대","기존-축소","보수완료"].index(selected["status"] or "신규"),
                               key="estatus")
        ew = st.number_input("균열폭(mm)", min_value=0.0, value=float(selected["crack_width"] or 0), step=0.1, key="ew")
        el = st.number_input("균열길이(m)", min_value=0.0, value=float(selected["crack_length"] or 0), step=0.1, key="el")
        ea = st.number_input("개소(EA)", min_value=1, value=int(selected["count_ea"] or 1), step=1, key="ea")
    c1,c2 = st.columns(2)
    if c1.button("수정 저장", type="primary", key="save_edit"):
        q("""UPDATE defects SET location=?,member=?,defect_type=?,status=?,crack_width=?,
             crack_length=?,count_ea=?,cause=?,updated_at=? WHERE id=?""",
          (eloc,emember,etype,estatus,ew,el,ea,ecause,now(),selected["id"]))
        st.session_state.edit_mode = False
        st.success("수정했습니다.")
        st.rerun()
    if c2.button("닫기", key="close_edit"):
        st.session_state.edit_mode = False
        st.rerun()

# =========================================================
# 8. 외부 / 부대시설 / 정기점검표
# =========================================================
st.markdown("### ⑦ 기타 조사")

tab1, tab2, tab3 = st.tabs(["외부조사","부대시설","정기점검표"])

with tab1:
    external_items = [
        "외벽","파라펫","옥상","도로포장","배수시설","담장","외부계단",
        "창호","캐노피","신축이음부","환기구 덮개","기타"
    ]
    item = st.selectbox("외부조사 항목", external_items)
    result = st.radio("상태", ["양호","이상","손상","해당없음"], horizontal=True)
    location_ext = st.text_input("위치", key="ext_loc")
    opinion_ext = st.text_area("의견", key="ext_opinion")
    if st.button("외부조사 저장", key="save_external"):
        fid = uid("FAC_")
        q("""INSERT INTO facilities(id,project_id,category,item,result,location,opinion,updated_at)
             VALUES(?,?,?,?,?,?,?,?)""",
          (fid,project["id"],"외부조사",item,result,location_ext,opinion_ext,now()))
        st.success("외부조사를 저장했습니다.")

with tab2:
    facility_items = ["옹벽","축대","담장","포장","배수시설","운동장","계단","캐노피","기타"]
    fi = st.selectbox("부대시설", facility_items)
    fr = st.radio("상태", ["양호","이상","손상","해당없음"], horizontal=True, key="facility_result")
    fl = st.text_input("위치", key="facility_loc")
    fo = st.text_area("의견", key="facility_opinion")
    if st.button("부대시설 저장", key="save_facility"):
        fid = uid("FAC_")
        q("""INSERT INTO facilities(id,project_id,category,item,result,location,opinion,updated_at)
             VALUES(?,?,?,?,?,?,?,?)""",
          (fid,project["id"],"부대시설",fi,fr,fl,fo,now()))
        st.success("부대시설을 저장했습니다.")

with tab3:
    check_items = [
        "지반","기초","구조체","지붕","외벽","창호","천장","바닥","계단",
        "난간","옥외시설","배수시설","전기·기계 관련 시설","소방 관련 시설",
        "마감재","공중이용부위"
    ]
    ci = st.selectbox("점검항목", check_items)
    cr = st.radio("점검결과", ["양호","이상","손상","해당없음"], horizontal=True, key="check_result")
    co = st.text_area("점검자 의견", key="check_opinion")
    if st.button("정기점검 결과 저장", key="save_check"):
        cid = uid("CHK_")
        q("""INSERT INTO check_items(id,project_id,category,item,result,opinion,updated_at)
             VALUES(?,?,?,?,?,?,?)""",
          (cid,project["id"],"정기점검",ci,cr,co,now()))
        st.success("저장했습니다.")

# =========================================================
# 9. 층 조사 완료
# =========================================================
st.markdown("### ⑧ 층 조사 완료")
if st.button(f"✓ {floor['floor_name']} 조사 완료", type="primary", key="finish_floor"):
    st.session_state.message = f"{floor['floor_name']} 조사 완료"
    # 다음 층으로 이동
    idx = [f["id"] for f in floors].index(floor["id"])
    if idx + 1 < len(floors):
        st.session_state.floor_id = floors[idx+1]["id"]
        st.success(f"{floor['floor_name']} 완료. 다음 층으로 이동합니다.")
    else:
        st.success("등록된 마지막 층까지 조사했습니다.")
    st.rerun()

# =========================================================
# 10. 결과 / 자동 생성
# =========================================================
st.markdown("### ⑨ 결과자료")

def defects_dataframe(project_id):
    rows = defect_rows(project_id)
    data = []
    for d in rows:
        data.append({
            "층": get_floor(d["floor_id"])["floor_name"] if get_floor(d["floor_id"]) else "",
            "손상번호": d["display_no"],
            "손상상태": d["status"],
            "발생위치": d["location"],
            "부재": d["member"],
            "유형 및 형상": d["defect_type"],
            "균열폭(mm)": d["crack_width"],
            "균열길이(m)": d["crack_length"],
            "손상가로(m)": d["damage_width"],
            "손상세로(m)": d["damage_height"],
            "개소(EA)": d["count_ea"],
            "발생원인": d["cause"],
            "사진번호": d["photo_no"],
            "비고": d["note"],
        })
    return pd.DataFrame(data)

def export_excel(project_id):
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        defects_dataframe(project_id).to_excel(writer, index=False, sheet_name="손상물량표")

        ps = photo_rows(project_id)
        pdata = []
        for p in ps:
            f = get_floor(p["floor_id"]) if p["floor_id"] else None
            pdata.append({
                "사진번호": p["photo_no"],
                "층": f["floor_name"] if f else "",
                "구분": p["category"],
                "손상ID": p["defect_id"],
                "설명": p["caption"],
                "파일": p["path"],
            })
        pd.DataFrame(pdata).to_excel(writer, index=False, sheet_name="사진목록")

        fs = q("SELECT * FROM facilities WHERE project_id=? ORDER BY category,item", (project_id,), fetch=True)
        pd.DataFrame([dict(x) for x in fs]).to_excel(writer, index=False, sheet_name="외부부대시설")

        cs = q("SELECT * FROM check_items WHERE project_id=? ORDER BY item", (project_id,), fetch=True)
        pd.DataFrame([dict(x) for x in cs]).to_excel(writer, index=False, sheet_name="정기점검표")
    out.seek(0)
    return out

c1,c2,c3 = st.columns(3)
with c1:
    df = defects_dataframe(project["id"])
    st.download_button(
        "📊 손상물량표 Excel",
        data=df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig"),
        file_name=f"{project['name']}_손상물량표.csv",
        mime="text/csv",
        use_container_width=True
    )
with c2:
    xlsx = export_excel(project["id"])
    st.download_button(
        "📥 전체 조사자료 Excel",
        data=xlsx,
        file_name=f"{project['name']}_현장조사자료.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )
with c3:
    if floor["plan_path"] and os.path.exists(floor["plan_path"]):
        mp = marked_plan(floor, project["id"])
        if mp:
            st.download_button(
                "🗺️ 현재층 조사망도 PNG",
                data=image_bytes(mp),
                file_name=f"{project['name']}_{floor['floor_name']}_조사망도.png",
                mime="image/png",
                use_container_width=True
            )

# =========================================================
# 11. 사진첩 미리보기: 6장 단위
# =========================================================
st.markdown("### ⑩ 사진첩 미리보기")
photos = photo_rows(project["id"], floor["id"])
if photos:
    for start in range(0, len(photos), 6):
        batch = photos[start:start+6]
        cols = st.columns(3)
        for i, p in enumerate(batch):
            with cols[i % 3]:
                if os.path.exists(p["path"]):
                    st.image(p["path"], use_container_width=True)
                st.caption(f'NO.{p["photo_no"]}  {p["caption"]}')
else:
    st.info("현재 층 사진이 없습니다.")

# =========================================================
# 12. 현재 데이터 요약
# =========================================================
st.markdown("### ⑪ 현재 프로젝트 데이터")
all_d = defect_rows(project["id"])
all_p = photo_rows(project["id"])
facs = q("SELECT * FROM facilities WHERE project_id=?", (project["id"],), fetch=True)
checks = q("SELECT * FROM check_items WHERE project_id=?", (project["id"],), fetch=True)
st.write({
    "손상": len(all_d),
    "사진": len(all_p),
    "외부/부대시설 기록": len(facs),
    "정기점검 기록": len(checks),
    "층": len(floors),
})

st.caption("주의: 이 버전은 정기안전점검 현장 프로토타입입니다. 최종 보고서의 안전등급·기술판정은 반드시 담당 기술자가 검토해야 합니다.")
