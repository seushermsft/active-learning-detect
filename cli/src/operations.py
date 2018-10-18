import configparser
import requests
import time
import os
import uuid
import shutil
from azure.storage.blob import BlockBlobService

FUNCTIONS_SECTION = 'FUNCTIONS'
FUNCTIONS_KEY = 'FUNCTIONS_KEY'
FUNCTIONS_URL = 'FUNCTIONS_URL'

STORAGE_SECTION = 'STORAGE'
STORAGE_KEY = 'STORAGE_KEY'
STORAGE_ACCOUNT = 'STORAGE_ACCOUNT'
STORAGE_CONTAINER = 'STORAGE_CONTAINER'

TAGGING_SECTION = 'TAGGING'
TAGGING_LOCATION_KEY = 'TAGGING_LOCATION'


DEFAULT_NUM_IMAGES = 40
LOWER_LIMIT = 0
UPPER_LIMIT = 100

CONFIG_PATH = "./config.ini"

azure_storage_client = None


class MissingConfigException(Exception):
    pass


class ImageLimitException(Exception):
    pass


def get_azure_storage_client(config):
    global azure_storage_client

    if azure_storage_client is not None:
        return azure_storage_client

    azure_storage_client = BlockBlobService(
        config.get("storage_account"),
        account_key=config.get("storage_key")
    )

    return azure_storage_client


def _download_bounds(num_images):
    images_to_download = num_images

    if num_images is None:
        images_to_download = DEFAULT_NUM_IMAGES

    if images_to_download <= LOWER_LIMIT or images_to_download > UPPER_LIMIT:
        raise ImageLimitException()

    return images_to_download


def download(config, num_images, strategy=None):
    images_to_download = _download_bounds(num_images)
    functions_url = config.get("url")

    query = {
        "imageCount": num_images
    }

    response = requests.get(functions_url, params=query)
    response.raise_for_status()

    json_resp = response.json()

    print("Received " + str(json_resp["count"]) + " files.")

    file_tree = "./test/"

    if os.path.exists(file_tree):
        shutil.rmtree(file_tree, ignore_errors=True)
        os.mkdir(file_tree)

    download_images(file_tree, json_resp['urls'])

    print("Downloaded files. Ready to tag!")

    return images_to_download


def download_images(file_dir, urls):
    dummy = urls[0]

    for index in range(len(urls)):
        url = urls[index]
        response = requests.get(dummy)

        with open(file_dir + "test" + str(index) + ".jpg", "wb") as file:
            for chunk in response.iter_content(chunk_size=128):
                file.write(chunk)
            file.close()


def upload(config):
    storage_container = config.get("storage_container")
    storage_client = get_azure_storage_client(config)

    print("Uploading VOTT json file…")

    path_to_file = os.path.abspath("./images/vott.json")

    storage_client.create_blob_from_path(
        storage_container,
        str(uuid.uuid4()) + "_vott.json",
        path_to_file
    )

    print("Done!")


def read_config(config_path):
    parser = configparser.ConfigParser()
    parser.read(config_path)
    return read_config_with_parsed_config(parser)


def functions_config_section(functions_config_section):
    functions_key_value = functions_config_section.get(FUNCTIONS_KEY)
    functions_url_value = functions_config_section.get(FUNCTIONS_URL)

    if not functions_key_value or not functions_url_value:
        raise MissingConfigException()

    return functions_key_value, functions_url_value


def storage_config_section(storage_config_section):
    storage_account_value = storage_config_section.get(STORAGE_ACCOUNT)
    storage_key_value = storage_config_section.get(STORAGE_KEY)
    storage_container_value = storage_config_section.get(STORAGE_CONTAINER)

    if not storage_account_value or not storage_key_value or not storage_container_value:
        raise MissingConfigException()

    return storage_account_value, storage_key_value, storage_container_value


def tagging_config_section(tagging_config_section):
    tagging_location_value = tagging_config_section.get(TAGGING_LOCATION_KEY)

    if not tagging_location_value:
        raise MissingConfigException()

    return tagging_location_value


def read_config_with_parsed_config(parser):
    sections = parser.sections()

    if FUNCTIONS_SECTION not in sections:
        raise MissingConfigException()

    if STORAGE_SECTION not in sections:
        raise MissingConfigException()

    if TAGGING_SECTION not in sections:
        raise MissingConfigException()

    functions_key, functions_url = functions_config_section(
        parser[FUNCTIONS_SECTION]
    )

    storage_account, storage_key, storage_container = storage_config_section(
        parser[STORAGE_SECTION]
    )

    tagging_location = tagging_config_section(parser[TAGGING_SECTION])

    return {
        "key": functions_key,
        "url": functions_url,
        "storage_account": storage_account,
        "storage_key": storage_key,
        "storage_container": storage_container,
        "tagging_location": tagging_location
    }
