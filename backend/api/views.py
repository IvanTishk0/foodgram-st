from rest_framework import viewsets, permissions, status, generics, serializers
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import (
    IsAuthenticatedOrReadOnly
)
from rest_framework.decorators import action
from rest_framework.authtoken.models import Token
from rest_framework.generics import (
    ListAPIView, get_object_or_404, RetrieveAPIView
)
from django.db.models import Sum

from django.contrib.auth import get_user_model
from django.http import HttpResponse
from recipes.models import Ingredient, Recipe, RecipeIngredient

from api.serializers import (
    IngredientSerializer, RecipeSerializer,
    RecipeCreateSerializer, RecipeUpdateSerializer,
    UserSerializer, FollowSerializer, UserCreateSerializer,
    SetPasswordSerializer, SubscriptionSerializer,
    CustomAuthTokenSerializer, UserDetailSerializer,
    UserAvatarSerializer, RecipeShortSerializer
)

User = get_user_model()


class IngredientViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Ingredient.objects.all()
    serializer_class = IngredientSerializer
    permission_classes = [permissions.AllowAny]
    pagination_class = None

    def get_queryset(self):
        queryset = super().get_queryset()
        name = self.request.query_params.get('name')
        if name:
            queryset = queryset.filter(name__startswith=name)
        return queryset.order_by('name')


class RecipePagination(PageNumberPagination):
    page_size = 6
    page_size_query_param = 'limit'
    max_page_size = 6

    def get_paginated_response(self, data):
        return Response({
            'count': self.page.paginator.count,
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'results': data
        })


class IsAuthorOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        return (
            request.method in permissions.SAFE_METHODS
            or request.user.is_authenticated
        )

    def has_object_permission(self, request, view, obj):
        return (
            request.method in permissions.SAFE_METHODS
            or obj.author == request.user
        )


class RecipeViewSet(viewsets.ModelViewSet):
    queryset = Recipe.objects.all()
    pagination_class = RecipePagination
    permission_classes = [IsAuthorOrReadOnly]

    def get_permissions(self):
        if self.action in [
            'add_to_shopping_cart',
            'remove_from_shopping_cart',
            'download_shopping_cart',
            'add_to_favorites',
            'remove_from_favorites'
        ]:
            return [IsAuthenticatedOrReadOnly()]
        return super().get_permissions()

    def get_serializer_class(self):
        if self.action == 'create':
            return RecipeCreateSerializer
        if self.action in ['partial_update', 'update']:
            return RecipeUpdateSerializer
        if self.action in ['add_to_shopping_cart', 'add_to_favorites']:
            return RecipeShortSerializer
        return RecipeSerializer

    def get_queryset(self):
        queryset = Recipe.objects.all()
        author = self.request.query_params.get('author')
        is_favorited = self.request.query_params.get('is_favorited')
        is_in_shopping_cart = self.request.query_params.get(
            'is_in_shopping_cart'
        )
        user = self.request.user

        if author:
            queryset = queryset.filter(author__id=author)
        if is_favorited in ('1', 1, True, 'true') and user.is_authenticated:
            queryset = queryset.filter(favorited_by__user=user)
        if (is_in_shopping_cart in ('1', 1, True, 'true')
                and user.is_authenticated):
            queryset = queryset.filter(in_shopping_carts__user=user)
        return queryset

    def perform_create(self, serializer):
        recipe = serializer.save(author=self.request.user)
        return RecipeSerializer(
            recipe,
            context={'request': self.request}
        ).data

    @action(detail=True, methods=['get'], url_path='get-link')
    def short_link(self, request, pk=None):
        recipe = self.get_object()
        short_url = request.build_absolute_uri(f'/recipes/{recipe.id}/')
        return Response({'short-link': short_url})

    @action(
        detail=False,
        methods=['get'],
        url_path='download_shopping_cart',
        permission_classes=[IsAuthenticatedOrReadOnly]
    )
    def download_shopping_cart(self, request):
        if not request.user.is_authenticated:
            return Response(
                {'detail': 'Учетная запись не авторизована.'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        ingredients = RecipeIngredient.objects.filter(
            recipe__in_shopping_carts__user=request.user
        ).values(
            'ingredient__name',
            'ingredient__measurement_unit'
        ).annotate(
            amount=Sum('amount')
        ).order_by('ingredient__name')

        lines = [
            f'{item["ingredient__name"]} '
            f'({item["ingredient__measurement_unit"]}) — {item["amount"]}'
            for item in ingredients
        ]

        content = '\n'.join(lines)
        response = HttpResponse(content, content_type='text/plain')
        response['Content-Disposition'] = (
            'attachment; '
            'filename="shopping_list.txt"'
        )
        return response

    @action(
        detail=True,
        methods=['post', 'delete'],
        url_path='shopping_cart',
        permission_classes=[IsAuthenticatedOrReadOnly]
    )
    def shopping_cart(self, request, pk=None):
        if not request.user.is_authenticated:
            return Response(
                {'detail': 'Учетная запись не авторизована.'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        recipe = self.get_object()

        if request.method == 'POST':
            if request.user.shopping_cart.filter(recipe=recipe).exists():
                return Response(
                    {'errors': 'Рецепт уже в списке покупок.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            request.user.shopping_cart.create(recipe=recipe)
            serializer = RecipeShortSerializer(recipe)
            return Response(
                serializer.data,
                status=status.HTTP_201_CREATED
            )
        elif request.method == 'DELETE':
            cart_item = request.user.shopping_cart.filter(recipe=recipe)
            if not cart_item.exists():
                return Response(
                    {'errors': 'Рецепта нет в списке покупок.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            cart_item.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)

    @action(
        detail=True,
        methods=['post', 'delete'],
        url_path='favorite',
        permission_classes=[IsAuthenticatedOrReadOnly]
    )
    def favorite(self, request, pk=None):
        if not request.user.is_authenticated:
            return Response(
                {'detail': 'Учетная запись не авторизована.'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        recipe = self.get_object()

        if request.method == 'POST':
            if request.user.favorites.filter(recipe=recipe).exists():
                return Response(
                    {'errors': 'Рецепт уже в избранном.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            request.user.favorites.create(recipe=recipe)
            serializer = RecipeShortSerializer(recipe)
            return Response(
                serializer.data,
                status=status.HTTP_201_CREATED
            )
        elif request.method == 'DELETE':
            fav_item = request.user.favorites.filter(recipe=recipe)
            if not fav_item.exists():
                return Response(
                    {'errors': 'Рецепта нет в избранном.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            fav_item.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)

    @action(
        detail=True,
        methods=['post'],
        permission_classes=[IsAuthenticatedOrReadOnly]
    )
    def add_to_favorites(self, request, pk=None):
        recipe = self.get_object()
        if request.user.favorites.filter(recipe=recipe).exists():
            raise serializers.ValidationError(
                {'errors': 'Рецепт уже добавлен в избранное.'}
            )
        request.user.favorites.add(recipe)
        serializer = self.get_serializer(recipe)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


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
        return self.request.user.follower.all()

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
        serializer = UserDetailSerializer(
            request.user,
            context={'request': request}
        )
        return Response(
            serializer.data,
            status=status.HTTP_200_OK
        )


class UserAvatarUpdateView(generics.UpdateAPIView):
    serializer_class = UserAvatarSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user

    def update(self, request, *args, **kwargs):
        if 'avatar' not in request.data:
            return Response(
                {'avatar': 'Поле avatar является обязательным.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        kwargs['partial'] = True
        try:
            response = super().update(request, *args, **kwargs)
            return response
        except Exception as e:
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
            return Response({
                'auth_token': token.key
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
            return Response(status=status.HTTP_204_NO_CONTENT)
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

        if request.user.follower.filter(author=author).exists():
            return Response(
                {'errors': 'Вы уже подписаны на этого пользователя.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = FollowSerializer(
            data={
                'user': request.user.id,
                'author': author.id
            }, context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        follow = serializer.save(user=request.user)

        response_serializer = SubscriptionSerializer(
            follow,
            context={'request': request}
        )

        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED
        )

    def delete(self, request, id):
        author = get_object_or_404(get_user_model(), id=id)
        follow = request.user.follower.filter(author=author)
        if not follow.exists():
            return Response(
                {'errors': 'Вы не были подписаны на этого пользователя.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        follow.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class UserListView(ListAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    pagination_class = UserPagination


class UserDetailView(RetrieveAPIView):
    queryset = User.objects.all()
    serializer_class = UserDetailSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]


class UserListCreateView(generics.ListCreateAPIView):
    queryset = User.objects.all()
    permission_classes = [permissions.AllowAny]
    pagination_class = UserPagination

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return UserCreateSerializer
        return UserSerializer


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
