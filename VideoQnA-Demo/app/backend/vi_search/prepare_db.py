import os
import json
from pathlib import Path
import time
from azure.storage.blob import BlobServiceClient, ContainerClient
from dotenv import load_dotenv

from vi_search.constants import BASE_DIR
from vi_search.language_models.azure_openai import OpenAI  # Import the OpenAI class
from vi_search.prep_scenes import get_sections_generator
from vi_search.prompt_content_db.prompt_content_db import PromptContentDB, VECTOR_FIELD_NAME
from vi_search.vi_client.video_indexer_client import init_video_indexer_client, VideoIndexerClient  # Ensure correct import

# Load environment variables from .env file
load_dotenv(BASE_DIR / ".env")

# Custom JSON encoder to handle Path objects
class CustomEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Path):
            return str(obj)
        return super().default(obj)  # Use default serialization for other types

# Function to index videos by uploading them to Azure Video Indexer
def index_videos(client: VideoIndexerClient, blobs, container_client, cache_file: Path, privacy: str = 'private', excluded_ai=None) -> dict[str, str]:
    start = time.time()
    videos_ids = {}

    # Load cached video IDs if available
    if cache_file.exists():
        with cache_file.open('r') as f:
            videos_ids = json.load(f)

    for blob in blobs:
        if blob.name in videos_ids:
            print(f"Video {blob.name} already processed with ID {videos_ids[blob.name]}. Skipping upload.")
            continue

        blob_client = container_client.get_blob_client(blob.name)
        video_url = blob_client.url
        print(f"Checking if video exists: {blob.name}")
        video_id = client.video_exists(blob.name)
        if video_id:
            print(f"Video {blob.name} already exists with ID {video_id}. Skipping upload.")
            videos_ids[blob.name] = video_id
        else:
            print(f"Uploading video: {video_url}")
            try:
                video_id = client.upload_url_async(video_name=blob.name, video_url=video_url, excluded_ai=excluded_ai, privacy=privacy)
                if video_id:
                    videos_ids[blob.name] = video_id
                    print(f"Uploaded video {blob.name} with ID {video_id}")
                else:
                    print(f"Failed to upload video {blob.name}")
            except Exception as e:
                print(f"Failed to upload video {blob.name}: {e}")

    # Save cached video IDs
    with cache_file.open('w') as f:
        json.dump(videos_ids, f, cls=CustomEncoder)

    print(f"Videos uploaded: {videos_ids}, took {time.time() - start} seconds")
    return videos_ids

# Function to wait for videos to be processed by Azure Video Indexer and save insights to Blob Storage
def wait_for_videos_processing_and_save_insights(client: VideoIndexerClient, videos_ids: dict[str, str], container_client, timeout: int = 600):
    for video_name, video_id in videos_ids.items():
        try:
            print(f"Checking if video {video_id} has finished indexing...")
            client.wait_for_index_async(video_id, timeout_sec=timeout)
            print(f"Retrieving insights for video {video_name} with ID {video_id}.")
            insights = client.get_video_async(video_id)
            insights_blob_client = container_client.get_blob_client(f"{video_name}_insights.json")
            insights_blob_client.upload_blob(json.dumps(insights), overwrite=True)
            print(f"Saved insights for video {video_name} with ID {video_id}")
        except Exception as e:
            print(f"Failed to process video {video_id} or save insights: {e}")

    print("Videos processing and insights saving completed")

# Function to print all environment variables
def print_env_variables():
    print("Environment variables:")
    for key, value in os.environ.items():
        print(f"{key}={value}")

# Main function to prepare the database
def prepare_db(db_name, language_models: OpenAI, prompt_content_db: PromptContentDB,  # Use the OpenAI class
               use_videos_ids_cache=True, video_ids_cache_file='videos_ids_cache.json', verbose=False,
               use_blob_storage=False, blob_sas_url=None, blob_container_name=None, dry_run=False):

    print("Starting prepare_db function")
    video_ids_cache_file = Path(video_ids_cache_file)

    # Load configuration from .env file
    print("Loading configuration from .env file")
    client = init_video_indexer_client(os.environ)

    # Print environment variables for debugging
    print_env_variables()
    print(f"USE_BLOB_STORAGE: {use_blob_storage}")
    print(f"AZURE_STORAGE_SAS_URL: {blob_sas_url}")
    print(f"AZURE_STORAGE_CONTAINER_NAME: {blob_container_name}")

    # Check if using Azure Blob Storage for videos
    if use_blob_storage and blob_sas_url and blob_container_name:
        print("Using Azure Blob Storage for videos and insights")
        container_client = ContainerClient.from_container_url(blob_sas_url)
        blobs = container_client.list_blobs()

        if dry_run:
            print("Dry run: Successfully connected to Azure Blob Storage and listed blobs.")
            for blob in blobs:
                print(f"Blob: {blob.name}")

            # Test connection to Azure Video Indexer
            try:
                print("Testing connection to Azure Video Indexer")
                account_details = client.get_account_details()
                print("Dry run: Successfully connected to Azure Video Indexer.")
                print("Listing videos in Azure Video Indexer:")
                videos = client.list_videos()
                for video in videos:
                    print(f"Video ID: {video['id']}, Name: {video['name']}")
            except Exception as e:
                print(f"Dry run: Failed to connect to Azure Video Indexer. Error: {e}")

            # Test connection to Azure OpenAI
            try:
                print("Testing connection to Azure OpenAI")
                language_models = OpenAI()  # Instantiate the OpenAI class
                embeddings_size = language_models.get_embeddings_size()
                print("Dry run: Successfully connected to Azure OpenAI.")
            except Exception as e:
                print(f"Dry run: Failed to connect to Azure OpenAI. Error: {e}")

            # Test connection to Azure AI Search
            try:
                print("Testing connection to Azure AI Search")
                prompt_content_db.create_db(db_name, vector_search_dimensions=embeddings_size)
                print("Dry run: Successfully connected to Azure AI Search.")
                print("Checking for content in Azure AI Search:")
                # Add logic to check for content in Azure AI Search
                # Example: List all documents in the Azure AI Search index
                documents = prompt_content_db.list_all_documents()
                for doc in documents:
                    print(f"Document ID: {doc['id']}, Content: {doc['content']}")
            except Exception as e:
                print(f"Dry run: Failed to connect to Azure AI Search. Error: {e}")

            return

        # Use cached video IDs if available
        if use_videos_ids_cache and video_ids_cache_file.exists():
            print(f"Using cached videos IDs from {video_ids_cache_file}")
            videos_ids = json.loads(video_ids_cache_file.read_text())
        else:
            # Index videos by uploading them to Azure Video Indexer
            print("Indexing videos by uploading them to Azure Video Indexer")
            videos_ids = index_videos(client, blobs, container_client, video_ids_cache_file, privacy='public')
            if use_videos_ids_cache:
                print(f"Saving videos IDs to {video_ids_cache_file}")
                video_ids_cache_file.write_text(json.dumps(videos_ids, cls=CustomEncoder))

        # Wait for videos to be processed and save insights
        print("Waiting for videos to be processed by Azure Video Indexer and saving insights")
        wait_for_videos_processing_and_save_insights(client, videos_ids, container_client, timeout=600)

        # Retry mechanism for generating prompt content
        print("Getting indexed videos prompt content")
        for video_id in videos_ids.values():
            retries = 5
            while retries > 0:
                try:
                    response = client.generate_prompt_content_async(video_id)
                    if response.status_code == 202:
                        print(f"Prompt content generation for video ID {video_id} is still in progress. Retrying...")
                        time.sleep(60)  # Wait for 60 seconds before retrying
                        retries -= 1
                    elif response.status_code == 409:
                        print(f"Prompt content generation for video ID {video_id} is already in progress. Retrying...")
                        time.sleep(60)  # Wait for 60 seconds before retrying
                        retries -= 1
                    else:
                        response.raise_for_status()
                        break
                except Exception as e:
                    print(f"Failed to generate prompt content for video ID {video_id}. Error: {e}")
                    retries -= 1

        try:
            videos_prompt_content = client.get_collection_prompt_content(list(videos_ids.values()))
        except Exception as e:
            print(f"Failed to get collection prompt content. Error: {e}")
            return

        # Prepare language models
        print("Preparing language models")
        embeddings_size = language_models.get_embeddings_size()

        # Generate sections of prompt content
        print("Generating sections of prompt content")
        account_details = client.get_account_details()
        print(f"Account details: {account_details}")  # Add debugging information
        sections_generator = get_sections_generator(videos_prompt_content, account_details, embedding_cb=language_models.get_text_embeddings,
                                                    embeddings_col_name=VECTOR_FIELD_NAME)

        # Create new database and add sections to it
        print("Creating new database and adding sections to it")
        prompt_content_db.create_db(db_name, vector_search_dimensions=embeddings_size)
        prompt_content_db.add_sections_to_db(sections_generator, upload_batch_size=100, verbose=verbose)

        print("Done adding sections to DB. Exiting...")

def main():
    '''
    Two options to run this script:
    1. Put your videos in the data directory and run the script.
    2. Create JSON file with the following structure:
           {"VIDEO_1_NAME": "VIDEO_1_ID",
            "VIDEO_2_NAME": "VIDEO_2_ID"}
       and run the script while calling `prepate_db()` with arguments:
            `use_videos_ids_cache=True`
            `video_ids_cache_file="path_to_json_file"`.

        Important note: If you choose ChromaDB as a your prompt content DB, you need to make sure the DB location which
                        is by default on local disk is accessible by the Azure Function App.
    '''
    print("This program will prepare a vector DB for LLM queries using the Video Indexer prompt content API")

    verbose = True
    dry_run = os.environ.get("DRY_RUN", "false").lower() == "true"
    print(f"Dry run mode: {dry_run}")

    # For UI parsing keep the name in the format: "vi-<your-name>-index"
    db_name = os.environ.get("PROMPT_CONTENT_DB_NAME", "vi-prompt-content-example-index")
    print(f"Database name: {db_name}")

    # Determine which prompt content DB to use
    search_db = os.environ.get("PROMPT_CONTENT_DB", "azure_search")
    print(f"Prompt content DB: {search_db}")
    if search_db == "chromadb":
        from vi_search.prompt_content_db.chroma_db import ChromaDB
        prompt_content_db = ChromaDB()
    elif search_db == "azure_search":
        from vi_search.prompt_content_db.azure_search import AzureVectorSearch
        prompt_content_db = AzureVectorSearch()

    # Check if using Azure Blob Storage for videos
    use_blob_storage = os.environ.get("USE_BLOB_STORAGE", "false").lower() == "true"
    print(f"Use blob storage: {use_blob_storage}")
    blob_sas_url = os.environ.get("AZURE_STORAGE_SAS_URL")
    blob_container_name = os.environ.get("AZURE_STORAGE_CONTAINER_NAME")
    print(f"Blob SAS URL: {blob_sas_url}")
    print(f"Blob container name: {blob_container_name}")

    # Initialize language models
    print("Initializing language models")
    language_models = OpenAI()  # Instantiate the OpenAI class

    # Prepare the database
    prepare_db(db_name, language_models, prompt_content_db, verbose=verbose,
               use_blob_storage=use_blob_storage, blob_sas_url=blob_sas_url, blob_container_name=blob_container_name, dry_run=dry_run)

if __name__ == "__main__":
    main()