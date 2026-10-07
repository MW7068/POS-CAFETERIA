"""Prueba de estructura inicial, NO validacion del dominio aun no implementado."""

from pathlib import Path
import unittest


class StructureTests(unittest.TestCase):
    def test_required_files_exist(self):
        root = Path(__file__).resolve().parents[1]
        paths = (
            ".github/PULL_REQUEST_TEMPLATE.md", "src/__init__.py", "src/main.py",
            "src/domain/__init__.py", "src/domain/exceptions.py", "src/domain/models.py",
            "src/services/__init__.py", "src/services/app_service.py", "src/services/data_manager.py",
            "src/ui/__init__.py", "src/ui/cli_interface.py", "tests/test_domain.py",
            ".gitignore", "architecture.md", "README.md",
        )
        for path in paths:
            with self.subTest(path=path):
                self.assertTrue((root / path).is_file(), path)
