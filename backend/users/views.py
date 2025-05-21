from django.contrib.auth import get_user_model
from rest_framework import generics, permissions, viewsets
from .models import Follow
from .serializers import (
    UserSerializer, FollowSerializer, UserCreateSerializer,
    SetPasswordSerializer, SubscriptionSerializer,
    CustomAuthTokenSerializer
)
from rest_framework.pagination import PageNumberPagination
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.authtoken.models import Token
from rest_framework.generics import (
    ListAPIView, get_object_or_404, RetrieveAPIView
)

User = get_user_model()


class UserPagination(PageNumberPagination):
    page_size_query_param = 'limit'


class UserViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    pagination_class = UserPagination


class FollowViewSet(viewsets.ModelViewSet):
    serializer_class = FollowSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Follow.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class UserCreateView(generics.CreateAPIView):
    serializer_class = UserCreateSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED,
            headers=headers
        )


class CurrentUserView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(
            serializer.data,
            status=status.HTTP_200_OK
        )


class UserAvatarUpdateView(generics.UpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user

    def update(self, request, *args, **kwargs):
        print("Request data for avatar update:", request.data)
        if 'avatar' in request.data:
            print("Avatar data type:", type(request.data['avatar']))
            print(
                "Avatar data (first 100 chars):",
                str(request.data['avatar'])[:100]
            )

        kwargs['partial'] = True
        try:
            response = super().update(request, *args, **kwargs)
            print("Update successful, response data:", response.data)
            return response
        except Exception as e:
            print("Error during update:", e)
            raise e

    def delete(self, request, *args, **kwargs):
        user = self.get_object()
        if user.avatar:
            user.avatar.delete(save=True)
        return Response(
            {'detail': 'Аватар удалён.'},
            status=status.HTTP_204_NO_CONTENT
        )


class UserAvatarDeleteView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request):
        user = request.user
        user.avatar = None
        user.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


class SetPasswordView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = SetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = request.user
        if not user.check_password(
            serializer.validated_data['current_password']
        ):
            return Response(
                {'current_password': ['Неверный текущий пароль.']},
                status=status.HTTP_400_BAD_REQUEST
            )
        user.set_password(serializer.validated_data['new_password'])
        user.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CustomAuthToken(ObtainAuthToken):
    permission_classes = [permissions.AllowAny]
    serializer_class = CustomAuthTokenSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
            user = serializer.validated_data['user']
            token, _ = Token.objects.get_or_create(user=user)

            user_data = UserSerializer(user).data

            return Response({
                'auth_token': token.key,
                'user': user_data
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            if not hasattr(request.user, 'auth_token'):
                return Response(
                    {'error': 'Токен не найден'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            request.user.auth_token.delete()
            return Response(
                {'message': 'Успешный выход из системы'},
                status=status.HTTP_200_OK
            )
        except Exception:
            return Response(
                {'error': 'Ошибка при выходе из системы'},
                status=status.HTTP_400_BAD_REQUEST
            )


class SubscriptionPagination(PageNumberPagination):
    page_size_query_param = 'limit'


class SubscriptionListView(ListAPIView):
    serializer_class = SubscriptionSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = SubscriptionPagination

    def get_queryset(self):
        return self.request.user.follower.select_related('author').all()


class SubscribeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, id):
        author = get_object_or_404(get_user_model(), id=id)
        if author == request.user:
            return Response(
                {'errors': 'Нельзя подписаться на самого себя.'},
                status=400
            )
        if Follow.objects.filter(user=request.user, author=author).exists():
            return Response(
                {'errors': 'Вы уже подписаны на этого пользователя.'},
                status=400
            )
        follow = Follow.objects.create(user=request.user, author=author)
        serializer = SubscriptionSerializer(
            follow,
            context={'request': request}
        )
        return Response(serializer.data, status=201)

    def delete(self, request, id):
        author = get_object_or_404(get_user_model(), id=id)
        follow = Follow.objects.filter(user=request.user, author=author)
        if not follow.exists():
            return Response(
                {'errors': 'Вы не были подписаны на этого пользователя.'},
                status=400
            )
        follow.delete()
        return Response(status=204)


class UserListView(ListAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    pagination_class = UserPagination


class UserDetailView(RetrieveAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]


class UserListCreateView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        users = User.objects.all()
        serializer = UserSerializer(users, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = UserCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ResetPasswordView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = request.data.get('email')
        if not email:
            return Response({'error': 'Email обязателен'}, status=400)
        user = User.objects.filter(email=email).first()
        if not user:
            return Response(
                {'error': 'Пользователь с таким email не найден'},
                status=404
            )
        return Response(
            {'detail': 'Инструкция по сбросу пароля отправлена на email'},
            status=200
        )
