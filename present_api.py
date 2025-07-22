import streamlit as st
from openai import OpenAI
import json
from pptx import Presentation
import io
import pandas as pd
import fitz

# --- Начальная настройка ---
st.set_page_config(
    page_title="Эксперт по подготовке к защите",
    page_icon="🤖",
    layout="wide"
)

EXAMPLE_STORYTELLING_TEXT = """Добрый день, уважаемые коллеги, эксперты и партнёры.
... (сокращено для читаемости) ...
"""

@st.cache_resource
def get_openai_client():
    try:
        client = OpenAI(
            api_key=st.secrets["DEEPSEEK_API_KEY"],
            base_url="https://api.studio.nebius.ai/v1/"
        )
        return client
    except Exception as e:
        st.error(f"Ошибка при инициализации клиента API: {e}")
        return None

client = get_openai_client()

def extract_text_from_pptx(uploaded_file):
    try:
        pptx_buffer = io.BytesIO(uploaded_file.getvalue())
        prs = Presentation(pptx_buffer)
        text_runs = []
        for slide in prs.slides:
            for shape in slide.shapes:
                if not shape.has_text_frame:
                    continue
                for paragraph in shape.text_frame.paragraphs:
                    for run in paragraph.runs:
                        text_runs.append(run.text)
        return "\n".join(text_runs)
    except Exception as e:
        st.error(f"Ошибка при чтении файла презентации: {e}")
        return ""

def extract_text_from_pdf(uploaded_file):
    try:
        pdf_bytes = uploaded_file.getvalue()
        with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
            return "\n".join([page.get_text() for page in doc])
    except Exception as e:
        st.error(f"Ошибка при чтении PDF-файла: {e}")
        return ""

def get_analysis_from_deepseek(project_text: str, tone: str):
    if not client:
        return None

    storytelling_instruction = f"""
"storytelling_script": Объект со сценарием выступления (5–7 минут), оформленным в жанре {tone.lower()} сторителлинга, который можно произнести вслух перед жюри. Он должен быть логичным, убедительным, увлекательным и структурированным по трём блокам:

- "introduction": яркое вступление (≈1 минута), в котором раскрывается проблема, вызывается интерес и обозначается название проекта.
- "main_part": основная часть (≈3–5 минут), где раскрываются: зачем проект нужен, как он работает, в чём новизна, ход разработки и сравнение с аналогами.
- "conclusion": финал (≈1 минута), в котором подводятся итоги, озвучиваются планы и делается вдохновляющий акцент на значимость проекта для общества, природы или технологий.

Стиль речи — живой, современный, адресованный экспертам и партнёрам. Без клише, с примерами, риторическими вопросами, образами. Максимум конкретики, минимум абстракций.
"""

    prompt = f"""
Ты — опытный эксперт по оценке учебно-исследовательских и проектных работ школьников. Твоя задача — провести комплексный анализ проекта и вернуть результат в виде **валидного JSON-объекта** со следующими ключами:

1. "strengths": Список сильных сторон проекта (массив строк).
2. "weaknesses": Список слабых сторон и зон для улучшения с краткими рекомендациями (массив строк).
3. "fact_check": Проверка 3–5 ключевых утверждений. Каждый объект должен содержать "claim", "verdict" ('Истина', 'Ложь', 'Непроверяемо/Требует уточнения') и "explanation".
4. {storytelling_instruction.strip()}
5. "tricky_questions": Список из 5 каверзных вопросов (массив строк).

Материалы проекта:
{project_text}
"""

    try:
        response = client.chat.completions.create(
            model="deepseek-ai/DeepSeek-R1",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.6,
            top_p=0.9,
            max_tokens=2048,
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        st.error(f"Ошибка при вызове API DeepSeek: {e}")
        return None

# --- Интерфейс приложения ---
st.title("🤖 Эксперт по подготовке к защите")
st.markdown("Загрузите презентацию (`.pdf`, `.pptx`) и/или вставьте текст доклада, чтобы получить комплексную оценку и рекомендации.")

col1, col2 = st.columns(2)

with col1:
    uploaded_file = st.file_uploader("Загрузите презентацию (PDF или PPTX)", type=["pptx", "pdf"])

with col2:
    def load_example_text():
        st.session_state.report_text_input = EXAMPLE_STORYTELLING_TEXT

    if "report_text_input" not in st.session_state:
        st.session_state.report_text_input = ""

    report_text = st.text_area(
        "Вставьте текст доклада",
        height=218,
        placeholder="Здесь может быть ваш сценарий выступления...",
        key="report_text_input"
    )

    st.button("✍️ Вставить пример идеального текста", on_click=load_example_text, use_container_width=True)

tone = st.selectbox("🎭 Выберите стиль сценария выступления", ["Вдохновляющий", "Формальный", "Научно-популярный"], index=0)

if st.button("🚀 Провести экспертизу проекта", type="primary", use_container_width=True):
    project_text = ""
    if uploaded_file is not None:
        with st.spinner("Извлекаю текст из файла..."):
            file_name = uploaded_file.name.lower()
            if file_name.endswith('.pptx'):
                project_text = extract_text_from_pptx(uploaded_file)
            elif file_name.endswith('.pdf'):
                project_text = extract_text_from_pdf(uploaded_file)

    combined_text = (project_text + "\n\n" + report_text).strip()

    if not combined_text:
        st.warning("Пожалуйста, загрузите файл или введите текст для анализа.")
    else:
        with st.spinner("ИИ-эксперт изучает ваш проект... Это может занять до 2 минут."):
            analysis_result = get_analysis_from_deepseek(combined_text, tone)

        if analysis_result:
            st.success("Анализ завершен! Вот результаты:")

            col_strengths, col_weaknesses = st.columns(2)
            with col_strengths:
                st.subheader("👍 Сильные стороны")
                for s in analysis_result.get("strengths", []):
                    st.markdown(f"- {s}")

            with col_weaknesses:
                st.subheader("🤔 Слабые стороны")
                for w in analysis_result.get("weaknesses", []):
                    st.markdown(f"- {w}")

            st.divider()

            st.header("🔍 Проверка фактов")
            facts = analysis_result.get("fact_check", [])
            if facts:
                df = pd.DataFrame(facts)
                df.columns = ["Утверждение", "Вердикт", "Пояснение"]
                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.info("Факты не найдены или не были выделены.")

            st.divider()

            st.header("🎤 Сценарий выступления")
            script = analysis_result.get("storytelling_script", {})
            with st.expander("Показать сценарий", expanded=True):
                st.subheader("Вступление")
                st.markdown(script.get("introduction", "_Не сгенерировано_"))
                st.subheader("Основная часть")
                st.markdown(script.get("main_part", "_Не сгенерировано_"))
                st.subheader("Заключение")
                st.markdown(script.get("conclusion", "_Не сгенерировано_"))

            st.divider()

            st.header("🤔 Каверзные вопросы")
            for i, q in enumerate(analysis_result.get("tricky_questions", []), 1):
                st.markdown(f"**{i}.** {q}")
        else:
            st.error("Не удалось получить результат анализа. Проверьте текст или попробуйте позже.")
