import streamlit as st
import pandas as pd
from PIL import Image, ImageDraw, ImageFont, ImageOps
from streamlit_image_coordinates import streamlit_image_coordinates
import sqlite3
import uuid
import io
import os
from datetime import datetime


# =========================================================
# 학교 시설물 현장조사 시스템 V5
# =========================================================

st.set_page_config(
    page_title="학교 시설물 현장조사",
    page_icon="🏫",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# =========================================================
# 기본 폴더
# Path를 사용하지 않고 os.path 방식으로 처리
# =========================================================

BASE = "field_data"
PHOTO_DIR = os.path.join(BASE, "photos")
PLAN_DIR = os.path.join(BASE, "plans")

os.makedirs(BASE, exist_ok=True)
os.makedirs(PHOTO_DIR, exist_ok=True)
os.makedirs(PLAN_DIR, exist_ok=True)

DB_PATH = os.path.join(BASE, "inspection.db")


# =========================================================
# CSS
# =========================================================

st.markdown("""
<style>

html, body {
    font-family: sans-serif;
}

.block-container {
    padding-top: 0.7rem;
    padding-bottom: 4rem;
    max-width: 1100px;
}

.stButton > button {
    min-height: 48px;
    border-radius: 10px;
    font-weight: 700;
    width: 100%;
}

div[data-testid="stHorizontalBlock"] {
    gap: 0.45rem;
}

.big-title {
    font-size: 1.4rem;
    font-weight: 800;
}

.small-note {
    color: #666;
    font-size: 0.86rem;
}

</style>
""", unsafe_allow_html=True)


# =========================================================
# DB 연결
# =========================================================

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def now():
    return datetime.now().isoformat(timespec="seconds")


def uid(prefix=""):
    return prefix + uuid.uuid4().hex[:10]


def q(sql, params=(), fetch=False):
    conn = db()
    cur = conn.cursor()
    cur.execute(sql, params)

    rows = cur.fetchall() if fetch else None

    conn.commit()
    conn.close()

    return rows


# =========================================================
# DB 생성
# =========================================================

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

    conn.commit()
    conn.close()


init_db()


# =========================================================
# DB 조회 함수
# =========================================================

def project_rows():

    return q(
        """
        SELECT *
        FROM projects
        ORDER BY created_at DESC
        """,
        fetch=True
    )


def floor_rows(project_id):

    return q(
        """
        SELECT *
        FROM floors
        WHERE project_id=?
        ORDER BY sort_order, floor_name
        """,
        (project_id,),
        fetch=True
    )


def defect_rows(project_id, floor_id=None):

    if floor_id:

        return q(
            """
            SELECT *
            FROM defects
            WHERE project_id=? AND floor_id=?
            ORDER BY display_no, created_at
            """,
            (project_id, floor_id),
            fetch=True
        )

    return q(
        """
        SELECT *
        FROM defects
        WHERE project_id=?
        ORDER BY floor_id, display_no, created_at
        """,
        (project_id,),
        fetch=True
    )


def photo_rows(project_id, floor_id=None):

    if floor_id:

        return q(
            """
            SELECT *
            FROM photos
            WHERE project_id=? AND floor_id=?
            ORDER BY photo_no
            """,
            (project_id, floor_id),
            fetch=True
        )

    return q(
        """
        SELECT *
        FROM photos
        WHERE project_id=?
        ORDER BY photo_no
        """,
        (project_id,),
        fetch=True
    )


def get_floor(floor_id):

    rows = q(
        """
        SELECT *
        FROM floors
        WHERE id=?
        """,
        (floor_id,),
        fetch=True
    )

    return rows[0] if rows else None


def get_defect(defect_id):

    rows = q(
        """
        SELECT *
        FROM defects
        WHERE id=?
        """,
        (defect_id,),
        fetch=True
    )

    return rows[0] if rows else None


def next_display_no(project_id, floor_id):

    rows = q(
        """
        SELECT COALESCE(MAX(display_no), 0) + 1 AS n
        FROM defects
        WHERE project_id=? AND floor_id=?
        """,
        (project_id, floor_id),
        fetch=True
    )

    return int(rows[0]["n"])


def next_photo_no(project_id):

    rows = q(
        """
        SELECT COALESCE(MAX(photo_no), 0) + 1 AS n
        FROM photos
        WHERE project_id=?
        """,
        (project_id,),
        fetch=True
    )

    return int(rows[0]["n"])


# =========================================================
# 이미지 처리
# =========================================================

def load_font(size=22):

    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "C:/Windows/Fonts/malgun.ttf",
        "C:/Windows/Fonts/arialbd.ttf"
    ]

    for path in candidates:

        if os.path.exists(path):

            try:
                return ImageFont.truetype(path, size)

            except:
                pass

    return ImageFont.load_default()


def normalize_image(uploaded):

    im = Image.open(uploaded)

    # 스마트폰 사진 방향 자동 보정
    im = ImageOps.exif_transpose(im)

    im = im.convert("RGB")

    # 지나치게 큰 사진 자동 축소
    max_width = 1600

    if im.width > max_width:

        ratio = max_width / im.width

        im = im.resize(
            (
                max_width,
                int(im.height * ratio)
            )
        )

    return im


def save_plan(uploaded, project_id, floor_id):

    im = normalize_image(uploaded)

    path = os.path.join(
        PLAN_DIR,
        f"{project_id}_{floor_id}.png"
    )

    im.save(path, "PNG")

    return path


def save_photo(uploaded, project_id, photo_no):

    if uploaded is None:
        return None

    im = normalize_image(uploaded)

    path = os.path.join(
        PHOTO_DIR,
        f"{project_id}_{photo_no:03d}.jpg"
    )

    im.save(
        path,
        "JPEG",
        quality=88,
        optimize=True
    )

    return path


def image_bytes(im):

    bio = io.BytesIO()

    im.save(
        bio,
        format="PNG"
    )

    bio.seek(0)

    return bio


# =========================================================
# 조사망도 만들기
# =========================================================

def marked_plan(floor, project_id, selected_id=None):

    if not floor:
        return None

    plan_path = floor["plan_path"]

    if not plan_path:
        return None

    if not os.path.exists(plan_path):
        return None

    im = Image.open(plan_path).convert("RGB")

    draw = ImageDraw.Draw(im)

    font = load_font(
        max(
            16,
            int(min(im.size) / 45)
        )
    )

    rows = defect_rows(
        project_id,
        floor["id"]
    )

    for d in rows:

        if d["x"] is None or d["y"] is None:
            continue

        x = float(d["x"])
        y = float(d["y"])

        r = max(
            10,
            int(min(im.size) / 120)
        )

        # 선택된 손상
        if d["id"] == selected_id:

            draw.ellipse(
                (
                    x-r-5,
                    y-r-5,
                    x+r+5,
                    y+r+5
                ),
                outline="blue",
                width=5
            )

        draw.ellipse(
            (
                x-r,
                y-r,
                x+r,
                y+r
            ),
            fill="white",
            outline="red",
            width=3
        )

        draw.text(
            (
                x+r+4,
                y-r
            ),
            str(d["display_no"]),
            fill="red",
            font=font
        )

    return im


# =========================================================
# Session State
# =========================================================

defaults = {

    "project_id": None,

    "floor_id": None,

    "selected_defect_id": None,

    "move_mode": False,

    "copy_source_id": None,

    "pending_xy": None,

    "edit_mode": False,

    "photo_add_mode": False,

    "message": ""

}

for key, value in defaults.items():

    if key not in st.session_state:

        st.session_state[key] = value


# =========================================================
# 제목
# =========================================================

st.markdown(
    '<div class="big-title">🏫 학교 시설물 현장조사 시스템 V5</div>',
    unsafe_allow_html=True
)

st.caption(
    "정기안전점검 현장용 · 도면 · 손상망도 · 물량표 · 사진첩"
)


# =========================================================
# 1. 프로젝트
# =========================================================

st.markdown("### ① 학교 / 조사 프로젝트")

projects = project_rows()

with st.expander(
    "학교 / 조사 프로젝트",
    expanded=st.session_state.project_id is None
):

    if projects:

        names = [
            f'{p["name"]} · {p["inspection_year"]} · {p["mode"]}'
            for p in projects
        ]

        idx = 0

        if st.session_state.project_id:

            for i, p in enumerate(projects):

                if p["id"] == st.session_state.project_id:

                    idx = i

        chosen = st.selectbox(
            "기존 프로젝트",
            names,
            index=idx
        )

        selected_project = projects[
            names.index(chosen)
        ]

        if st.button(
            "이 프로젝트 사용",
            key="use_project"
        ):

            st.session_state.project_id = selected_project["id"]

            st.session_state.floor_id = None

            st.session_state.selected_defect_id = None

            st.session_state.pending_xy = None

            st.rerun()

    st.divider()

    st.write("새 학교 조사 시작")

    c1, c2 = st.columns(2)

    with c1:

        new_name = st.text_input(
            "학교명",
            placeholder="예: ○○초등학교"
        )

        year = st.text_input(
            "점검연도",
            value=str(datetime.now().year)
        )

    with c2:

        mode = st.radio(
            "조사 구분",
            [
                "기존학교",
                "신규학교"
            ]
        )

        itype = st.selectbox(
            "점검종류",
            [
                "정기안전점검",
                "정밀안전점검",
                "정밀안전진단"
            ]
        )

    if st.button(
        "새 프로젝트 만들기",
        type="primary",
        key="create_project"
    ):

        if not new_name.strip():

            st.error("학교명을 입력하세요.")

        else:

            pid = uid("PRJ_")

            q(
                """
                INSERT INTO projects
                (
                    id,
                    name,
                    inspection_year,
                    inspection_type,
                    mode,
                    created_at
                )
                VALUES(?,?,?,?,?,?)
                """,
                (
                    pid,
                    new_name.strip(),
                    year,
                    itype,
                    mode,
                    now()
                )
            )

            st.session_state.project_id = pid

            st.session_state.floor_id = None

            st.success(
                "프로젝트를 만들었습니다."
            )

            st.rerun()


if not st.session_state.project_id:

    st.info(
        "학교 프로젝트를 먼저 만들어주세요."
    )

    st.stop()


project = q(
    """
    SELECT *
    FROM projects
    WHERE id=?
    """,
    (st.session_state.project_id,),
    fetch=True
)[0]


# =========================================================
# 2. 층 / 도면
# =========================================================

st.markdown(
    f"### {project['name']} · "
    f"{project['inspection_year']}년 · "
    f"{project['inspection_type']}"
)

st.markdown("### ② 층 / 도면 등록")

floors = floor_rows(
    project["id"]
)

with st.expander(
    "층 / 도면 등록",
    expanded=not bool(floors)
):

    if floors:

        floor_names = [
            f["floor_name"]
            for f in floors
        ]

        current_idx = 0

        if st.session_state.floor_id:

            ids = [
                f["id"]
                for f in floors
            ]

            if st.session_state.floor_id in ids:

                current_idx = ids.index(
                    st.session_state.floor_id
                )

        chosen_floor = st.selectbox(
            "현재 층",
            floor_names,
            index=current_idx
        )

        current = next(
            f for f in floors
            if f["floor_name"] == chosen_floor
        )

        st.session_state.floor_id = current["id"]

        st.write(
            "📐 도면을 아래 영역으로 "
            "**끌어다 놓거나 클릭해서 선택**하세요."
        )

        new_plan = st.file_uploader(
            "📂 도면 첨부",
            type=[
                "png",
                "jpg",
                "jpeg",
                "webp"
            ],
            key=f"plan_{current['id']}"
        )

        if new_plan:

            path = save_plan(
                new_plan,
                project["id"],
                current["id"]
            )

            q(
                """
                UPDATE floors
                SET plan_path=?
                WHERE id=?
                """,
                (
                    path,
                    current["id"]
                )
            )

            st.success(
                "도면을 저장했습니다."
            )

            st.rerun()

    else:

        st.info(
            "옥상 → 5층 → 4층 → 3층 순서로 "
            "등록해도 됩니다."
        )

        c1, c2 = st.columns(2)

        with c1:

            floor_name = st.text_input(
                "층 이름",
                placeholder="예: 5층"
            )

        with c2:

            sort_order = st.number_input(
                "정렬순서",
                min_value=0,
                value=1,
                step=1
            )

        plan = st.file_uploader(
            "📂 첫 도면 첨부",
            type=[
                "png",
                "jpg",
                "jpeg",
                "webp"
            ],
            key="first_plan"
        )

        if st.button(
            "층 등록",
            type="primary"
        ):

            if not floor_name.strip():

                st.error(
                    "층 이름을 입력하세요."
                )

            else:

                fid = uid("FLR_")

                plan_path = None

                if plan:

                    plan_path = save_plan(
                        plan,
                        project["id"],
                        fid
                    )

                q(
                    """
                    INSERT INTO floors
                    (
                        id,
                        project_id,
                        floor_name,
                        plan_path,
                        sort_order
                    )
                    VALUES(?,?,?,?,?)
                    """,
                    (
                        fid,
                        project["id"],
                        floor_name.strip(),
                        plan_path,
                        int(sort_order)
                    )
                )

                st.session_state.floor_id = fid

                st.success(
                    "층을 등록했습니다."
                )

                st.rerun()


# =========================================================
# 층 확인
# =========================================================

floors = floor_rows(
    project["id"]
)

if not floors:

    st.warning(
        "먼저 층을 등록하세요."
    )

    st.stop()


floor_ids = [
    f["id"]
    for f in floors
]

if st.session_state.floor_id not in floor_ids:

    st.session_state.floor_id = floor_ids[0]


# =========================================================
# 현재 층 선택
# =========================================================

floor_labels = [
    f["floor_name"]
    for f in floors
]

current_idx = floor_ids.index(
    st.session_state.floor_id
)

chosen_label = st.selectbox(
    "현재 조사층",
    floor_labels,
    index=current_idx
)

st.session_state.floor_id = next(
    f["id"]
    for f in floors
    if f["floor_name"] == chosen_label
)

floor = get_floor(
    st.session_state.floor_id
)


# =========================================================
# 조사 현황
# =========================================================

rows = defect_rows(
    project["id"],
    floor["id"]
)

photos = photo_rows(
    project["id"],
    floor["id"]
)

st.markdown("### 조사 현황")

a, b, c, d = st.columns(4)

a.metric(
    "손상",
    len(rows)
)

b.metric(
    "사진",
    len(photos)
)

c.metric(
    "도면",
    "완료"
    if floor["plan_path"]
    and os.path.exists(floor["plan_path"])
    else "미등록"
)

d.metric(
    "현재층",
    floor["floor_name"]
)


# =========================================================
# 3. 도면 위치
# =========================================================

st.markdown("### ③ 도면 / 손상 위치")

if (
    floor["plan_path"]
    and os.path.exists(floor["plan_path"])
):

    plan_im = Image.open(
        floor["plan_path"]
    ).convert("RGB")

    display = plan_im.copy()

    draw = ImageDraw.Draw(
        display
    )

    font = load_font(
        max(
            14,
            int(min(display.size) / 50)
        )
    )

    rows = defect_rows(
        project["id"],
        floor["id"]
    )

    for d in rows:

        if d["x"] is None or d["y"] is None:
            continue

        x = float(d["x"])
        y = float(d["y"])

        r = max(
            8,
            int(min(display.size) / 140)
        )

        # 선택된 손상
        if (
            d["id"]
            == st.session_state.selected_defect_id
        ):

            draw.ellipse(
                (
                    x-r-4,
                    y-r-4,
                    x+r+4,
                    y+r+4
                ),
                outline="blue",
                width=4
            )

        # 손상 마커
        draw.ellipse(
            (
                x-r,
                y-r,
                x+r,
                y+r
            ),
            fill="white",
            outline="red",
            width=2
        )

        draw.text(
            (
                x+r+3,
                y-r
            ),
            str(d["display_no"]),
            fill="red",
            font=font
        )

    if st.session_state.move_mode:

        st.warning(
            "📍 위치 수정 모드입니다. "
            "도면에서 새 위치를 터치하세요."
        )

    elif st.session_state.copy_source_id:

        source = get_defect(
            st.session_state.copy_source_id
        )

        if source:

            st.info(
                f'{source["display_no"]}번 손상을 '
                "복사합니다. "
                "새 위치를 도면에서 터치하세요."
            )

    else:

        st.caption(
            "도면에서 손상 위치를 터치하면 "
            "신규 손상을 입력할 수 있습니다."
        )

    clicked = streamlit_image_coordinates(
        display,
        key=(
            f"coord_"
            f"{project['id']}_"
            f"{floor['id']}_"
            f"{st.session_state.move_mode}_"
            f"{st.session_state.copy_source_id}_"
            f"{st.session_state.selected_defect_id}"
        ),
        width=850
    )

    if clicked:

        sx = plan_im.width / display.width
        sy = plan_im.height / display.height

        ox = clicked["x"] * sx
        oy = clicked["y"] * sy

        # -------------------------------------------------
        # 위치 수정
        # -------------------------------------------------

        if (
            st.session_state.move_mode
            and st.session_state.selected_defect_id
        ):

            q(
                """
                UPDATE defects
                SET x=?,
                    y=?,
                    updated_at=?
                WHERE id=?
                """,
                (
                    ox,
                    oy,
                    now(),
                    st.session_state.selected_defect_id
                )
            )

            st.session_state.move_mode = False

            st.success(
                "위치를 수정했습니다."
            )

            st.rerun()

        # -------------------------------------------------
        # 복사
        # -------------------------------------------------

        elif st.session_state.copy_source_id:

            source = get_defect(
                st.session_state.copy_source_id
            )

            if source:

                did = uid("DEF_")

                no = next_display_no(
                    project["id"],
                    floor["id"]
                )

                q(
                    """
                    INSERT INTO defects
                    (
                        id,
                        project_id,
                        floor_id,
                        display_no,
                        source,
                        status,
                        location,
                        member,
                        defect_type,
                        crack_width,
                        crack_length,
                        damage_width,
                        damage_height,
                        count_ea,
                        cause,
                        x,
                        y,
                        photo_no,
                        note,
                        created_at,
                        updated_at
                    )
                    VALUES
                    (
                        ?,?,?,?,?,?,?,?,?,?,
                        ?,?,?,?,?,?,?,?,?,?
                    )
                    """,
                    (
                        did,
                        project["id"],
                        floor["id"],
                        no,
                        "복사",
                        "신규",
                        source["location"],
                        source["member"],
                        source["defect_type"],
                        source["crack_width"],
                        source["crack_length"],
                        source["damage_width"],
                        source["damage_height"],
                        source["count_ea"],
                        source["cause"],
                        ox,
                        oy,
                        None,
                        "복사 후 위치만 변경",
                        now(),
                        now()
                    )
                )

                st.session_state.copy_source_id = None

                st.session_state.selected_defect_id = did

                st.success(
                    f"{no}번 신규손상을 복사했습니다."
                )

                st.rerun()

        # -------------------------------------------------
        # 신규 손상 위치
        # -------------------------------------------------

        else:

            st.session_state.pending_xy = (
                ox,
                oy
            )

            st.success(
                f"위치 지정 완료 "
                f"X={ox:.0f}, Y={oy:.0f}"
            )

else:

    st.warning(
        "현재 층에 도면이 없습니다."
    )


# =========================================================
# 4. 손상 관리
# =========================================================

st.markdown("### ④ 손상 관리")

rows = defect_rows(
    project["id"],
    floor["id"]
)

if rows:

    for d in rows:

        title = (
            f'{d["display_no"]}번 · '
            f'{d["status"]} · '
            f'{d["location"] or "-"} · '
            f'{d["member"] or "-"} · '
            f'{d["defect_type"] or "-"}'
        )

        with st.container(border=True):

            st.write(title)

            c1, c2, c3, c4 = st.columns(4)

            # 선택
            if c1.button(
                "선택",
                key=f"sel_{d['id']}"
            ):

                st.session_state.selected_defect_id = d["id"]

                st.rerun()

            # 위치 수정
            if c2.button(
                "📍 위치수정",
                key=f"move_{d['id']}"
            ):

                st.session_state.selected_defect_id = d["id"]

                st.session_state.move_mode = True

                st.rerun()

            # 복사
            if c3.button(
                "📋 복사",
                key=f"copy_{d['id']}"
            ):

                st.session_state.copy_source_id = d["id"]

                st.session_state.move_mode = False

                st.rerun()

            # 수정
            if c4.button(
                "✏️ 수정",
                key=f"edit_{d['id']}"
            ):

                st.session_state.selected_defect_id = d["id"]

                st.session_state.edit_mode = True

                st.rerun()

else:

    st.info(
        "현재 층에 등록된 손상이 없습니다."
    )


# =========================================================
# 5. 신규 손상 입력
# =========================================================

st.markdown("### ⑤ 신규손상 등록")

pending = st.session_state.get(
    "pending_xy"
)


if pending:

    st.success(
        f"📍 위치 지정됨 "
        f"X={pending[0]:.0f}, "
        f"Y={pending[1]:.0f}"
    )


# =========================================================
# 빠른 유형
# =========================================================

presets = {

    "일반":
        ("벽체", "도장들뜸", ""),

    "균열":
        ("벽체", "일반균열(수직)", ""),

    "누수/습기":
        ("천장", "누수흔적", "우수유입등"),

    "박리/박락":
        ("벽체", "박락", ""),

    "철근노출":
        ("보", "철근노출", ""),

    "상태양호":
        ("", "상태양호", "")

}


preset = st.radio(
    "빠른 유형",
    list(presets.keys()),
    horizontal=True
)

pmember, ptype, pcause = presets[preset]


# =========================================================
# 입력
# =========================================================

c1, c2, c3 = st.columns(3)

with c1:

    location = st.text_input(
        "발생위치",
        placeholder="예: 복도, 계단실"
    )

    member = st.text_input(
        "부재",
        value=pmember
    )

with c2:

    defect_type = st.text_input(
        "유형 및 형상",
        value=ptype
    )

    cause = st.text_input(
        "발생원인",
        value=pcause
    )

with c3:

    status_list = [
        "신규",
        "기존-유지",
        "기존-확대",
        "기존-축소",
        "보수완료"
    ]

    status = st.selectbox(
        "상태",
        status_list
    )

    count_ea = st.number_input(
        "개소(EA)",
        min_value=1,
        value=1,
        step=1
    )


c1, c2, c3, c4 = st.columns(4)

with c1:

    crack_width = st.number_input(
        "균열폭(mm)",
        min_value=0.0,
        value=0.0,
        step=0.1
    )

with c2:

    crack_length = st.number_input(
        "균열길이(m)",
        min_value=0.0,
        value=0.0,
        step=0.1
    )

with c3:

    damage_width = st.number_input(
        "손상가로(m)",
        min_value=0.0,
        value=0.0,
        step=0.1
    )

with c4:

    damage_height = st.number_input(
        "손상세로(m)",
        min_value=0.0,
        value=0.0,
        step=0.1
    )


note = st.text_area(
    "비고 / 현장 메모",
    height=70
)


# =========================================================
# 사진
# =========================================================

st.markdown("#### 📷 사진")

cam_photo = st.camera_input(
    "현장에서 바로 촬영",
    key=(
        f"cam_"
        f"{project['id']}_"
        f"{floor['id']}_"
        f"{len(rows)}"
    )
)

photo_upload = st.file_uploader(
    "🖼️ 갤러리에서 사진 선택",
    type=[
        "jpg",
        "jpeg",
        "png",
        "webp"
    ],
    key=(
        f"damage_photo_"
        f"{project['id']}_"
        f"{floor['id']}_"
        f"{len(rows)}"
    )
)

# 중요:
# 카메라 사진이 있으면 카메라 사진,
# 없으면 갤러리 사진 사용

photo_source = (
    cam_photo
    if cam_photo is not None
    else photo_upload
)


# =========================================================
# 저장 버튼
# =========================================================

c1, c2, c3 = st.columns(3)


# ---------------------------------------------------------
# 손상 저장
# ---------------------------------------------------------

if c1.button(
    "💾 손상 저장",
    type="primary",
    key="save_damage"
):

    if not pending:

        st.error(
            "먼저 도면에서 손상 위치를 터치하세요."
        )

    else:

        did = uid("DEF_")

        no = next_display_no(
            project["id"],
            floor["id"]
        )

        q(
            """
            INSERT INTO defects
            (
                id,
                project_id,
                floor_id,
                display_no,
                source,
                status,
                location,
                member,
                defect_type,
                crack_width,
                crack_length,
                damage_width,
                damage_height,
                count_ea,
                cause,
                x,
                y,
                photo_no,
                note,
                created_at,
                updated_at
            )
            VALUES
            (
                ?,?,?,?,?,?,?,?,?,?,
                ?,?,?,?,?,?,?,?,?,?
            )
            """,
            (
                did,
                project["id"],
                floor["id"],
                no,
                "신규",
                status,
                location,
                member,
                defect_type,
                crack_width if crack_width > 0 else None,
                crack_length if crack_length > 0 else None,
                damage_width if damage_width > 0 else None,
                damage_height if damage_height > 0 else None,
                int(count_ea),
                cause,
                pending[0],
                pending[1],
                None,
                note,
                now(),
                now()
            )
        )


        # -------------------------------------------------
        # 사진 저장
        # -------------------------------------------------

        if photo_source:

            pn = next_photo_no(
                project["id"]
            )

            # 여기서 photo_source를 사용해야 함
            # 기존 코드의 photo_upload 오류 수정

            path = save_photo(
                photo_source,
                project["id"],
                pn
            )

            caption = (
                f'{floor["floor_name"]} '
                f'{location} '
                f'{member} '
                f'{defect_type}'
            ).strip()

            phid = uid("PHT_")

            q(
                """
                INSERT INTO photos
                (
                    id,
                    project_id,
                    floor_id,
                    defect_id,
                    photo_no,
                    category,
                    path,
                    caption,
                    taken_at
                )
                VALUES(?,?,?,?,?,?,?,?,?)
                """,
                (
                    phid,
                    project["id"],
                    floor["id"],
                    did,
                    pn,
                    "손상",
                    path,
                    caption,
                    now()
                )
            )

            q(
                """
                UPDATE defects
                SET photo_no=?,
                    updated_at=?
                WHERE id=?
                """,
                (
                    str(pn),
                    now(),
                    did
                )
            )


        st.session_state.pending_xy = None

        st.session_state.selected_defect_id = did

        st.success(
            f"{no}번 손상을 저장했습니다."
        )

        st.rerun()


# ---------------------------------------------------------
# 사진만 추가
# ---------------------------------------------------------

if c2.button(
    "📷 사진만 추가",
    key="photo_only"
):

    st.session_state.photo_add_mode = True


# ---------------------------------------------------------
# 입력 초기화
# ---------------------------------------------------------

if c3.button(
    "↺ 입력 초기화",
    key="clear_input"
):

    st.session_state.pending_xy = None

    st.rerun()


# =========================================================
# 6. 선택 손상 수정
# =========================================================

selected = None

if st.session_state.selected_defect_id:

    selected = get_defect(
        st.session_state.selected_defect_id
    )


if (
    selected
    and st.session_state.get("edit_mode")
):

    st.markdown(
        "### ⑥ 선택 손상 수정"
    )

    st.info(
        f'{selected["display_no"]}번 손상을 수정합니다.'
    )

    c1, c2 = st.columns(2)

    with c1:

        eloc = st.text_input(
            "발생위치",
            value=selected["location"] or "",
            key="eloc"
        )

        emember = st.text_input(
            "부재",
            value=selected["member"] or "",
            key="emember"
        )

        etype = st.text_input(
            "유형 및 형상",
            value=selected["defect_type"] or "",
            key="etype"
        )

        ecause = st.text_input(
            "발생원인",
            value=selected["cause"] or "",
            key="ecause"
        )

    with c2:

        status_list = [
            "신규",
            "기존-유지",
            "기존-확대",
            "기존-축소",
            "보수완료"
        ]

        selected_status = (
            selected["status"]
            if selected["status"] in status_list
            else "신규"
        )

        estatus = st.selectbox(
            "상태",
            status_list,
            index=status_list.index(
                selected_status
            ),
            key="estatus"
        )

        ew = st.number_input(
            "균열폭(mm)",
            min_value=0.0,
            value=float(
                selected["crack_width"] or 0
            ),
            step=0.1,
            key="ew"
        )

        el = st.number_input(
            "균열길이(m)",
            min_value=0.0,
            value=float(
                selected["crack_length"] or 0
            ),
            step=0.1,
            key="el"
        )

        edw = st.number_input(
            "손상가로(m)",
            min_value=0.0,
            value=float(
                selected["damage_width"] or 0
            ),
            step=0.1,
            key="edw"
        )

        edh = st.number_input(
            "손상세로(m)",
            min_value=0.0,
            value=float(
                selected["damage_height"] or 0
            ),
            step=0.1,
            key="edh"
        )

        ea = st.number_input(
            "개소(EA)",
            min_value=1,
            value=int(
                selected["count_ea"] or 1
            ),
            step=1,
            key="ea"
        )

    edit_note = st.text_area(
        "비고",
        value=selected["note"] or "",
        key="edit_note"
    )

    c1, c2 = st.columns(2)

    if c1.button(
        "수정 저장",
        type="primary",
        key="save_edit"
    ):

        q(
            """
            UPDATE defects
            SET
                location=?,
                member=?,
                defect_type=?,
                status=?,
                crack_width=?,
                crack_length=?,
                damage_width=?,
                damage_height=?,
                count_ea=?,
                cause=?,
                note=?,
                updated_at=?
            WHERE id=?
            """,
            (
                eloc,
                emember,
                etype,
                estatus,
                ew if ew > 0 else None,
                el if el > 0 else None,
                edw if edw > 0 else None,
                edh if edh > 0 else None,
                ea,
                ecause,
                edit_note,
                now(),
                selected["id"]
            )
        )

        st.session_state.edit_mode = False

        st.success(
            "수정했습니다."
        )

        st.rerun()


    if c2.button(
        "닫기",
        key="close_edit"
    ):

        st.session_state.edit_mode = False

        st.rerun()


# =========================================================
# 7. 외부 / 부대시설 / 점검표
# =========================================================

st.markdown("### ⑦ 기타 조사")

tab1, tab2, tab3 = st.tabs(
    [
        "외부조사",
        "부대시설",
        "정기점검표"
    ]
)


# ---------------------------------------------------------
# 외부
# ---------------------------------------------------------

with tab1:

    external_items = [
        "외벽",
        "파라펫",
        "옥상",
        "도로포장",
        "배수시설",
        "담장",
        "외부계단",
        "창호",
        "캐노피",
        "신축이음부",
        "환기구 덮개",
        "기타"
    ]

    item = st.selectbox(
        "외부조사 항목",
        external_items
    )

    result = st.radio(
        "상태",
        [
            "양호",
            "이상",
            "손상",
            "해당없음"
        ],
        horizontal=True
    )

    location_ext = st.text_input(
        "위치",
        key="ext_loc"
    )

    opinion_ext = st.text_area(
        "의견",
        key="ext_opinion"
    )

    if st.button(
        "외부조사 저장",
        key="save_external"
    ):

        fid = uid("FAC_")

        q(
            """
            INSERT INTO facilities
            (
                id,
                project_id,
                category,
                item,
                result,
                location,
                opinion,
                updated_at
            )
            VALUES(?,?,?,?,?,?,?,?)
            """,
            (
                fid,
                project["id"],
                "외부조사",
                item,
                result,
                location_ext,
                opinion_ext,
                now()
            )
        )

        st.success(
            "외부조사를 저장했습니다."
        )


# ---------------------------------------------------------
# 부대시설
# ---------------------------------------------------------

with tab2:

    facility_items = [
        "옹벽",
        "축대",
        "담장",
        "포장",
        "배수시설",
        "운동장",
        "계단",
        "캐노피",
        "기타"
    ]

    fi = st.selectbox(
        "부대시설",
        facility_items
    )

    fr = st.radio(
        "상태",
        [
            "양호",
            "이상",
            "손상",
            "해당없음"
        ],
        horizontal=True,
        key="facility_result"
    )

    fl = st.text_input(
        "위치",
        key="facility_loc"
    )

    fo = st.text_area(
        "의견",
        key="facility_opinion"
    )

    if st.button(
        "부대시설 저장",
        key="save_facility"
    ):

        fid = uid("FAC_")

        q(
            """
            INSERT INTO facilities
            (
                id,
                project_id,
                category,
                item,
                result,
                location,
                opinion,
                updated_at
            )
            VALUES(?,?,?,?,?,?,?,?)
            """,
            (
                fid,
                project["id"],
                "부대시설",
                fi,
                fr,
                fl,
                fo,
                now()
            )
        )

        st.success(
            "부대시설을 저장했습니다."
        )


# ---------------------------------------------------------
# 정기점검표
# ---------------------------------------------------------

with tab3:

    check_items = [
        "지반",
        "기초",
        "구조체",
        "지붕",
        "외벽",
        "창호",
        "천장",
        "바닥",
        "계단",
        "난간",
        "옥외시설",
        "배수시설",
        "전기·기계 관련 시설",
        "소방 관련 시설",
        "마감재",
        "공중이용부위"
    ]

    ci = st.selectbox(
        "점검항목",
        check_items
    )

    cr = st.radio(
        "점검결과",
        [
            "양호",
            "이상",
            "손상",
            "해당없음"
        ],
        horizontal=True,
        key="check_result"
    )

    co = st.text_area(
        "점검자 의견",
        key="check_opinion"
    )

    if st.button(
        "정기점검 결과 저장",
        key="save_check"
    ):

        cid = uid("CHK_")

        q(
            """
            INSERT INTO check_items
            (
                id,
                project_id,
                category,
                item,
                result,
                opinion,
                updated_at
            )
            VALUES(?,?,?,?,?,?,?)
            """,
            (
                cid,
                project["id"],
                "정기점검",
                ci,
                cr,
                co,
                now()
            )
        )

        st.success(
            "저장했습니다."
        )


# =========================================================
# 8. 층 조사 완료
# =========================================================

st.markdown("### ⑧ 층 조사 완료")

if st.button(
    f"✓ {floor['floor_name']} 조사 완료",
    type="primary",
    key="finish_floor"
):

    idx = [
        f["id"]
        for f in floors
    ].index(
        floor["id"]
    )

    if idx + 1 < len(floors):

        st.session_state.floor_id = (
            floors[idx + 1]["id"]
        )

        st.success(
            f"{floor['floor_name']} 완료. "
            "다음 층으로 이동합니다."
        )

    else:

        st.success(
            "등록된 마지막 층까지 조사했습니다."
        )

    st.rerun()


# =========================================================
# 9. 결과자료
# =========================================================

st.markdown("### ⑨ 결과자료")


def defects_dataframe(project_id):

    rows = defect_rows(
        project_id
    )

    data = []

    for d in rows:

        f = get_floor(
            d["floor_id"]
        )

        data.append(
            {
                "층":
                    f["floor_name"]
                    if f else "",

                "손상번호":
                    d["display_no"],

                "손상상태":
                    d["status"],

                "발생위치":
                    d["location"],

                "부재":
                    d["member"],

                "유형 및 형상":
                    d["defect_type"],

                "균열폭(mm)":
                    d["crack_width"],

                "균열길이(m)":
                    d["crack_length"],

                "손상가로(m)":
                    d["damage_width"],

                "손상세로(m)":
                    d["damage_height"],

                "개소(EA)":
                    d["count_ea"],

                "발생원인":
                    d["cause"],

                "사진번호":
                    d["photo_no"],

                "비고":
                    d["note"]
            }
        )

    return pd.DataFrame(data)


def export_excel(project_id):

    out = io.BytesIO()

    with pd.ExcelWriter(
        out,
        engine="openpyxl"
    ):

        # 손상물량표
        defects_dataframe(
            project_id
        ).to_excel(
            out,
            index=False,
            sheet_name="손상물량표"
        )

        # 사진목록
        ps = photo_rows(
            project_id
        )

        pdata = []

        for p in ps:

            f = (
                get_floor(p["floor_id"])
                if p["floor_id"]
                else None
            )

            pdata.append(
                {
                    "사진번호":
                        p["photo_no"],

                    "층":
                        f["floor_name"]
                        if f else "",

                    "구분":
                        p["category"],

                    "손상ID":
                        p["defect_id"],

                    "설명":
                        p["caption"],

                    "파일":
                        p["path"]
                }
            )

        pd.DataFrame(
            pdata
        ).to_excel(
            out,
            index=False,
            sheet_name="사진목록"
        )

        # 외부 / 부대시설
        fs = q(
            """
            SELECT *
            FROM facilities
            WHERE project_id=?
            ORDER BY category,item
            """,
            (project_id,),
            fetch=True
        )

        pd.DataFrame(
            [dict(x) for x in fs]
        ).to_excel(
            out,
            index=False,
            sheet_name="외부부대시설"
        )

        # 점검표
        cs = q(
            """
            SELECT *
            FROM check_items
            WHERE project_id=?
            ORDER BY item
            """,
            (project_id,),
            fetch=True
        )

        pd.DataFrame(
            [dict(x) for x in cs]
        ).to_excel(
            out,
            index=False,
            sheet_name="정기점검표"
        )

    out.seek(0)

    return out


c1, c2, c3 = st.columns(3)


with c1:

    df = defects_dataframe(
        project["id"]
    )

    st.download_button(
        "📊 손상물량표 CSV",
        data=df.to_csv(
            index=False,
            encoding="utf-8-sig"
        ).encode("utf-8-sig"),
        file_name=(
            f"{project['name']}_"
            "손상물량표.csv"
        ),
        mime="text/csv",
        use_container_width=True
    )


with c2:

    xlsx = export_excel(
        project["id"]
    )

    st.download_button(
        "📥 전체 조사자료 Excel",
        data=xlsx,
        file_name=(
            f"{project['name']}_"
            "현장조사자료.xlsx"
        ),
        mime=(
            "application/vnd.openxmlformats-"
            "officedocument.spreadsheetml.sheet"
        ),
        use_container_width=True
    )


with c3:

    if (
        floor["plan_path"]
        and os.path.exists(
            floor["plan_path"]
        )
    ):

        mp = marked_plan(
            floor,
            project["id"]
        )

        if mp:

            st.download_button(
                "🗺️ 조사망도 PNG",
                data=image_bytes(mp),
                file_name=(
                    f"{project['name']}_"
                    f"{floor['floor_name']}_"
                    "조사망도.png"
                ),
                mime="image/png",
                use_container_width=True
            )


# =========================================================
# 10. 사진첩
# =========================================================

st.markdown(
    "### ⑩ 사진첩 미리보기"
)

photos = photo_rows(
    project["id"],
    floor["id"]
)

if photos:

    # 6장 단위
    for start in range(
        0,
        len(photos),
        6
    ):

        batch = photos[
            start:start + 6
        ]

        cols = st.columns(3)

        for i, p in enumerate(batch):

            with cols[i % 3]:

                if (
                    p["path"]
                    and os.path.exists(
                        p["path"]
                    )
                ):

                    st.image(
                        p["path"],
                        use_container_width=True
                    )

                st.caption(
                    f'NO.{p["photo_no"]} '
                    f'{p["caption"]}'
                )

else:

    st.info(
        "현재 층 사진이 없습니다."
    )


# =========================================================
# 11. 프로젝트 요약
# =========================================================

st.markdown(
    "### ⑪ 현재 프로젝트 데이터"
)

all_d = defect_rows(
    project["id"]
)

all_p = photo_rows(
    project["id"]
)

facs = q(
    """
    SELECT *
    FROM facilities
    WHERE project_id=?
    """,
    (project["id"],),
    fetch=True
)

checks = q(
    """
    SELECT *
    FROM check_items
    WHERE project_id=?
    """,
    (project["id"],),
    fetch=True
)

st.write(
    {
        "손상": len(all_d),
        "사진": len(all_p),
        "외부/부대시설 기록": len(facs),
        "정기점검 기록": len(checks),
        "층": len(floors)
    }
)


st.caption(
    "현장조사 데이터 입력용 프로토타입입니다."
)
