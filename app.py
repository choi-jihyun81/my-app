import io
import pandas as pd
from PIL import Image
import streamlit as st
from streamlit_drawable_canvas import st_canvas

# 페이지 설정을 넓게 하여 도면이 잘 보이도록 함
st.set_page_config(
    page_title="스마트 건축안전 현장 조사 앱", page_icon="🏗️", layout="wide"
)

st.title("🏗️ 스마트 건축안전 현장 조사 시스템")
st.write(
    "1단계: 층별 도면 업로드 ➔ 2단계: 도면 위 손상 위치 터치(클릭) ➔ 3단계:"
    " 상세 정보 입력"
)

# 세션 상태 초기화 (데이터 누적용)
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
  # 도면 이미지 열기
  img = Image.open(floor_plan_file)
  img_width, img_height = img.size

  st.info(
      f"💡 **[{floor_name}] 도면이 준비되었습니다.** 아래 도면 위에서 균열이나"
      " 손상이 있는 위치를 **마우스나 손가락으로 콕 찍어주세요.**"
  )

  # 화면에 맞게 캔버스 크기 조절 (너비 700 기준 비율 유지)
  canvas_width = 700
  canvas_height = int(img_height * (canvas_width / img_width))

  # 도면 마킹 캔버스 실행
  canvas_result = st_canvas(
      fill_color="rgba(255, 0, 0, 0.4)",  # 반투명 빨간색 점
      stroke_width=2,
      stroke_color="#FF0000",
      background_image=img,
      update_streamlit=True,
      height=canvas_height,
      width=canvas_width,
      drawing_mode="point",  # 점 찍기 모드
      key=f"canvas_{floor_name}",
  )

  # --- [2단계 & 3단계] 도면을 찍었을 때만 정보 입력 폼 활성화 ---
  if canvas_result.json_data is not None:
    objects = canvas_result.json_data["objects"]

    if objects:
      # 가장 최근에 찍은 좌표 가져오기
      last_obj = objects[-1]
      cx, cy = int(last_obj["left"]), int(last_obj["top"])

      st.success(
          f"📍 도면 좌표 지정됨 (X: {cx}, Y: {cy}) ➔ 아래에 손상 정보를"
          " 입력하세요."
      )

      with st.form(
          key=f"damage_form_{len(st.session_state.inspection_data)}",
          clear_on_submit=True,
      ):
        st.subheader("📝 손상 상세 정보 입력")

        c1, c2, c3 = st.columns(3)
        with c1:
          location = st.selectbox(
              "위치", ["계단실", "복도", "외벽", "실내 벽체", "천장"]
          )
          member = st.selectbox("부재", ["벽체", "천장", "기둥", "보", "바닥"])
        with c2:
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
          cause = st.selectbox(
              "발생원인", ["우수유입등", "응력집중등", "구조거동등", "건조수축등"]
          )
        with c3:
          crack_width = st.text_input("균열 폭(mm)", "-")
          crack_length = st.text_input("균열 길이(m)", "-")
          ea = st.number_input("개수 (EA)", min_value=1, value=1)

        photo_file = st.file_uploader(
            "📷 현장 사진 업로드 (가로 사진)", type=["jpg", "png", "jpeg"]
        )

        submitted = st.form_submit_button("✅ 이 손상 정보 저장하기")

        if submitted:
          # 사진 1024x768 자동 리사이징 처리
          processed_img = None
          if photo_file:
            p_img = Image.open(photo_file)
            processed_img = p_img.resize((1024, 768))

          # 데이터 저장 (층, 좌표, 입력값, 사진)
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
              "발생원인": cause,
              "사진": processed_img,
          }
          st.session_state.inspection_data.append(new_entry)
          st.rerun()  # 화면 새로고침하여 목록 반영

else:
  st.warning("⚠️ 먼저 조사를 시작할 층의 도면 이미지를 업로드해 주세요.")

# --- [결과 출력] 실시간 물량표 및 사진 대장 ---
if st.session_state.inspection_data:
  st.markdown("---")
  st.subheader("📋 실시간 자동 정렬된 손상 물량표")

  # 중간에 번호가 추가/삭제되어도 1, 2, 3... 순차 번호 자동 부여
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
          "발생원인",
          "X",
          "Y",
      ]
  ]
  st.dataframe(view_df, use_container_width=True)

  # 데이터 삭제 버튼 (실수로 잘못 찍었을 때)
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

  # 엑셀 다운로드
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

  # 사진 6분할 스타일 미리보기
  st.markdown("---")
  st.subheader("🖼️ 사진 대장 미리보기 (1024x768 규격)")
  photo_items = [
      (d["번호"], d["층"], d["위치"], d["부재"], d["사진"])
      for d in st.session_state.inspection_data
      if d["사진"] is not None
  ]

  if photo_items:
    for i in range(0, len(photo_items), 2):
      cols = st.columns(2)
      for j in range(2):
        if i + j < len(photo_items):
          p_no, p_fl, p_lc, p_mb, p_img = photo_items[i + j]
          with cols[j]:
            st.image(p_img, use_container_width=True)
            st.caption(f"NO.{p_no} | {p_fl} {p_lc} {p_mb}")
  else:
    st.info("등록된 현장 사진이 없습니다.")
