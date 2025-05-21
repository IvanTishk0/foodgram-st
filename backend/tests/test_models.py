"""Tests for Django models."""
import pytest
from django.test import TestCase


@pytest.mark.django_db
def test_database_access():
    """Test that we can access the database."""
    from django.contrib.auth import get_user_model
    User = get_user_model()
    assert User.objects.count() == 0


class IngredientModelTests(TestCase):
    """Tests for the Ingredient model."""

    def test_create_ingredient(self):
        """Test creating a new ingredient."""
        from recipes.models import Ingredient
        ingredient = Ingredient.objects.create(
            name='Test Ingredient',
            measurement_unit='g'
        )
        self.assertEqual(ingredient.name, 'Test Ingredient')
        self.assertEqual(ingredient.measurement_unit, 'g') 