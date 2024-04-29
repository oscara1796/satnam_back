import pytest
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.utils import IntegrityError

User = get_user_model()


@pytest.mark.django_db
def test_custom_user_creation():

    # Create a custom user
    user = User.objects.create_user(
        username="testuser",
        email="testuser@example.com",
        password="testpass",
        first_name="Test",
        last_name="User",
        telephone="1234567890",
    )

    # Check that the user was created successfully
    assert user.username == "testuser"
    assert user.email == "testuser@example.com"
    assert user.check_password("testpass")
    assert user.first_name == "Test"
    assert user.last_name == "User"
    assert user.telephone == "1234567890"
    assert str(user) == user.username


@pytest.mark.django_db
def test_create_and_delete_user():

    # Create a custom user
    user = User.objects.create_user(
        username="testuser",
        email="testuser@example.com",
        password="testpass",
        first_name="Test",
        last_name="User",
        telephone="1234567890",
    )

    # Check that the user was created successfully
    assert user.username == "testuser"
    assert user.email == "testuser@example.com"
    assert user.check_password("testpass")
    assert user.first_name == "Test"
    assert user.last_name == "User"
    assert user.telephone == "1234567890"
    assert str(user) == user.username

    # Delete the user
    user.delete()

    assert not User.objects.filter(username="testuser").exists()


@pytest.mark.django_db
def test_update_user():

    # Create a custom user
    user = User.objects.create_user(
        username="testuser",
        email="testuser@example.com",
        password="testpass",
        first_name="Test",
        last_name="User",
        telephone="1234567890",
    )

    # Check that the user was created successfully
    assert user.username == "testuser"
    assert user.email == "testuser@example.com"
    assert user.check_password("testpass")
    assert user.first_name == "Test"
    assert user.last_name == "User"
    assert user.telephone == "1234567890"
    assert str(user) == user.username

    user.set_password("newpass")
    user.username = "alice"
    user.email = "alice@gmail.com"

    # Update the user
    user.save()
    assert user.username == "alice"
    assert user.email == "alice@gmail.com"
    assert user.check_password("newpass")


@pytest.mark.django_db
def test_create_custom_user_unique_fields():
    """Test creating a custom user with unique email and username"""

    User.objects.create_user(
        username="testuser",
        email="testuser@example.com",
        password="testpass",
        first_name="Test",
        last_name="User",
        telephone="555-1234",
    )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            User.objects.create_user(
                username="testuser",
                email="testuser@example.com",
                password="testpass2",
                first_name="Test2",
                last_name="User2",
                telephone="555-5678",
            )

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            User.objects.create_user(
                username="testuser2",
                email="testuser@example.com",
                password="testpass3",
                first_name="Test3",
                last_name="User3",
                telephone="555-9012",
            )
