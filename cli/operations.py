import configparser
import requests
import time
import os
import shutil
import pathlib
import json
import copy
from azure.storage.blob.blockblobservice import BlockBlobService
from azure.storage.file import ContentSettings

FUNCTIONS_SECTION = 'FUNCTIONS'
FUNCTIONS_KEY = 'FUNCTIONS_KEY'
FUNCTIONS_URL = 'FUNCTIONS_URL'

STORAGE_SECTION = 'STORAGE'
STORAGE_KEY = 'STORAGE_KEY'
STORAGE_ACCOUNT = 'STORAGE_ACCOUNT'
STORAGE_CONTAINER = 'STORAGE_CONTAINER'

TAGGING_SECTION = 'TAGGING'
TAGGING_LOCATION_KEY = 'TAGGING_LOCATION'
TAGGING_USER_KEY = 'TAGGING_USER'


DEFAULT_NUM_IMAGES = 40
LOWER_LIMIT = 0
UPPER_LIMIT = 100

CONFIG_PATH = os.environ.get('ALCONFIG', None)

azure_storage_client = None


class MissingConfigException(Exception):
    pass


class ImageLimitException(Exception):
    pass

#TODO: Verify the storage account is correct. Currently we get an unhelpful error message if you have a type in Storage Name
def get_azure_storage_client(config):
    # Todo: Move away from global client.
    global azure_storage_client

    if azure_storage_client is not None:
        return azure_storage_client

    azure_storage_client = BlockBlobService(
        config.get("storage_account"),
        account_key=config.get("storage_key")
    )

    return azure_storage_client

#TODO We should create the container if it does not exist
def onboard(config, folder_name):
    blob_storage = get_azure_storage_client(config)
    uri = 'https://' + config.get("storage_account") + '.blob.core.windows.net/' + config.get("storage_container") + '/'
    functions_url = config.get('url') + '/api/onboarding'
    user_name = config.get("tagging_user")
    images = []
    for image in os.listdir(folder_name):
        if image.lower().endswith('.png') or image.lower().endswith('.jpg') or image.lower().endswith('.jpeg') or image.lower().endswith('.gif'):
            local_path=os.path.join(folder_name, image)
            print('Uploading image ' + image)

            # Upload the created file, use image name for the blob name
            blob_storage.create_blob_from_path(config.get("storage_container"), image, local_path, content_settings=ContentSettings(content_type='image/png'))
            images.append(uri + image)
    
    # Post this data to the server to add them to database and kick off active learning
    data = {}
    data['imageUrls'] = images
    headers = {'content-type': 'application/json'}
    query = {
        "code": config.get('key'),
        "userName": user_name
    }

    #TODO: Ensure we don't get 4xx or 5xx return codes
    response = requests.post(functions_url, data=json.dumps(data), headers=headers, params=query)
    json_resp = response.json()
    count = len(json_resp['imageUrls'])
    print("Successfully uploaded " + str(count) + " images.")
    for url in json_resp['imageUrls']:
        print(url)


def _download_bounds(num_images):
    images_to_download = num_images

    if num_images is None:
        images_to_download = DEFAULT_NUM_IMAGES

    if images_to_download <= LOWER_LIMIT or images_to_download > UPPER_LIMIT:
        raise ImageLimitException()

    return images_to_download


def download(config, num_images, strategy=None):
    # TODO: better/more proper URI handling.
    functions_url = config.get("url") + "/api/download"
    user_name = config.get("tagging_user")
    images_to_download = _download_bounds(num_images)
    query = {
        "imageCount": images_to_download,
        "userName": user_name
    }

    response = requests.get(functions_url, params=query)
    response.raise_for_status()

    json_resp = response.json()
    count = len(json_resp['imageUrls'])

    print("Received " + str(count) + " files.")

    file_tree = pathlib.Path(os.path.expanduser(
        config.get("tagging_location"))
    )

    if file_tree.exists():
        print("Removing existing tag data directory: " + str(file_tree))

        shutil.rmtree(str(file_tree), ignore_errors=True)

    data_dir = pathlib.Path(file_tree / "data")
    data_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    local_images = download_images(config, data_dir, json_resp)
    count = len(local_images)
    print("Successfully downloaded " + str(count) + " images.")
    for image_path in local_images:
        print(image_path)
    print("Ready to tag!")


def download_images(config, image_dir, json_resp):
    print("Downloading files to " + str(image_dir))

    # Write generated VoTT data from the function to a file.
    write_vott_data(image_dir, json_resp)

    urls = json_resp['imageUrls']
    downloaded_file_paths = []
    for index in range(len(urls)):
        url = urls[index]

        file_name = url.split('/')[-1]

        #TODO: We will download an empty file if we get a permission error on the blob store URL
        # We should raise an exception. For now the blob store must be publically accessible 
        response = requests.get(url)
        file_path = pathlib.Path(image_dir / file_name)

        with open(str(file_path), "wb") as file:
            for chunk in response.iter_content(chunk_size=128):
                file.write(chunk)
            file.close()
        downloaded_file_paths.append(file_path)
    return downloaded_file_paths


def write_vott_data(image_dir, json_resp):
    data_file = pathlib.Path(image_dir / "data.json")
    # vott_data = json_resp.get("vott", None)
    vott_data = None

    if not vott_data:
        return

    try:
        vott_json = json.loads(vott_data)
    except ValueError as e:
        print("Corrupted VOTT data received.")
        return

    vott_json_with_fixed_paths = prepend_file_paths(image_dir, vott_json)

    with open(str(data_file), "wb") as file:
        vott_json_string = json.dumps(vott_json_with_fixed_paths)
        file.writelines(vott_json_string)
        file.close()


def prepend_file_paths(image_dir, vott_json):
    # Don't clobber the response.
    modified_json = copy.deepcopy(vott_json)
    frames = modified_json["frames"]

    # Replace the frame keys with the fully qualified path
    # for the image. Should look something like:
    # This is the /path/to/tagging_location/data/1.png in the end.
    for frame_key in frames.keys():
        new_key = str(pathlib.Path(image_dir / frame_key))
        frames[new_key] = frames.pop(frame_key)

    modified_json["frames"] = frames

    return modified_json


def upload(config):
    functions_url = config.get("url") + "/api/upload"
    user_name = config.get("tagging_user")
    tagging_location = pathlib.Path(
        os.path.expanduser(config.get("tagging_location"))
    )

    print("Uploading VOTT json file...")
    vott_json = pathlib.Path(tagging_location / "data.json")

    with open(str(vott_json)) as json_file:
        json_data = json.load(json_file)

    # Munge the vott json file.
    munged_json = trim_file_paths(json_data)

    query = {
        "userName": user_name
    }

    response = requests.post(functions_url, json=munged_json, params=query)
    response.raise_for_status()

    resp_json = response.json()
    print("Done!")


def trim_file_paths(json_data):
    modified_json = copy.deepcopy(json_data)

    munged_frames = modified_json["frames"]
    visited_frames = modified_json["visitedFrames"]

    for frame_key in munged_frames.keys():
        frame_name = pathlib.Path(frame_key).name
        munged_frames[frame_name] = munged_frames.pop(frame_key)

    munged_visited_frames = []
    for frame_path in visited_frames:
        #TODO: This line assumes that the visited frames name is a full path. 
        # Centralize this business logic in the codebase. It probably exists in shared code too
        munged_visited_frames.append(
            pathlib.Path(frame_path).name
        )

    modified_json["frames"] = munged_frames
    modified_json["visitedFrames"] = munged_visited_frames

    return modified_json


def read_config(config_path):
    if config_path is None:
        raise MissingConfigException()

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
    tagging_user_value = tagging_config_section.get(TAGGING_USER_KEY)

    if not tagging_location_value or not tagging_user_value:
        raise MissingConfigException()

    return tagging_location_value, tagging_user_value


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

    tagging_location, tagging_user = tagging_config_section(parser[TAGGING_SECTION])

    return {
        "key": functions_key,
        "url": functions_url,
        "storage_account": storage_account,
        "storage_key": storage_key,
        "storage_container": storage_container,
        "tagging_location": tagging_location,
        "tagging_user": tagging_user
    }
