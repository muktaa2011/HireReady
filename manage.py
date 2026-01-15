#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


def main():
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'resume_generator.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()

from app.models import ResumeTemplate

templates = [
    {
        "name": "Modern Tech",
        "slug": "modern-tech",
        "description": "Clean, developer-friendly with skill-focused typography"
    },
    {
        "name": "Professional Classic",
        "slug": "professional-classic",
        "description": "Traditional layout ideal for corporate roles"
    },
    {
        "name": "Amrutvahini College",
        "slug": "creative-minimal",
        "description": "Minimal modern layout"
    },
]

for t in templates:
    ResumeTemplate.objects.get_or_create(
        slug=t["slug"],
        defaults={
            "name": t["name"],
            "description": t["description"]
        }
    )
