import os
import json
import shutil
from PyPDF2 import PdfReader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.prompts import PromptTemplate
from dotenv import load_dotenv


def get_text_chunks(text):
    """
    Splits the given text into chunks of text.

    This function uses the RecursiveCharacterTextSplitter to split the given text into
    chunks of size 10000 with an overlap of 1000.  The resulting chunks are returned as a list.

    Args:
        text (str): The text to be split.

    Returns:
        list[str]: A list of text chunks.
    """
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=10000, chunk_overlap=1000)
    chunks = text_splitter.split_text(text)
    return chunks


def get_conversational_chain(conversation_context):
    """
    Creates a conversational chain using the given context and the Google Gemini model.

    This function generates a conversational chain that takes into account both the document
    context and the previous conversation history. It uses the Google Gemini model to generate
    responses that are relevant to the given context and previous conversation history.

    Args:
        conversation_context (str): The context of the conversation that should be used to
            generate the response.

    Returns:
        langchain.chains.CombinedChain: The conversational chain that takes into account both the
            document context and the previous conversation history.
    """
    prompt_template = f"""
    Context from documents:\n {{context}}

    {conversation_context}

    Question (in {{question_language}}):\n {{question}}

    Please understand both the document context and the previous conversation history.
    Provide your answer in {{output_language}}, taking into account both the document content
    and any relevant information from the previous conversation.
    If there are any references to previous questions or answers, make sure to maintain consistency.

    Answer:
    """

    model = ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0.3, google_api_key=os.getenv("API_KEY"))
    prompt = PromptTemplate(
        template=prompt_template,
        input_variables=["context", "question", "question_language", "output_language"]
    )
    chain = create_stuff_documents_chain(llm=model, prompt=prompt)
    return chain


def detect_language(text):
    """
    Detects the language of the given text.

    This function uses the Google Gemini model to identify the language of the
    provided text. It sends a query to the model asking for the language name
    and returns the response as a string.

    Args:
        text (str): The text whose language needs to be detected.

    Returns:
        str: The name of the language detected by the model.
    """
    model = ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0, google_api_key=os.getenv("API_KEY"))
    response = model.invoke(f"What language is this text in? Reply with just the language name: {text}")
    return response.content.strip()


def get_pdf_text(pdf_files):
    """
    Extracts the text from the given PDF files.

    This function reads the given PDF files, extracts the text from each page of
    each file, and returns the concatenated text.

    Args:
        pdf_files (list[str]): A list of paths to PDF files.

    returns:
    str: The extracted text.
    """
    text = ""
    for pdf_path in pdf_files:
        with open(pdf_path, 'rb') as file:
            pdf_reader = PdfReader(file)
            for page in pdf_reader.pages:
                text += page.extract_text()
    return text


class PDFProcessor:
    def __init__(self, data_dir="../data"):
        """
        Initialize the PDFProcessor with a specified data directory.

        This constructor sets up the environment by changing the working directory
        to the location of the script and loading environment variables from a .env file.
        It initializes the data directory and index information file path, and loads
        previously processed PDF information.

        Args:
            data_dir (str): The directory where data files are stored. Defaults to "../data".
        """
        os.chdir(os.path.dirname(os.path.abspath(__file__)))
        load_dotenv(dotenv_path="../.env")
        self.data_dir = data_dir
        self.index_info_file = os.path.join(self.data_dir, "index_info.json")
        self.load_index_info()

    def load_index_info(self):
        """
        Loads the index information from the index info file.

        If the index info file does not exist, it initializes the index information
        as an empty dictionary with a single key, "processed_files", which is an
        empty list.

        Returns:
            dict: The loaded index information.
        """
        if os.path.exists(self.index_info_file):
            with open(self.index_info_file, 'r') as f:
                self.index_info = json.load(f)
        else:
            self.index_info = {"processed_files": []}

    def save_index_info(self):
        """
        Saves the index information to the index info file.

        This function saves the current index information, which is a dictionary
        containing the list of processed PDF files, to the index info file.

        Returns:
            None
        """
        with open(self.index_info_file, 'w') as f:
            json.dump(self.index_info, f)

    def process_pdfs(self, pdf_files):
        """
        Processes the given PDF files and stores the embeddings in a local FAISS index.

        This function reads the given PDF files, extracts the text from each page of
        each file, splits the text into chunks of size 10000 with an overlap of 1000,
        computes the embeddings for each chunk using the Google Generative AI Embeddings
        model, and stores the embeddings in a local FAISS index.

        If the index already exists and the given PDF files have not already been
        processed, the embeddings are added to the existing index.  Otherwise, a new
        index is created and saved to the local directory.

        Args:
            pdf_files (list[str]): A list of paths to PDF files.
        """
        raw_text = get_pdf_text(pdf_files)
        text_chunks = get_text_chunks(raw_text)

        embeddings = GoogleGenerativeAIEmbeddings(
            model="models/embedding-001",
            google_api_key=os.getenv("API_KEY")
        )

        index_path = os.path.join(self.data_dir, "faiss_index")

        if os.path.exists(index_path) and self.index_info["processed_files"]:
            vector_store = FAISS.load_local(index_path, embeddings, allow_dangerous_deserialization=True)
            vector_store.add_texts(text_chunks)
        else:
            vector_store = FAISS.from_texts(text_chunks, embedding=embeddings)

        vector_store.save_local(index_path)

        for pdf_path in pdf_files:
            self.index_info["processed_files"].append({
                "filename": os.path.basename(pdf_path)
            })
        self.save_index_info()

    def clear_index(self):
        """
        Clears the local FAISS index and resets the index information.

        This function deletes the local FAISS index directory and resets the index
        information to an empty list.  It is used to clear the existing index when
        the user wants to upload and process a new set of PDF files.

        Returns:
            None
        """
        try:
            index_path = os.path.join(self.data_dir, "faiss_index")
            if os.path.exists(index_path):
                shutil.rmtree(index_path)
            self.index_info["processed_files"] = []
            self.save_index_info()
        except Exception as e:
            raise e


    def get_vector_store(self):
        """
        Loads the local FAISS vector store with embeddings.

        This function initializes the Google Generative AI Embeddings model using the
        API key from the environment variables. It then loads the local FAISS vector
        store from the specified data directory, using the embeddings for deserialization.

        Returns:
            FAISS: The loaded FAISS vector store containing the document embeddings.

        Raises:
            Exception: If there is an issue loading the FAISS index.
        """
        embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001", google_api_key=os.getenv("API_KEY"))
        vector_store = FAISS.load_local(os.path.join(self.data_dir, "faiss_index"), embeddings, allow_dangerous_deserialization=True)
        return vector_store
