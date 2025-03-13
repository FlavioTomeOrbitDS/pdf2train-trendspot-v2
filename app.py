import streamlit as st
from google import genai
from google.genai import types
from google.cloud import storage
import base64
import pdf2image
import tempfile
from PIL import Image
import re
from dotenv import load_dotenv



#************************** SYSTEM INSTRUCTIONS *********************************
system_instructions_1 = """O usuário irá anexar um arquivo pdf de um relatório chamado trendspot.
Extraia as informações dos relatórios no seguinte formato:
Nome : Trendspot do dia "data que aparece no inicio do arquivo"
Categoria : "categoria que aparece logo abaixo da data", podendo ser "Beleza", "Alimentação" ou outro
Com Potencial de Crescimento: Os 2 primeiros quadros do relatório (Os que estão dentro da área com findo cinza escuro)
Em Destaque: Os demais quadros
Para Aproveitar Agora: última linha do relatório.

Observações:
Para cada quadro extraia o título e a descrição, além do tipo, que aparece na parte inferior do quadro ("Áudio", "Produto"...)
Para deixe uma linha com a informação "Link : Insira o link aqui"
Retorne somente o que está sendo pedido, nenhuma informação a mais.
Não retorne no formato MArkdown"""

#************************** FUNCTIONS ***************************************
def suggest_report_name(text, max_words=10):
    """
    Sugere um nome de relatório baseado nas primeiras palavras do texto gerado.
    
    - Remove caracteres especiais
    - Limita o nome a `max_words` palavras
    - Substitui espaços por underscores (_) para evitar erros no nome do arquivo

    Args:
        text (str): Texto do relatório
        max_words (int): Número máximo de palavras no nome do arquivo

    Returns:
        str: Nome sugerido do relatório
    """
    if not text.strip():
        return "relatorio_sem_nome"

    # Extrai as primeiras `max_words` palavras do texto
    words = text.split()[:max_words]
    clean_text = " ".join(words)

    # Remove caracteres especiais e mantém apenas letras, números e espaços
    clean_text = re.sub(r"[^a-zA-Z0-9\s]", "", clean_text)

    # Substitui espaços por underscores para evitar problemas no nome do arquivo
    clean_text = clean_text.replace(" ", "_")

    return clean_text[:50]  # Limita a 50 caracteres para evitar nomes muito longos


# Função para converter PDF para Base64
def pdf_to_base64(pdf_file):
    return base64.b64encode(pdf_file.read()).decode("utf-8")

def get_gemini_response(base64_document):
  client = genai.Client(
      vertexai=True,
      project="orbit-web-apps",
      location="us-central1",
  )  
    
  model = "gemini-2.0-flash-exp"
  
  document1 = types.Part.from_bytes(
      data=base64.b64decode(base64_document),
      mime_type="application/pdf",
  )
  
  
  contents = [
    types.Content(
      role="user",
      parts=[
        document1,
        types.Part.from_text("Avalie o documento anexado")
      ]
    )
  ]
  generate_content_config = types.GenerateContentConfig(
    temperature = 1,
    top_p = 0.95,
    max_output_tokens = 8192,
    response_modalities = ["TEXT"],
    safety_settings = [types.SafetySetting(
      category="HARM_CATEGORY_HATE_SPEECH",
      threshold="OFF"
    ),types.SafetySetting(
      category="HARM_CATEGORY_DANGEROUS_CONTENT",
      threshold="OFF"
    ),types.SafetySetting(
      category="HARM_CATEGORY_SEXUALLY_EXPLICIT",
      threshold="OFF"
    ),types.SafetySetting(
      category="HARM_CATEGORY_HARASSMENT",
      threshold="OFF"
    )],
    system_instruction=[types.Part.from_text(system_instructions_1)],
  )

#   for chunk in client.models.generate_content_stream(
#     model = model,
#     contents = contents,
#     config = generate_content_config,
#     ):
#     print(chunk, end="")

  for chunk in client.models.generate_content_stream(
        model=model,
        contents=contents,
        config=generate_content_config,
    ):
      if not chunk.candidates or not chunk.candidates[0].content.parts:
          continue
      yield chunk.text
      
      

# Função para salvar relatório no Google Cloud Storage
def save_report_to_gcs(bucket_name, file_name, report_content):
    project_id = "orbit-web-apps"  # Substitua pelo ID do seu projeto no Google Cloud

    storage_client = storage.Client(project_id)
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(file_name)
    blob.upload_from_string(report_content)
    return f"Relatório Salvo !!"


load_dotenv()


#************************** STREAMLIT APP ***************************************
st.set_page_config(layout="centered",
                   page_title="Orbit PDF2Train - TrendSpot",
                   page_icon = "https://firebasestorage.googleapis.com/v0/b/orbit-personas-1a705.firebasestorage.app/o/ORBIT%20-%20ICONE%205%20(1).png?alt=media&token=375bcfd7-0499-482b-a515-cce68dcd488c")


# Hiding the Streamlit status bar
hide_streamlit_style = """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    h1,h2,h3,h4{
        color:#4c4c4c;
    }
    
    [data-testid="stSidebar"] {
        background-color:#c3e2ff; /* Substitua pela cor desejada */
        color : #595353;
    }
    
    .st-emotion-cache-jkfxgf.e1nzilvr5 p {        
        font-size: 16px; /* Define o tamanho da fonte */
        font-weight: bold; /* Define a fonte como negrito */
    }
    
   button {
        background-color: #c3e2ff !important;
        box-shadow: 2px 4px 6px rgba(0, 0, 0, 0.2); /* Adiciona a sombra */
        border: none; /* Remove bordas (opcional) */
        border-radius: 4px; /* Bordas arredondadas (opcional) */
        transition: box-shadow 0.3s ease; /* Suaviza o efeito ao interagir */
        color: #127bb5 !important
    }

    button:hover {
        box-shadow: 4px 8px 12px rgba(0, 0, 0, 0.3); /* Sombra mais intensa ao passar o mouse */
        border: none; /* Remove bordas (opcional) */
    }
    
    .st-emotion-cache-1h9usn1{
        box-shadow: 2px 4px 6px rgba(0, 0, 0, 0.2); /* Adiciona a sombra */
        border: none; /* Remove bordas (opcional) */
        border-radius: 10px; /* Bordas arredondadas (opcional) */
        transition: box-shadow 0.3s ease; /* Suaviza o efeito ao interagir */
        
    }
    
    .st-emotion-cache-1h9usn1:hover{
        box-shadow: 4px 8px 12px rgba(0, 0, 0, 0.3); /* Sombra mais intensa ao passar o mouse */
        border: none; /* Remove bordas (opcional) */
    }
    
    textarea {
        box-shadow: 2px 4px 6px rgba(0, 0, 0, 0.2); /* Adiciona a sombra */
        border: none; /* Remove bordas (opcional) */
        border-radius: 10px; /* Bordas arredondadas (opcional) */
        transition: box-shadow 0.3s ease; /* Suaviza o efeito ao interagir */
        
    }
    
    </style>
    """

st.markdown(hide_streamlit_style, unsafe_allow_html=True)

if "response" not in st.session_state:
    st.session_state["response"] = ""

if "uploaded_file" not in st.session_state:
    st.session_state["uploaded_file"] = ""

# Interface do Streamlit
st.title("Orbit PDF2Train - Trendspot")
st.divider()

with st.sidebar:
    st.markdown(
                f"""
                <div style="text-align: center;">
                    <img src="https://firebasestorage.googleapis.com/v0/b/orbit-personas-1a705.firebasestorage.app/o/logo.png?alt=media&token=a98d1253-dadb-4fc0-a3a0-20391cad094b" width="150">
                </div>
                """,
                unsafe_allow_html=True,
            )        
    st.divider()
    

    uploaded_file = st.file_uploader("Faça o upload de um arquivo PDF", type=["pdf"])
    st.session_state["uploaded_file"] = uploaded_file

if uploaded_file is not None:
    # # Create a temporary file to store the PDF
    # with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_pdf:
    #     temp_pdf.write(uploaded_file.read())
    #     temp_pdf_path = temp_pdf.name

    # # Convert the first page of the PDF to an image
    # images = pdf2image.convert_from_path(temp_pdf_path, first_page=1, last_page=1)
    
    # if images:
    #     st.image(images[0], caption="PDF Thumbnail", use_column_width=True)
    if st.button("Gerar Relatório"):
        with st.spinner("Extraindo Dados. Aguarde...") :
                base64_value = pdf_to_base64(uploaded_file)
                st.session_state["response"] = ""
                                                
                placeholder = st.empty()
                                
                for chunk in get_gemini_response(base64_value):
                                st.session_state["response"] += chunk  # Acumula os dados recebidos
                                #placeholder.markdown(st.session_state["response"])  # Atualiza o placeholder com o conteúdo do stream
                
                #placeholder.markdown("")                                                
                
    
    if st.session_state["response"] != "":        
      
        st.markdown("### Relatório Gerado")
        edited_response = st.text_area("Edite o relatório antes de salvar:", 
                                        value=st.session_state["response"], 
                                        height=300)
        
        #st.markdown(st.session_state["response"])                
        # Exibir campo para inserir nome do relatório
        st.divider()
        suggested_name = suggest_report_name(st.session_state["response"])
        report_name = st.text_input("Nome do Relatório:", suggested_name)        
        if st.button("Salvar Relatório"):
            with st.spinner("Salvando Relatório. Aguarde...") :
                if report_name.strip():
                    bucket_name = "orbit-reports-repository"  # Substituir pelo nome real do bucket
                    file_name = f"trendspot/{report_name}.txt"
                    result = save_report_to_gcs(bucket_name, file_name, edited_response)
                    st.success(result)
                else:
                    st.error("O nome do relatório não pode estar em branco.")