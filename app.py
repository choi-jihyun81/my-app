import streamlit as st
import pandas as pd
from PIL import Image, ImageDraw, ImageFont, ImageOps
import sqlite3
import os
import io
import uuid
from datetime import datetime

# =========================================================
# 학교 시설물 현장조사 APP
# V4.2
# =========================================================

st.set_page_config(
    page_title="학교 현장조사",
    page_icon="🏫",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# =========================================================
# 기본 설정
# =========================================================

BASE = "field_data"
PHOTO_DIR = os.path.join(BASE, "photos")
PLAN_DIR = os.path.join(BASE, "plans")
DB_PATH = os.path.join(BASE, "inspection.db")

os.makedirs(BASE, exist_ok=True)
os.makedirs(PHOTO_DIR, exist_ok=True)
os.makedirs(PLAN_DIR, exist_ok=True)

# 스마트폰 화면
st.markdown("""
<style>
.block-container {
    padding-top: 0.7rem;
    padding-left: 0.8rem;
    padding-right: 0.8rem;
}

.stButton button {
    min-height: 48px;
    font-size: 16px;
    font-weight: 700;
}

input, textarea, select {
    font-size: 16px !important;
}

.damage-card {
    border: 1px solid #ddd;
    border-radius: 10px;
    padding: 10px;
    margin-bottom: 8px;
}
</style>
""", unsafe_allow_html=True)


# =========================================================
# DB
# =========================================================

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS projects (
        id TEXT PRIMARY KEY,
        school_name TEXT,
        year TEXT,
        inspection_type TEXT,
        school_type TEXT,
        created_at TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS floors (
        id TEXT PRIMARY KEY,
        project_id TEXT,
        floor_name TEXT,
        plan_path TEXT,
        sort_order INTEGER
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS damages (
        id TEXT PRIMARY KEY,
        project_id TEXT,
        floor_id TEXT,
        damage_no INTEGER,

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
        note TEXT,

        x REAL,
        y REAL,

        photo_no INTEGER,

        created_at TEXT,
        updated_at TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS photos (
        id TEXT PRIMARY KEY,
        project_id TEXT,
        floor_id TEXT,
        damage_id TEXT,
        photo_no INTEGER,
        category TEXT,
        path TEXT,
        caption TEXT,
        created_at TEXT
    )
    """)

    conn.commit()
    conn.close()


init_db()


# =========================================================
# 공통 함수
# =========================================================

def new_id(prefix):
    return prefix + uuid.uuid4().hex[:10]


def now():
    return datetime.now().isoformat(timespec="seconds")


def execute(sql, params=()):

    conn = get_db()
    cur = conn.cursor()
    cur.execute(sql, params)
    conn.commit()
    conn.close()


def fetchall(sql, params=()):

    conn = get_db()
    cur = conn.cursor()
    cur.execute(sql, params)
    result = cur.fetchall()
    conn.close()

    return result


def get_projects():

    return fetchall("""
        SELECT *
        FROM projects
        ORDER BY created_at DESC
    """)


def get_floors(project_id):

    return fetchall("""
        SELECT *
        FROM floors
        WHERE project_id=?
        ORDER BY sort_order
    """, (project_id,))


def get_damages(project_id, floor_id):

    return fetchall("""
        SELECT *
        FROM damages
        WHERE project_id=?
        AND floor_id=?
        ORDER BY damage_no
    """, (project_id, floor_id))


def get_damage(damage_id):

    rows = fetchall("""
        SELECT *
        FROM damages
        WHERE id=?
    """, (damage_id,))

    return rows[0] if rows else None


def next_damage_no(project_id, floor_id):

    rows = fetchall("""
        SELECT MAX(damage_no) AS n
        FROM damages
        WHERE project_id=?
        AND floor_id=?
    """, (project_id, floor_id))

    if not rows or rows[0]["n"] is None:
        return 1

    return int(rows[0]["n"]) + 1


def next_photo_no(project_id):

    rows = fetchall("""
        SELECT MAX(photo_no) AS n
        FROM photos
        WHERE project_id=?
    """, (project_id,))

    if not rows or rows[0]["n"] is None:
        return 1

    return int(rows[0]["n"]) + 1


# =========================================================
# 세션
# =========================================================

if "project_id" not in st.session_state:
    st.session_state.project_id = None

if "floor_id" not in st.session_state:
    st.session_state.floor_id = None

if "selected_damage" not in st.session_state:
    st.session_state.selected_damage = None

if "move_mode" not in st.session_state:
    st.session_state.move_mode = False

if "pending_x" not in st.session_state:
    st.session_state.pending_x = None

if "pending_y" not in st.session_state:
    st.session_state.pending_y = None


# =========================================================
# 제목
# =========================================================

st.title("🏫 학교 시설물 현장조사")

st.caption(
    "정기안전점검 · 기존학교 / 신규학교 · 손상망도 · 물량표 · 사진"
)


# =========================================================
# 1. 학교 선택
# =========================================================

with st.expander("① 학교 조사 선택", expanded=True):

    projects = get_projects()

    if projects:

        project_names = [
            f"{p['school_name']} / {p['year']}"
            for p in projects
        ]

        selected_name = st.selectbox(
            "기존 조사",
            project_names
        )

        selected_project = projects[
            project_names.index(selected_name)
        ]

        if st.button("이 학교 조사 시작"):

            st.session_state.project_id = selected_project["id"]
            st.session_state.floor_id = None

            st.rerun()

    st.divider()

    st.subheader("새 학교")

    school_name = st.text_input(
        "학교명",
        placeholder="○○초등학교"
    )

    year = st.text_input(
        "점검연도",
        value=str(datetime.now().year)
    )

    school_type = st.radio(
        "조사 구분",
        [
            "기존학교 - 전회자료 있음",
            "신규학교"
        ]
    )

    inspection_type = st.selectbox(
        "점검종류",
        [
            "정기안전점검",
            "정밀안전점검",
            "정밀안전진단"
        ]
    )

    if st.button(
        "새 조사 만들기",
        type="primary"
    ):

        if school_name.strip() == "":
            st.error("학교명을 입력하세요.")

        else:

            pid = new_id("PRJ_")

            execute("""
            INSERT INTO projects
            VALUES (?, ?, ?, ?, ?, ?)
            """, (
                pid,
                school_name,
                year,
                inspection_type,
                school_type,
                now()
            ))

            st.session_state.project_id = pid

            st.success("조사를 만들었습니다.")

            st.rerun()


if not st.session_state.project_id:

    st.info("학교를 선택하거나 새 조사를 만들어주세요.")
    st.stop()


# =========================================================
# 현재 프로젝트
# =========================================================

project = fetchall("""
SELECT *
FROM projects
WHERE id=?
""", (st.session_state.project_id,))[0]


st.header(
    f"{project['school_name']} / {project['inspection_type']}"
)


# =========================================================
# 2. 층 등록
# =========================================================

floors = get_floors(project["id"])

with st.expander(
    "② 층 / 도면 등록",
    expanded=len(floors) == 0
):

    floor_name = st.text_input(
        "층",
        placeholder="옥상 / 5층 / 4층 / 3층"
    )

    floor_order = st.number_input(
        "순서",
        min_value=1,
        value=len(floors) + 1
    )

    plan_file = st.file_uploader(
        "도면",
        type=["jpg", "jpeg", "png"]
    )

    if st.button("층 등록"):

        if not floor_name:
            st.error("층 이름을 입력하세요.")

        else:

            fid = new_id("FLR_")

            plan_path = ""

            if plan_file:

                img = Image.open(plan_file)

                plan_path = os.path.join(
                    PLAN_DIR,
                    f"{fid}.png"
                )

                img.save(plan_path)

            execute("""
            INSERT INTO floors
            VALUES (?, ?, ?, ?, ?)
            """, (
                fid,
                project["id"],
                floor_name,
                plan_path,
                floor_order
            ))

            st.session_state.floor_id = fid

            st.success(
                f"{floor_name} 등록 완료"
            )

            st.rerun()


# =========================================================
# 층 선택
# =========================================================

floors = get_floors(project["id"])

if not floors:

    st.warning("먼저 층과 도면을 등록하세요.")
    st.stop()


floor_names = [
    f["floor_name"]
    for f in floors
]

if st.session_state.floor_id is None:

    st.session_state.floor_id = floors[0]["id"]

current_index = 0

for i, f in enumerate(floors):

    if f["id"] == st.session_state.floor_id:
        current_index = i


selected_floor_name = st.selectbox(
    "현재 조사층",
    floor_names,
    index=current_index
)


for f in floors:

    if f["floor_name"] == selected_floor_name:
        st.session_state.floor_id = f["id"]
        floor = f
        break


# =========================================================
# 현재 층 손상
# =========================================================

damages = get_damages(
    project["id"],
    floor["id"]
)


# =========================================================
# 3. 도면
# =========================================================

st.header(
    f"③ {floor['floor_name']} 조사망도"
)


if floor["plan_path"] and os.path.exists(
    floor["plan_path"]
):

    plan = Image.open(
        floor["plan_path"]
    ).convert("RGB")

    display = plan.copy()

    draw = ImageDraw.Draw(display)

    # -----------------------------------------------------
    # 손상 마커 표시
    # -----------------------------------------------------

    for d in damages:

        if d["x"] is None:
            continue

        x = int(d["x"])
        y = int(d["y"])

        r = 14

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
                x+16,
                y-12
            ),
            str(d["damage_no"]),
            fill="red"
        )

    # -----------------------------------------------------
    # 이미지 터치
    # -----------------------------------------------------

    from streamlit_image_coordinates import (
        streamlit_image_coordinates
    )

    clicked = streamlit_image_coordinates(
        display,
        width=850,
        key=f"plan_{floor['id']}"
    )

    if clicked:

        scale_x = plan.width / display.width
        scale_y = plan.height / display.height

        x = clicked["x"] * scale_x
        y = clicked["y"] * scale_y

        # 위치 수정
        if (
            st.session_state.move_mode
            and
            st.session_state.selected_damage
        ):

            execute("""
            UPDATE damages
            SET x=?,
                y=?,
                updated_at=?
            WHERE id=?
            """, (
                x,
                y,
                now(),
                st.session_state.selected_damage
            ))

            st.session_state.move_mode = False

            st.success(
                "도면 위치를 수정했습니다."
            )

            st.rerun()

        # 신규 손상 위치
        else:

            st.session_state.pending_x = x
            st.session_state.pending_y = y

            st.success(
                "도면 위치가 지정되었습니다."
            )


else:

    st.warning(
        "현재 층에 도면이 없습니다."
    )


# =========================================================
# 위치 상태
# =========================================================

if (
    st.session_state.pending_x is not None
):

    st.info(
        "📍 신규 손상 위치 지정 완료"
    )


if st.session_state.move_mode:

    st.warning(
        "📍 위치수정 모드입니다. "
        "도면에서 새로운 위치를 터치하세요."
    )


# =========================================================
# 4. 손상 입력
# =========================================================

st.header("④ 손상 조사")


preset = st.radio(
    "빠른 입력",
    [
        "일반",
        "균열",
        "누수",
        "박락",
        "철근노출"
    ],
    horizontal=True
)


preset_data = {

    "일반": ("벽체", "도장들뜸"),
    "균열": ("벽체", "일반균열"),
    "누수": ("천장", "누수흔적"),
    "박락": ("벽체", "박락"),
    "철근노출": ("보", "철근노출")
}


default_member, default_type = preset_data[
    preset
]


col1, col2 = st.columns(2)


with col1:

    location = st.text_input(
        "발생위치",
        placeholder="복도 / 계단실 / 교실"
    )

    member = st.text_input(
        "부재",
        value=default_member
    )

    defect_type = st.text_input(
        "유형 및 형상",
        value=default_type
    )

    status = st.selectbox(
        "상태",
        [
            "신규",
            "기존-유지",
            "기존-확대",
            "기존-축소",
            "보수완료"
        ]
    )


with col2:

    cause = st.text_input(
        "발생원인"
    )

    crack_width = st.number_input(
        "균열폭(mm)",
        min_value=0.0,
        step=0.1
    )

    crack_length = st.number_input(
        "균열길이(m)",
        min_value=0.0,
        step=0.1
    )

    count_ea = st.number_input(
        "개소(EA)",
        min_value=1,
        value=1
    )


damage_width = st.number_input(
    "손상가로(m)",
    min_value=0.0,
    step=0.1
)

damage_height = st.number_input(
    "손상세로(m)",
    min_value=0.0,
    step=0.1
)


note = st.text_area(
    "현장 메모"
)


# =========================================================
# 사진
# =========================================================

st.subheader("📷 사진")

camera_photo = st.camera_input(
    "현장에서 바로 촬영"
)

gallery_photo = st.file_uploader(
    "갤러리 사진",
    type=[
        "jpg",
        "jpeg",
        "png",
        "webp"
    ]
)

photo = (
    camera_photo
    if camera_photo
    else gallery_photo
)


# =========================================================
# 저장
# =========================================================

if st.button(
    "💾 손상 저장",
    type="primary"
):

    if (
        st.session_state.pending_x is None
    ):

        st.error(
            "먼저 도면에서 위치를 지정하세요."
        )

    else:

        damage_id = new_id("DMG_")

        damage_no = next_damage_no(
            project["id"],
            floor["id"]
        )

        execute("""
        INSERT INTO damages
        (
            id,
            project_id,
            floor_id,
            damage_no,
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
            note,
            x,
            y,
            photo_no,
            created_at,
            updated_at
        )
        VALUES (
            ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?
        )
        """, (

            damage_id,

            project["id"],

            floor["id"],

            damage_no,

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

            note,

            st.session_state.pending_x,

            st.session_state.pending_y,

            None,

            now(),

            now()
        ))


        # -------------------------------------------------
        # 사진 저장
        # -------------------------------------------------

        if photo:

            photo_no = next_photo_no(
                project["id"]
            )

            img = Image.open(photo)

            img = ImageOps.exif_transpose(
                img
            ).convert("RGB")

            # 보고서용 크기
            max_width = 1024

            if img.width > max_width:

                ratio = (
                    max_width /
                    img.width
                )

                img = img.resize(
                    (
                        max_width,
                        int(
                            img.height *
                            ratio
                        )
                    )
                )


            photo_path = os.path.join(
                PHOTO_DIR,
                f"{project['id']}_{photo_no:04d}.jpg"
            )

            img.save(
                photo_path,
                "JPEG",
                quality=88
            )


            caption = (
                f"{floor['floor_name']} "
                f"{location} "
                f"{member} "
                f"{defect_type}"
            )


            execute("""
            INSERT INTO photos
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (

                new_id("PHT_"),

                project["id"],

                floor["id"],

                damage_id,

                photo_no,

                "손상",

                photo_path,

                caption,

                now()
            ))


            execute("""
            UPDATE damages
            SET photo_no=?
            WHERE id=?
            """, (
                photo_no,
                damage_id
            ))


        st.session_state.pending_x = None
        st.session_state.pending_y = None

        st.success(
            f"{damage_no}번 손상 저장 완료"
        )

        st.rerun()


# =========================================================
# 5. 손상 목록
# =========================================================

st.header("⑤ 현재층 손상 목록")


damages = get_damages(
    project["id"],
    floor["id"]
)


for d in damages:

    st.markdown(
        f"""
        <div class="damage-card">

        <b>
        NO.{d['damage_no']}
        </b>

        &nbsp; {d['status']}

        <br>

        {d['location']}
        /
        {d['member']}
        /
        {d['defect_type']}

        </div>
        """,
        unsafe_allow_html=True
    )


    c1, c2, c3 = st.columns(3)


    # 위치수정
    if c1.button(
        "📍 위치수정",
        key=f"move_{d['id']}"
    ):

        st.session_state.selected_damage = d["id"]

        st.session_state.move_mode = True

        st.rerun()


    # 복사
    if c2.button(
        "📋 복사",
        key=f"copy_{d['id']}"
    ):

        st.session_state.pending_x = d["x"]
        st.session_state.pending_y = d["y"]

        st.session_state.copy_source = d["id"]

        st.info(
            "도면에서 새 위치를 터치한 후 "
            "저장하세요."
        )


    # 삭제
    if c3.button(
        "🗑 삭제",
        key=f"delete_{d['id']}"
    ):

        execute(
            "DELETE FROM damages WHERE id=?",
            (d["id"],)
        )

        st.rerun()


# =========================================================
# 6. 사진첩
# =========================================================

st.header("⑥ 사진첩")


photos = fetchall("""
SELECT *
FROM photos
WHERE project_id=?
AND floor_id=?
ORDER BY photo_no
""", (
    project["id"],
    floor["id"]
))


for start in range(
    0,
    len(photos),
    6
):

    batch = photos[
        start:start+6
    ]

    cols = st.columns(3)

    for i, p in enumerate(batch):

        with cols[i % 3]:

            if os.path.exists(
                p["path"]
            ):

                st.image(
                    p["path"],
                    use_container_width=True
                )

            st.caption(
                f"NO.{p['photo_no']} "
                f"{p['caption']}"
            )


# =========================================================
# 7. 물량표
# =========================================================

st.header("⑦ 손상물량표")


rows = fetchall("""
SELECT
    floor_id,
    damage_no,
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
    photo_no
FROM damages
WHERE project_id=?
ORDER BY floor_id, damage_no
""", (
    project["id"],
))


data = []


for r in rows:

    floor_rows = fetchall(
        """
        SELECT floor_name
        FROM floors
        WHERE id=?
        """,
        (r["floor_id"],)
    )

    floor_name = (
        floor_rows[0]["floor_name"]
        if floor_rows
        else ""
    )


    data.append({

        "층":
        floor_name,

        "손상번호":
        r["damage_no"],

        "상태":
        r["status"],

        "위치":
        r["location"],

        "부재":
        r["member"],

        "유형 및 형상":
        r["defect_type"],

        "균열폭(mm)":
        r["crack_width"],

        "균열길이(m)":
        r["crack_length"],

        "손상가로(m)":
        r["damage_width"],

        "손상세로(m)":
        r["damage_height"],

        "개소(EA)":
        r["count_ea"],

        "발생원인":
        r["cause"],

        "사진번호":
        r["photo_no"]

    })


df = pd.DataFrame(data)


st.dataframe(
    df,
    use_container_width=True,
    hide_index=True
)


# =========================================================
# CSV 다운로드
# =========================================================

csv_data = df.to_csv(
    index=False,
    encoding="utf-8-sig"
)


st.download_button(
    "📥 손상물량표 다운로드",
    csv_data,
    file_name=f"{project['school_name']}_손상물량표.csv",
    mime="text/csv"
)
