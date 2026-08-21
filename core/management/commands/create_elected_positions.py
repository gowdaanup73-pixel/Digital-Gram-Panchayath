from django.core.management.base import BaseCommand
from core.models import ElectedPosition

class Command(BaseCommand):
    help = 'Creates initial elected positions'

    def handle(self, *args, **options):
        positions = [
            {
                'name': 'Gram Panchayat President',
                'description': 'Leads the Gram Panchayat and oversees all development activities.',
                'term_length': 5
            },
            {
                'name': 'Vice President',
                'description': 'Assists the president and acts as president in their absence.',
                'term_length': 5
            },
            {
                'name': 'Ward Member',
                'description': 'Represents a specific ward in the Gram Panchayat.',
                'term_length': 5
            },
            {
                'name': 'Development Committee Chair',
                'description': 'Leads the committee responsible for planning and implementing development projects.',
                'term_length': 3
            },
            {
                'name': 'Social Justice Committee Chair',
                'description': 'Leads the committee ensuring social justice and welfare of underprivileged sections.',
                'term_length': 3
            }
        ]

        for pos in positions:
            ElectedPosition.objects.get_or_create(
                name=pos['name'],
                defaults={
                    'description': pos['description'],
                    'term_length': pos['term_length']
                }
            )
            self.stdout.write(self.style.SUCCESS(f'Successfully created position: {pos["name"]}'))