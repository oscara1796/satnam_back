from rest_framework.test import APITestCase
from django.urls import reverse
from videos.models import Video, Category
from django.contrib.auth import get_user_model
from faker import Faker
from django.utils import timezone
from rest_framework import status

PASSWORD = 'pAssw0rd!'


def create_user(username='testuser', password=PASSWORD, active =False, email= 'user@example.com'):
     # Function to create a user with the specified parameters
    return get_user_model().objects.create_user(
        username=username,
        password=password,
        first_name='Test',
        last_name='User',
        email=email,
        telephone='3331722789',
        active=active
    )

def create_random_videos(count=20):
    fake = Faker()
    for i in range(count):
            # Generate random video details
            title = fake.text(max_nb_chars=50)
            image = f"https://picsum.photos/seed/{i}/200/300"
            description = fake.text(max_nb_chars=200)
            url = f"https://www.youtube.com/watch?v={fake.random_int(min=1000, max=9999)}"
            free= False
            if i%5 == 0:
                free= True
            date_of_creation = timezone.now()
            date_of_modification = timezone.now()

            # Create a video object with the generated details
            video = Video.objects.create(
                title=title,
                image=image,
                description=description,
                free=free,
                url=url,
                date_of_creation=date_of_creation,
                date_of_modification=date_of_modification
            )
            # Uncomment the following line if you want to print the video ID
            # print("VIDEO id", video.id)

class VideoPaginationTest(APITestCase):
    def setUp(self):
        # create some test videos in the database
        self.user = create_user()
        self.updated_user = create_user('testuser2', PASSWORD, True, 'testuser2@test.com')
        self.staff_user = create_user('testuser3', PASSWORD, False, 'testuser3@test.com')
        self.staff_user.is_staff = True
        self.staff_user.save()
        response1 = self.client.post(reverse('log_in'), data={
            'username': self.user.username,
            'password': PASSWORD,
        })
        response2 = self.client.post(reverse('log_in'), data={
            'username': self.updated_user.username,
            'password': PASSWORD,
        })
        response3 = self.client.post(reverse('log_in'), data={
            'username': self.staff_user.username,
            'password': PASSWORD,
        })
        
        self.access_free_user_1 = response1.data['access']
        self.access_paid_user_2 = response2.data['access']
        self.access_staff_user_3 = response3.data['access']
        self.fake = Faker()
        create_random_videos()
        
            
    

    def test_video_pagination_free(self):
        # Test video pagination for free user
        url = reverse('video-list') + '?page=1&page_size=10'
        response = self.client.get(url, HTTP_AUTHORIZATION=f'Bearer {self.access_free_user_1}')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['results']), 10)
        self.assertEqual(response.data['total_count'], 20)
        self.assertEqual(response.data['count'], 10)

    def test_video_pagination_payed_and_staff(self):
        # Test video pagination for paid and staff users
       
        url = reverse('video-list') + '?page=1&page_size=10'
        response = self.client.get(url, HTTP_AUTHORIZATION=f'Bearer {self.access_paid_user_2}')
        # print(response.data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['results']), 10)
        self.assertEqual(response.data['total_count'], 20)
        self.assertEqual(response.data['count'], 10)

        response = self.client.get(url, HTTP_AUTHORIZATION=f'Bearer {self.access_staff_user_3}')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['results']), 10)
        self.assertEqual(response.data['total_count'], 20)
        self.assertEqual(response.data['count'], 10)
    
    def test_video_detail(self):
        # Test retrieving video details

        # Not free video should return 401 
        # Retrieve the ID of a random video
        video_id=Video.objects.filter(free=False).order_by('?').first().id
        url = reverse('video-detail', args=[video_id])
        video = Video.objects.get(id=video_id)
        response = self.client.get(url, 
            HTTP_AUTHORIZATION=f'Bearer {self.access_free_user_1}')
        self.assertEqual(response.status_code, 401)


        #Free video for a free user should be allowed to see 
        # Choose a random free video 
        video = Video.objects.filter(free=True).order_by('?').first()
        video_id=video.id
        url = reverse('video-detail', args=[video_id])
        response = self.client.get(url, 
            HTTP_AUTHORIZATION=f'Bearer {self.access_free_user_1}')
        
        # Assert that the response is successful and the returned data matches the video details
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['id'], video.id)
        self.assertEqual(response.data['title'], video.title)
        self.assertEqual(response.data['description'], video.description)
        self.assertEqual(response.data['url'], video.url)
        self.assertEqual(response.data['free'], video.free)
        self.assertEqual(response.data['image'], video.image.url)
         # Convert actual value to datetime object in UTC
        actual_date = timezone.datetime.strptime(response.data['date_of_creation'], '%Y-%m-%dT%H:%M:%S.%f%z').astimezone(timezone.utc)

        # Ensure expected value is also in UTC
        expected_date = video.date_of_creation.astimezone(timezone.utc)

        # Now compare the two datetime objects directly
        self.assertEqual(actual_date, expected_date)

         # Convert actual value to datetime object in UTC
        actual_date = timezone.datetime.strptime(response.data['date_of_modification'], '%Y-%m-%dT%H:%M:%S.%f%z').astimezone(timezone.utc)

        # Ensure expected value is also in UTC
        expected_date = video.date_of_modification.astimezone(timezone.utc)

        # Now compare the two datetime objects directly
        self.assertEqual(actual_date, expected_date)

        # Paid user should be allowed to see any video
        # Choose a random non-free video
        video = Video.objects.filter(free=False).order_by('?').first()
        video_id=video.id
        url = reverse('video-detail', args=[video_id])
        response = self.client.get(url, 
            HTTP_AUTHORIZATION=f'Bearer {self.access_paid_user_2}')
        
        # Assert that the response is successful and the returned data matches the video details
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['id'], video.id)
        self.assertEqual(response.data['title'], video.title)
        self.assertEqual(response.data['description'], video.description)
        self.assertEqual(response.data['url'], video.url)
        self.assertEqual(response.data['free'], video.free)
        self.assertEqual(response.data['image'], video.image.url)
         # Convert actual value to datetime object in UTC
        actual_date = timezone.datetime.strptime(response.data['date_of_creation'], '%Y-%m-%dT%H:%M:%S.%f%z').astimezone(timezone.utc)

        # Ensure expected value is also in UTC
        expected_date = video.date_of_creation.astimezone(timezone.utc)

        # Now compare the two datetime objects directly
        self.assertEqual(actual_date, expected_date)

         # Convert actual value to datetime object in UTC
        actual_date = timezone.datetime.strptime(response.data['date_of_modification'], '%Y-%m-%dT%H:%M:%S.%f%z').astimezone(timezone.utc)

        # Ensure expected value is also in UTC
        expected_date = video.date_of_modification.astimezone(timezone.utc)

        # Now compare the two datetime objects directly
        self.assertEqual(actual_date, expected_date)


        # Staff user should be allowed to see any video
        # Choose a random non-free video
        video = Video.objects.filter(free=False).order_by('?').first()
        video_id=video.id
        url = reverse('video-detail', args=[video_id])
        response = self.client.get(url, 
            HTTP_AUTHORIZATION=f'Bearer {self.access_staff_user_3}')
        
        # Assert that the response is successful and the returned data matches the video details
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['id'], video.id)
        self.assertEqual(response.data['title'], video.title)
        self.assertEqual(response.data['description'], video.description)
        self.assertEqual(response.data['url'], video.url)
        self.assertEqual(response.data['free'], video.free)
        self.assertEqual(response.data['image'], video.image.url)
         # Convert actual value to datetime object in UTC
        actual_date = timezone.datetime.strptime(response.data['date_of_creation'], '%Y-%m-%dT%H:%M:%S.%f%z').astimezone(timezone.utc)

        # Ensure expected value is also in UTC
        expected_date = video.date_of_creation.astimezone(timezone.utc)

        # Now compare the two datetime objects directly
        self.assertEqual(actual_date, expected_date)

         # Convert actual value to datetime object in UTC
        actual_date = timezone.datetime.strptime(response.data['date_of_modification'], '%Y-%m-%dT%H:%M:%S.%f%z').astimezone(timezone.utc)

        # Ensure expected value is also in UTC
        expected_date = video.date_of_modification.astimezone(timezone.utc)

        # Now compare the two datetime objects directly
        self.assertEqual(actual_date, expected_date)
    

    def test_update_video(self):
        import io 
        from django.core.files.uploadedfile import SimpleUploadedFile
        from PIL import Image
        import os

        # Create an in-memory binary stream to save the image data
        image_data = io.BytesIO()

        # Create a new image with size 50x50 and color (155, 0, 0)
        image = Image.new('RGBA', size=(50, 50), color=(155, 0, 0))

        # Save the image data to the in-memory stream as PNG
        image.save(image_data, 'png')
        image_data.seek(0)

        # Create a SimpleUploadedFile object from the in-memory image data
        image_file = SimpleUploadedFile('test_image.png', image_data.getvalue(), content_type='image/png')

        import random 

        # Get all ids from the Video model
        ids_queryset = Video.objects.values_list('id', flat=True)

        # Convert the queryset to a list
        ids_list = list(ids_queryset)

        # Choose a random number from the list of ids
        random_id = random.choice(ids_list)

        # Generate the URL for the video detail endpoint with the random id
        url = reverse('video-detail', args=[random_id])

        # Create the data payload for updating the video
        data = {
            'title': "el video de test",
            'image': image_file,
            'description': "testing is great",
            'url': "https://www.youtube.com/watch?v=1000",
            'free': False,
        }

        # Send a PUT request to update the video using the generated URL and data payload
        # with the authorization token of the staff user
        response = self.client.put(url, data, HTTP_AUTHORIZATION=f'Bearer {self.access_staff_user_3}', format='multipart')

        # Check the response status code is 200 (OK)
        self.assertEqual(response.status_code, 200)

        # Retrieve the updated video object from the database
        video = Video.objects.get(id=random_id)

        # Assert that the response data matches the updated video attributes
        self.assertEqual(response.data['id'], video.id)
        self.assertEqual(response.data['title'], video.title)
        self.assertEqual(response.data['description'], video.description)
        self.assertEqual(response.data['url'], video.url)
        self.assertEqual(response.data['free'], video.free)
        self.assertEqual(response.data['image'], video.image.url)
        
         # Convert actual value to datetime object in UTC
        actual_date = timezone.datetime.strptime(response.data['date_of_creation'], '%Y-%m-%dT%H:%M:%S.%f%z').astimezone(timezone.utc)

        # Ensure expected value is also in UTC
        expected_date = video.date_of_creation.astimezone(timezone.utc)

        # Now compare the two datetime objects directly
        self.assertEqual(actual_date, expected_date)

         # Convert actual value to datetime object in UTC
        actual_date = timezone.datetime.strptime(response.data['date_of_modification'], '%Y-%m-%dT%H:%M:%S.%f%z').astimezone(timezone.utc)

        # Ensure expected value is also in UTC
        expected_date = video.date_of_modification.astimezone(timezone.utc)

        # Now compare the two datetime objects directly
        self.assertEqual(actual_date, expected_date)

        # Assert that the data used for the update matches the updated video attributes
        self.assertEqual(data['title'], video.title)
        self.assertEqual(data['description'], video.description)
        self.assertEqual(data['url'], video.url)
        self.assertEqual(data['free'], video.free)

        # Assert that the uploaded image file name is contained within the video's image name
        

        # Remove the uploaded image file
        os.remove(f"media/{video.image.name}")


    def test_create_video(self):
        create_random_videos()
        import io 
        from django.core.files.uploadedfile import SimpleUploadedFile
        from PIL import Image
        import os

        # Generate an in-memory binary stream to save the image data
        image_data = io.BytesIO()

        # Create a new RGB image with size 50x50
        image = Image.new('RGB', size=(50, 50))

        # Save the image data to the in-memory stream as JPEG
        image.save(image_data, 'JPEG')
        image_data.seek(0)

        # Create a SimpleUploadedFile object from the in-memory image data
        image_file = SimpleUploadedFile('test_image.jpg', image_data.getvalue(), content_type='image/jpeg')

        # Generate random data for creating a video
        data = {
            'title': self.fake.text(max_nb_chars=50),
            'image': image_file,
            'description': self.fake.text(max_nb_chars=200),
            'url': f"https://www.youtube.com/watch?v={self.fake.random_int(min=1000, max=9999)}",
            'free': True,
        }

        # Generate the URL for the video detail endpoint
        url = reverse('video-detail')

        # Send a POST request to create the video using the generated URL and data payload
        # with the authorization token of the staff user
        response = self.client.post(url, data, HTTP_AUTHORIZATION=f'Bearer {self.access_staff_user_3}', format='multipart')

        # Retrieve the last created video object from the database
        video = Video.objects.last()

        # Assert that the response status code is 201 (Created)
        self.assertEqual(response.status_code, 201)

        # Assert that the response data matches the created video attributes
        self.assertEqual(response.data['id'], video.id)
        self.assertEqual(response.data['title'], video.title)
        self.assertEqual(response.data['description'], video.description)
        self.assertEqual(response.data['url'], video.url)
        self.assertEqual(response.data['free'], video.free)
        self.assertTrue(video.image.name in response.data['image'])
         # Convert actual value to datetime object in UTC
        actual_date = timezone.datetime.strptime(response.data['date_of_creation'], '%Y-%m-%dT%H:%M:%S.%f%z').astimezone(timezone.utc)

        # Ensure expected value is also in UTC
        expected_date = video.date_of_creation.astimezone(timezone.utc)

        # Now compare the two datetime objects directly
        self.assertEqual(actual_date, expected_date)

         # Convert actual value to datetime object in UTC
        actual_date = timezone.datetime.strptime(response.data['date_of_modification'], '%Y-%m-%dT%H:%M:%S.%f%z').astimezone(timezone.utc)

        # Ensure expected value is also in UTC
        expected_date = video.date_of_modification.astimezone(timezone.utc)

        # Now compare the two datetime objects directly
        self.assertEqual(actual_date, expected_date)

        # Remove the uploaded image file
        os.remove(f"media/{video.image.name}")

        # Delete all videos in the database
        Video.objects.all().delete()

        # Repeat the process to create another video without any data in the database
        image_data = io.BytesIO()
        image = Image.new('RGB', size=(50, 50))
        image.save(image_data, 'JPEG')
        image_data.seek(0)
        image_file = SimpleUploadedFile('test_image.jpg', image_data.getvalue(), content_type='image/jpeg')
        data = {
            'title': self.fake.text(max_nb_chars=50),
            'image': image_file,
            'description': self.fake.text(max_nb_chars=200),
            'url': f"https://www.youtube.com/watch?v={self.fake.random_int(min=1000, max=9999)}",
            'free': True,
        }

        # Send a POST request to create the video without any data in the database
        response = self.client.post(url, data, HTTP_AUTHORIZATION=f'Bearer {self.access_staff_user_3}', format='multipart')

        # Retrieve the last created video object from the database
        video = Video.objects.last()

        # Assert that the response data matches the created video attributes
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['id'], video.id)
        self.assertEqual(response.data['title'], video.title)
        self.assertEqual(response.data['description'], video.description)
        self.assertEqual(response.data['url'], video.url)
        self.assertEqual(response.data['free'], video.free)
        self.assertTrue(video.image.name in response.data['image'] )
         # Convert actual value to datetime object in UTC
        actual_date = timezone.datetime.strptime(response.data['date_of_creation'], '%Y-%m-%dT%H:%M:%S.%f%z').astimezone(timezone.utc)

        # Ensure expected value is also in UTC
        expected_date = video.date_of_creation.astimezone(timezone.utc)

        # Now compare the two datetime objects directly
        self.assertEqual(actual_date, expected_date)

         # Convert actual value to datetime object in UTC
        actual_date = timezone.datetime.strptime(response.data['date_of_modification'], '%Y-%m-%dT%H:%M:%S.%f%z').astimezone(timezone.utc)

        # Ensure expected value is also in UTC
        expected_date = video.date_of_modification.astimezone(timezone.utc)

        # Now compare the two datetime objects directly
        self.assertEqual(actual_date, expected_date)
        # Remove the uploaded image file
        os.remove(f"media/{video.image.name}")

        # Call the function to create random videos again
        create_random_videos()

        # Send a POST request to create a video with the authorization token of a paid user
        response = self.client.post(url, data, HTTP_AUTHORIZATION=f'Bearer {self.access_paid_user_2}', format='multipart')

        # Retrieve the last created video object from the database
        video = Video.objects.last()

        # Assert that the response status code is 401 (Unauthorized)
        self.assertEqual(response.status_code, 401)

        # Send a POST request to create a video with the authorization token of a free user
        response = self.client.post(url, data, HTTP_AUTHORIZATION=f'Bearer {self.access_free_user_1}', format='multipart')

        # Retrieve the last created video object from the database
        video = Video.objects.last()

        # Assert that the response status code is 401 (Unauthorized)
        self.assertEqual(response.status_code, 401)
    
    def test_create_video_with_category(self):
        category_data = {
            'title': 'Test Category',
            'description': 'Test description'
        }

        url = reverse('category-detail')
        response = self.client.post(url, category_data, format='json', HTTP_AUTHORIZATION=f'Bearer {self.access_staff_user_3}')
        category = response.data
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        create_random_videos()
        import io 
        from django.core.files.uploadedfile import SimpleUploadedFile
        from PIL import Image
        import os

        # Generate an in-memory binary stream to save the image data
        image_data = io.BytesIO()

        # Create a new RGB image with size 50x50
        image = Image.new('RGB', size=(50, 50))

        # Save the image data to the in-memory stream as JPEG
        image.save(image_data, 'JPEG')
        image_data.seek(0)

        # Create a SimpleUploadedFile object from the in-memory image data
        image_file = SimpleUploadedFile('test_image.jpg', image_data.getvalue(), content_type='image/jpeg')

        # Generate random data for creating a video
        import json
        data = {
            'title': self.fake.text(max_nb_chars=50),
            'image': image_file,
            'description': self.fake.text(max_nb_chars=200),
            'url': f"https://www.youtube.com/watch?v={self.fake.random_int(min=1000, max=9999)}",
            'free': True,
            'categories': json.dumps( {"data_key": response.data["id"]})
        }

        # Generate the URL for the video detail endpoint
        url = reverse('video-detail')

        # Send a POST request to create the video using the generated URL and data payload
        # with the authorization token of the staff user
        response = self.client.post(url, data, HTTP_AUTHORIZATION=f'Bearer {self.access_staff_user_3}', format='multipart')

        # Retrieve the last created video object from the database
        video = Video.objects.last()

        # Assert that the response status code is 201 (Created)
        self.assertEqual(response.status_code, 201)

        # Assert that the response data matches the created video attributes
        self.assertEqual(response.data['id'], video.id)
        self.assertEqual(response.data['title'], video.title)
        self.assertEqual(response.data['description'], video.description)
        self.assertEqual(response.data['url'], video.url)
        self.assertEqual(response.data['free'], video.free)
        self.assertTrue(video.image.name in response.data['image'])
        self.assertEqual(response.data["categories"][0]["id"], category["id"])
        self.assertEqual(response.data["categories"][0]["description"], category["description"])
         # Convert actual value to datetime object in UTC
        actual_date = timezone.datetime.strptime(response.data['date_of_creation'], '%Y-%m-%dT%H:%M:%S.%f%z').astimezone(timezone.utc)

        # Ensure expected value is also in UTC
        expected_date = video.date_of_creation.astimezone(timezone.utc)

        # Now compare the two datetime objects directly
        self.assertEqual(actual_date, expected_date)

         # Convert actual value to datetime object in UTC
        actual_date = timezone.datetime.strptime(response.data['date_of_modification'], '%Y-%m-%dT%H:%M:%S.%f%z').astimezone(timezone.utc)

        # Ensure expected value is also in UTC
        expected_date = video.date_of_modification.astimezone(timezone.utc)

        # Now compare the two datetime objects directly
        self.assertEqual(actual_date, expected_date)
        

    def test_delete_video(self):
        # Set the ID of the video to be created
        id = 21

        # Generate a fake title for the video
        title = self.fake.text(max_nb_chars=50)

        # Generate a random image URL using the ID
        image = f"https://picsum.photos/seed/{id}/200/300"

        # Generate a fake description for the video
        description = self.fake.text(max_nb_chars=200)

        # Generate a random YouTube URL using a fake random integer
        url = f"https://www.youtube.com/watch?v={self.fake.random_int(min=1000, max=9999)}"

        # Set the 'free' attribute of the video to False
        free = False

        # Get the current date and time
        date_of_creation = timezone.now()
        date_of_modification = timezone.now()

        # Create a new Video object with the specified attributes
        Video.objects.create(
            id=id,
            title=title,
            image=image,
            description=description,
            free=free,
            url=url,
            date_of_creation=date_of_creation,
            date_of_modification=date_of_modification
        )

        # Get the URL for the video detail view
        url = reverse('video-detail', args=[id])

        # Send a DELETE request to delete the video with the specified ID, using the authorization token of a staff user
        response = self.client.delete(url, HTTP_AUTHORIZATION=f'Bearer {self.access_staff_user_3}')

        # Assert that the response status code is 204 (No Content)
        self.assertEqual(response.status_code, 204)

        # Assert that attempting to retrieve the video with the specified ID raises a Video.DoesNotExist exception
        with self.assertRaises(Video.DoesNotExist):
            Video.objects.get(id=21)
        


class CategoryAPITestCase(APITestCase):
    def setUp(self):
        self.category_data = {
            'title': 'Test Category',
            'description': 'Test description'
        }
        self.category = Category.objects.create(
            title='Existing Category',
            description='Existing description'
        )
        self.user = create_user('testuser2', PASSWORD, True, 'testuser2@test.com')
        self.staff_user = create_user('testuser3', PASSWORD, False, 'testuser3@test.com')
        self.staff_user.is_staff = True
        self.staff_user.save()


        response1 = self.client.post(reverse('log_in'), data={
            'username': self.user.username,
            'password': PASSWORD,
        })

        response2 = self.client.post(reverse('log_in'), data={
            'username': self.staff_user.username,
            'password': PASSWORD,
        })
        
        self.access_free_user_1 = response1.data['access']
        self.access_staff_user_2 = response2.data['access']
        self.fake = Faker()

    def test_get_all_categories(self):
        url = reverse('category-list')
        response = self.client.get(url, HTTP_AUTHORIZATION=f'Bearer {self.access_free_user_1}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_create_category(self):
        url = reverse('category-detail')
        response = self.client.post(url, self.category_data, format='json', HTTP_AUTHORIZATION=f'Bearer {self.access_staff_user_2}')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Category.objects.count(), 2)

    def test_update_category(self):
        url = reverse('category-detail', args=[self.category.id])
        updated_data = {
            'title': 'Updated Category',
            'description': 'Updated description'
        }
        response = self.client.put(url, updated_data, format='json', HTTP_AUTHORIZATION=f'Bearer {self.access_staff_user_2}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.category.refresh_from_db()
        self.assertEqual(self.category.title, 'Updated Category')

    def test_delete_category(self):
        url = reverse('category-detail', args=[self.category.id])
        response = self.client.delete(url, HTTP_AUTHORIZATION=f'Bearer {self.access_staff_user_2}')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Category.objects.count(), 0)
    
    def test_patch_add_video_to_category(self):
        import io 
        from django.core.files.uploadedfile import SimpleUploadedFile
        from PIL import Image
        import os

        # Generate an in-memory binary stream to save the image data
        image_data = io.BytesIO()

        # Create a new RGB image with size 50x50
        image = Image.new('RGB', size=(50, 50))

        # Save the image data to the in-memory stream as JPEG
        image.save(image_data, 'JPEG')
        image_data.seek(0)

        # Create a SimpleUploadedFile object from the in-memory image data
        image_file = SimpleUploadedFile('test_image.jpg', image_data.getvalue(), content_type='image/jpeg')

        # Generate random data for creating a video
        data = {
            'title': self.fake.text(max_nb_chars=50),
            'image': image_file,
            'description': self.fake.text(max_nb_chars=200),
            'url': f"https://www.youtube.com/watch?v={self.fake.random_int(min=1000, max=9999)}",
            'free': True,
        }


        url = reverse('category-detail', args=[self.category.id])
        response = self.client.patch(url, data, HTTP_AUTHORIZATION=f'Bearer {self.access_staff_user_2}')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(self.category.category_videos.count(), 1)



        video = Video.objects.first()
        self.assertEqual(video.title, data["title"])
        self.assertEqual(video.description, data["description"])
        self.assertEqual(video.url, data["url"])
        self.assertEqual(video.free, data["free"])

        os.remove(f"media/{video.image.name}")



class SearchVideoAPITestCase(APITestCase):
    def setUp(self):
        # Create sample data for testing
        fake = Faker()
        image = f"https://picsum.photos/seed/{fake.random_int(min=1, max=9999)}/200/300"
        description = fake.text(max_nb_chars=200)
        url = f"https://www.youtube.com/watch?v={fake.random_int(min=1000, max=9999)}"
        free= False
        Video.objects.create(title='Sample Video 1', description=description, image=image, url='http://example.com/video1/', free=False)
        Video.objects.create(title='Sample Video 2', description=description, image=image, url='http://example.com/video2/', free=False)

    def test_search_video_api(self):
        # Test searching for a video with a valid query
        search_query = 'Sample Video 1'
        url = reverse('search_videos') + f'?search={search_query}'

        response = self.client.get(url)


        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)  # Assuming there is only one video with the specified title
        self.assertEqual(response.data['results'][0]['title'], 'Sample Video 1')

    def test_search_video_api_several_objects(self):
        # Test searching for a video with a valid query
        search_query = 'Sample'
        url = reverse('search_videos') + f'?search={search_query}'

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)  # Assuming there is only one video with the specified title
        self.assertEqual(response.data['results'][0]['title'], 'Sample Video 1')
        self.assertEqual(response.data['results'][1]['title'], 'Sample Video 2')

    def test_search_video_api_missing_query(self):
        # Test the case where the search parameter is missing
        url = reverse('search_videos')

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data, {'error': 'Search parameter or category parameter is required'})
    
       


