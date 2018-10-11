import configparser

CONFIG_SECTION = 'FUNCTIONS'
FUNCTIONS_KEY = 'FUNCTIONS_KEY'
FUNCTIONS_URL = 'FUNCTIONS_URL'

DEFAULT_NUM_IMAGES = 40
LOWER_LIMIT = 0
UPPER_LIMIT = 100

CONFIG_PATH = "./config.ini"


class MissingConfigException(Exception):
    pass


class ImageLimitException(Exception):
    pass


def download(num_images):
    images_to_download = num_images

    if num_images is None:
        images_to_download = DEFAULT_NUM_IMAGES

    if images_to_download <= LOWER_LIMIT or images_to_download > UPPER_LIMIT:
        raise ImageLimitException()

    return images_to_download


def upload():
    raise NotImplementedError()


def read_config(config_path):
    parser = configparser.ConfigParser()
    parser.read(config_path)
    return read_config_with_parsed_config(parser)


def read_config_with_parsed_config(parser):
    functions_config_section = parser.get(CONFIG_SECTION)

    if functions_config_section is None:
        raise MissingConfigException()

    functions_key_value = functions_config_section.get(FUNCTIONS_KEY)
    functions_url_value = functions_config_section.get(FUNCTIONS_URL)

    if not functions_key_value or not functions_url_value:
        raise MissingConfigException()

    return {
        "key": functions_key_value,
        "url": functions_url_value
    }
