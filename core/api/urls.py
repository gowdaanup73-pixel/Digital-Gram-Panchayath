from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)

from core.api.views import (
    RegisterAPIView,
    LogoutAPIView,
    ProfileAPIView,
    ServiceViewSet,
    ApplicationViewSet,
    ComplaintViewSet,
    VotingSessionViewSet,
)

router = DefaultRouter()
router.register(r'services', ServiceViewSet, basename='api-service')
router.register(r'applications', ApplicationViewSet, basename='api-application')
router.register(r'complaints', ComplaintViewSet, basename='api-complaint')
router.register(r'voting-sessions', VotingSessionViewSet, basename='api-voting-session')

urlpatterns = [
    # JWT Authentication Endpoints
    path('auth/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/token/verify/', TokenVerifyView.as_view(), name='token_verify'),
    path('auth/register/', RegisterAPIView.as_view(), name='api_register'),
    path('auth/logout/', LogoutAPIView.as_view(), name='api_logout'),

    # Profile Endpoints
    path('profile/', ProfileAPIView.as_view(), name='api_profile'),

    # Resource ViewSets
    path('', include(router.urls)),
]
