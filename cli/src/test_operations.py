import unittest

from operations import (
    download,
    upload,
    read_config_with_parsed_config,
    MissingConfigException,
    ImageLimitException,
    DEFAULT_NUM_IMAGES,
    LOWER_LIMIT,
    UPPER_LIMIT,
    CONFIG_SECTION,
    FUNCTIONS_KEY,
    FUNCTIONS_URL
)


class TestCLIOperations(unittest.TestCase):
    def test_download_under_limit(self):
        with self.assertRaises(ImageLimitException):
            download(LOWER_LIMIT)

    def test_download_over_limit(self):
        with self.assertRaises(ImageLimitException):
            download(UPPER_LIMIT + 1)

    def test_download_missing_image_count(self):
        downloaded_image_count = download(None)
        self.assertEqual(DEFAULT_NUM_IMAGES, downloaded_image_count)

    def test_download_with_image_count(self):
        downloaded_image_count = download(10)
        self.assertEqual(10, downloaded_image_count)

    def test_upload(self):
        with self.assertRaises(NotImplementedError):
            upload()


class TestConfig(unittest.TestCase):
    def test_missing_config_section(self):
        with self.assertRaises(MissingConfigException):
            read_config_with_parsed_config({})

    def test_missing_config_values(self):
        with self.assertRaises(MissingConfigException):
            read_config_with_parsed_config({
                CONFIG_SECTION: {}
            })

    def test_acceptable_config(self):
        read_config_with_parsed_config({
            CONFIG_SECTION: {
                FUNCTIONS_KEY: "test",
                FUNCTIONS_URL: "test"
            }
        })

if __name__ == '__main__':
    unittest.main()