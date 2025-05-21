from django.test import TestCase

class SimpleTestCase(TestCase):
    def test_basic_addition(self):
        """Простой тест для проверки работы pytest."""
        self.assertEqual(1 + 1, 2)


