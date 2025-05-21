from django.shortcuts import render
from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from .models import Ingredient, Recipe, ShoppingCart, Favorite
from .serializers import IngredientSerializer, RecipeSerializer, RecipeCreateSerializer, RecipeUpdateSerializer
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticatedOrReadOnly, BasePermission
from rest_framework import filters
from rest_framework.decorators import action
from django.http import HttpResponse

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
        else:
            page = self.paginate_queryset(queryset)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)

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
        is_in_shopping_cart = self.request.query_params.get('is_in_shopping_cart')
        user = self.request.user

        if author:
            queryset = queryset.filter(author__id=author)
        if is_favorited in ('1', 1, True, 'true') and user.is_authenticated:
            queryset = queryset.filter(favorited_by__user=user)
        if is_in_shopping_cart in ('1', 1, True, 'true') and user.is_authenticated:
            queryset = queryset.filter(in_shopping_carts__user=user)
        return queryset

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    @action(detail=True, methods=['get'], url_path='get-link')
    def short_link(self, request, pk=None):
        recipe = self.get_object()
        short_url = request.build_absolute_uri(f'/recipes/{recipe.id}/')
        return Response({'short-link': short_url})

    @action(detail=False, methods=['get'], url_path='download_shopping_cart', permission_classes=[IsAuthenticatedOrReadOnly])
    def download_shopping_cart(self, request):
        if not request.user.is_authenticated:
            return Response({'detail': 'Учетная запись не авторизована.'}, status=status.HTTP_401_UNAUTHORIZED)
        ingredients = {}
        for item in request.user.shopping_cart.select_related('recipe').all():
            for ri in item.recipe.recipe_ingredients.select_related('ingredient').all():
                name = ri.ingredient.name
                unit = ri.ingredient.measurement_unit
                amount = ri.amount
                key = (name, unit)
                ingredients[key] = ingredients.get(key, 0) + amount
        lines = [f'{name} ({unit}) — {amount}' for (name, unit), amount in ingredients.items()]
        content = '\n'.join(lines)
        response = HttpResponse(content, content_type='text/plain')
        response['Content-Disposition'] = 'attachment; filename="shopping_list.txt"'
        return response

    @action(detail=True, methods=['post'], url_path='shopping_cart', permission_classes=[IsAuthenticatedOrReadOnly])
    def add_to_shopping_cart(self, request, pk=None):
        if not request.user.is_authenticated:
            return Response({'detail': 'Учетная запись не авторизована.'}, status=status.HTTP_401_UNAUTHORIZED)
        recipe = self.get_object()
        if ShoppingCart.objects.filter(user=request.user, recipe=recipe).exists():
            return Response({'errors': 'Рецепт уже в списке покупок.'}, status=status.HTTP_400_BAD_REQUEST)
        ShoppingCart.objects.create(user=request.user, recipe=recipe)
        return Response({'success': 'Рецепт добавлен в список покупок.'}, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['delete'], url_path='remove-shopping-cart', permission_classes=[IsAuthenticatedOrReadOnly])
    def remove_from_shopping_cart(self, request, pk=None):
        if not request.user.is_authenticated:
            return Response({'detail': 'Учетная запись не авторизована.'}, status=status.HTTP_401_UNAUTHORIZED)
        recipe = self.get_object()
        cart_item = ShoppingCart.objects.filter(user=request.user, recipe=recipe)
        if not cart_item.exists():
            return Response({'errors': 'Рецепта нет в списке покупок.'}, status=status.HTTP_400_BAD_REQUEST)
        cart_item.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post'], url_path='favorite', permission_classes=[IsAuthenticatedOrReadOnly])
    def add_to_favorite(self, request, pk=None):
        if not request.user.is_authenticated:
            return Response({'detail': 'Учетная запись не авторизована.'}, status=status.HTTP_401_UNAUTHORIZED)
        recipe = self.get_object()
        if Favorite.objects.filter(user=request.user, recipe=recipe).exists():
            return Response({'errors': 'Рецепт уже в избранном.'}, status=status.HTTP_400_BAD_REQUEST)
        Favorite.objects.create(user=request.user, recipe=recipe)
        serializer = RecipeSerializer(recipe, context={'request': request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['delete'], url_path='remove-favorite', permission_classes=[IsAuthenticatedOrReadOnly])
    def remove_from_favorite(self, request, pk=None):
        if not request.user.is_authenticated:
            return Response({'detail': 'Учетная запись не авторизована.'}, status=status.HTTP_401_UNAUTHORIZED)
        recipe = self.get_object()
        fav_item = Favorite.objects.filter(user=request.user, recipe=recipe)
        if not fav_item.exists():
            return Response({'errors': 'Рецепта нет в избранном.'}, status=status.HTTP_400_BAD_REQUEST)
        fav_item.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
