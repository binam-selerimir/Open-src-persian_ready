"""
Regression and integration tests for the comments app.

Run with:  python manage.py test comments
"""

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from posts.models import Category, Post, PostType

from .models import Comment
from .forms import CommentForm

User = get_user_model()


# ---------------------------------------------------------------------------
# Comment model tests
# ---------------------------------------------------------------------------

class CommentModelTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser', password='testpass123', email='test@example.com'
        )
        self.cat = Category.objects.create(name_en='News', name_fa='اخبار', slug='news')
        self.pt = PostType.objects.create(name_en='Article', slug='article')
        self.post = Post.objects.create(
            title='Test Post', slug='test-post', category=self.cat, post_type=self.pt,
            body='<p>Body</p>', pub_date=timezone.now(), is_visible=True,
        )

    def test_comment_str(self):
        comment = Comment.objects.create(
            post=self.post, author_name='John', author_email='john@example.com',
            body='Nice article!',
        )
        self.assertEqual(str(comment), 'John on Test Post')

    def test_comment_default_not_approved(self):
        comment = Comment.objects.create(
            post=self.post, author_name='John', author_email='john@example.com',
            body='Nice article!',
        )
        self.assertFalse(comment.is_approved)

    def test_comment_post_relationship_cascade(self):
        Comment.objects.create(
            post=self.post, author_name='John', author_email='john@example.com',
            body='Nice article!',
        )
        self.assertEqual(Comment.objects.count(), 1)
        self.post.delete()
        self.assertEqual(Comment.objects.count(), 0)

    def test_comment_ordering(self):
        c1 = Comment.objects.create(
            post=self.post, author_name='First', author_email='a@b.com',
            body='First comment',
        )
        c2 = Comment.objects.create(
            post=self.post, author_name='Second', author_email='b@c.com',
            body='Second comment',
        )
        comments = list(Comment.objects.all())
        self.assertEqual(comments[0].pk, c2.pk)
        self.assertEqual(comments[1].pk, c1.pk)


# ---------------------------------------------------------------------------
# CommentForm tests
# ---------------------------------------------------------------------------

class CommentFormTests(TestCase):

    def test_valid_form(self):
        form = CommentForm(data={
            'body': 'Great article!',
        })
        self.assertTrue(form.is_valid())

    def test_empty_body_rejected(self):
        form = CommentForm(data={
            'body': '',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('body', form.errors)

    def test_oversized_body_rejected(self):
        form = CommentForm(data={
            'body': 'x' * 2001,
        })
        self.assertFalse(form.is_valid())

    def test_xss_in_body_sanitized(self):
        form = CommentForm(data={
            'body': '<script>alert(1)</script><p>Safe</p>',
        })
        self.assertTrue(form.is_valid())
        cleaned = form.cleaned_data['body']
        self.assertNotIn('<script>', cleaned)
        self.assertIn('Safe', cleaned)

    def test_allowed_tags_preserved(self):
        form = CommentForm(data={
            'body': '<p>Hello</p><strong>Bold</strong><em>Italic</em>',
        })
        self.assertTrue(form.is_valid())
        cleaned = form.cleaned_data['body']
        self.assertIn('<p>', cleaned)
        self.assertIn('<strong>', cleaned)
        self.assertIn('<em>', cleaned)

    def test_form_only_has_body_field(self):
        form = CommentForm()
        self.assertEqual(list(form.fields.keys()), ['body'])


# ---------------------------------------------------------------------------
# add_comment view tests
# ---------------------------------------------------------------------------

class AddCommentViewTests(TestCase):

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username='testuser', password='testpass123', email='test@example.com',
            first_name='Test', last_name='User',
        )
        self.cat = Category.objects.create(name_en='News', name_fa='اخبار', slug='news')
        self.pt = PostType.objects.create(name_en='Article', slug='article')
        self.post = Post.objects.create(
            title='Test Post', slug='test-post', category=self.cat, post_type=self.pt,
            body='<p>Body</p>', pub_date=timezone.now(), is_visible=True,
        )
        self.url = reverse('comments:add_comment', kwargs={'slug': self.post.slug})

    def tearDown(self):
        cache.clear()

    def test_add_comment_requires_login(self):
        self.client.logout()
        resp = self.client.post(self.url, {
            'body': 'Nice!',
        })
        self.assertEqual(resp.status_code, 302)
        self.assertIn('login', resp.url)

    def test_add_comment_get_not_allowed(self):
        self.client.force_login(self.user)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 302)

    def test_add_comment_creates_comment(self):
        self.client.force_login(self.user)
        resp = self.client.post(self.url, {
            'body': 'Nice article!',
        })
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(Comment.objects.count(), 1)
        comment = Comment.objects.first()
        self.assertEqual(comment.body, 'Nice article!')
        self.assertFalse(comment.is_approved)

    def test_add_comment_uses_account_name(self):
        self.client.force_login(self.user)
        self.client.post(self.url, {'body': 'Test'})
        comment = Comment.objects.first()
        self.assertEqual(comment.author_name, 'Test User')

    def test_add_comment_uses_account_email(self):
        self.client.force_login(self.user)
        self.client.post(self.url, {'body': 'Test'})
        comment = Comment.objects.first()
        self.assertEqual(comment.author_email, 'test@example.com')

    def test_add_comment_cannot_override_name(self):
        self.client.force_login(self.user)
        self.client.post(self.url, {
            'body': 'Hacked!',
            'author_name': 'Hacker',
            'author_email': 'hacker@evil.com',
        })
        comment = Comment.objects.first()
        self.assertEqual(comment.author_name, 'Test User')
        self.assertEqual(comment.author_email, 'test@example.com')

    def test_add_comment_fallback_to_username(self):
        user = User.objects.create_user(
            username='naminguy', password='pass123', email='no@name.com',
            first_name='', last_name='',
        )
        self.client.force_login(user)
        self.client.post(self.url, {'body': 'Fallback test'})
        comment = Comment.objects.first()
        self.assertEqual(comment.author_name, 'naminguy')

    def test_add_comment_invalid_form(self):
        self.client.force_login(self.user)
        resp = self.client.post(self.url, {
            'body': '',
        })
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(Comment.objects.count(), 0)

    def test_add_comment_rate_limit(self):
        self.client.force_login(self.user)
        for _ in range(5):
            self.client.post(self.url, {'body': 'Comment'})
        resp = self.client.post(self.url, {'body': 'Rate limited'})
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(Comment.objects.count(), 5)

    def test_add_comment_unpublished_post_404(self):
        self.post.is_visible = False
        self.post.save()
        self.client.force_login(self.user)
        resp = self.client.post(self.url, {'body': 'Nice!'})
        self.assertEqual(resp.status_code, 404)


# ---------------------------------------------------------------------------
# Admin comments view tests
# ---------------------------------------------------------------------------

class AdminCommentsViewTests(TestCase):

    def setUp(self):
        cache.clear()
        self.admin = User.objects.create_user(
            username='admin', password='adminpass123', email='admin@example.com',
            is_staff=True, is_site_admin=True,
        )
        self.user = User.objects.create_user(
            username='user', password='userpass123', email='user@example.com',
        )
        self.cat = Category.objects.create(name_en='News', name_fa='اخبار', slug='news')
        self.pt = PostType.objects.create(name_en='Article', slug='article')
        self.post = Post.objects.create(
            title='Test Post', slug='test-post', category=self.cat, post_type=self.pt,
            body='<p>Body</p>', pub_date=timezone.now(), is_visible=True,
            publisher=self.admin,
        )
        self.comment = Comment.objects.create(
            post=self.post, author_name='John', author_email='john@example.com',
            body='Test comment',
        )
        self.url = reverse('accounts:admin_comments')

    def tearDown(self):
        cache.clear()

    def test_admin_comments_requires_login(self):
        self.client.logout()
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 302)

    def test_admin_comments_requires_admin(self):
        self.client.force_login(self.user)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 403)

    def test_admin_comments_list(self):
        self.client.force_login(self.admin)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Test comment')

    def test_admin_comments_filter_pending(self):
        self.client.force_login(self.admin)
        resp = self.client.get(self.url, {'status': 'pending'})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Test comment')

    def test_admin_comments_filter_approved(self):
        self.comment.is_approved = True
        self.comment.save()
        self.client.force_login(self.admin)
        resp = self.client.get(self.url, {'status': 'approved'})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Test comment')

    def test_admin_approve_comment(self):
        self.client.force_login(self.admin)
        resp = self.client.post(self.url, {
            'bulk_action': 'approve',
            'selected_comments': [str(self.comment.pk)],
        })
        self.assertEqual(resp.status_code, 302)
        self.comment.refresh_from_db()
        self.assertTrue(self.comment.is_approved)

    def test_admin_reject_comment(self):
        self.comment.is_approved = True
        self.comment.save()
        self.client.force_login(self.admin)
        resp = self.client.post(self.url, {
            'bulk_action': 'reject',
            'selected_comments': [str(self.comment.pk)],
        })
        self.assertEqual(resp.status_code, 302)
        self.comment.refresh_from_db()
        self.assertFalse(self.comment.is_approved)

    def test_admin_delete_comment(self):
        self.client.force_login(self.admin)
        resp = self.client.post(self.url, {
            'bulk_action': 'delete',
            'selected_comments': [str(self.comment.pk)],
        })
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(Comment.objects.count(), 0)

    def test_admin_bulk_invalid_pks(self):
        self.client.force_login(self.admin)
        resp = self.client.post(self.url, {
            'bulk_action': 'approve',
            'selected_comments': ['abc', 'xyz'],
        })
        self.assertEqual(resp.status_code, 302)


# ---------------------------------------------------------------------------
# Comment visibility integration tests
# ---------------------------------------------------------------------------

class CommentVisibilityTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser', password='testpass123', email='test@example.com'
        )
        self.cat = Category.objects.create(name_en='News', name_fa='اخبار', slug='news')
        self.pt = PostType.objects.create(name_en='Article', slug='article')
        self.post = Post.objects.create(
            title='Test Post', slug='test-post', category=self.cat, post_type=self.pt,
            body='<p>Body</p>', pub_date=timezone.now(), is_visible=True,
        )

    def test_unapproved_comment_not_in_context(self):
        Comment.objects.create(
            post=self.post, author_name='John', author_email='john@example.com',
            body='Pending', is_approved=False,
        )
        resp = self.client.get(reverse('posts:post_detail', kwargs={'slug': self.post.slug}))
        self.assertNotContains(resp, 'Pending')

    def test_approved_comment_in_context(self):
        Comment.objects.create(
            post=self.post, author_name='John', author_email='john@example.com',
            body='Approved', is_approved=True,
        )
        resp = self.client.get(reverse('posts:post_detail', kwargs={'slug': self.post.slug}))
        self.assertContains(resp, 'Approved')

    def test_multiple_comments_displayed(self):
        for i in range(3):
            Comment.objects.create(
                post=self.post, author_name=f'User{i}', author_email=f'u{i}@e.com',
                body=f'Comment {i}', is_approved=True,
            )
        resp = self.client.get(reverse('posts:post_detail', kwargs={'slug': self.post.slug}))
        self.assertContains(resp, 'Comment 0')
        self.assertContains(resp, 'Comment 1')
        self.assertContains(resp, 'Comment 2')


# ---------------------------------------------------------------------------
# Per-post comment management tests (in admin_edit_post)
# ---------------------------------------------------------------------------

class PerPostCommentManagementTests(TestCase):

    def setUp(self):
        cache.clear()
        self.admin = User.objects.create_user(
            username='admin', password='adminpass123', email='admin@example.com',
            is_staff=True, is_site_admin=True,
        )
        self.user = User.objects.create_user(
            username='user', password='userpass123', email='user@example.com',
        )
        self.cat = Category.objects.create(name_en='News', name_fa='اخبار', slug='news')
        self.pt = PostType.objects.create(name_en='Article', slug='article')
        self.post = Post.objects.create(
            title='Test Post', slug='test-post', category=self.cat, post_type=self.pt,
            body='<p>Body</p>', pub_date=timezone.now(), is_visible=True,
            publisher=self.admin,
        )
        self.comment1 = Comment.objects.create(
            post=self.post, author_name='John', author_email='john@example.com',
            body='Pending comment', is_approved=False,
        )
        self.comment2 = Comment.objects.create(
            post=self.post, author_name='Jane', author_email='jane@example.com',
            body='Approved comment', is_approved=True,
        )
        self.other_post = Post.objects.create(
            title='Other Post', slug='other-post', category=self.cat, post_type=self.pt,
            body='<p>Body</p>', pub_date=timezone.now(), is_visible=True,
            publisher=self.admin,
        )
        self.other_comment = Comment.objects.create(
            post=self.other_post, author_name='Bob', author_email='bob@example.com',
            body='Other post comment', is_approved=False,
        )
        self.url = reverse('accounts:admin_edit_post', kwargs={'pk': self.post.pk})

    def tearDown(self):
        cache.clear()

    def test_edit_post_shows_comments(self):
        self.client.force_login(self.admin)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Pending comment')
        self.assertContains(resp, 'Approved comment')
        self.assertNotContains(resp, 'Other post comment')

    def test_edit_post_requires_admin(self):
        self.client.force_login(self.user)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 403)

    def test_approve_comment_on_post(self):
        self.client.force_login(self.admin)
        resp = self.client.post(self.url, {
            'form_type': 'comment_action',
            'comment_action': 'approve',
            'selected_comments': [str(self.comment1.pk)],
        })
        self.assertEqual(resp.status_code, 302)
        self.comment1.refresh_from_db()
        self.assertTrue(self.comment1.is_approved)

    def test_reject_comment_on_post(self):
        self.client.force_login(self.admin)
        resp = self.client.post(self.url, {
            'form_type': 'comment_action',
            'comment_action': 'reject',
            'selected_comments': [str(self.comment2.pk)],
        })
        self.assertEqual(resp.status_code, 302)
        self.comment2.refresh_from_db()
        self.assertFalse(self.comment2.is_approved)

    def test_delete_comment_on_post(self):
        self.client.force_login(self.admin)
        resp = self.client.post(self.url, {
            'form_type': 'comment_action',
            'comment_action': 'delete',
            'selected_comments': [str(self.comment1.pk)],
        })
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(Comment.objects.filter(pk=self.comment1.pk).exists())

    def test_comment_action_does_not_affect_other_posts(self):
        self.client.force_login(self.admin)
        resp = self.client.post(self.url, {
            'form_type': 'comment_action',
            'comment_action': 'approve',
            'selected_comments': [str(self.other_comment.pk)],
        })
        self.assertEqual(resp.status_code, 302)
        self.other_comment.refresh_from_db()
        self.assertFalse(self.other_comment.is_approved)

    def test_bulk_approve_multiple_comments(self):
        comment3 = Comment.objects.create(
            post=self.post, author_name='Bob', author_email='bob@example.com',
            body='Third comment', is_approved=False,
        )
        self.client.force_login(self.admin)
        resp = self.client.post(self.url, {
            'form_type': 'comment_action',
            'comment_action': 'approve',
            'selected_comments': [str(self.comment1.pk), str(comment3.pk)],
        })
        self.assertEqual(resp.status_code, 302)
        self.comment1.refresh_from_db()
        comment3.refresh_from_db()
        self.assertTrue(self.comment1.is_approved)
        self.assertTrue(comment3.is_approved)

    def test_comment_action_invalid_pks(self):
        self.client.force_login(self.admin)
        resp = self.client.post(self.url, {
            'form_type': 'comment_action',
            'comment_action': 'approve',
            'selected_comments': ['abc', 'xyz'],
        })
        self.assertEqual(resp.status_code, 302)

    def test_admin_posts_shows_comment_count(self):
        self.client.force_login(self.admin)
        resp = self.client.get(reverse('accounts:admin_posts'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, '2')
        self.assertContains(resp, '1 pending')
