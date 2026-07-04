"""Category, subcategory, and post type CRUD."""

import re

from django.contrib import messages
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from posts.models import Category, PostType, Subcategory

from ._common import _admin_login_required, _safe_int


def _taxonomy_create(Model, request, label, extra_defaults=None):
    """Create a taxonomy object via get_or_create."""
    name_en = request.POST.get('name_en', '').strip()
    name_fa = request.POST.get('name_fa', '').strip()
    slug = request.POST.get('slug', '').strip() or slugify(name_en, allow_unicode=True)
    if not name_en:
        messages.error(request, _('%s name (English) is required.') % label)
        return
    defaults = {'name_en': name_en, 'name_fa': name_fa or name_en}
    if extra_defaults:
        defaults.update(extra_defaults)
    obj, created = Model.objects.get_or_create(slug=slug, defaults=defaults)
    if created:
        messages.success(request, _('"%s" created.') % name_en)
    else:
        messages.info(request, _('"%s" already exists.') % name_en)


def _taxonomy_edit(Model, request, pk, label, extra_fields=None):
    """Update a taxonomy object's fields."""
    pk = _safe_int(pk, default=None)
    if pk is None:
        messages.error(request, _('Invalid ID.'))
        return
    obj = get_object_or_404(Model, pk=pk)
    obj.name_en = request.POST.get('name_en', obj.name_en).strip()
    obj.name_fa = request.POST.get('name_fa', obj.name_fa).strip()
    slug = request.POST.get('slug', '').strip()
    if slug and slug != obj.slug:
        obj.slug = slug
    if extra_fields:
        for field, post_key in extra_fields.items():
            val = request.POST.get(post_key, getattr(obj, field))
            if field == 'order':
                val = _safe_int(val, default=getattr(obj, field))
            elif field == 'accent_color':
                val = val.strip() if isinstance(val, str) else val
                if not re.match(r'^#[0-9a-fA-F]{6}$', val or ''):
                    val = getattr(obj, field)
            elif field == 'category_id':
                from posts.models import Category
                cat_pk = _safe_int(val, default=None)
                if cat_pk is None or not Category.objects.filter(pk=cat_pk).exists():
                    messages.error(request, _('That category no longer exists.'))
                    return
                val = cat_pk
            setattr(obj, field, val)
    try:
        with transaction.atomic():
            obj.save()
        messages.success(request, _('"%s" updated.') % obj.name_en)
    except IntegrityError:
        messages.error(request, _('That slug is already in use by another %s.') % label.lower())


def _taxonomy_delete(Model, request, pk, label, related_name='posts'):
    """Delete a taxonomy object if it has no related items."""
    pk = _safe_int(pk, default=None)
    if pk is None:
        messages.error(request, _('Invalid ID.'))
        return
    obj = get_object_or_404(Model, pk=pk)
    if getattr(obj, related_name).exists():
        messages.error(request, _('Cannot delete "%s" — it has related items.') % obj.name_en)
    else:
        name = obj.name_en
        obj.delete()
        messages.success(request, _('"%s" deleted.') % name)


def _handle_taxonomy_post(request):
    """Dispatch taxonomy POST actions. Returns the section anchor."""
    action = request.POST.get('action', '')
    section = request.POST.get('section', 'categories')

    if action == 'create_category':
        _taxonomy_create(Category, request, _('Category'))
    elif action == 'edit_category':
        _taxonomy_edit(Category, request, request.POST.get('category_id'), _('Category'),
                       extra_fields={'order': 'order'})
    elif action == 'delete_category':
        _taxonomy_delete(Category, request, request.POST.get('category_id'), _('Category'))

    elif action == 'create_subcategory':
        cat = get_object_or_404(Category, pk=request.POST.get('category_id'))
        name_en = request.POST.get('name_en', '').strip()
        name_fa = request.POST.get('name_fa', '').strip()
        slug = request.POST.get('slug', '').strip() or slugify(name_en, allow_unicode=True)
        if name_en:
            Subcategory.objects.get_or_create(
                category=cat, slug=slug,
                defaults={'name_en': name_en, 'name_fa': name_fa or name_en},
            )
            messages.success(request, _('Subcategory "%s" created.') % name_en)
        else:
            messages.error(request, _('Subcategory name (English) is required.'))
    elif action == 'edit_subcategory':
        _taxonomy_edit(Subcategory, request, request.POST.get('subcategory_id'),
                       _('Subcategory'), extra_fields={'category_id': 'category_id'})
    elif action == 'delete_subcategory':
        _taxonomy_delete(Subcategory, request, request.POST.get('subcategory_id'),
                         _('Subcategory'))

    elif action == 'create_post_type':
        accent_raw = request.POST.get('accent_color', '#ffcc00').strip() or '#ffcc00'
        accent = accent_raw if re.match(r'^#[0-9a-fA-F]{6}$', accent_raw) else '#ffcc00'
        _taxonomy_create(PostType, request, _('Post type'), extra_defaults={
            'accent_color': accent,
            'order': _safe_int(request.POST.get('order', 0), default=0),
        })
    elif action == 'edit_post_type':
        _taxonomy_edit(PostType, request, request.POST.get('post_type_id'),
                       _('Post type'), extra_fields={'order': 'order',
                                                     'accent_color': 'accent_color'})
    elif action == 'delete_post_type':
        _taxonomy_delete(PostType, request, request.POST.get('post_type_id'),
                         _('Post type'), related_name='posts')

    return section


@_admin_login_required
def admin_post_taxonomy(request):
    """Manage categories, subcategories, and post types."""
    if request.method == 'POST':
        section = _handle_taxonomy_post(request)
        base_url = reverse('accounts:admin_post_taxonomy')
        return redirect(f'{base_url}#{section}' if section else base_url)

    return render(request, 'accounts/admin_post_taxonomy.html', {
        'categories': Category.objects.prefetch_related('subcategories').all(),
        'subcategories': Subcategory.objects.select_related('category').all(),
        'post_types': PostType.objects.all(),
        'active_tab': 'taxonomy',
    })


@_admin_login_required
def admin_tags(request):
    """Create and delete tags."""
    from posts.models import Tag
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'create':
            name = request.POST.get('name', '').strip()
            if name:
                Tag.objects.get_or_create(
                    slug=slugify(name, allow_unicode=True),
                    defaults={'name': name},
                )
                messages.success(request, _('Tag "%s" created.') % name)
        elif action == 'delete':
            tag = Tag.objects.filter(pk=request.POST.get('tag_id')).first()
            if tag:
                if tag.posts.exists():
                    messages.error(request, _('Cannot delete "%s" — it is used by posts.') % tag.name)
                else:
                    tag.delete()
                    messages.success(request, _('Tag deleted.'))
        return redirect('accounts:admin_tags')

    return render(request, 'accounts/admin_tags.html', {
        'tags': Tag.objects.all(), 'active_tab': 'tags',
    })


__all__ = ['admin_post_taxonomy', 'admin_tags']
