import io
import numpy as np
import pandas as pd
from PIL import Image, ImageDraw
import streamlit as st
from streamlit_image_coordinates import streamlit_image_coordinates

st.set_page_config(
    page_title="스마트 건축안전 현장 조사 앱", page_icon="🏗️", layout="wide"
)

st.title("🏗️ 건축안전진단 현장 조사 물량표 시스템")
st.write(
    "1단계: 층별 도면 업로드 ➔ 2단계: 도면 위 손상 위치 클릭 ➔ 3단계: 상세 제원"
    " 입력"
)

# 세션 상태 초기화
if "inspection_data" not in st.session_state:
  st.session_state.inspection_data = []

# --- [1단계] 층별 도면 업로드 ---
st.markdown("---")
col_f1, col_f2 = st.columns([1, 2])
with col_f1:
  floor_name = st.selectbox(
      "조사할 층 선택",
      ["옥상층", "5층", "4층", "3층", "2층", "1층", "지하 1층", "외부 부대시설"],
  )
with col_f2:
  floor_plan_file = st.file_uploader(
      f"📂 [{floor_name}] 도면 이미지 업로드 (JPG, PNG)",
      type=["jpg", "jpeg", "png"],
  )

if floor_plan_file is not None:
  base_img = Image.open(floor_plan_file).convert("RGB")

  st.info(
      f"💡 **[{floor_name}] 도면이 준비되었습니다.** 아래 도면에서 손상된 위치를"
      " 마우스로 클릭해 주세요. (이미 등록된 곳은 파란점, 선택한 곳은 빨간점)"
  )

  # 세션에 임시 저장된 클릭 좌표 가져오기
  coord_key = f"clicked_coord_{floor_name}"
  if coord_key not in st.session_state:
    st.session_state[coord_key] = None

  # 도면 이미지에 기존 점(파란색)과 현재 클릭된 점(빨간색)을 함께 그린 단 하나의 이미지 생성
  interactive_img = base_img.copy()
  draw = ImageDraw.Draw(interactive_img)

  # 1. 이미 등록된 손상 위치 표시 (파란색 점)
  for item in st.session_state.inspection_data:
    if item["층"] == floor_name:
      x, y = item["X"], item["Y"]
      r = 8
      draw.ellipse([x - r, y - r, x + r, y + r], fill="blue", outline="white")

  # 2. 현재 선택된 위치가 있다면 강조 표시 (빨간색 점)
  if st.session_state[coord_key] is not None:
    cx, cy = st.session_state[coord_key]
    r = 11
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill="red", outline="white")

  # 📌 도면은 화면에 오직 이 컴포넌트를 통해서만 1개만 출력됩니다.
  coord = streamlit_image_coordinates(interactive_img, key=f"coord_{floor_name}")

  if coord is not None:
    clicked_x, clicked_y = int(coord["x"]), int(coord["y"])
    # 좌표가 실제로 변경되었을 때만 세션 업데이트 후 리런
    if st.session_state[coord_key] != (clicked_x, clicked_y):
      st.session_state[coord_key] = (clicked_x, clicked_y)
      st.rerun()

  # 위치가 선택된 경우에만 하단에 제원 입력 폼 제공
  if st.session_state[coord_key] is not None:
    cx, cy = st.session_state[coord_key]
    st.success(
        f"📍 위치 선택됨 (X: {cx}, Y: {cy}) ➔ 아래에 세부 제원을 입력하세요."
    )

    with st.form(
        key=f"damage_form_{len(st.session_state.inspection_data)}",
        clear_on_submit=True,
    ):
      st.subheader("📝 손상 부위 및 세부 제원 입력")

      col1, col2 = st.columns(2)
      with col1:
        location = st.selectbox(
            "📍 위치",
            ["계단실", "복도", "외벽", "실내 벽체", "천장", "바닥", "옥상"],
        )
        member = st.selectbox(
            "🧱 부재", ["벽체", "천장", "기둥", "보", "바닥", "개구부"]
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
                "텍스오염",
                "콘크리트 박리/박락",
            ],
        )
        cause = st.selectbox(
            "⚠️ 발생원인",
            [
                "우수유입등",
                "응력집중등",
                "구조거동등",
                "건조수축등",
                "시공불량",
                "재료노후화",
            ],
        )

      st.markdown("---")
      st.markdown("##### 📏 균열 및 손상 크기 (0.1 단위 조절 가능)")

      c3, c4, c5 = st.columns(3)
      with c3:
        st.markdown("**균열 크기**")
        c_width = st.number_input(
            "폭 (mm)", min_value=0.0, value=0.0, step=0.1, format="%.1f"
        )
        c_length = st.number_input(
            "길이 (m)", min_value=0.0, value=0.0, step=0.1, format="%.1f"
        )
      with c4:
        st.markdown("**손상 크기**")
        d_width = st.number_input(
            "가로 (m)", min_value=0.0, value=0.5, step=0.1, format="%.1f"
        )
        d_height = st.number_input(
            "세로 (m)", min_value=0.0, value=0.5, step=0.1, format="%.1f"
        )
      with c5:
        st.markdown("**수량 및 사진**")
        ea = st.number_input("개수 (EA)", min_value=1, value=1, step=1)

      photo_file = st.file_uploader(
          "📷 현장 사진 업로드 (가로 사진)", type=["jpg", "png", "jpeg"]
      )

      submitted = st.form_submit_button("✅ 물량표에 추가하기")

      if submitted:
        processed_img = None
        if photo_file:
          p_img = Image.open(photo_file)
          processed_img = p_img.resize((1024, 768))

        w_str = f"{c_width:.1f}" if c_width > 0 else "-"
        l_str = f"{c_length:.1f}" if c_length > 0 else "-"

        new_entry = {
            "층": floor_name,
            "X": cx,
            "Y": cy,
            "위치": location,
            "부재": member,
            "유형 및 형상": damage_type,
            "폭(mm)": w_str,
            "길이(m)": l_str,
            "가로(m)": f"{d_width:.1f}",
            "세로(m)": f"{d_height:.1f}",
            "개수(EA)": ea,
            "발생원인": cause,
            "사진": processed_img,
        }
        st.session_state.inspection_data.append(new_entry)
        # 등록 후 좌표 초기화
        st.session_state[coord_key] = None
        st.rerun()

else:
  st.warning("⚠️ 먼저 조사를 시작할 층의 도면 이미지를 업로드해 주세요.")

# --- [결과 출력] 실시간 물량표 및 사진 대장 ---
if st.session_state.inspection_data:
  st.markdown("---")
  st.subheader("📋 실시간 손상 물량표 (보고서 양식 일치)")

  table_list = []
  photo_counter = 1

  for idx, data in enumerate(st.session_state.inspection_data, start=1):
    row = data.copy()
    enc_circles = [
        "①",
        "②",
        "③",
        "④",
        "⑤",
        "⑥",
        "⑦",
        "⑧",
        "⑨",
        "⑩",
        "⑪",
        "⑫",
        "⑬",
        "⑭",
        "⑮",
    ]
    row["손상위치"] = (
        enc_circles[idx - 1] if idx <= len(enc_circles) else f"({idx})"
    )

    if row["사진"] is not None:
      row["사진번호"] = photo_counter
      photo_counter += 1
    else:
      row["사진번호"] = "-"

    table_list.append(row)

  df = pd.DataFrame(table_list)

  view_columns = [
      "층",
      "손상위치",
      "위치",
      "부재",
      "유형 및 형상",
      "폭(mm)",
      "길이(m)",
      "가로(m)",
      "세로(m)",
      "개수(EA)",
      "발생원인",
      "사진번호",
  ]
  view_df = df[view_columns]

  st.dataframe(view_df, use_container_width=True)

  del_num = st.number_input(
      "삭제할 항목 번호 (순서)",
      min_value=0,
      max_value=len(st.session_state.inspection_data),
      step=1,
  )
  if st.button("🗑️ 선택한 항목 삭제"):
    if del_num > 0:
      st.session_state.inspection_data.pop(del_num - 1)
      st.rerun()


  @st.cache_data
  def convert_df_to_excel(df_in):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
      df_in.to_excel(writer, index=False, sheet_name="손상물량표")
    return output.getvalue()


  st.download_button(
      label="📥 손상물량표 엑셀(Excel) 다운로드",
      data=convert_df_to_excel(view_df),
      file_name="건축안전진단_손상물량표.xlsx",
      mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  )

  st.markdown("---")
  st.subheader("🖼️ 사진 대장 미리보기 (1024x768 규격)")

  photo_items = [
      (
          d["사진번호"],
          d["층"],
          d["손상위치"],
          d["위치"],
          d["부재"],
          d["유형 및 형상"],
          d["사진"],
      )
      for d in table_list
      if d["사진"] is not None
  ]

  if photo_items:
    for i in range(0, len(photo_items), 2):
      cols = st.columns(2)
      for j in range(2):
        if i + j < len(photo_items):
          p_no, p_fl, p_pos, p_lc, p_mb, p_tp, p_img = photo_items[i + j]
          with cols[j]:
            st.image(p_img, use_container_width=True)
            st.caption(
                f"사진 {p_no} | {p_fl} {p_pos} ({p_lc} {p_mb} - {p_tp})"
            )
  else:
    st.info("등록된 현장 사진이 없습니다.")
