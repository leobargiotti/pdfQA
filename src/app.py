import sys
import os
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget,
                             QHBoxLayout, QPushButton, QTextEdit, QLabel,
                             QFileDialog, QProgressDialog, QComboBox, QListWidget, QDialog,
                             QDialogButtonBox, QVBoxLayout)
from PyQt6.QtCore import Qt
from utils import PDFProcessor, detect_language, get_conversational_chain


class CustomTextEdit(QTextEdit):
    def __init__(self, parent=None):
        """
        Initializes the CustomTextEdit widget with a parent widget.

        Args:
            parent (QWidget, optional): The parent widget. Defaults to None.
        """
        super().__init__(parent)
        self.parent = parent

    def keyPressEvent(self, event: QKeyEvent):
        """
        Overrides the keyPressEvent of the QTextEdit widget to intercept the Return key and
        ask if the user presses Return without holding down Shift.

        Args:
            event (QKeyEvent): The key event to be processed.
        """
        if event.key() == Qt.Key.Key_Return and not event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            if self.parent and hasattr(self.parent, 'ask_question'):
                self.parent.ask_question()
        else:
            super().keyPressEvent(event)


class HistoryDialog(QDialog):
    def __init__(self, conversation_history, parent=None):
        """
        Initializes the HistoryDialog widget with a parent widget and a list of conversation history.

        Args:
            conversation_history (list[str]): A list of strings containing the conversation history.
            parent (QWidget, optional): The parent widget. Defaults to None.
        """
        super().__init__(parent)
        self.setWindowTitle("Question History")
        self.setGeometry(100, 100, 600, 400)
        self.conversation_history = conversation_history
        self.init_ui()

    def init_ui(self):
        """
        Initializes the UI of the HistoryDialog widget.

        This method creates a QVBoxLayout and adds to it a QListWidget to display the
        conversation history, a QPushButton to clear the history, and a QDialogButtonBox
        with an Ok button to accept and close the dialog.

        Returns:
            None
        """
        layout = QVBoxLayout(self)

        self.history_list = QListWidget()
        self.update_history_list()

        self.clear_button = QPushButton("Clear History")
        self.clear_button.clicked.connect(self.clear_history)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        button_box.accepted.connect(self.accept)

        layout.addWidget(self.history_list)
        layout.addWidget(self.clear_button)
        layout.addWidget(button_box)

    def update_history_list(self):
        """
        Updates the history list widget with the current conversation history.

        This method clears the existing items in the history list and repopulates it
        with the questions stored in the conversation history. Each question is
        displayed as a list item prefixed with 'Q:'.

        Returns:
            None
        """
        self.history_list.clear()
        for question in self.conversation_history:
            self.history_list.addItem(f"Q: {question}")

    def clear_history(self):
        """
        Clears the conversation history and resets the history list widget.

        This method clears the current conversation history and updates the
        history list widget to reflect the change. It also truncates the
        question history file to zero length.

        Returns:
            None
        """
        self.conversation_history.clear()
        self.update_history_list()
        with open("../data/question_history.txt", "w") as file:
            file.write("")


class PDFChatApp(QMainWindow):
    def __init__(self):
        """
        Initializes the PDFChatApp instance.

        This method initializes the PDFChatApp instance by calling the superclass
        constructor, initializing the PDFProcessor instance, setting up the initial
        state of the application, loading the conversation history from the file,
        and initializing the UI.

        Returns:
            None
        """
        super().__init__()
        self.processor = PDFProcessor()
        self.pdf_files = []
        self.conversation_history = []
        self.load_history()
        self.init_ui()

    def init_ui(self):
        """
        Initializes the UI of the PDFChatApp instance.

        This method creates a main window with two panels: a left panel that contains
        a menu with buttons to upload, process, and clear the PDF index, and a right
        panel that contains a chat history display, an input field to ask questions,
        a language selection dropdown, and a send button to submit the question.

        Returns:
            None
        """
        self.setWindowTitle('Chat with PDF using Gemini')
        self.setGeometry(100, 100, 1200, 800)

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QHBoxLayout(main_widget)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_panel.setMaximumWidth(300)

        menu_label = QLabel("Menu:")
        menu_label.setStyleSheet("font-size: 18px; font-weight: bold;")

        self.processed_files_label = QLabel("Processed PDFs:")
        self.processed_files_list = QListWidget()
        self.update_processed_files_list()

        self.upload_button = QPushButton("Upload New PDF Files")
        self.process_button = QPushButton("Process New Files")
        self.process_button.setEnabled(False)
        self.clear_button = QPushButton("Clear Index")

        left_layout.addWidget(menu_label)
        left_layout.addWidget(self.processed_files_label)
        left_layout.addWidget(self.processed_files_list)
        left_layout.addWidget(self.upload_button)
        left_layout.addWidget(self.process_button)
        left_layout.addWidget(self.clear_button)
        left_layout.addStretch()

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        header_layout = QHBoxLayout()
        header_label = QLabel("Chat with PDF using Gemini💁")
        header_label.setStyleSheet("font-size: 24px; font-weight: bold;")

        self.clear_chat_button = QPushButton("↺")
        self.clear_chat_button.setFixedSize(30, 30)
        self.clear_chat_button.setToolTip("Clear chat")
        self.clear_chat_button.clicked.connect(self.clear_chat_history)

        self.show_history_button = QPushButton("🕒")
        self.show_history_button.setFixedSize(30, 30)
        self.show_history_button.setToolTip("Show question history")
        self.show_history_button.clicked.connect(self.show_history)

        header_layout.addWidget(header_label)
        header_layout.addStretch()
        header_layout.addWidget(self.show_history_button)
        header_layout.addWidget(self.clear_chat_button)

        self.chat_history = QTextEdit()
        self.chat_history.setReadOnly(True)

        input_layout = QHBoxLayout()
        self.question_input = CustomTextEdit(self)
        self.question_input.setMaximumHeight(50)
        self.send_button = QPushButton("Ask")

        self.send_button.setEnabled(len(self.processor.index_info["processed_files"]) > 0)

        input_layout.addWidget(self.question_input)
        input_layout.addWidget(self.send_button)

        language_layout = QHBoxLayout()
        language_label = QLabel("Response Language:")
        self.language_combo = QComboBox()
        self.language_combo.addItems(["Auto (Same as Question)", "English", "Italian", "Spanish", "French", "German"])
        language_layout.addWidget(language_label)
        language_layout.addWidget(self.language_combo)

        right_layout.addLayout(header_layout)
        right_layout.addWidget(self.chat_history)
        right_layout.addLayout(language_layout)
        right_layout.addLayout(input_layout)

        layout.addWidget(left_panel)
        layout.addWidget(right_panel)

        self.upload_button.clicked.connect(self.upload_pdfs)
        self.process_button.clicked.connect(self.process_pdfs)
        self.send_button.clicked.connect(self.ask_question)
        self.clear_button.clicked.connect(self.clear_index)

    def update_processed_files_list(self):
        """
        Updates the list of processed PDF files in the UI.

        This method clears the current items in the processed files list widget
        and repopulates it with the filenames of the PDFs that have been indexed.
        The filenames are extracted from the 'processed_files' information in the
        PDF processor's index.

        Returns:
            None
        """
        self.processed_files_list.clear()
        for file_info in self.processor.index_info["processed_files"]:
            self.processed_files_list.addItem(file_info["filename"])

    def upload_pdfs(self):
        """
        Opens a file dialog for selecting PDF files and stores the selected files in the instance variable `pdf_files`.

        This method is connected to the "Upload PDF Files" button in the UI. It opens a file dialog for selecting PDF files,
        removes any files that have already been processed from the selection, and stores the remaining files in the
        `pdf_files` instance variable. It also updates the chat history with a message indicating how many new files have
        been selected, and enables the "Process New Files" button if new files have been selected.

        Returns:
            None
        """
        files, _ = QFileDialog.getOpenFileNames(self, "Select PDF Files", "", "PDF Files (*.pdf)")
        if files:
            existing_filenames = [f["filename"] for f in self.processor.index_info["processed_files"]]

            self.pdf_files = [f for f in files if os.path.basename(f) not in existing_filenames]

            if not self.pdf_files:
                self.chat_history.append("All selected files have already been processed!")
                return

            self.process_button.setEnabled(True)
            self.chat_history.append(f"Selected {len(self.pdf_files)} new PDF files")

    def process_pdfs(self):
        """
        Processes the selected PDF files and stores their embeddings in a local FAISS index.

        If no PDF files have been selected, this method does nothing.

        Otherwise, it opens a progress dialog to show the progress of the processing, and
        attempts to process the selected PDF files using the `PDFProcessor` instance. After
        processing is complete, it updates the list of processed PDF files in the UI,
        enables the "Ask" button, and appends a success message to the chat history. It also
        resets the `pdf_files` instance variable to an empty list and disables the "Process New Files"
        button.

        If an error occurs during processing, it appends an error message to the chat history.
        In any case, it closes the progress dialog.

        Returns:
            None
        """
        if not self.pdf_files:
            return

        progress = QProgressDialog("Processing PDFs...", None, 0, 100, self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.show()

        try:
            progress.setValue(20)
            self.processor.process_pdfs(self.pdf_files)
            self.update_processed_files_list()
            progress.setValue(100)
            self.send_button.setEnabled(True)
            self.chat_history.append("Processing complete! You can now ask questions.")
            self.pdf_files = []
            self.process_button.setEnabled(False)

        except Exception as e:
            self.chat_history.append(f"Error during processing: {str(e)}")
        finally:
            progress.close()

    def ask_question(self):
        """
        Handles the process of asking a question and retrieving an answer.

        This method retrieves the question input from the user, detects its language,
        and searches for relevant document context using the FAISS vector store.
        It constructs a conversational chain with the previous conversation history
        and obtains a response from the Google Gemini model. The question and response
        are appended to the chat history and the question is saved to a history file.

        Returns:
            None

        Raises:
            Exception: If an error occurs during processing, it appends an error
            message to the chat history.
        """
        question = self.question_input.toPlainText().strip()
        if not question:
            return

        self.chat_history.append(f"\nQuestion: {question}")
        self.question_input.clear()

        # Save the question to the history file
        with open("../data/question_history.txt", "a") as file:
            file.write(f"{question}\n")

        self.question_history.append(question)

        try:
            question_language = detect_language(question)
            selected_language = self.language_combo.currentText()
            output_language = question_language if selected_language == "Auto (Same as Question)" else selected_language

            vector_store = self.processor.get_vector_store()
            docs = vector_store.similarity_search(question)

            conversation_context = ""
            if self.conversation_history:
                conversation_context = "\nPrevious conversation:\n"
                for prev_qa in self.conversation_history[-3:]:
                    conversation_context += f"Q: {prev_qa['question']}\nA: {prev_qa['answer']}\n"

            chain = get_conversational_chain(conversation_context)
            response = chain.invoke({
                "question": question,
                "context": docs,
                "question_language": question_language,
                "output_language": output_language
            })


            self.conversation_history.append({
                "question": question,
                "answer": response
            })

            response = response.replace("  ", " ").replace("*", "").replace("* ", "").replace("** ", "")


            self.chat_history.append(f"Response: {response}\n")

        except Exception as e:
            self.chat_history.append(f"Error: {str(e)}")

    def clear_index(self):
        """
        Clears the current FAISS index and updates the application state.

        This method calls the PDFProcessor's `clear_index` method to remove the
        existing FAISS vectorstore index. It then updates the list of processed
        files in the UI, disables the "Ask" button, and appends a message to the
        chat history indicating that the index has been cleared. In case of an
        error, an error message is appended to the chat history.

        Returns:
            None
        """
        try:
            self.processor.clear_index()
            self.update_processed_files_list()
            self.send_button.setEnabled(False)
            self.chat_history.append("Index cleared. You can upload and process new PDF files.")
        except Exception as e:
            self.chat_history.append(f"Error: {str(e)}")

    def clear_chat_history(self):
        """
        Clears the conversation history in the chat window.

        This method is connected to the "Clear" button in the chat window. It
        clears the list of questions and answers displayed in the chat window.

        Returns:
            None
        """
        self.chat_history.clear()
        self.conversation_history.clear()

    def show_history(self):
        """
        Opens a dialog displaying the conversation history.

        This method is connected to the "History" button in the chat window. It
        creates a HistoryDialog widget with the conversation history and displays
        it as a modal dialog. The user can then scroll through the conversation
        history and close the dialog when finished.

        Returns:
            None
    """
        dialog = HistoryDialog(self.question_history, self)
        dialog.exec()

    def load_history(self):
        """
        Loads the conversation history from a file.

        This method reads from a file named "question_history.txt" in the data directory
        and populates the `question_history` attribute with the loaded questions.

        Returns:
            None
        """
        if os.path.exists("../data/question_history.txt"):
            with open("../data/question_history.txt", "r") as file:
                self.question_history = [line.strip() for line in file.readlines()]



def main():
    """
    Starts the application's main event loop.

    This function creates a :py:class:`QApplication` instance and a
    :py:class:`PDFChatApp` window, shows the window, and starts the application's
    main event loop with :py:meth:`QApplication.exec()`. The application will exit
    when the window is closed.

    Returns:
        int: The exit status of the application.
    """
    app = QApplication(sys.argv)
    window = PDFChatApp()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()