import io
import pandas as pd
from PIL import Image, ImageDraw, ImageFont
import streamlit as st
from streamlit_drawable_canvas import st_canvas

st.set_page_config(page_title="스마트 건축안전 현장 조사 앱", layout="wide")

st.title("🏗️ 스마트 건축안전 현장 조사 앱 (도면 마킹 연동형)")
st.write(
    "층별 도면을 올리고, 도면 위를 터치하여 손상 위치를 지정하면 번호와 물량표가 자동으로 연동됩니다."
)

# 세션 상태 초기화
if "inspection_data" not in st.session_state:
  st.session_state.inspection_data = []

# 1. 층별 도면 업로드 섹션
st.subheader("🗺️ 1. 층별 도면 준비")
floor_name = st.selectbox(
    "조사할 층 선택", ["옥상층", "5층", "4층", "3층", "2층", "1층", "지하 1층"]
)
floor_plan_file = st.file_uploader(
    f"{floor_name} 도면 이미지 업로드 (JPG, PNG)",
    type=["jpg", "jpeg", "png"],
    key=floor_name,
)

if floor_plan_file is not None:
  image = Image.open(floor_plan_file)
  w, h = image.size

  st.info(
      "👇 아래 도면 위에서 손상이 발생한 위치를 마우스나 손가락으로"
      " 터치(클릭)하세요."
  )

  # 도면 위에 마킹을 하기 위한 캔버스 생성
  canvas_result = st_canvas(
      fill_color="rgba(255, 0, 0, 0.3)",
      stroke_width=3,
      stroke_color="#FF0000",
      background_image=image,
      update_streamlit=True,
      height=int(h * (700 / w)),  # 비율 유지 리사이징
      width=700,
      drawing_mode="point",  "점(포인트) 찍기 모드"
      key=f"canvas_{floor_name}",
  )

  # 캔버스에 찍힌 좌표(포인트)가 있다면 해당 위치에 대한 상세 정보 입력 폼 활성화
  if canvas_result.json_data is not None:
    objects = canvas_result.json_data["objects"]
    if objects:
      latest_point = objects[-1]  # 가장 최근에 찍은 위치
      px, py = latest_point["left"], latest_point["top"]

      st.markdown("---")
      st.subheader(
          f"📝 [방금 찍은 위치 ({int(px)}, {int(py)})] 손상 정보 입력"
      )

      with st.form(
          key=f"form_{len(st.session_state.inspection_data)}",
          clear_on_submit=True,
      ):
        col1, col2, col3 = st.columns(3)
        with col1:
          location = st.selectbox("위치", ["계단실", "복도", "외벽", "실내"])
          member = st.selectbox("부재", ["벽체", "천장", "기둥", "보"])
        with col2:
          damage_type = st.selectbox(
              "유형 및 형상",
              [
                  "도장들뜸",
                  "우각부균열",
                  "일반균열(사선)",
                  "일반균열(수직)",
                  "누수흔적",
                  "텍스오염",
              ],
          )
          cause = st.selectbox(
              "발생원인", ["우수유입등", "응력집중등", "구조거동등", "건조수축등"]
          )
        with col3:
          crack_width = st.text_input("균열 폭(mm)", "-")
          crack_length = st.text_input("균열 길이(m)", "-")
          ea = st.number_input("개수 (EA)", min_value=1, value=1)

        photo_file = st.file_uploader(
            "현장 사진 업로드", type=["jpg", "png"], key=f"p_{len(objects)}"
        )

        submitted = st.form_submit_button("✅ 이 위치에 손상 등록하기")

        if submitted:
          # 사진 리사이징 (1024x768)
          processed_img = None
          if photo_file:
            img_opened = Image.open(photo_file)
            processed_img = img_opened.resize((1024, 768))

          # 데이터 저장 (좌표 포함)
          new_item = {
              "층": floor_name,
              "X좌표": px,
              "Y좌표": py,
              "위치": location,
              "부재": member,
              "유형 및 형상": damage_type,
              "폭(mm)": crack_width,
              "길이(m)": crack_length,
              "개수": ea,
              "발생원인": cause,
              "사진": processed_img,
          }
          st.session_state.inspection_data.append(new_item)
          st.success("손상이 도면 좌표와 함께 등록되었습니다!")
          st.rerun()

# --- 2. 실시간 집계된 물량표 및 현황 ---
if st.session_state.inspection_data:
  st.markdown("---")
  st.subheader("📋 전체 손상물량표 (자동 순번 정렬)")

  df_list = []
  for idx, item in enumerate(st.session_state.inspection_data, start=1):
    row = item.copy()
    row["손상번호"] = f"({idx})"  # 중간에 추가해도 1부터 자동 정렬
    row["번호"] = idx
    df_list.append(row)

  df = pd.DataFrame(df_list)
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
      ]
  ]
  st.dataframe(view_df, use_container_width=True)

  # 엑셀 다운로드
  @st.cache_data
  def to_excel(df_to_save):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
      df_to_save.to_excel(writer, index=False, sheet_name="물량표")
    return output.getvalue()

  st.download_button(
      "📥 손상물량표 엑셀 다운로드", data=to_excel(view_df), file_name="물량표.xlsx"
  )
