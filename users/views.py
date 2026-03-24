from rest_framework import generics, permissions, response, status
from rest_framework.views import APIView

from users.serializers import DemoLoginSerializer, UserPreferencesSerializer, UserSerializer
from users.services import UserService


class DemoLoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = DemoLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = UserService.demo_login(request, **serializer.validated_data)
        return response.Response(UserSerializer(user).data, status=status.HTTP_200_OK)


class MeView(APIView):
    def get(self, request):
        return response.Response(UserSerializer(request.user).data)


class MePreferencesView(generics.UpdateAPIView):
    serializer_class = UserPreferencesSerializer

    def get_object(self):
        return self.request.user

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        serializer = self.get_serializer(self.get_object(), data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return response.Response(UserSerializer(self.get_object()).data)
