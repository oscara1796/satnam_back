from django.contrib.auth import get_user_model
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
import stripe
from dotenv import dotenv_values
from .models import TrialDays


env_vars = dotenv_values(".env.dev")
stripe.api_key = env_vars["STRIPE_SECRET_KEY"]

class UserSerializer(serializers.ModelSerializer):
    password1 = serializers.CharField(write_only=True)
    password2 = serializers.CharField(write_only=True)


    def validate(self, data):
        if data['password1'] != data['password2']:
            raise serializers.ValidationError({'password1':"Contraseñas deben ser iguales"})
        return data
    
    def create(self, validated_data):

        data = {
            key: value for key, value in validated_data.items()
            if key not in ('password1', 'password2')
        }
        data['password'] = validated_data['password1']
       
        stripe_response=stripe.Customer.create(name=data["first_name"] + " " + data["last_name"], email=data["email"], phone=data["telephone"], metadata={"username": data["username"]})
        data['stripe_customer_id'] = stripe_response.id
        return self.Meta.model.objects.create_user(**data)
    

    def update(self, instance, validated_data):
        for key, value in validated_data.items():
            if key in ('password1', 'password2'):
                instance.set_password(value)
            setattr(instance, key, value)
        
        instance.save()
        return instance
    
    class Meta:
        model = get_user_model()
        fields = (
            'id', 'username', 'password1', 'password2',
            'first_name', 'last_name', 'email', 'telephone', 'active', 'stripe_customer_id',
            'stripe_subscription_id',
        )
        read_only_fields = ('id',)

class LogInSerializer(TokenObtainPairSerializer): 
    @classmethod
    def get_token(cls, user):

        
        token = super().get_token(user)
       
        user_data = UserSerializer(user).data
        for key, value in user_data.items():
            if key != 'id':
                token[key] = value
        token['is_staff'] = user.is_staff
        return token

class TrialDaysSerializer(serializers.ModelSerializer):
    class Meta:
        model = TrialDays
        fields = ['id', 'days']