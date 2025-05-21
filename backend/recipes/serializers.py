from rest_framework import serializers
from .models import Ingredient, Recipe, RecipeIngredient
from drf_extra_fields.fields import Base64ImageField
from users.models import User, Follow


class IngredientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ingredient
        fields = ('id', 'name', 'measurement_unit')


class RecipeIngredientSerializer(serializers.ModelSerializer):
    id = serializers.PrimaryKeyRelatedField(
        queryset=Ingredient.objects.all(),
        source='ingredient.id'
    )
    name = serializers.CharField(
        source='ingredient.name',
        read_only=True
    )
    measurement_unit = serializers.CharField(
        source='ingredient.measurement_unit',
        read_only=True
    )

    class Meta:
        model = RecipeIngredient
        fields = ('id', 'name', 'measurement_unit', 'amount')


class RecipeIngredientWriteSerializer(serializers.ModelSerializer):
    id = serializers.PrimaryKeyRelatedField(
        queryset=Ingredient.objects.all(),
        source='ingredient'
    )
    amount = serializers.IntegerField(min_value=1)

    class Meta:
        model = RecipeIngredient
        fields = ('id', 'amount')

class RecipeIngredientReadSerializer(serializers.ModelSerializer):
    id = serializers.ReadOnlyField(source='ingredient.id')
    name = serializers.ReadOnlyField(source='ingredient.name')
    measurement_unit = serializers.ReadOnlyField(
        source='ingredient.measurement_unit'
    )
    amount = serializers.IntegerField()

    class Meta:
        model = RecipeIngredient
        fields = ('id', 'name', 'measurement_unit', 'amount')


class AuthorRecipeSerializer(serializers.ModelSerializer):
    avatar = Base64ImageField(required=False, allow_null=True)
    is_subscribed = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            'id',
            'username',
            'first_name',
            'last_name',
            'avatar',
            'is_subscribed'
        )

    def get_is_subscribed(self, obj):
        request = self.context.get('request')
        if request is None or not request.user.is_authenticated:
            return False
        return Follow.objects.filter(user=request.user, author=obj).exists()


class RecipeSerializer(serializers.ModelSerializer):
    author = AuthorRecipeSerializer(read_only=True)
    ingredients = RecipeIngredientReadSerializer(
        source='recipe_ingredients',
        many=True,
        read_only=True
    )
    is_favorited = serializers.SerializerMethodField()
    is_in_shopping_cart = serializers.SerializerMethodField()

    class Meta:
        model = Recipe
        fields = (
            'id', 'author', 'name', 'image', 'text',
            'ingredients', 'cooking_time', 'pub_date',
            'is_favorited', 'is_in_shopping_cart'
        )

    def get_is_favorited(self, obj):
        request = self.context.get('request')
        if request is None or not request.user.is_authenticated:
            return False
        return obj.favorited_by.filter(user=request.user).exists()

    def get_is_in_shopping_cart(self, obj):
        request = self.context.get('request')
        if request is None or not request.user.is_authenticated:
            return False
        return obj.in_shopping_carts.filter(user=request.user).exists()


class RecipeCreateSerializer(serializers.ModelSerializer):
    ingredients_write = RecipeIngredientWriteSerializer(
        many=True,
        write_only=True,
        source='recipe_ingredients_data_for_write'
    )
    ingredients = RecipeIngredientReadSerializer(
        many=True,
        read_only=True,
        source='recipe_ingredients'
    )
    image = Base64ImageField()

    class Meta:
        model = Recipe
        fields = (
            'id', 'ingredients', 'ingredients_write', 'image', 'name', 'text', 'cooking_time'
        )

    def validate_cooking_time(self, value):
        if value < 1:
            raise serializers.ValidationError(
                'Время приготовления должно быть не менее 1 минуты.'
            )
        return value

    def create(self, validated_data):
        ingredients_data_from_payload = validated_data.pop(
            'recipe_ingredients_data_for_write'
        )
        recipe = Recipe.objects.create(**validated_data)
        for ingredient_item in ingredients_data_from_payload:
            RecipeIngredient.objects.create(
                recipe=recipe,
                ingredient=ingredient_item['ingredient'],
                amount=ingredient_item['amount']
            )
        return recipe


class RecipeUpdateSerializer(RecipeCreateSerializer):
    ingredients_write = RecipeIngredientWriteSerializer(
        many=True,
        write_only=True,
        source='recipe_ingredients_data_for_write',
        required=False 
    )
    image = Base64ImageField(required=False, allow_null=True)

    def update(self, instance, validated_data):
        ingredients_data_list = validated_data.pop(
            'recipe_ingredients_data_for_write', None
        )

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        instance.save()

        if ingredients_data_list is not None:
            instance.recipe_ingredients.all().delete()
            for ingredient_data in ingredients_data_list:
                RecipeIngredient.objects.create(
                    recipe=instance,
                    ingredient=ingredient_data['ingredient'],
                    amount=ingredient_data['amount']
                )
        return instance
