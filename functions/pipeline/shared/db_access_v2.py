# import sys
import string
# import os
# import time
import random
from enum import IntEnum, unique
import getpass
import itertools
from db_provider import DatabaseInfo, PostGresProvider

@unique
class ImageTagState(IntEnum):
    NOT_READY = 0
    READY_TO_TAG = 1
    TAG_IN_PROGRESS = 2
    COMPLETED_TAG = 3
    INCOMPLETE_TAG = 4
    ABANDONED = 5

# An entity class for a VOTT image
class ImageInfo(object):
    def __init__(self, image_name, image_location, height, width):
        self.image_name = image_name
        self.image_location = image_location
        self.height = height
        self.width = width

class ImageTag(object):
    def __init__(self, image_id, x_min, x_max, y_min, y_max, classification_names):
            self.image_id = image_id
            self.x_min = x_min
            self.x_max = x_max
            self.y_min = y_min
            self.y_max = y_max
            self.classification_names = classification_names

class ImageTagDataAccess(object):
    def __init__(self,  db_provider):
        self._db_provider = db_provider

    def test_connection(self):
        conn = self._db_provider.get_connection()
        cursor = conn.cursor()
        cursor.execute('select * from tagstate')
        row = cursor.fetchone()
        print()
        while row:
            print(str(row[0]) + " " + str(row[1]))
            row = cursor.fetchone()

    def create_user(self,user_name):
        user_id = -1
        if not user_name:
            raise ArgumentException("Parameter cannot be an empty string")
        try:
            with self._db_provider.get_connection() as conn:
                with conn.cursor() as cursor:
                    query = "INSERT INTO User_Info (UserName) VALUES (%s) ON CONFLICT (username) DO UPDATE SET username=EXCLUDED.username RETURNING UserId;"
                    cursor.execute(query,(user_name,))
                    user_id = cursor.fetchone()[0]
                    conn.commit()
        except Exception as e:
            print("An error occured creating a user: {0}".format(e))
            raise
        return user_id

    def get_new_images(self, number_of_images, user_id):
        if number_of_images <= 0:
            raise ArgumentException("Parameter must be greater than zero")

        selected_images_to_tag = {}
        try:
            with self._db_provider.get_connection() as conn:
                with conn.cursor() as cursor:
                    # TODO: Should we add TagStateId = INCOMPLETE_TAG also for fetching images?
                    query = ("SELECT b.ImageId, b.ImageLocation, a.TagStateId FROM Image_Tagging_State a "
                            "JOIN Image_Info b ON a.ImageId = b.ImageId WHERE a.TagStateId = 1 order by "
                            "a.createddtim DESC limit {0}")
                    cursor.execute(query.format(number_of_images))
                    for row in cursor:
                        print('Image Id: {0} \t\tImage Name: {1} \t\tTag State: {2}'.format(row[0], row[1], row[2]))
                        selected_images_to_tag[str(row[0])] = str(row[1])
                    self._update_images(selected_images_to_tag,ImageTagState.TAG_IN_PROGRESS, user_id, conn)
        except Exception as e:
            print("An errors occured getting images: {0}".format(e))
            raise
        return selected_images_to_tag.values()

    def add_new_images(self,list_of_image_infos, user_id):

        if type(user_id) is not int:
            raise TypeError('user id must be an integer')

        url_to_image_id_map = {}
        if(len(list_of_image_infos) > 0):
            try:
                with self._db_provider.get_connection() as conn:
                    with conn.cursor() as cursor:
                        for img in list(list_of_image_infos):
                            query = ("INSERT INTO Image_Info (OriginalImageName,ImageLocation,Height,Width,CreatedByUser) "
                                    "VALUES (%s,%s,%s,%s,%s) RETURNING ImageId;")
                            cursor.execute(query,(img.image_name,img.image_location,img.height,img.width,user_id))
                            new_img_id = cursor.fetchone()[0]
                            url_to_image_id_map[img.image_location] = new_img_id
                        conn.commit()
                        print("Inserted {0} images to the DB".format(len(url_to_image_id_map)))
            except Exception as e:
                print("An errors occured getting image ids: {0}".format(e))
                raise
        return url_to_image_id_map

    def update_incomplete_images(self, list_of_image_ids, user_id):
        #TODO: Make sure the image ids are in a TAG_IN_PROGRESS state
        self._update_images(list_of_image_ids,ImageTagState.INCOMPLETE_TAG,user_id, self._db_provider.get_connection())
        print("Updated {0} image(s) to the state {1}".format(len(list_of_image_ids),ImageTagState.INCOMPLETE_TAG.name))

    def update_completed_untagged_images(self,list_of_image_ids, user_id):
        #TODO: Make sure the image ids are in a TAG_IN_PROGRESS state
        self._update_images(list_of_image_ids,ImageTagState.COMPLETED_TAG,user_id, self._db_provider.get_connection())
        print("Updated {0} image(s) to the state {1}".format(len(list_of_image_ids),ImageTagState.COMPLETED_TAG.name))

    def _update_images(self, list_of_image_ids, new_image_tag_state, user_id, conn):
        if not isinstance(new_image_tag_state, ImageTagState):
            raise TypeError('new_image_tag_state must be an instance of Direction Enum')

        if type(user_id) is not int:
            raise TypeError('user id must be an integer')

        if not conn:
            conn = self._db_provider.get_connection()

        try:
            if(len(list_of_image_ids) > 0):
                with conn.cursor() as cursor:
                    image_ids_as_strings = [str(i) for i in list_of_image_ids]
                    images_to_update = '{0}'.format(', '.join(image_ids_as_strings))
                    # TODO: find another way to do string subsitution that doesn't break this query
                    query = "UPDATE Image_Tagging_State SET TagStateId = {0}, ModifiedByUser = {2}, ModifiedDtim = now() WHERE ImageId IN ({1})"
                    cursor.execute(query.format(new_image_tag_state,images_to_update,user_id))
                    conn.commit()
            else:
                print("No images to update")
        except Exception as e:
            print("An errors occured updating images: {0}".format(e))
            raise

    def update_image_urls(self,image_id_to_url_map, user_id):
        if type(user_id) is not int:
            raise TypeError('user id must be an integer')

        if(len(image_id_to_url_map.items())):
            try:
                with self._db_provider.get_connection() as conn:
                    with conn.cursor() as cursor:
                        for image_id, new_url in image_id_to_url_map.items():
                            cursor = conn.cursor()
                            query = "UPDATE Image_Info SET ImageLocation = '{0}', ModifiedDtim = now() WHERE ImageId = {1}"
                            cursor.execute(query.format(new_url,image_id))
                            conn.commit()
                            print("Updated ImageId: {0} to new ImageLocation: {1}".format(image_id,new_url))
                            self._update_images([image_id],ImageTagState.READY_TO_TAG, user_id,conn)
                            print("ImageId: {0} to has a new state: {1}".format(image_id,ImageTagState.READY_TO_TAG.name))
            except Exception as e:
                print("An errors occured updating image urls: {0}".format(e))
                raise
            finally: conn.close()

    #TODO: Do safer query string formatting
    def update_tagged_images(self,list_of_image_tags, user_id):
        if(not list_of_image_tags):
            return

        if type(user_id) is not int:
            raise TypeError('user id must be an integer')

        groups_by_image_id = itertools.groupby(list_of_image_tags, key=lambda it:it.image_id)
        try:
            with self._db_provider.get_connection() as conn:
                with conn.cursor() as cursor:
                    for img_id, list_of_tags in groups_by_image_id:
                        for img_tag in list(list_of_tags):
                            query = ("with iti AS ( "
                                    "INSERT INTO image_tags (ImageId, X_Min,X_Max,Y_Min,Y_Max,CreatedByUser) "
                                    "VALUES ({0}, {1},{2},{3},{4},{5}) "
                                    "RETURNING ImageTagId), "
                                    "ci AS ( "
                                        "INSERT INTO classification_info (ClassificationName) "
                                        "VALUES {6} "
                                        "ON CONFLICT (ClassificationName) DO UPDATE SET ClassificationName=EXCLUDED.ClassificationName "
                                        "RETURNING (SELECT iti.ImageTagId FROM iti), ClassificationId) "
                                    "INSERT INTO tags_classification (ImageTagId,ClassificationId) "
                                    "SELECT imagetagid,classificationid from ci;")
                            classifications = ", ".join("('{0}')".format(name) for name in img_tag.classification_names)
                            cursor.execute(query.format(img_tag.image_id,img_tag.x_min,img_tag.x_max,img_tag.y_min,img_tag.y_max,user_id,classifications))
                        self._update_images([img_id],ImageTagState.COMPLETED_TAG,user_id,conn)
                        conn.commit()
                    print("Updated {0} image tags".format(len(list_of_image_tags)))
        except Exception as e:
            print("An errors occured updating tagged image: {0}".format(e))
            raise

class ArgumentException(Exception):
    pass


def main():
    #################################################################
    # This main method is an example of how to use some of
    #  the ImageTagDataAccess methods. For instance:
    #   Creating a User
    #   Onboarding of new images
    #   Checking in images been tagged
    #################################################################

    #Replace me for testing
    db_config = DatabaseInfo("seusherpostgres.postgres.database.azure.com","seusher","seusher@seusherpostgres","P@ssword1234")
    data_access = ImageTagDataAccess(PostGresProvider(db_config))
    user_id = data_access.create_user(getpass.getuser())
    print("The user id for '{0}' is {1}".format(getpass.getuser(),user_id))

    list_of_image_infos = generate_test_image_infos(5)
    url_to_image_id_map = data_access.add_new_images(list_of_image_infos,user_id)

    image_tags = generate_test_image_tags(list(url_to_image_id_map.values()),4,4)
    data_access.update_tagged_images(image_tags,user_id)

TestClassifications = ("maine coon","german shephard","goldfinch","mackerel"," african elephant","rattlesnake")

def generate_test_image_infos(count):
    list_of_image_infos = []
    for i in range(count):
        file_name = "{0}.jpg".format(id_generator(size=random.randint(4,10)))
        image_location = "https://mock-storage.blob.core.windows.net/new-uploads/{0}".format(file_name)
        img = ImageInfo(file_name,image_location,random.randint(100,600),random.randint(100,600))
        list_of_image_infos.append(img)
    return list_of_image_infos

def generate_test_image_tags(list_of_image_ids,max_tags_per_image,max_classifications_per_tag):
    list_of_image_tags = []
    for image_id in list(list_of_image_ids):
        tags_per_image = random.randint(1,max_tags_per_image)
        for i in range(tags_per_image):
            x_min = random.uniform(50,300)
            x_max = random.uniform(x_min,300)
            y_min = random.uniform(50,300)
            y_max = random.uniform(y_min,300)
            classifications_per_tag = random.randint(1,max_classifications_per_tag)
            image_tag = ImageTag(image_id,x_min,x_max,y_min,y_max,random.sample(TestClassifications,classifications_per_tag))
            list_of_image_tags.append(image_tag)
    return list_of_image_tags

def id_generator(size=6, chars=string.ascii_uppercase + string.digits):
    return ''.join(random.choice(chars) for _ in range(size))

if __name__ == "__main__":
    main()
