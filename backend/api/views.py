from rest_framework import viewsets, permissions, status, generics
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import (
    IsAuthenticatedOrReadOnly, BasePermission
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
    CustomAuthTokenSerializer
)

User = get_user_model()


class IngredientViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Ingredient.objects.all()
    serializer_class = IngredientSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        queryset = super().get_queryset()
        name = self.request.query_params.get('name')
        if name:
            queryset = queryset.filter(name__istartswith=name)
        return queryset

    def list(self, request, *args, **kwargs):
        name = request.query_params.get('name')
        queryset = self.filter_queryset(self.get_queryset())

        if name:
            serializer = self.get_serializer(queryset, many=True)
            return Response(serializer.data)


class RecipePagination(PageNumberPagination):
    page_size_query_param = 'limit'


class IsAuthorOrReadOnly(BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return True
        return obj.author == request.user


class RecipeViewSet(viewsets.ModelViewSet):
    queryset = Recipe.objects.all()
    pagination_class = RecipePagination
    permission_classes = [IsAuthorOrReadOnly]

    def get_serializer_class(self):
        if self.action == 'create':
            return RecipeCreateSerializer
        if self.action in ['update', 'partial_update']:
            return RecipeUpdateSerializer
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
        serializer.save(author=self.request.user)

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
        methods=['post'],
        url_path='shopping_cart',
        permission_classes=[IsAuthenticatedOrReadOnly]
    )
    def add_to_shopping_cart(self, request, pk=None):
        if not request.user.is_authenticated:
            return Response(
                {'detail': 'Учетная запись не авторизована.'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        recipe = self.get_object()
        if request.user.shopping_cart.filter(recipe=recipe).exists():
            return Response(
                {'errors': 'Рецепт уже в списке покупок.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        request.user.shopping_cart.create(recipe=recipe)
        return Response(
            {'success': 'Рецепт добавлен в список покупок.'},
            status=status.HTTP_201_CREATED
        )

    @action(
        detail=True,
        methods=['delete'],
        url_path='remove-shopping-cart',
        permission_classes=[IsAuthenticatedOrReadOnly]
    )
    def remove_from_shopping_cart(self, request, pk=None):
        if not request.user.is_authenticated:
            return Response(
                {'detail': 'Учетная запись не авторизована.'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        recipe = self.get_object()
        cart_item = request.user.shopping_cart.filter(recipe=recipe)
        if not cart_item.exists():
            return Response(
                {'errors': 'Рецепта нет в списке покупок.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        cart_item.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(
        detail=True,
        methods=['post'],
        url_path='favorite',
        permission_classes=[IsAuthenticatedOrReadOnly]
    )
    def add_to_favorite(self, request, pk=None):
        if not request.user.is_authenticated:
            return Response(
                {'detail': 'Учетная запись не авторизована.'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        recipe = self.get_object()
        if request.user.favorites.filter(recipe=recipe).exists():
            return Response(
                {'errors': 'Рецепт уже в избранном.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        request.user.favorites.create(recipe=recipe)
        serializer = RecipeSerializer(
            recipe, context={'request': request}
        )
        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED
        )

    @action(
        detail=True,
        methods=['delete'],
        url_path='remove-favorite',
        permission_classes=[IsAuthenticatedOrReadOnly]
    )
    def remove_from_favorite(self, request, pk=None):
        if not request.user.is_authenticated:
            return Response(
                {'detail': 'Учетная запись не авторизована.'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        recipe = self.get_object()
        fav_item = request.user.favorites.filter(recipe=recipe)
        if not fav_item.exists():
            return Response(
                {'errors': 'Рецепта нет в избранном.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        fav_item.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


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
        if request.user.follower.filter(author=author).exists():
            return Response(
                {'errors': 'Вы уже подписаны на этого пользователя.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        follow = request.user.follower.create(author=author)
        serializer = SubscriptionSerializer(
            follow,
            context={'request': request}
        )
        return Response(serializer.data, status=status.HTTP_201_CREATED)

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
