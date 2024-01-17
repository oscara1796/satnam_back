from django.urls import path 
from .views import SignUpView, LogInView, UserDetailView, CustomTokenRefreshView, TrialDaysDetail

urlpatterns = [
    path('api/sign_up/', SignUpView.as_view(), name='sign_up'),
    path('api/log_in/', LogInView.as_view(), name='log_in'), 
    path('api/users/<int:pk>/', UserDetailView.as_view(), name='user-detail'), 
    path('api/token/refresh/', CustomTokenRefreshView.as_view(), name='token_refresh'),
    path('api/trial-days/', TrialDaysDetail.as_view(), name='trial_days'),
    path('api/trial-days/<int:pk>/', TrialDaysDetail.as_view(), name='trial_day_detail')
]
    