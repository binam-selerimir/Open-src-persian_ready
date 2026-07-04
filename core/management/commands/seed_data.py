"""
core/management/commands/seed_data.py
========================================
Django management command: seed the database with starter Page objects.

Usage:
    python manage.py seed_data

Creates three flat content pages (Philosophy, Licensing Guide, Get Involved)
that are shown in the site navigation bar.  Uses get_or_create so the command
is idempotent — running it multiple times has no effect after the first run.

Intended for use during initial project setup, CI pipelines, and staging
environment provisioning.
"""

from django.core.management.base import BaseCommand
from core.models import Page


class Command(BaseCommand):
    help = 'Seed the database with sample Page objects for testing.'

    def handle(self, *args, **options):

        # Define the pages to create.  Each dict maps directly to Page field names.
        # show_in_nav=True means the page link appears in the site navigation bar.
        # nav_order controls the display position (lower number = further left/first).
        pages = [
            {
                'title_en': 'Philosophy of Free Software',
                'slug': 'philosophy',
                'show_in_nav': True,
                'nav_order': 1,
                'body_en': (
                    'Free software is a matter of liberty, not price. To understand the concept, '
                    'you should think of "free" as in "free speech," not as in "free beer."\n\n'
                    'Free software gives users four essential freedoms: the freedom to run the program '
                    'for any purpose, the freedom to study and modify it, the freedom to redistribute '
                    'copies, and the freedom to distribute copies of your modified versions.\n\n'
                    'A program is free software if the program\'s users have all these freedoms. '
                    'Users should have control over the software they use — not the other way around.\n\n'
                    'The philosophy of free software has influenced not just technology but also '
                    'culture, law, and academia. The Creative Commons movement, Wikipedia, and '
                    'open access publishing all draw on ideas first articulated by the free '
                    'software community.\n\n'
                    'We encourage you to read the GNU Manifesto, available on the GNU Project '
                    'website, for a deeper exploration of these ideas and their implications.'
                ),
            },
            {
                'title_en': 'Licensing Guide',
                'slug': 'licensing',
                'show_in_nav': True,
                'nav_order': 2,
                'body_en': (
                    'Choosing the right license is one of the most important decisions you make '
                    'when releasing free software. This guide summarises the most common options.\n\n'
                    'GNU General Public License (GPL)\n\n'
                    'The GPL is the most widely used free software license. It guarantees users '
                    'the four freedoms and requires that any modified versions also be distributed '
                    'under the GPL. This "copyleft" provision ensures that the software and its '
                    'derivatives remain free.\n\n'
                    'GNU Lesser General Public License (LGPL)\n\n'
                    'The LGPL is intended mainly for software libraries. It allows proprietary '
                    'applications to link against the library without being subject to copyleft, '
                    'while ensuring the library itself remains free.\n\n'
                    'GNU Affero General Public License (AGPL)\n\n'
                    'The AGPL extends the GPL to cover the case where software is used to '
                    'provide a network service. If you modify AGPL software and run it on a server, '
                    'you must make your modified source code available to the users of that service.\n\n'
                    'MIT / BSD / Apache Licenses\n\n'
                    'These permissive licenses allow software to be included in proprietary products '
                    'without copyleft obligations. While they qualify as free software licenses, '
                    'they do not protect against proprietarisation of derivatives.'
                ),
            },
            {
                'title_en': 'Get Involved',
                'slug': 'get-involved',
                'show_in_nav': True,
                'nav_order': 3,
                'body_en': (
                    'The free software movement depends on participation. Whatever your skills and '
                    'background, there is something meaningful you can contribute.\n\n'
                    'For developers: Contribute code to free software projects. Fix bugs, add '
                    'features, improve documentation, write tests. Many projects tag issues as '
                    '"good first issue" for new contributors.\n\n'
                    'For writers: Help write or translate documentation. Many projects need manuals, '
                    'tutorials, and how-to guides. Clear documentation lowers the barrier for new users.\n\n'
                    'For designers: Free software projects often need interface design, icon sets, '
                    'and website improvements. Accessibility work is especially valuable.\n\n'
                    'For advocates: Talk about free software with friends, family, and colleagues. '
                    'Write to your elected representatives. Support organisations that defend '
                    'software freedom.\n\n'
                    'For everyone: Use free software in your daily life. Every user counts. '
                    'When you use free software, you demonstrate that it works and you help '
                    'build the community around it.'
                ),
            },
        ]

        # get_or_create makes this command idempotent: safe to run multiple times.
        for data in pages:
            page, created = Page.objects.get_or_create(slug=data['slug'], defaults=data)
            status = 'Created' if created else 'Already exists'
            self.stdout.write(f'  [{status}] Page: {data["title_en"]}')

        self.stdout.write(self.style.SUCCESS('\nDone! Sample data seeded successfully.'))
