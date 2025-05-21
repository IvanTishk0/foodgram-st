import json
from django.core.management.base import BaseCommand, CommandError
from recipes.models import Ingredient
from django.db import transaction


class Command(BaseCommand):
    help = 'Loads ingredients from a JSON file into the database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--json_path',
            type=str,
            default='/app/data/ingredients.json',
            help='Path to the JSON file with ingredients'
        )

    def handle(self, *args, **options):
        json_file_path = options['json_path']

        try:
            with open(json_file_path, 'r', encoding='utf-8') as f:
                ingredients_data = json.load(f)
        except FileNotFoundError:
            raise CommandError(f'File not found: {json_file_path}')
        except json.JSONDecodeError:
            raise CommandError(f'Error decoding JSON: {json_file_path}')

        created_count = 0
        updated_count = 0
        skipped_count = 0

        with transaction.atomic():
            for item in ingredients_data:
                name = item.get('name')
                measurement_unit = item.get('measurement_unit')

                if not name or not measurement_unit:
                    skipped_count += 1
                    continue

                try:
                    _, created = Ingredient.objects.update_or_create(
                        name=name,
                        defaults={'measurement_unit': measurement_unit}
                    )
                    if created:
                        created_count += 1
                    else:
                        updated_count += 1
                except Exception:
                    skipped_count += 1
