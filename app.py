import io
import pandas as pd
import streamlit as st
from PIL import Image

# 페이지 설정 (모바일 화면에 최적화)
st.set_page_config(
    page_title="스마트 건축안전 점검 시스템", page_icon="🏗️", layout="centered"
)

st.title("🏗️ 스마트 건축안전 현장 조사 앱")
st.write(
    "현장에서 스마트폰으로 손상 정보를 입력하고 사진을 업로드하면, 번호가 자동으로 정렬되며 물량표와 사진대장 데이터가 생성됩니다."
)

# 세션 상태 초기화 (데이터를 임시로 기억하는 공간)
if "inspection_data" not in st.session_state:
  st.session_state.inspection_data = []

with st.form("inspection_form", clear_on_submit=True):
  st.subheader("📝 손상 정보 입력")

  col1, col2 = st.columns(2)
  with col1:
    floor = st.selectbox(
        "층 선택",
        ["옥상층", "5층", "4층", "3층", "2층", "1층", "지하 1층", "외부 부대시설"],
    )
    location = st.selectbox("위치", ["계단실", "복도", "외벽", "기타 실내"])
  with col2:
    member = st.selectbox("부재", ["벽체", "천장", "기둥", "보", "바닥"])
    damage_type = st.selectbox(
        "유형 및 형상",
        [
            "도장들뜸",
            "우각부균열",
            "일반균열(사선)",
            "일반균열(수직)",
            "일반균열(수평)",
            "누수흔적",
            "텍스오염",
        ],
    )

  col3, col4, col5 = st.columns(3)
  with col3:
    crack_width = st.text_input("균열 폭(mm)", "-")
  with col4:
    crack_length = st.text_input("균열 길이(m)", "-")
  with col5:
    ea = st.number_input("개수 (EA)", min_value=1, value=1)

  cause = st.selectbox(
      "발생원인", ["우수유입등", "응력집중등", "구조거동등", "건조수축등"]
  )

  # 사진 업로드 (모바일에서 카메라 촬영 또는 갤러리 선택 가능)
  uploaded_photo = st.file_uploader(
      "현장 사진 업로드 (가로 사진 권장)", type=["jpg", "jpeg", "png"]
  )

  submitted = st.form_submit_button("➕ 손상 항목 추가하기")

  if submitted:
    # 사진 처리 (1024x768 리사이징)
    processed_image = None
    if uploaded_photo is not None:
      image = Image.open(uploaded_photo)
      # 1024x768 비율로 리사이징 (원하시는 규격 적용)
      image = image.resize((1024, 768))
      processed_image = image

    # 데이터 저장
    new_item = {
        "층": floor,
        "위치": location,
        "부재": member,
        "유형 및 형상": damage_type,
        "폭(mm)": crack_width,
        "길이(m)": crack_length,
        "개수": ea,
        "발생원인": cause,
        "사진": processed_image,
    }
    st.session_state.inspection_data.append(new_item)
    st.success("손상 항목이 성공적으로 추가되었습니다!")

# --- 입력된 데이터 관리 및 자동 번호 부여 ---
if st.session_state.inspection_data:
  st.markdown("---")
  st.subheader("📋 실시간 조사 현황 및 물량표 미리보기")

  # 데이터프레임으로 변환하며 '손상 위치' 번호를 1부터 순서대로 자동 부여 (중간 삽입 문제 해결)
  df_list = []
  for idx, item in enumerate(st.session_state.inspection_data, start=1):
    row = item.copy()
    row["손상번호"] = f"①"  # 원문자 형태 또는 숫자 지정 가능
    row["번호"] = idx
    df_list.append(row)

  display_df = pd.DataFrame(df_list)

  # 화면 표시용 컬럼 정리
  view_df = display_df[
      [
          "번호",
          "층",
          "위치",
          "부재",
          "유형 및 형상",
          "폭(mm)",
          "길이(m)",
          "개수",
          "발생원인",
      ]
  ]
  st.dataframe(view_df, use_container_width=True)

  # 데이터 삭제 기능
  delete_idx = st.number_input(
      "삭제할 항목 번호 선택",
      min_value=0,
      max_value=len(st.session_state.inspection_data),
      step=1,
  )
  if st.button("선택한 항목 삭제"):
    if delete_idx > 0:
      st.session_state.inspection_data.pop(delete_idx - 1)
      st.rerun()

  st.markdown("---")
  st.subheader("📤 보고서 출력 및 다운로드")

  # 엑셀 다운로드 기능
  @st.cache_data
  def convert_df_to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
      df.to_excel(writer, index=False, sheet_name="손상물량표")
    return output.getvalue()

  excel_data = convert_df_to_excel(view_df)
  st.download_button(
      label="📥 손상물량표 엑셀(Excel) 다운로드",
      data=excel_data,
      file_name="손상물량표_결과.xlsx",
      mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  )

  # 사진 6분할 대장 레이아웃 미리보기 (페이지당 6개씩 배치)
  st.markdown("### 🖼️ 사진대장 미리보기 (6분할 레이아웃)")
  photos_to_show = [
      (item["번호"], item["층"], item["위치"], item["부재"], item["사진"])
      for item in st.session_state.inspection_data
      if item["사진"] is not None
  ]

  # 2열씩 3행 구조로 6개씩 끊어서 보여주기
  if photos_to_show:
    for i in range(0, len(photos_to_show), 2):
      cols = st.columns(2)
      for j in range(2):
        if i + j < len(photos_to_show):
          p_num, p_floor, p_loc, p_member, p_img = photos_to_show[i + j]
          with cols[j]:
            st.image(p_img, use_container_width=True)
            st.caption(
                f"NO.{p_num} | {p_floor} {p_loc} {p_member} (1024x768 조절됨)"
            )
  else:
    st.info("등록된 사진이 없습니다. 사진을 업로드해 주세요.")
