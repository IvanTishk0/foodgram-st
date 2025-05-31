from rest_framework import serializers
from recipes.models import Ingredient, Recipe, RecipeIngredient
from drf_extra_fields.fields import Base64ImageField
from users.models import User, Follow
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.validators import RegexValidator

MIN_INGREDIENT_AMOUNT = 1
MAX_INGREDIENT_AMOUNT = 32000
MIN_COOKING_TIME = 1
MAX_COOKING_TIME = 32000


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
    amount = serializers.IntegerField(
        min_value=MIN_INGREDIENT_AMOUNT,
        max_value=MAX_INGREDIENT_AMOUNT
    )

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
        return request.user.following.filter(author=obj).exists()


class RecipeSerializer(serializers.ModelSerializer):
    author = AuthorRecipeSerializer(read_only=True)
    ingredients = RecipeIngredientReadSerializer(
        source='recipe_ingredients',
        many=True,
        read_only=True
    )
    is_favorited = serializers.SerializerMethodField()
    is_in_shopping_cart = serializers.SerializerMethodField()
    cooking_time = serializers.IntegerField(
        min_value=MIN_COOKING_TIME,
        max_value=MAX_COOKING_TIME
    )

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
        return request.user.favorites.filter(recipe=obj).exists()

    def get_is_in_shopping_cart(self, obj):
        request = self.context.get('request')
        if request is None or not request.user.is_authenticated:
            return False
        return request.user.shopping_cart.filter(recipe=obj).exists()


class RecipeCreateSerializer(serializers.ModelSerializer):
    ingredients = RecipeIngredientWriteSerializer(
        many=True,
        write_only=True,
        source='recipe_ingredients_data_for_write',
        allow_empty=False
    )
    ingredients_read = RecipeIngredientReadSerializer(
        many=True,
        read_only=True,
        source='recipe_ingredients'
    )
    image = Base64ImageField()
    cooking_time = serializers.IntegerField(
        min_value=MIN_COOKING_TIME,
        max_value=MAX_COOKING_TIME
    )

    class Meta:
        model = Recipe
        fields = (
            'id',
            'ingredients',
            'ingredients_read',
            'image',
            'name',
            'text',
            'cooking_time'
        )

    def _create_recipe_ingredients(self, recipe, ingredients_data):
        recipe_ingredients = [
            RecipeIngredient(
                recipe=recipe,
                ingredient=ingredient_item['ingredient'],
                amount=ingredient_item['amount']
            )
            for ingredient_item in ingredients_data
        ]
        RecipeIngredient.objects.bulk_create(recipe_ingredients)

    def create(self, validated_data):
        ingredients_data_from_payload = validated_data.pop(
            'recipe_ingredients_data_for_write'
        )
        recipe = Recipe.objects.create(**validated_data)
        self._create_recipe_ingredients(recipe, ingredients_data_from_payload)
        return recipe


class RecipeUpdateSerializer(RecipeCreateSerializer):
    ingredients = RecipeIngredientWriteSerializer(
        many=True,
        write_only=True,
        source='recipe_ingredients_data_for_write',
        required=False
    )
    ingredients_read = RecipeIngredientReadSerializer(
        many=True,
        read_only=True,
        source='recipe_ingredients'
    )
    image = Base64ImageField(required=False, allow_null=True)

    class Meta(RecipeCreateSerializer.Meta):
        fields = (
            'id',
            'ingredients',
            'ingredients_read',
            'image',
            'name',
            'text',
            'cooking_time'
        )
        extra_kwargs = {
            'name': {'required': False},
            'text': {'required': False},
            'cooking_time': {'required': False},
            'ingredients_read': {'read_only': True}
        }

    def validate(self, attrs):
        if self.instance is not None:
            if 'ingredients' not in self.initial_data:
                raise serializers.ValidationError(
                    {'ingredients': [
                        'Поле ingredients является обязательным при обновлении рецепта.'
                    ]}
                )
            if ('ingredients' in self.initial_data
                and not self.initial_data['ingredients']):
                raise serializers.ValidationError(
                    {'ingredients': [
                        'Список ингредиентов не может быть пустым.'
                    ]}
                )
        return super().validate(attrs)

    def update(self, instance, validated_data):
        ingredients_data_list = validated_data.pop(
            'recipe_ingredients_data_for_write', None
        )

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()

        if ingredients_data_list is not None:
            instance.recipe_ingredients.all().delete()
            self._create_recipe_ingredients(instance, ingredients_data_list)
        return instance


class CustomAuthTokenSerializer(serializers.Serializer):
    email = serializers.EmailField(label="Email")
    password = serializers.CharField(
        label="Password",
        style={'input_type': 'password'},
        trim_whitespace=False
    )

    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')

        if email and password:
            user = authenticate(
                request=self.context.get('request'),
                username=email, password=password
            )

            if not user:
                msg = 'Неверный email или пароль'
                raise serializers.ValidationError(msg, code='authorization')

            if not user.is_active:
                msg = 'Пользователь неактивен'
                raise serializers.ValidationError(msg, code='authorization')
        else:
            msg = 'Необходимо указать email и пароль'
            raise serializers.ValidationError(msg, code='authorization')

        attrs['user'] = user
        return attrs


class UserSerializer(serializers.ModelSerializer):
    avatar = Base64ImageField(required=False, allow_null=True)

    class Meta:
        model = User
        fields = (
            'id',
            'username',
            'email',
            'first_name',
            'last_name',
            'avatar'
        )


class UserCreateSerializer(serializers.ModelSerializer):
    avatar = Base64ImageField(
        required=False,
        allow_null=True
    )
    email = serializers.EmailField(
        max_length=254,
        required=True
    )
    username = serializers.CharField(
        max_length=150,
        required=True,
        validators=[RegexValidator(
            regex=r'^[\w.@+-]+$',
            message='Недопустимые символы в username.'
        )]
    )
    first_name = serializers.CharField(max_length=150, required=True)
    last_name = serializers.CharField(max_length=150, required=True)
    password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password]
    )

    class Meta:
        model = User
        fields = (
            'id',
            'email',
            'username',
            'first_name',
            'last_name',
            'password',
            'avatar'
        )
        read_only_fields = ('id',)

    def validate(self, data):
        if User.objects.filter(username=data['username']).exists():
            raise serializers.ValidationError(
                {'username': 'Пользователь с таким именем уже существует'}
            )
        if User.objects.filter(email=data['email']).exists():
            raise serializers.ValidationError(
                {'email': 'Пользователь с таким email уже существует'}
            )
        return data

    def create(self, validated_data):
        try:
            avatar = validated_data.pop('avatar', None)
            user = User.objects.create_user(
                email=validated_data['email'],
                username=validated_data['username'],
                first_name=validated_data['first_name'],
                last_name=validated_data['last_name'],
                password=validated_data['password']
            )
            if avatar:
                user.avatar = avatar
                user.save()

            from rest_framework.authtoken.models import Token
            token, _ = Token.objects.get_or_create(user=user)

            self.token = token.key
            return user
        except Exception as e:
            raise serializers.ValidationError(str(e))

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        ret['auth_token'] = self.token
        return ret


class FollowSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
    author = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())

    class Meta:
        model = Follow
        fields = ('id', 'user', 'author')

    def validate_author(self, value):
        if self.context['request'].user == value:
            raise serializers.ValidationError(
                'Нельзя подписаться на самого себя.'
            )
        if self.context['request'].user.follower.filter(author=value).exists():
            raise serializers.ValidationError(
                'Вы уже подписаны на этого пользователя.'
            )
        return value

    def create(self, validated_data):
        user = validated_data.get('user')
        author = validated_data.get('author')
        follow = Follow.objects.create(user=user, author=author)
        return follow


class SetPasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(required=True)
    new_password = serializers.CharField(
        required=True,
        validators=[validate_password]
    )


class SubscriptionSerializer(serializers.ModelSerializer):
    recipes = serializers.SerializerMethodField()
    recipes_count = serializers.SerializerMethodField()
    email = serializers.EmailField(
        source='author.email',
        read_only=True
    )
    id = serializers.IntegerField(
        source='author.id',
        read_only=True
    )
    username = serializers.CharField(
        source='author.username',
        read_only=True
    )
    first_name = serializers.CharField(
        source='author.first_name',
        read_only=True
    )
    last_name = serializers.CharField(
        source='author.last_name',
        read_only=True
    )
    avatar = Base64ImageField(
        source='author.avatar',
        required=False,
        allow_null=True
    )

    class Meta:
        model = Follow
        fields = (
            'id',
            'email',
            'username',
            'first_name',
            'last_name',
            'avatar',
            'recipes',
            'recipes_count'
        )

    def get_recipes(self, obj):
        request = self.context.get('request')
        recipes_limit = request.query_params.get(
            'recipes_limit') if request else None
        recipes = obj.author.recipes.all()
        if recipes_limit:
            try:
                recipes = recipes[:int(recipes_limit)]
            except ValueError:
                pass
        return RecipeSerializer(
            recipes,
            many=True,
            context=self.context).data

    def get_recipes_count(self, obj):
        return obj.author.recipes.count()
