from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render

from .models import Category, Post


def post_list(request, slug=None):
    posts = Post.published.select_related("category")
    category = None
    if slug:
        category = get_object_or_404(Category, slug=slug)
        posts = posts.filter(category=category)
    page = Paginator(posts, 9).get_page(request.GET.get("page"))
    return render(
        request,
        "blog/post_list.html",
        {"page_obj": page, "category": category, "categories": Category.objects.all()},
    )


def post_detail(request, slug):
    post = get_object_or_404(Post.published.select_related("category"), slug=slug)
    rings = post.related_rings.filter(is_active=True)
    return render(
        request,
        "blog/post_detail.html",
        {
            "post": post,
            "faqs": post.faqs.all(),
            "related_rings": [(ring, ring.starting_price) for ring in rings],
            "more_posts": Post.published.exclude(pk=post.pk)[:3],
        },
    )
