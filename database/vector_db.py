import cohere
from qdrant_client import QdrantClient, models


class VectorDB:
    """Database for storing and retrieving vector data.
    The database uses Qdrant for storing and retrieving vector data and Cohere for generating embeddings.

    Attributes:
    -----------
    client: QdrantClient
        Qdrant client instance
    co: cohere.Client
        Cohere client instance

    Methods:
    --------
    create_collection(collection_name: str, size: int = 1024) -> None
        Creates a collection in the database
    insert_data(text: str, payload: dict, collection_name: str = "market_announcements", model: str = "embed-english-v3.0") -> str
        Inserts data into the database
    """

    def __init__(self, url: str, api_key: str):
        self.client = QdrantClient(url=url, api_key=api_key)
        self.co = cohere.Client()
        self.collection_name = None

    def __del__(self):
        """Closes the database connection."""
        self.client.close()

    def create_collection_if_not_exists(
        self, collection_name: str, vector_size: int = 1024
    ) -> bool:
        """Creates a collection in the database if it does not exist already and sets the collection_name attribute.
        If the collection already exists, sets the collection_name attribute and does nothing.

        Args:
        -----
        collection_name: str
            Name of the collection
        size: int
            Size of the vectors

        Returns:
        --------
        bool
            True if the collection was created, False if the collection already exists
        """
        if not self.client.collection_exists(collection_name):
            self.client.create_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(
                    size=vector_size,
                    distance=models.Distance.COSINE,
                ),
            )
            return True
        self.collection_name = collection_name
        return False

    def insert_data(
        self,
        text: str,
        payload: dict,
        collection_name: str = None,
        model: str = "embed-english-v3.0",
    ) -> str:
        """Generates embeddings for the text using Cohere, inserts the data into the database, and returns the point id.

        Args:
        -----
        text: str
            Text to insert into the database
        payload: dict
            Payload to insert into the database
        collection_name: str
            Name of the collection to insert the data into (default: None).
            If not provided, the collection_name attribute is used.
            If the collection_name attribute is not set, an error is raised.
        model: str
            Cohere model to use for generating embeddings (default: "embed-english-v3.0")

        Returns:
        --------
        Point ID: str
            Point id of the inserted data

        Raises:
        -------
        AssertionError
            If the collection_name is neither provided as an argument nor set as an attribute.
        """
        if collection_name is None:
            collection_name = self.collection_name
        assert (
            collection_name is not None
        ), "Collection name is not set. Please set the collection name using create_collection method. or pass it as an argument."

        embeddings = self.co.embed(
            texts=[text], model=model, input_type="search_document"
        )
        vector = embeddings.embeddings[0]
        pt_id = payload["id"]
        point = models.PointStruct(
            id=pt_id,
            vector=vector,
            payload=payload,
        )
        self.client.upsert(
            collection_name=collection_name,
            points=[point],
        )
        return pt_id

    def get_data_by_ids(
        self, ids: list[str], collection_name: str = None
    ) -> list[models.Record]:
        """Retrieves data from the database using the given ids.

        Args:
        -----
        ids: list[str]
            List of ids to retrieve from the database
        collection_name: str
            Name of the collection to retrieve the data from (default: None).
            If not provided, the collection_name attribute is used.
            If the collection_name attribute is not set, an error is raised.

        Returns:
        --------
        list[Record]
            List of records retrieved from the database
        """
        if collection_name is None:
            collection_name = self.collection_name
        assert (
            collection_name is not None
        ), "Collection name is not set. Please set the collection name using create_collection method. or pass it as an argument."
        return self.client.retrieve(collection_name=collection_name, ids=ids)

    def search(
        self, query: str, collection_name: str = None, top_k: int = 10
    ) -> list[models.ScoredPoint]:
        """Searches the database for the given query and returns the top k results.

        Args:
        -----
        query: str
            Query to search for
        collection_name: str
            Name of the collection to search in (default: None).
            If not provided, the collection_name attribute is used.
            If the collection_name attribute is not set, an error is raised.
        top_k: int
            Number of results to return (default: 10)

        Returns:
        --------
        list
            List of search results
        """
        if collection_name is None:
            collection_name = self.collection_name
        assert (
            collection_name is not None
        ), "Collection name is not set. Please set the collection name using create_collection method. or pass it as an argument."
        embeddings = self.co.embed(
            texts=[query], model="embed-english-v3.0", input_type="search_query"
        )
        vector = embeddings.embeddings[0]
        search_result = self.client.search(
            collection_name=collection_name,
            query_vector=vector,
            limit=top_k,
        )
        return search_result
