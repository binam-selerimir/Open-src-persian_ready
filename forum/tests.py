from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from accounts.models import AuditLog

from .models import Board, ForumPost, Thread

User = get_user_model()


def _make_user(username='alice', **kwargs):
    email = kwargs.pop('email', f'{username}@example.com')
    return User.objects.create_user(username=username, email=email, password='pass1234', **kwargs)


class BoardModelTests(TestCase):
    def setUp(self):
        self.board = Board.objects.create(
            name_en='General', name_fa='\u0628\u062d\u062b\u062b',
            slug='general', description_en='General discussion',
        )

    def test_str(self):
        self.assertEqual(str(self.board), 'General')

    def test_get_absolute_url(self):
        url = self.board.get_absolute_url()
        self.assertIn('/forum/general/', url)

    def test_thread_count(self):
        self.assertEqual(self.board.thread_count, 0)
        Thread.objects.create(board=self.board, title='T1', slug='t1')
        self.assertEqual(self.board.thread_count, 1)

    def test_post_count(self):
        t = Thread.objects.create(board=self.board, title='T1', slug='t1')
        ForumPost.objects.create(thread=t, body='Hello')
        self.assertEqual(self.board.post_count, 1)

    def test_last_post(self):
        self.assertIsNone(self.board.last_post)
        t = Thread.objects.create(board=self.board, title='T1', slug='t1')
        p = ForumPost.objects.create(thread=t, body='Hello')
        self.assertEqual(self.board.last_post.pk, p.pk)

    def test_ordering(self):
        Board.objects.create(name_en='Z Board', slug='z', order=2)
        Board.objects.create(name_en='A Board', slug='a', order=0)
        boards = list(Board.objects.all())
        self.assertEqual(boards[0].slug, 'a')
        self.assertEqual(boards[1].slug, 'general')
        self.assertEqual(boards[2].slug, 'z')


class ThreadModelTests(TestCase):
    def setUp(self):
        self.board = Board.objects.create(name_en='Test', slug='test')
        self.user = _make_user('alice')

    def test_str(self):
        t = Thread.objects.create(board=self.board, title='Hello World', slug='hello')
        self.assertEqual(str(t), 'Hello World')

    def test_get_absolute_url(self):
        t = Thread.objects.create(board=self.board, title='Hello', slug='hello')
        url = t.get_absolute_url()
        self.assertIn('/forum/test/hello/', url)

    def test_slug_auto_generated(self):
        t = Thread.objects.create(board=self.board, title='My Thread Title')
        self.assertTrue(t.slug)

    def test_slug_uniqueness(self):
        Thread.objects.create(board=self.board, title='Duplicate', slug='dup')
        t2 = Thread.objects.create(board=self.board, title='Duplicate', slug='dup-1')
        self.assertTrue(t2.slug)
        self.assertNotEqual('dup', t2.slug)

    def test_sticky_ordering(self):
        Thread.objects.create(board=self.board, title='Normal', slug='normal')
        Thread.objects.create(board=self.board, title='Sticky', slug='sticky', is_sticky=True)
        threads = list(Thread.objects.filter(board=self.board))
        self.assertEqual(threads[0].slug, 'sticky')

    def test_active_filter(self):
        Thread.objects.create(board=self.board, title='Active', slug='active')
        Thread.objects.create(board=self.board, title='Deleted', slug='deleted', is_deleted=True)
        self.assertEqual(Thread.objects.filter(is_deleted=False).count(), 1)


class ForumPostModelTests(TestCase):
    def setUp(self):
        self.board = Board.objects.create(name_en='Test', slug='test')
        self.thread = Thread.objects.create(board=self.board, title='Thread', slug='thread')
        self.user = _make_user('bob')

    def test_str(self):
        p = ForumPost.objects.create(thread=self.thread, body='Hello')
        self.assertIn(f'Post #{p.pk}', str(p))

    def test_body_sanitized(self):
        p = ForumPost.objects.create(
            thread=self.thread,
            body='<script>alert("xss")</script><p>Safe</p>',
        )
        p.refresh_from_db()
        self.assertNotIn('<script>', p.body)
        self.assertIn('Safe', p.body)

    def test_first_post_updates_reply_count(self):
        ForumPost.objects.create(thread=self.thread, body='First', is_first_post=True)
        self.assertEqual(self.thread.reply_count, 0)
        ForumPost.objects.create(thread=self.thread, body='Reply 1')
        self.thread.refresh_from_db()
        self.assertEqual(self.thread.reply_count, 1)
        ForumPost.objects.create(thread=self.thread, body='Reply 2')
        self.thread.refresh_from_db()
        self.assertEqual(self.thread.reply_count, 2)

    def test_deleted_post_not_counted(self):
        ForumPost.objects.create(thread=self.thread, body='Reply', is_deleted=True)
        self.thread.refresh_from_db()
        self.assertEqual(self.thread.reply_count, 0)


class ForumIndexViewTests(TestCase):
    def setUp(self):
        self.board = Board.objects.create(
            name_en='General', slug='general', is_active=True,
        )
        Board.objects.create(
            name_en='Hidden', slug='hidden', is_active=False,
        )

    def test_index_status_code(self):
        resp = self.client.get(reverse('forum:index'))
        self.assertEqual(resp.status_code, 200)

    def test_index_shows_active_boards(self):
        resp = self.client.get(reverse('forum:index'))
        self.assertContains(resp, 'General')
        self.assertNotContains(resp, 'Hidden')

    def test_index_uses_correct_template(self):
        resp = self.client.get(reverse('forum:index'))
        self.assertTemplateUsed(resp, 'forum/index.html')


class NewBoardViewTests(TestCase):
    def setUp(self):
        cache.clear()
        self.admin = _make_user('admin', is_site_admin=True)
        self.user = _make_user('alice')

    def test_new_board_requires_login(self):
        resp = self.client.get(reverse('forum:new_board'))
        self.assertEqual(resp.status_code, 302)

    def test_new_board_requires_admin(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse('forum:new_board'))
        self.assertEqual(resp.status_code, 403)

    def test_new_board_get_admin(self):
        self.client.force_login(self.admin)
        resp = self.client.get(reverse('forum:new_board'))
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, 'forum/new_board.html')

    def test_new_board_post_creates_board(self):
        self.client.force_login(self.admin)
        resp = self.client.post(reverse('forum:new_board'), {
            'name_en': 'Test Board',
            'name_fa': '\u062a\u0635\u0645\u06cc\u0645',
            'description_en': 'A test board',
            'description_fa': '',
            'order': 0,
        })
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(Board.objects.filter(name_en='Test Board').exists())

    def test_new_board_slug_auto_generated(self):
        self.client.force_login(self.admin)
        self.client.post(reverse('forum:new_board'), {
            'name_en': 'My Board',
            'description_en': '',
            'order': 0,
        })
        board = Board.objects.get(name_en='My Board')
        self.assertEqual(board.slug, 'my-board')

    def test_new_board_creates_audit_log(self):
        self.client.force_login(self.admin)
        self.client.post(reverse('forum:new_board'), {
            'name_en': 'Audited Board',
            'description_en': '',
            'order': 0,
        })
        self.assertTrue(AuditLog.objects.filter(action='POST_CREATE').exists())


class BoardDetailViewTests(TestCase):
    def setUp(self):
        self.board = Board.objects.create(name_en='General', slug='general')

    def test_board_detail_status_code(self):
        resp = self.client.get(reverse('forum:board_detail', kwargs={'board_slug': 'general'}))
        self.assertEqual(resp.status_code, 200)

    def test_board_detail_404_for_inactive(self):
        self.board.is_active = False
        self.board.save()
        resp = self.client.get(reverse('forum:board_detail', kwargs={'board_slug': 'general'}))
        self.assertEqual(resp.status_code, 404)

    def test_board_detail_lists_threads(self):
        Thread.objects.create(board=self.board, title='Test Thread', slug='test-thread')
        resp = self.client.get(reverse('forum:board_detail', kwargs={'board_slug': 'general'}))
        self.assertContains(resp, 'Test Thread')

    def test_board_detail_hides_deleted_threads(self):
        Thread.objects.create(board=self.board, title='Deleted', slug='deleted', is_deleted=True)
        resp = self.client.get(reverse('forum:board_detail', kwargs={'board_slug': 'general'}))
        self.assertNotContains(resp, 'Deleted')


class ThreadDetailViewTests(TestCase):
    def setUp(self):
        self.board = Board.objects.create(name_en='General', slug='general')
        self.thread = Thread.objects.create(
            board=self.board, title='My Thread', slug='my-thread',
        )
        self.user = _make_user('alice')

    def test_thread_detail_status_code(self):
        resp = self.client.get(reverse('forum:thread_detail', kwargs={
            'board_slug': 'general', 'slug': 'my-thread',
        }))
        self.assertEqual(resp.status_code, 200)

    def test_thread_detail_increments_view_count(self):
        self.client.get(reverse('forum:thread_detail', kwargs={
            'board_slug': 'general', 'slug': 'my-thread',
        }))
        self.thread.refresh_from_db()
        self.assertEqual(self.thread.view_count, 1)

    def test_thread_detail_404_for_deleted(self):
        self.thread.is_deleted = True
        self.thread.save()
        resp = self.client.get(reverse('forum:thread_detail', kwargs={
            'board_slug': 'general', 'slug': 'my-thread',
        }))
        self.assertEqual(resp.status_code, 404)

    def test_thread_detail_shows_posts(self):
        ForumPost.objects.create(thread=self.thread, body='Hello world', is_first_post=True)
        resp = self.client.get(reverse('forum:thread_detail', kwargs={
            'board_slug': 'general', 'slug': 'my-thread',
        }))
        self.assertContains(resp, 'Hello world')

    def test_thread_detail_reply_form_for_authenticated(self):
        ForumPost.objects.create(thread=self.thread, body='First', is_first_post=True)
        self.client.force_login(self.user)
        resp = self.client.get(reverse('forum:thread_detail', kwargs={
            'board_slug': 'general', 'slug': 'my-thread',
        }))
        self.assertContains(resp, 'Post a Reply')

    def test_thread_detail_no_reply_form_for_anon(self):
        ForumPost.objects.create(thread=self.thread, body='First', is_first_post=True)
        resp = self.client.get(reverse('forum:thread_detail', kwargs={
            'board_slug': 'general', 'slug': 'my-thread',
        }))
        self.assertNotContains(resp, 'Post a Reply')

    def test_thread_detail_no_reply_form_for_closed(self):
        ForumPost.objects.create(thread=self.thread, body='First', is_first_post=True)
        self.thread.is_closed = True
        self.thread.save()
        self.client.force_login(self.user)
        resp = self.client.get(reverse('forum:thread_detail', kwargs={
            'board_slug': 'general', 'slug': 'my-thread',
        }))
        self.assertNotContains(resp, 'Post a Reply')
        self.assertContains(resp, 'closed')


class NewThreadViewTests(TestCase):
    def setUp(self):
        cache.clear()
        self.board = Board.objects.create(name_en='General', slug='general')
        self.user = _make_user('alice')

    def test_new_thread_get_requires_login(self):
        resp = self.client.get(reverse('forum:new_thread', kwargs={'board_slug': 'general'}))
        self.assertEqual(resp.status_code, 302)

    def test_new_thread_get_authenticated(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse('forum:new_thread', kwargs={'board_slug': 'general'}))
        self.assertEqual(resp.status_code, 200)

    def test_new_thread_post_creates_thread(self):
        self.client.force_login(self.user)
        resp = self.client.post(reverse('forum:new_thread', kwargs={'board_slug': 'general'}), {
            'title': 'Test Thread',
            'body': 'This is the body of my new thread with enough text.',
        })
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(Thread.objects.filter(title='Test Thread').exists())
        thread = Thread.objects.get(title='Test Thread')
        self.assertTrue(ForumPost.objects.filter(thread=thread, is_first_post=True).exists())

    def test_new_thread_invalid_form(self):
        self.client.force_login(self.user)
        resp = self.client.post(reverse('forum:new_thread', kwargs={'board_slug': 'general'}), {
            'title': '',
            'body': 'Short',
        })
        self.assertEqual(resp.status_code, 200)

    def test_new_thread_creates_audit_log(self):
        self.client.force_login(self.user)
        self.client.post(reverse('forum:new_thread', kwargs={'board_slug': 'general'}), {
            'title': 'Audited Thread',
            'body': 'This is a thread body with enough characters.',
        })
        self.assertTrue(AuditLog.objects.filter(action='POST_CREATE').exists())

    def test_new_thread_404_for_inactive_board(self):
        self.board.is_active = False
        self.board.save()
        self.client.force_login(self.user)
        resp = self.client.get(reverse('forum:new_thread', kwargs={'board_slug': 'general'}))
        self.assertEqual(resp.status_code, 404)


class ReplyViewTests(TestCase):
    def setUp(self):
        cache.clear()
        self.board = Board.objects.create(name_en='General', slug='general')
        self.thread = Thread.objects.create(
            board=self.board, title='Thread', slug='thread',
        )
        self.user = _make_user('alice')

    def test_reply_requires_login(self):
        resp = self.client.post(reverse('forum:reply', kwargs={'pk': self.thread.pk}), {
            'body': 'A reply body with enough characters.',
        })
        self.assertEqual(resp.status_code, 302)

    def test_reply_creates_post(self):
        self.client.force_login(self.user)
        resp = self.client.post(reverse('forum:reply', kwargs={'pk': self.thread.pk}), {
            'body': 'This is a valid reply body.',
        })
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(ForumPost.objects.filter(thread=self.thread, is_first_post=False).exists())

    def test_reply_closed_thread_403(self):
        self.thread.is_closed = True
        self.thread.save()
        self.client.force_login(self.user)
        resp = self.client.post(reverse('forum:reply', kwargs={'pk': self.thread.pk}), {
            'body': 'This should fail.',
        })
        self.assertEqual(resp.status_code, 403)

    def test_reply_invalid_body(self):
        self.client.force_login(self.user)
        resp = self.client.post(reverse('forum:reply', kwargs={'pk': self.thread.pk}), {
            'body': 'Short',
        })
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(ForumPost.objects.filter(thread=self.thread, is_first_post=False).exists())


class EditPostViewTests(TestCase):
    def setUp(self):
        self.board = Board.objects.create(name_en='General', slug='general')
        self.thread = Thread.objects.create(
            board=self.board, title='Thread', slug='thread',
        )
        self.user = _make_user('alice')
        self.post = ForumPost.objects.create(
            thread=self.thread, author=self.user, body='Original body',
        )

    def test_edit_post_requires_login(self):
        resp = self.client.get(reverse('forum:edit_post', kwargs={'pk': self.post.pk}))
        self.assertEqual(resp.status_code, 302)

    def test_edit_post_get(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse('forum:edit_post', kwargs={'pk': self.post.pk}))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Original body')

    def test_edit_post_updates_body(self):
        self.client.force_login(self.user)
        resp = self.client.post(reverse('forum:edit_post', kwargs={'pk': self.post.pk}), {
            'body': 'Updated body text here.',
        })
        self.assertEqual(resp.status_code, 302)
        self.post.refresh_from_db()
        self.assertIn('Updated', self.post.body)

    def test_edit_post_forbidden_for_other_user(self):
        other = _make_user('bob')
        self.client.force_login(other)
        resp = self.client.get(reverse('forum:edit_post', kwargs={'pk': self.post.pk}))
        self.assertEqual(resp.status_code, 403)

    def test_edit_post_allowed_for_admin(self):
        admin = _make_user('admin', is_site_admin=True)
        self.client.force_login(admin)
        resp = self.client.get(reverse('forum:edit_post', kwargs={'pk': self.post.pk}))
        self.assertEqual(resp.status_code, 200)


class DeletePostViewTests(TestCase):
    def setUp(self):
        self.board = Board.objects.create(name_en='General', slug='general')
        self.thread = Thread.objects.create(
            board=self.board, title='Thread', slug='thread',
        )
        self.user = _make_user('alice')
        self.post = ForumPost.objects.create(
            thread=self.thread, author=self.user, body='Delete me',
        )

    def test_delete_post_requires_post(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse('forum:delete_post', kwargs={'pk': self.post.pk}))
        self.assertEqual(resp.status_code, 400)

    def test_delete_post_soft_deletes(self):
        self.client.force_login(self.user)
        resp = self.client.post(reverse('forum:delete_post', kwargs={'pk': self.post.pk}))
        self.assertEqual(resp.status_code, 302)
        self.post.refresh_from_db()
        self.assertTrue(self.post.is_deleted)

    def test_delete_first_post_returns_400(self):
        self.post.is_first_post = True
        self.post.save()
        self.client.force_login(self.user)
        resp = self.client.post(reverse('forum:delete_post', kwargs={'pk': self.post.pk}))
        self.assertEqual(resp.status_code, 400)

    def test_delete_post_forbidden_for_other_user(self):
        other = _make_user('bob')
        self.client.force_login(other)
        resp = self.client.post(reverse('forum:delete_post', kwargs={'pk': self.post.pk}))
        self.assertEqual(resp.status_code, 403)


class DeleteThreadViewTests(TestCase):
    def setUp(self):
        self.board = Board.objects.create(name_en='General', slug='general')
        self.thread = Thread.objects.create(
            board=self.board, title='Thread', slug='thread',
        )
        self.admin = _make_user('admin', is_site_admin=True)
        self.user = _make_user('alice')

    def test_delete_thread_requires_admin(self):
        self.client.force_login(self.user)
        resp = self.client.post(reverse('forum:delete_thread', kwargs={'pk': self.thread.pk}))
        self.assertEqual(resp.status_code, 403)

    def test_delete_thread_admin(self):
        self.client.force_login(self.admin)
        resp = self.client.post(reverse('forum:delete_thread', kwargs={'pk': self.thread.pk}))
        self.assertEqual(resp.status_code, 302)
        self.thread.refresh_from_db()
        self.assertTrue(self.thread.is_deleted)


class ToggleStickyViewTests(TestCase):
    def setUp(self):
        self.board = Board.objects.create(name_en='General', slug='general')
        self.thread = Thread.objects.create(
            board=self.board, title='Thread', slug='thread',
        )
        self.admin = _make_user('admin', is_site_admin=True)
        self.user = _make_user('alice')

    def test_toggle_sticky_requires_admin(self):
        self.client.force_login(self.user)
        resp = self.client.post(reverse('forum:toggle_sticky', kwargs={'pk': self.thread.pk}))
        self.assertEqual(resp.status_code, 403)

    def test_toggle_sticky_admin(self):
        self.client.force_login(self.admin)
        self.assertFalse(self.thread.is_sticky)
        resp = self.client.post(reverse('forum:toggle_sticky', kwargs={'pk': self.thread.pk}))
        self.assertEqual(resp.status_code, 302)
        self.thread.refresh_from_db()
        self.assertTrue(self.thread.is_sticky)


class ToggleCloseViewTests(TestCase):
    def setUp(self):
        self.board = Board.objects.create(name_en='General', slug='general')
        self.thread = Thread.objects.create(
            board=self.board, title='Thread', slug='thread',
        )
        self.admin = _make_user('admin', is_site_admin=True)

    def test_toggle_close_admin(self):
        self.client.force_login(self.admin)
        self.assertFalse(self.thread.is_closed)
        resp = self.client.post(reverse('forum:toggle_close', kwargs={'pk': self.thread.pk}))
        self.assertEqual(resp.status_code, 302)
        self.thread.refresh_from_db()
        self.assertTrue(self.thread.is_closed)


class ForumPostCountFilterTests(TestCase):
    def setUp(self):
        self.user = _make_user('alice')
        self.board = Board.objects.create(name_en='General', slug='general')
        self.thread = Thread.objects.create(board=self.board, title='T', slug='t')

    def test_count_with_posts(self):
        ForumPost.objects.create(thread=self.thread, author=self.user, body='A')
        ForumPost.objects.create(thread=self.thread, author=self.user, body='B', is_deleted=True)
        from .templatetags.forum_extras import forum_post_count
        self.assertEqual(forum_post_count(self.user), 1)

    def test_count_with_no_user(self):
        from .templatetags.forum_extras import forum_post_count
        self.assertEqual(forum_post_count(None), 0)

    def test_count_with_empty_user(self):
        from .templatetags.forum_extras import forum_post_count
        u = User()
        self.assertEqual(forum_post_count(u), 0)


class ForumFormTests(TestCase):
    def test_new_thread_form_valid(self):
        from .forms import NewThreadForm
        form = NewThreadForm(data={'title': 'Hello', 'body': 'This is a long enough body.'})
        self.assertTrue(form.is_valid())

    def test_new_thread_form_short_body(self):
        from .forms import NewThreadForm
        form = NewThreadForm(data={'title': 'Hello', 'body': 'Short'})
        self.assertFalse(form.is_valid())

    def test_new_thread_form_empty_title(self):
        from .forms import NewThreadForm
        form = NewThreadForm(data={'title': '', 'body': 'This is long enough.'})
        self.assertFalse(form.is_valid())

    def test_reply_form_valid(self):
        from .forms import ReplyForm
        form = ReplyForm(data={'body': 'This is a valid reply body.'})
        self.assertTrue(form.is_valid())

    def test_reply_form_short_body(self):
        from .forms import ReplyForm
        form = ReplyForm(data={'body': 'Short'})
        self.assertFalse(form.is_valid())

    def test_reply_form_sanitizes(self):
        from .forms import ReplyForm
        form = ReplyForm(data={'body': '<script>alert(1)</script><p>Safe</p>'})
        self.assertTrue(form.is_valid())
        self.assertNotIn('<script>', form.cleaned_data['body'])


class UploadMediaViewTests(TestCase):
    def setUp(self):
        self.user = _make_user()
        self.url = reverse('forum:upload_media')

    def test_upload_requires_login(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 302)

    def test_upload_get_not_allowed(self):
        self.client.force_login(self.user)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 405)

    def test_upload_no_file(self):
        self.client.force_login(self.user)
        resp = self.client.post(self.url)
        self.assertEqual(resp.status_code, 400)

    def test_upload_invalid_file_type(self):
        self.client.force_login(self.user)
        from io import BytesIO
        f = BytesIO(b'test')
        f.name = 'test.exe'
        resp = self.client.post(self.url, {'file': f})
        self.assertEqual(resp.status_code, 400)
