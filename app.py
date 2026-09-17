import io
import json
import os
import sqlite3
import pandas as pd
from PIL import Image, ImageDraw, ImageFont
import streamlit as st
from streamlit_image_coordinates import streamlit_image_coordinates

# Page config for mobile usability
st.set_page_config(
    page_title="스마트 건축안전 현장조사 시스템",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# SQLite Database setup for persistent storage
DB_FILE = "building_inspection.db"


def init_db():
  conn = sqlite3.connect(DB_FILE)
  c = conn.cursor()
  c.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            school_name TEXT UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
  c.execute("""
        CREATE TABLE IF NOT EXISTS inspection_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            school_name TEXT,
            floor TEXT,
            num INTEGER,
            x INTEGER,
            y INTEGER,
            location TEXT,
            member TEXT,
            damage_type TEXT,
            width TEXT,
            length TEXT,
            d_width TEXT,
            d_height TEXT,
            ea INTEGER,
            cause TEXT,
            photo_data BLOB
        )
    """)
  conn.commit()
  conn.close()


init_db()

# Mobile viewport CSS optimization
st.markdown(
    """
    <style>
    /* Full width and touch optimized */
    .stApp {
        max-width: 100%;
        padding: 5px;
    }
    div.row-widget.stRadio > div {
        flex-direction: row;
        gap: 8px;
        flex-wrap: wrap;
    }
    /* Touch Pinch Zoom support */
    .element-container img {
        touch-action: pan-x pan-y pinch-zoom !important;
    }
    .stButton>button {
        width: 100%;
        height: 48px;
        font-weight: bold;
        font-size: 16px;
    }
    </style>
""",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------
# Sidebar Settings: Project Management & Marker Sizing
# ---------------------------------------------------------
st.sidebar.title("🏫 학교 및 도면 관리")

# Fetch school list from DB
conn = sqlite3.connect(DB_FILE)
schools_df = pd.read_sql_query("SELECT school_name FROM projects", conn)
conn.close()

school_list = schools_df["school_name"].tolist()

new_school = st.sidebar.text_input("➕ 신규 학교/건물명 입력")
if st.sidebar.button("학교 등록"):
  if new_school.strip():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    try:
      c.execute(
          "INSERT INTO projects (school_name) VALUES (?)", (new_school.strip(),)
      )
      conn.commit()
      st.sidebar.success(f"'{new_school}' 등록 완료!")
      st.rerun()
    except sqlite3.IntegrityError:
      st.sidebar.error("이미 존재하는 학교명입니다.")
    finally:
      conn.close()

selected_school = st.sidebar.selectbox(
    "📂 작업할 학교 선택",
    options=["선택하세요"] + school_list,
    index=1 if school_list else 0,
)

st.sidebar.markdown("---")
st.sidebar.header("⚙️ 도면 마커 설정")
marker_size = st.sidebar.slider(
    "📍 마커 크기 일괄 조절 (터치 확대 비율 연동)",
    min_value=5,
    max_value=50,
    value=18,
    step=1,
)

# ---------------------------------------------------------
# Main App Header
# ---------------------------------------------------------
st.title("🏗️ 모바일 건축안전 현장조사 앱")

if selected_school == "선택하세요" or not selected_school:
  st.warning(
      "👈 사이드바(왼쪽 상단 〉)에서 학교/건물명을 선택하거나 새로 등록해"
      " 주세요."
  )
  st.stop()

st.info(
    f"🏫 현재 조사 대상: **{selected_school}** (데이터 자동 저장 및 불러오기"
    " 적용됨)"
)

# Floors definition (Strict Top to Bottom order)
FLOOR_OPTIONS = [
    "옥상층",
    "5층",
    "4층",
    "3층",
    "2층",
    "1층",
    "지하 1층",
    "외부 부대시설",
]

# Top Horizontal Radio Buttons for Floor Selection
st.markdown("##### 🏢 조사할 층 선택 (위에서 아래로)")
selected_floor = st.radio(
    "층 선택",
    options=FLOOR_OPTIONS,
    horizontal=True,
    label_visibility="collapsed",
)

# Floor Plan File Storage via Session State or File Upload
if "plans" not in st.session_state:
  st.session_state.plans = {}

floor_file = st.file_uploader(
    f"📂 [{selected_floor}] 도면 첨부/변경",
    type=["jpg", "png", "jpeg"],
    key=f"plan_{selected_school}_{selected_floor}",
)
if floor_file is not None:
  st.session_state.plans[f"{selected_school}_{selected_floor}"] = (
      Image.open(floor_file).convert("RGB")
  )

# Fetch Records for Current Floor from DB
conn = sqlite3.connect(DB_FILE)
records_df = pd.read_sql_query(
    "SELECT * FROM inspection_records WHERE school_name=? AND floor=?"
    " ORDER BY num ASC",
    conn,
    params=(selected_school, selected_floor),
)
conn.close()

plan_key = f"{selected_school}_{selected_floor}"
has_plan = plan_key in st.session_state.plans

# ---------------------------------------------------------
# Step 1: Floor Plan Display & Marker Interaction
# ---------------------------------------------------------
if has_plan:
  base_img = st.session_state.plans[plan_key].copy()
  draw = ImageDraw.Draw(base_img)

  # Calculate Next Number for Current Floor
  next_num = len(records_df) + 1

  # Draw Existing Markers with Big Numbers
  for idx, row in records_df.iterrows():
    rx, ry, rnum = row["x"], row["y"], row["num"]
    r = marker_size
    # Blue Circle for Saved Markers
    draw.ellipse([rx - r, ry - r, rx + r, ry + r], fill="blue", outline="white")

    # Font handling
    try:
      font = ImageFont.truetype("arial.ttf", size=int(r * 1.3))
    except:
      font = ImageFont.load_default()

    draw.text(
        (rx, ry),
        str(rnum),
        fill="white",
        font=font,
        anchor="mm",
    )

  # Check if in "Edit Location Mode"
  if "edit_target_id" not in st.session_state:
    st.session_state.edit_target_id = None

  if st.session_state.edit_target_id is not None:
    st.warning(
        f"⚠️ [위치 수정 모드] 번호 {st.session_state.edit_target_num}의 새로운"
        " 위치를 도면에서 터치(꾹 누르기)하세요."
    )

  st.write(
      "👇 **도면을 두 손가락으로 확대(Zoom) 후 손상 위치를 터치하세요:**"
  )
  coords = streamlit_image_coordinates(
      base_img, key=f"canvas_{selected_school}_{selected_floor}"
  )

  # Handle Touch Input
  if coords is not None:
    cx, cy = int(coords["x"]), int(coords["y"])

    # If Location Edit Mode is Active
    if st.session_state.edit_target_id is not None:
      conn = sqlite3.connect(DB_FILE)
      c = conn.cursor()
      c.execute(
          "UPDATE inspection_records SET x=?, y=? WHERE id=?",
          (cx, cy, st.session_state.edit_target_id),
      )
      conn.commit()
      conn.close()
      st.session_state.edit_target_id = None
      st.session_state.edit_target_num = None
      st.success("✅ 위치 이동 수정이 완료되었습니다!")
      st.rerun()

    # Normal Mode: Add New Defect Record
    else:
      st.success(f"📍 위치 지정 완료: X={cx}, Y={cy} (생성될 번호: {next_num}번)")

      # Detailed Form Input
      with st.form(key="defect_form", clear_on_submit=True):
        st.subheader(
            f"📝 [{selected_floor}] 번호 {next_num}번 결함 상세 정보"
        )

        # Dynamic Location Dropdown Options
        if selected_floor == "옥상층":
          loc_options = [
              "파라펫",
              "처마",
              "방수층",
              "구조물",
              "계단실",
              "바닥",
              "기초",
              "기타(직접입력)",
          ]
        else:
          loc_options = [
              "복도",
              "교실",
              "계단실",
              "외벽",
              "실내 벽체",
              "천장",
              "바닥",
              "기타(직접입력)",
          ]

        col1, col2 = st.columns(2)
        with col1:
          loc_sel = st.selectbox("📍 세부 위치", loc_options)
          loc_custom = st.text_input(
              "위치 직접입력 (기타 선택시)", placeholder="입력시 글자 삭제 후 바로 작성"
          )
          final_loc = (
              loc_custom.strip()
              if (loc_sel == "기타(직접입력)" and loc_custom)
              else loc_sel
          )

          member_sel = st.selectbox(
              "🧱 부재명",
              ["벽체", "천장", "기둥", "보", "바닥", "개구부", "기타(직접입력)"],
          )
          member_custom = st.text_input("부재 직접입력")
          final_member = (
              member_custom.strip()
              if (member_sel == "기타(직접입력)" and member_custom)
              else member_sel
          )

        with col2:
          damage_type = st.selectbox(
              "🔍 유형 및 형상",
              [
                  "도장들뜸",
                  "우각부균열",
                  "일반균열(사선)",
                  "일반균열(수직)",
                  "일반균열(수평)",
                  "누수흔적",
                  "백태/백화",
                  "콘크리트 박리/박락",
                  "철근노출",
              ],
          )
          cause = st.selectbox(
              "⚠️ 손상 발생원인",
              [
                  "우수유입 및 습기",
                  "응력집중 및 구조거동",
                  "건조수축 및 온도변화",
                  "시공불량 및 쪼개짐",
                  "재료 노후화 및 열화",
                  "외부 충격",
              ],
          )

        st.markdown("---")
        st.markdown("##### 📏 손상 물량 및 치수 설정")

        c_w, c_l, d_w, d_h = st.columns(4)
        with c_w:
          width_val = st.selectbox(
              "균열폭 (mm)",
              [
                  "-",
                  "0.1",
                  "0.2",
                  "0.3",
                  "0.4",
                  "0.5 이상",
                  "0.6",
                  "0.7",
                  "0.8",
                  "1.0 이상",
              ],
          )
        with c_l:
          length_val = st.selectbox(
              "균열길이 (m)",
              [
                  "-",
                  "0.2",
                  "0.4",
                  "0.6",
                  "0.8",
                  "1.0",
                  "1.2",
                  "1.5",
                  "2.0 이상",
              ],
          )
        with d_w:
          d_w_val = st.number_input(
              "손상 가로 (m)", min_value=0.0, max_value=10.0, value=0.5, step=0.1
          )
        with d_h:
          d_h_val = st.number_input(
              "손상 세로 (m)", min_value=0.0, max_value=10.0, value=0.5, step=0.1
          )

        ea_val = st.number_input("수량 (EA)", min_value=1, value=1, step=1)

        st.markdown("---")
        st.markdown("##### 📷 현장 즉시 촬영 및 갤러리 저장을 위한 카메라")
        cam_photo = st.camera_input("카메라 촬영 (자동 저장 연동)")
        file_photo = st.file_uploader(
            "또는 갤러리에서 파일 선택", type=["jpg", "png", "jpeg"]
        )

        submit_btn = st.form_submit_button("✅ 결함 등록 및 DB 저장")

        if submit_btn:
          img_bytes = None
          target_photo = cam_photo if cam_photo is not None else file_photo

          if target_photo is not None:
            p_img = Image.open(target_photo).convert("RGB")
            p_img = p_img.resize((1024, 768))
            buf = io.BytesIO()
            p_img.save(buf, format="JPEG")
            img_bytes = buf.getvalue()

          # Insert into DB
          conn = sqlite3.connect(DB_FILE)
          c = conn.cursor()
          c.execute(
              """
                        INSERT INTO inspection_records 
                        (school_name, floor, num, x, y, location, member, damage_type, width, length, d_width, d_height, ea, cause, photo_data)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
              (
                  selected_school,
                  selected_floor,
                  next_num,
                  cx,
                  cy,
                  final_loc,
                  final_member,
                  damage_type,
                  width_val,
                  length_val,
                  f"{d_w_val:.1f}",
                  f"{d_h_val:.1f}",
                  ea_val,
                  cause,
                  img_bytes,
              ),
          )
          conn.commit()
          conn.close()
          st.success(f"🎉 [{selected_floor}] {next_num}번 항목 저장 완료!")
          st.rerun()

else:
  st.warning(
      f"⚠️ **[{selected_floor}]** 도면 이미지를 상단 '📂 도면 첨부' 버튼에서"
      " 업로드해 주세요."
  )

# ---------------------------------------------------------
# Step 2: Location Edit / Quick Manage List
# ---------------------------------------------------------
if not records_df.empty:
  st.markdown("---")
  st.subheader(f"📍 [{selected_floor}] 마킹 수정 및 관리")

  for idx, row in records_df.iterrows():
    c1, c2, c3 = st.columns([2, 2, 1])
    with c1:
      st.write(
          f"**{row['num']}번** | {row['location']} ({row['member']}) -"
          f" {row['damage_type']}"
      )
    with c2:
      if st.button(
          f"👆 {row['num']}번 마킹 위치 이동 (꾹 누르기)",
          key=f"edit_pos_{row['id']}",
      ):
        st.session_state.edit_target_id = row["id"]
        st.session_state.edit_target_num = row["num"]
        st.rerun()
    with c3:
      if st.button("🗑️ 삭제", key=f"del_{row['id']}"):
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute(
            "DELETE FROM inspection_records WHERE id=?", (row["id"],)
        )
        conn.commit()
        conn.close()
        st.rerun()

# ---------------------------------------------------------
# Step 3: Comprehensive Output (Order fixed Top-to-Bottom)
# ---------------------------------------------------------
st.markdown("---")
st.header("📊 종합 현장 조사 결과 및 출력 서식")

conn = sqlite3.connect(DB_FILE)
all_records = pd.read_sql_query(
    "SELECT * FROM inspection_records WHERE school_name=?",
    conn,
    params=(selected_school,),
)
conn.close()

if not all_records.empty:
  # Order Fix: Roof -> 5F -> ... -> B1F -> External
  all_records["floor_order"] = all_records["floor"].apply(
      lambda x: FLOOR_OPTIONS.index(x) if x in FLOOR_OPTIONS else 99
  )
  all_records = all_records.sort_values(
      by=["floor_order", "num"]
  ).reset_index(drop=True)

  # Sequential Global Photo Number Assignment
  photo_counter = 1
  photo_nums = []
  for idx, row in all_records.iterrows():
    if row["photo_data"] is not None:
      photo_nums.append(f"사진 {photo_counter}")
      photo_counter += 1
    else:
      photo_nums.append("-")
  all_records["사진번호"] = photo_nums

  # Display Quantity Table
  st.subheader("📋 1. 전체 손상 물량표 (위에서 아래층 순서)")
  display_df = all_records[[
      "floor",
      "num",
      "location",
      "member",
      "damage_type",
      "width",
      "length",
      "d_width",
      "d_height",
      "ea",
      "cause",
      "사진번호",
  ]].copy()
  display_df.columns = [
      "층",
      "발생위치",
      "위치",
      "부재",
      "유형 및 형상",
      "폭(mm)",
      "길이(m)",
      "가로(m)",
      "세로(m)",
      "개수",
      "발생원인",
      "사진연동",
  ]

  st.dataframe(display_df, use_container_width=True)


  # Excel Download Functionality
  def to_excel(df_in):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
      df_in.to_excel(writer, index=False, sheet_name="손상물량표")
    return output.getvalue()


  st.download_button(
      label="📥 전체 손상물량표 엑셀(Excel) 다운로드",
      data=to_excel(display_df),
      file_name=f"{selected_school}_손상물량표.xlsx",
      mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  )

  st.markdown("---")
  st.subheader("🖼️ 2. 사진대장 보고서 서식 (1024x768 규격)")

  photo_records = all_records[all_records["photo_data"].notnull()]

  if not photo_records.empty:
    for i in range(0, len(photo_records), 2):
      cols = st.columns(2)
      for j in range(2):
        if i + j < len(photo_records):
          row_p = photo_records.iloc[i + j]
          img_p = Image.open(io.BytesIO(row_p["photo_data"]))
          with cols[j]:
            st.image(img_p, use_container_width=True)
            st.caption(
                f"**[{row_p['사진번호']}]** {row_p['floor']} {row_p['num']}번 위치"
                f" ({row_p['location']} - {row_p['damage_type']})"
            )
  else:
    st.info("등록된 현장 결함 사진이 없습니다.")

else:
  st.write("📌 아직 등록된 결함 조사 내역이 없습니다.")
