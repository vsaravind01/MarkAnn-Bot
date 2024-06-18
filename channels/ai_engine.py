import logging
from typing import Optional

from langchain_cohere import ChatCohere
from langchain_core.prompts import PromptTemplate

from channels import utils
from database.decorators import document_existence_check

logger = logging.getLogger(__name__)

PROMPT = """You are an AI assistant who Checks whether a given CONTENT mentions any of the following
1. Acquisition
2. Orders or contracts worth more than 50 Crores in Indian Rupees (INR) or equivalent in any other currency
3. New product launches
4. New partnerships or collaborations
5. Financial results
6. Other significant events with a suitable category name

If found any, reply exactly in the following json format and make sure keep the keys and values enclosed in double quotes:
{{
    "company": Name of the company
    "type": Type of the event with a suitable category name (acquisition, order, product launch, partnership, or other suitable category name)
    "value": Value of the acquisition or order in Crores (only if the type is an order or acquisition). If it is a product launch or partnership, value should be null.
    "description": Summary of the CONTENT provided
}}

CONTENT: {text}"""


class AIEngine:
    """AI Engine for summarizing text and PDF files.

    Attributes:
    -----------
    prompt_template: PromptTemplate
        Template for the prompt
    chain: LLMChain
        Language model chain
    channel: ann_channels.AnnChannel
        Channel for fetching data

    Methods:
    --------
    summarize_text(text: str) -> dict
        Summarizes the given text
    summarize_pdf(pdf_path: str) -> dict
        Summarizes the text extracted from the given PDF file or URL
    """

    def __init__(self, channel, db):
        self.prompt = PromptTemplate(
            template=PROMPT,
            input_variables=["text"],
        )
        self.llm = ChatCohere()
        self.chain = self.prompt | self.llm
        self.channel = channel
        self.db = db

    @document_existence_check
    def summarize_text(self, text: str) -> Optional[dict]:
        """Summarizes the given text.
        If the text is already present in the database, it returns None.

        Args:
        -----
        text: str
            Text to be summarized

        Returns:
        --------
        dict | None
            Summary of the text if the text is not present in the database, else None
        """
        response = self.chain.invoke({"text": text})
        logger.info("AI Engine - Summary Generated")
        return utils.extract_json_from_text(response.content)

    def summarize_pdf(self, pdf_path: str) -> Optional[dict]:
        """Summarizes the text extracted from the given PDF file.
        If the PDF file is a URL, the function fetches the text from the URL.
        If the text is already present in the database, the function returns None.

        Args:
        -----
        pdf_path: str
            Path to the PDF file

        Returns:
        --------
        dict
            Summary of the text extracted from the PDF file if the text is not present in the database, else None
        """
        is_url = False
        if pdf_path.startswith("http"):
            is_url = True

        if is_url:
            text = utils.fetch_pdf_text_from_url(pdf_path, self.channel.proxy_headers)
        else:
            text = utils.extract_pdf_text_from_file(pdf_path)

        logger.info(f"AI Engine - Text Extracted from PDF - file: {pdf_path}")

        return self.summarize_text(text)
