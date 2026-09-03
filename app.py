import io
import pandas as pd
from PIL import Image
import streamlit as st
from streamlit_image_coordinates import streamlit_image_coordinates

st.set_page_config(
    page_title="스마트 건축안전 현장 조사 앱", page_icon="🏗️", layout="wide"
)

st.title("🏗️ 스마트 건축안전 현장 조사 시스템 (실무 맞춤형)")
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
  img = Image.open(floor_plan_file)

  st.info(
      f"💡 **[{floor_name}] 도면이 준비되었습니다.** 아래 도면에서 손상된 위치를"
      " 마우스로 클릭해 주세요."
  )

  # 도면 이미지 클릭 좌표 추출
  coord = streamlit_image_coordinates(img, key=f"coord_{floor_name}")

  if coord is not None:
    cx, cy = int(coord["x"]), int(coord["y"])
    st.success(
        f"📍 도면 선택 완료 (X: {cx}, Y: {cy}) ➔ 아래에 세부 정보를 입력하세요."
    )

    with st.form(
        key=f"damage_form_{len(st.session_state.inspection_data)}",
        clear_on_submit=True,
    ):
      st.subheader("📝 손상 부위 및 실무 분류 선택")

      # 실무 맞춤형 위치 및 부재
      col1, col2 = st.columns(2)
      with col1:
        location = st.selectbox(
            "📍 조사 위치",
            [
                "계단실",
                "복도",
                "외벽",
                "실내 벽체",
                "천장",
                "바닥",
                "옥상",
                "지하주차장",
            ],
        )
        member = st.selectbox(
            "🧱 대상 부재", ["벽체", "천장", "기둥", "보", "바닥", "개구부/창호"]
        )
      with col2:
        # 요청하신 세부 유형 반영
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
                "철근노출",
                "백화현상",
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
      st.markdown("##### 📏 균열 폭·길이 및 물량 세부 입력")
      col3, col4, col5, col6 = st.columns(4)
      with col3:
        crack_width = st.text_input(
            "균열 폭 (mm)", value="-", placeholder="예: 0.3"
        )
      with col4:
        crack_length = st.text_input(
            "균열 길이 (m)", value="-", placeholder="예: 1.2"
        )
      with col5:
        ea = st.number_input(
            "개소/개수 (EA)", min_value=1, value=1, step=1
        )
      with col6:
        severity = st.selectbox("상태/심각도", ["경미", "보통", "심각"])

      st.markdown("---")
      photo_file = st.file_uploader(
          "📷 현장 사진 업로드 (가로 사진 권장)", type=["jpg", "png", "jpeg"]
      )

      submitted = st.form_submit_button("✅ 손상 정보 등록")

      if submitted:
        processed_img = None
        if photo_file:
          p_img = Image.open(photo_file)
          processed_img = p_img.resize((1024, 768))

        new_entry = {
            "층": floor_name,
            "X": cx,
            "Y": cy,
            "위치": location,
            "부재": member,
            "유형 및 형상": damage_type,
            "폭(mm)": crack_width,
            "길이(m)": crack_length,
            "개수": ea,
            "심각도": severity,
            "발생원인": cause,
            "사진": processed_img,
        }
        st.session_state.inspection_data.append(new_entry)
        st.rerun()

else:
  st.warning("⚠️ 먼저 조사를 시작할 층의 도면 이미지를 업로드해 주세요.")

# --- [결과 출력] 실시간 물량표 및 사진 대장 ---
if st.session_state.inspection_data:
  st.markdown("---")
  st.subheader("📋 실시간 자동 정렬된 손상 물량표")

  table_list = []
  for idx, data in enumerate(st.session_state.inspection_data, start=1):
    row = data.copy()
    row["번호"] = idx
    table_list.append(row)

  df = pd.DataFrame(table_list)
  view_df = df[
      [
          "번호",
          "층",
          "위치",
          "부재",
          "유형 및 형상",
          "폭(mm)",
          "길이(m)",
          "개수",
          "심각도",
          "발생원인",
          "X",
          "Y",
      ]
  ]
  st.dataframe(view_df, use_container_width=True)

  del_num = st.number_input(
      "삭제할 항목 번호 입력",
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
          d["번호"],
          d["층"],
          d["위치"],
          d["부재"],
          d["유형 및 형상"],
          d["폭(mm)"],
          d["길이(m)"],
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
          p_no, p_fl, p_lc, p_mb, p_tp, p_w, p_l, p_img = photo_items[i + j]
          with cols[j]:
            st.image(p_img, use_container_width=True)
            st.caption(
                f"NO.{p_no} | {p_fl} {p_lc} {p_mb} [{p_tp}] (폭:{p_w}mm,"
                f" 길이:{p_l}m)"
            )
  else:
    st.info("등록된 현장 사진이 없습니다.")
