import streamlit as st
from google import genai
from google.genai import types
from google.cloud import storage
import base64
import pdf2image
import tempfile
import re
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Constants
PROJECT_ID = "orbit-web-apps"
LOCATION = "us-central1"
MODEL_NAME = "gemini-2.0-flash-exp"
BUCKET_NAME = "orbit-reports-repository"
REPORTS_FOLDER = "trendspot"

# System instructions for the AI model
SYSTEM_INSTRUCTIONS = """O usuário irá anexar um arquivo pdf de um relatório chamado trendspot.
Extraia as informações dos relatórios no seguinte formato:
Nome : Trendspot do dia "data que aparece no inicio do arquivo"
Categoria : "categoria que aparece logo abaixo da data", podendo ser "Beleza", "Alimentação" ou outro
Link do relatório : "link para o relatório no site do trendspot"
****************************************************************
Com Potencial de Crescimento: Os 2 primeiros quadros do relatório (Os que estão dentro da área com findo cinza escuro)
Em Destaque: Os demais quadros
Para Aproveitar Agora: Informações na área em cinza escuro na parte inferior do relatório.

Observações:
Para cada quadro extraia o título e a descrição, além do tipo, que aparece na parte inferior do quadro ("Áudio", "Produto"...)
Para deixe uma linha com a informação "Link : Insira o link aqui"
Retorne somente o que está sendo pedido, nenhuma informação a mais.
Não retorne no formato MArkdown
Separe cada informação com uma linha e com ***********************************************
"""

# CSS styles for the application
CUSTOM_CSS = """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    h1,h2,h3,h4{
        color:#4c4c4c;
    }
    
    [data-testid="stSidebar"] {
        background-color:#c3e2ff;
        color: #595353;
    }
    
    .st-emotion-cache-jkfxgf.e1nzilvr5 p {        
        font-size: 16px;
        font-weight: bold;
    }
    
   button {
        background-color: #c3e2ff !important;
        box-shadow: 2px 4px 6px rgba(0, 0, 0, 0.2);
        border: none;
        border-radius: 4px;
        transition: box-shadow 0.3s ease;
        color: #127bb5 !important
    }

    button:hover {
        box-shadow: 4px 8px 12px rgba(0, 0, 0, 0.3);
        border: none;
    }
    
    .st-emotion-cache-1h9usn1{
        box-shadow: 2px 4px 6px rgba(0, 0, 0, 0.2);
        border: none;
        border-radius: 10px;
        transition: box-shadow 0.3s ease;
    }
    
    .st-emotion-cache-1h9usn1:hover{
        box-shadow: 4px 8px 12px rgba(0, 0, 0, 0.3);
        border: none;
    }
    
    textarea {
        box-shadow: 2px 4px 6px rgba(0, 0, 0, 0.2);
        border: none;
        border-radius: 10px;
        transition: box-shadow 0.3s ease;
    }
    </style>
"""

class GeminiClient:
    """Client for interacting with Google's Gemini AI model."""
    
    def __init__(self, project_id, location):
        self.client = genai.Client(
            vertexai=True,
            project=project_id,
            location=location,
        )
    
    def get_safety_settings(self):
        """Define safety settings for the model."""
        return [
            types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="OFF"),
            types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="OFF"),
            types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="OFF"),
            types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="OFF")
        ]
    
    def process_pdf(self, base64_document, system_instructions):
        """Process a PDF document with Gemini AI model."""
        document = types.Part.from_bytes(
            data=base64.b64decode(base64_document),
            mime_type="application/pdf",
        )
        
        contents = [
            types.Content(
                role="user",
                parts=[
                    document,
                    types.Part.from_text("Avalie o documento anexado")
                ]
            )
        ]
        
        generate_content_config = types.GenerateContentConfig(
            temperature=1,
            top_p=0.95,
            max_output_tokens=8192,
            response_modalities=["TEXT"],
            safety_settings=self.get_safety_settings(),
            system_instruction=[types.Part.from_text(system_instructions)],
        )
        
        for chunk in self.client.models.generate_content_stream(
            model=MODEL_NAME,
            contents=contents,
            config=generate_content_config,
        ):
            if not chunk.candidates or not chunk.candidates[0].content.parts:
                continue
            yield chunk.text


class StorageManager:
    """Manager for Google Cloud Storage operations."""
    
    def __init__(self, project_id):
        self.storage_client = storage.Client(project_id)
    
    def save_report(self, bucket_name, file_path, report_content):
        """Save report content to Google Cloud Storage."""
        bucket = self.storage_client.bucket(bucket_name)
        blob = bucket.blob(file_path)
        blob.upload_from_string(report_content)
        return "Relatório Salvo !!"


class ReportNameGenerator:
    """Generator for report file names."""
    
    @staticmethod
    def suggest_name(text, max_words=10, max_length=50):
        """
        Suggest a report name based on the first words of the generated text.
        
        Args:
            text (str): Report text
            max_words (int): Maximum number of words to use
            max_length (int): Maximum length of the filename
            
        Returns:
            str: Suggested report name
        """
        if not text.strip():
            return "relatorio_sem_nome"

        # Extract the first `max_words` words from the text
        words = text.split()[:max_words]
        clean_text = " ".join(words)

        # Remove special characters, keep only letters, numbers and spaces
        clean_text = re.sub(r"[^a-zA-Z0-9\s]", "", clean_text)

        # Replace spaces with underscores to avoid filename issues
        clean_text = clean_text.replace(" ", "_")

        return clean_text[:max_length]


class PdfProcessor:
    """Processor for PDF files."""
    
    @staticmethod
    def to_base64(pdf_file):
        """Convert PDF file to base64 encoding."""
        return base64.b64encode(pdf_file.read()).decode("utf-8")
    
    @staticmethod
    def create_thumbnail(pdf_file):
        """Create a thumbnail image from the first page of a PDF."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_pdf:
            temp_pdf.write(pdf_file.getvalue())
            temp_pdf_path = temp_pdf.name

        # Convert the first page of the PDF to an image
        images = pdf2image.convert_from_path(temp_pdf_path, first_page=1, last_page=1)
        if images:
            return images[0]
        return None


class Pdf2TrainApp:
    """Main Streamlit application for Pdf2Train Trendspot."""
    
    def __init__(self):
        self.gemini_client = GeminiClient(PROJECT_ID, LOCATION)
        self.storage_manager = StorageManager(PROJECT_ID)
        self.initialize_session_state()
        self.setup_page_config()
        
    def initialize_session_state(self):
        """Initialize Streamlit session state variables."""
        if "response" not in st.session_state:
            st.session_state["response"] = ""
        if "uploaded_file" not in st.session_state:
            st.session_state["uploaded_file"] = None
            
    def setup_page_config(self):
        """Set up the page configuration."""
        st.set_page_config(
            layout="centered",
            page_title="Orbit PDF2Train - TrendSpot",
            page_icon="https://firebasestorage.googleapis.com/v0/b/orbit-personas-1a705.firebasestorage.app/o/ORBIT%20-%20ICONE%205%20(1).png?alt=media&token=375bcfd7-0499-482b-a515-cce68dcd488c"
        )
        st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
        
    def render_sidebar(self):
        """Render the sidebar UI."""
        with st.sidebar:
            st.markdown(
                """
                <div style="text-align: center;">
                    <img src="https://firebasestorage.googleapis.com/v0/b/orbit-personas-1a705.firebasestorage.app/o/logo.png?alt=media&token=a98d1253-dadb-4fc0-a3a0-20391cad094b" width="150">
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.divider()
            
            uploaded_file = st.file_uploader("Faça o upload de um arquivo PDF", type=["pdf"])
            st.session_state["uploaded_file"] = uploaded_file
            
            
    def process_pdf_document(self):
        """Process the uploaded PDF document."""
        
        with st.spinner("Extraindo Dados. Aguarde..."):
            uploaded_file = st.session_state["uploaded_file"]
            base64_pdf = PdfProcessor.to_base64(uploaded_file)
            st.session_state["response"] = ""
            
            placeholder = st.empty()
            
            for chunk in self.gemini_client.process_pdf(base64_pdf, SYSTEM_INSTRUCTIONS):
                st.session_state["response"] += chunk
                # Uncomment to show streaming updates:
                # placeholder.markdown(st.session_state["response"])
                
    def render_report_editor(self):
        """Render the report editor UI."""
        if st.session_state["response"] != "":
            st.markdown("### Relatório Gerado")
            edited_response = st.text_area(
                "Edite o relatório antes de salvar:", 
                value=st.session_state["response"], 
                height=300
            )
            
            st.divider()
            suggested_name = ReportNameGenerator.suggest_name(st.session_state["response"])
            report_name = st.text_input("Nome do Relatório:", suggested_name)
            
            if st.button("Salvar Relatório"):
                with st.spinner("Salvando Relatório. Aguarde..."):
                    if report_name.strip():
                        file_path = f"{REPORTS_FOLDER}/{report_name}.txt"
                        result = self.storage_manager.save_report(BUCKET_NAME, file_path, edited_response)
                        st.success(result)
                    else:
                        st.error("O nome do relatório não pode estar em branco.")
    
    def run(self):
        """Run the Streamlit application."""
        st.title("Orbit PDF2Train - Trendspot")
        st.divider()
        
        self.render_sidebar()
        
        if st.session_state["uploaded_file"] is not None:
            
            st.success("Arquivo PDF carregado com sucesso!")            
            #display_pdf(st.session_state["uploaded_file"])
            self.process_pdf_document()
            self.render_report_editor()



# Main entry point
if __name__ == "__main__":
    app = Pdf2TrainApp()
    print("Hello world")
    app.run()