from rest_framework.test import APITestCase
from django.urls import reverse
from videos.models import Video
from django.contrib.auth import get_user_model
from faker import Faker
from django.utils import timezone

PASSWORD = 'pAssw0rd!'


def create_user(username='testuser', password=PASSWORD, active =False, email= 'user@example.com'):
    return get_user_model().objects.create_user(
        username=username,
        password=password,
        first_name='Test',
        last_name='User',
        email=email,
        telephone='3331722789',
        active=active
    )

class VideoPaginationTest(APITestCase):
    def setUp(self):
        # create some test videos in the database
        self.user = create_user()
        self.updated_user = create_user('testuser2', PASSWORD, True, 'testuser2@test.com')
        response1 = self.client.post(reverse('log_in'), data={
            'username': self.user.username,
            'password': PASSWORD,
        })
        response2 = self.client.post(reverse('log_in'), data={
            'username': self.updated_user.username,
            'password': PASSWORD,
        })
        
        self.access_user_1 = response1.data['access']
        self.access_user_2 = response2.data['access']
        fake = Faker()
        for i in range(20):
            title = fake.text(max_nb_chars=50)
            image = f"https://picsum.photos/seed/{i}/200/300"
            description = fake.text(max_nb_chars=200)
            url = f"https://www.youtube.com/watch?v={fake.random_int(min=1000, max=9999)}"
            free= False
            if i%5 == 0:
                free= True
            date_of_creation = timezone.now()
            date_of_modification = timezone.now()

            Video.objects.create(title=title, image=image, description=description, free=free, url=url,
                                date_of_creation=date_of_creation, date_of_modification=date_of_modification)
            
    

    def test_video_pagination_free(self):
        url = reverse('video-list') + '?page=1&page_size=10'
        # print("self.user", self.user.active)
        response = self.client.get(url, HTTP_AUTHORIZATION=f'Bearer {self.access_user_1}')
        # print(response.data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['results']), 4)
        self.assertEqual(response.data['total_count'], 20)
        self.assertEqual(response.data['count'], 4)

    def test_video_pagination_payed(self):
        
        # print("updated_user", self.updated_user.username)
        # print("updated_user", self.updated_user.active)
        url = reverse('video-list') + '?page=1&page_size=10'
        response = self.client.get(url, HTTP_AUTHORIZATION=f'Bearer {self.access_user_2}')
        # print(response.data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['results']), 10)
        self.assertEqual(response.data['total_count'], 20)
        self.assertEqual(response.data['count'], 10)
    
    def test_video_detail(self):
        video_id=1
        url = reverse('video-detail', args=[video_id])
        response = self.client.get(url, 
            HTTP_AUTHORIZATION=f'Bearer {self.access_user_2}')
        video = Video.objects.get(id=1)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['id'], video.id)
        self.assertEqual(response.data['title'], video.title)
        self.assertEqual(response.data['description'], video.description)
        self.assertEqual(response.data['url'], video.url)
        self.assertEqual(response.data['free'], video.free)
        self.assertEqual(response.data['image'], video.image.url)
        self.assertEqual(response.data['date_of_creation'], video.date_of_creation.strftime('%Y-%m-%dT%H:%M:%S.%fZ'))
        self.assertEqual(response.data['date_of_modification'], video.date_of_modification.strftime('%Y-%m-%dT%H:%M:%S.%fZ'))