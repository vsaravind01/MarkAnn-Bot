import logging
from datetime import datetime

import pandas as pd
import pytz
import requests

from channels import utils

logger = logging.getLogger(__name__)


class AnnChannel:
    proxy_headers = {}
    """Base class for all announcement channels.

    Attributes:
    -----------
    url_template: str
        URL template for fetching data
    proxy_headers: dict (default={})
        Headers to be sent with the request
    n_items: int (default=10)
        Number of items to be fetched
    frequency: int (default=1)
        Frequency of fetching data in minutes
    start_date: datetime (default=datetime.today())
        Start date for fetching data
    end_date: datetime (default=datetime.today())
        End date for fetching data
    kwargs: dict
        Additional arguments

    Methods:
    --------
    fetch() -> list
        Fetches data from the channel
    get_pdf_text(file_name: str) -> str
        Fetches text from the given PDF file
    """

    def __init__(
        self,
        url_template: str,
        n_items: int = 10,
        frequency: int = 1,
        start_date: datetime = datetime.today(),
        end_date: datetime = datetime.today(),
        **kwargs,
    ):
        self.url_template = url_template
        self.n_items = n_items
        self.frequency = frequency
        self.start_date = start_date.astimezone(
            tz=pytz.timezone("Asia/Kolkata")
        ).replace(tzinfo=None)
        self.end_date = end_date.astimezone(tz=pytz.timezone("Asia/Kolkata")).replace(
            tzinfo=None
        )
        self.kwargs = kwargs

    def fetch(self) -> list:
        raise NotImplementedError("fetch method is not implemented")

    def get_pdf_text(self, file_name: str) -> str:
        raise NotImplementedError("get_pdf_text method is not implemented")


class BseChannel(AnnChannel):
    """Class for fetching data from BSE.

    Attributes:
    -----------
    category: str
        Category of the announcement
    subcategory: str
        Subcategory of the announcement
    """

    subcategory_url = "https://api.bseindia.com/BseIndiaAPI/api/DDLSubCategoryData/w?categoryname={category}"
    attachment_url = (
        "https://www.bseindia.com/xml-data/corpfiling/AttachLive/{file_name}"
    )
    proxy_headers = {
        "Origin": "https://www.bseindia.com",
        "Referer": "https://www.bseindia.com/",
        "Accept": "application/json, text/plain, */*",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36",
    }
    available_categories = [
        "AGM/EGM",
        "Board Meeting",
        "Company Update",
        "Corp. Action",
        "Insider Trading / SAST",
        "New Listing",
        "Result",
        "Others",
    ]

    def __init__(self, category: str, subcategory: str, **kwargs):
        super().__init__(
            url_template="https://api.bseindia.com/BseIndiaAPI/api/AnnSubCategoryGetData/w?pageno=1&strCat={"
            "category}&strPrevDate={from_date}&strScrip=&strSearch=P&strToDate={"
            "to_date}&strType=C&subcategory={sub_category}",
            **kwargs,
        )
        assert (
            category in self.available_categories
        ), f"category should be one of {self.available_categories}"
        self.category = category
        self.subcategory = subcategory

    def fetch(self) -> list:
        # Fetch data from BSE

        url = self.url_template.format(
            category=self.category,
            sub_category=self.subcategory,
            from_date=self.start_date.strftime("%Y%m%d"),
            to_date=self.end_date.strftime("%Y%m%d"),
        )
        response = requests.get(url, headers=self.proxy_headers)
        data = response.json()["Table"]
        if not data:
            return []

        df = pd.DataFrame(data)
        df = df[
            [
                "NEWSID",
                "NEWSSUB",
                "NEWS_DT",
                "HEADLINE",
                "SLONGNAME",
                "NSURL",
                "ATTACHMENTNAME",
            ]
        ]

        df.rename(
            columns={
                "NEWSID": "id",
                "NEWSSUB": "subject",
                "NEWS_DT": "date",
                "HEADLINE": "headline",
                "SLONGNAME": "company",
                "NSURL": "url",
                "ATTACHMENTNAME": "attachment",
            },
            inplace=True,
        )

        logger.info(
            f"AnnChannel - BSE - Data Fetched - category: {self.category} - subcategory: {self.subcategory} - "
            f"from_date: {self.start_date} - to_date: {self.end_date} - n_items: {self.n_items} -"
            f" frequency: {self.frequency}"
        )

        return df.to_dict(orient="records")

    @classmethod
    def get_sub_categories(cls, category) -> list:
        """Fetches sub-categories for the given category.

        Args:
        -----
        category: str
            Category for which sub-categories are to be fetched

        Returns:
        --------
        list:
            list of sub-categories
        """
        url = cls.subcategory_url.format(category=category)
        response = requests.get(url, headers=cls.proxy_headers)
        data = response.json()["Table"]
        logger.info(f"AnnChannel - BSE - Subcategories Fetched - category: {category}")
        return [item["subcategory"] for item in data]

    def get_pdf_text(self, file_name: str) -> str:
        """Fetches text from the given PDF file from BSE.

        Args:
        -----
        file_name: str
            Name of the file

        Returns:
        --------
        str
            Text extracted from the PDF file
        """
        url = self.attachment_url.format(file_name=file_name)
        text = utils.fetch_pdf_text_from_url(url, headers=self.proxy_headers)
        logger.info(f"AnnChannel - BSE - PDF Text Extracted - file: {file_name}")
        return text
