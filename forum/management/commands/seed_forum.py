from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils.text import slugify

from forum.models import Board, Thread, ForumPost

User = get_user_model()


class Command(BaseCommand):
    help = 'Seed the forum with sample boards, threads, and posts'

    def handle(self, *args, **options):
        user = User.objects.filter(is_superuser=True).first()
        if not user:
            self.stderr.write('No superuser found. Create one first.')
            return

        boards_data = [
            {
                'name_en': 'General Discussion',
                'name_fa': '\u0628\u062d\u062b\u062b \u0627\u0635\u0644\u06cc',
                'slug': 'general',
                'description_en': 'Talk about anything related to open-source software.',
                'description_fa': '\u062f\u0631\u0628\u0627\u0631\u0647 \u0647\u0631 \u0627\u0635\u0644\u06cc \u0645\u0631\u062a\u0628\u0637 \u0628\u0627 \u0646\u0631\u0645\u0627\u0641\u0632\u0627\u0646 \u0645\u0646\u0628\u0639 \u0628\u0627\u0632 \u0633\u0648\u0627\u0644 \u06a9\u0646\u06cc\u062f.',
                'order': 1,
            },
            {
                'name_en': 'Help & Support',
                'name_fa': '\u06a9\u0645\u06a9 \u0648 \u067e\u0634\u062a\u06cc\u0628\u0627\u0646\u06cc',
                'slug': 'help',
                'description_en': 'Get help with Linux, packages, and configuration.',
                'description_fa': '\u0627\u0637\u0644\u0627\u0639\u0627\u062a \u062f\u0631 \u0628\u0627\u0631\u0647 \u0644\u06cc\u0646\u0648\u06a9\u0633\u060c \u0628ست\u0647\u0647\u0627 \u0648 \u067e\u06cc\u06a9\u0631\u0628\u0646\u062f\u06cc.',
                'order': 2,
            },
            {
                'name_en': 'Projects & Showcase',
                'name_fa': '\u067e\u0631\u0648\u0698\u0647\u200c\u0647\u0627 \u0648 \u0646\u0645\u0627\u06cc\u0634\u06af\u0627\u0647',
                'slug': 'projects',
                'description_en': 'Showcase your open-source projects and get feedback.',
                'description_fa': '\u067e\u0631\u0648\u0698\u0647\u200c\u0647\u0627\u06cc \u0645\u0646\u0628\u0639 \u0628\u0627\u0632 \u0633\u0648\u0627\u0644 \u062e\u0648\u062f \u0631\u0627 \u0628\u0646\u0645\u0627\u06cc\u0634 \u062f\u0647\u06cc\u062f \u0648 \u0628\u0627\u0632\u062e\u0648\u0631\u062f\u0646\u062f\u0647 \u062f\u0631\u06cc\u0627\u0641\u062a \u06a9\u0646\u06cc\u062f.',
                'order': 3,
            },
            {
                'name_en': 'Off-Topic',
                'name_fa': '\u0628\u062d\u0633\u062b \u0627\u0635\u0644\u06cc',
                'slug': 'off-topic',
                'description_en': 'Non-technical discussions and everything else.',
                'description_fa': '\u0628\u062d\u0633\u062a\u200c\u0647\u0627\u06cc \u063a\u06cc\u0631 \u0641\u0646\u06cc \u0648 \u0647\u0631 \u0622\u0646\u0686\u0647 \u062f\u0647\u0631.',
                'order': 4,
            },
        ]

        boards = []
        for data in boards_data:
            board, created = Board.objects.get_or_create(
                slug=data['slug'], defaults=data,
            )
            boards.append(board)
            status = 'CREATED' if created else 'EXISTS'
            self.stdout.write(f'  Board: {board.name_en} [{status}]')

        thread_bodies = [
            ('Welcome to the forum!', 'This is the first thread. Feel free to introduce yourself and discuss open-source topics.'),
            ('Best Linux distros for 2026?', 'What distributions are you using this year? I have been testing several and would love to hear your experiences.'),
            ('How to contribute to open source?', 'I want to start contributing but I do not know where to begin. Any tips for newcomers?'),
            ('Favorite text editors', 'Vim, Emacs, or something else? Share your setup and configuration tips.'),
            ('Setting up a home lab', 'I am building a home server for self-hosting. What hardware and software do you recommend?'),
            ('Rust vs Go for systems programming', 'Both languages are gaining traction. Which one do you prefer and why?'),
            ('Weekly learning thread', 'What did you learn this week? Share your discoveries and learning resources.'),
            ('Recommend a good monitor', 'Looking for a 27 inch 4K monitor for development. Budget is around $400.'),
            ('Open source alternatives', 'Need an open source replacement for a proprietary tool? Ask here.'),
            ('Arch Linux installation tips', 'Share your Arch installation tips and post-install configuration advice.'),
            ('Container orchestration discussion', 'Docker, Podman, Kubernetes — what is your stack for container deployment?'),
            ('Book recommendations', 'What technical books are you reading right now?'),
        ]

        replies_data = [
            [
                'Great topic! I have been using this distribution for a while now and it works perfectly for my workflow.',
                'I agree, the package manager is really well designed. The documentation is also excellent.',
                'Has anyone tried the latest version? I heard there are some significant improvements.',
                'Thanks for sharing! This is exactly what I was looking for.',
            ],
            [
                'I would recommend starting with the "good first issue" label on GitHub repositories you use daily.',
                'Documentation contributions are always welcome and a great way to learn the codebase.',
                'Do not forget to read the contribution guidelines before submitting your first pull request.',
            ],
            [
                'I switched to Neovim last year and never looked back. The Lua configuration is so much faster.',
                'Emacs with org-mode is incredibly productive once you get past the learning curve.',
                'VS Code with remote development extensions is my go-to for server work.',
            ],
        ]

        for i, board in enumerate(boards):
            for j in range(3):
                t_idx = i * 3 + j
                if t_idx >= len(thread_bodies):
                    break
                title, body = thread_bodies[t_idx]
                thread, created = Thread.objects.get_or_create(
                    board=board,
                    slug=slugify(title, allow_unicode=True) if j == 0 else f'{board.slug}-thread-{j+1}',
                    defaults={
                        'title': title,
                        'author': user,
                        'is_sticky': (j == 0),
                    },
                )
                if created:
                    ForumPost.objects.create(
                        thread=thread,
                        author=user,
                        body=body,
                        is_first_post=True,
                    )
                    reply_pool = replies_data[t_idx % len(replies_data)]
                    for reply_body in reply_pool:
                        ForumPost.objects.create(
                            thread=thread,
                            author=user,
                            body=reply_body,
                        )
                    self.stdout.write(f'    Thread: {title} [CREATED]')
                else:
                    self.stdout.write(f'    Thread: {title} [EXISTS]')

        self.stdout.write(self.style.SUCCESS('Forum seeding complete.'))
