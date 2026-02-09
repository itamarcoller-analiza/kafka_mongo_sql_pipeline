"""Generate 100 seed posts with realistic engagement, lifecycle, and timestamps.

Uses direct DB insertion via motor/beanie (the API cannot set stats,
custom timestamps, author_type=LEADER, or deleted_at).
"""

import asyncio
import os
import random
import sys
from datetime import datetime, timedelta, timezone

# Path setup so shared models + utils resolve
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "apps", "mongo_backend"))
sys.path.insert(0, ROOT)

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402
from beanie import init_beanie  # noqa: E402

from shared.models.post import (  # noqa: E402
    Post, PostType, AuthorType, PostAuthor,
    MediaAttachment, LinkPreview, PostStats,
)
from shared.models.user import User  # noqa: E402

random.seed(42)

MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
DATABASE_NAME = os.getenv("DATABASE_NAME", "social_commerce")
NUM_POSTS = 100


# ================================================================
# 2.2  Content pools
# ================================================================

TOPICS = [
    "cooking", "fitness", "tech", "beauty",
    "gaming", "local events", "deals", "community questions",
]

TEXT_TEMPLATES = {
    "announcement": [
        "Exciting news! We just launched our new {topic} collection.",
        "Big announcement: our {topic} line is now available.",
        "Happy to share that our {topic} range has been updated.",
    ],
    "question": [
        "What's your favorite {topic} tip? Share below!",
        "Looking for recommendations in {topic}. Any suggestions?",
        "Has anyone tried the new {topic} trend? Thoughts?",
    ],
    "tutorial": [
        "Quick {topic} tutorial: here's how to get started.",
        "Step by step guide for {topic} beginners.",
        "Pro tip for {topic} enthusiasts — try this approach.",
    ],
    "opinion": [
        "Hot take: {topic} is underrated and deserves more attention.",
        "Unpopular opinion about {topic} — hear me out.",
        "My honest thoughts on the latest {topic} trends.",
    ],
    "meme_caption": [
        "When you discover a new {topic} hack. Game changer.",
        "Nobody: Me at 2am browsing {topic} content.",
        "That feeling when your {topic} setup finally works.",
    ],
    "mini_review": [
        "Just tried this {topic} product and here's my quick review.",
        "Honest mini-review of the trending {topic} item everyone talks about.",
        "Rating this {topic} find: would definitely recommend.",
    ],
}

CTA_POOL = [
    "What do you think?",
    "Vote below!",
    "Link in post.",
    "Drop your tips!",
    "Let me know in the comments.",
    "Share your experience!",
    "Tag a friend who needs this.",
    "Save for later!",
]


# ================================================================
# 2.3  Media URL pools
# ================================================================

IMAGE_URLS = [f"https://cdn.example.com/images/img-{i:04d}.jpg" for i in range(1, 51)]
VIDEO_URLS = [f"https://cdn.example.com/videos/vid-{i:04d}.mp4" for i in range(1, 21)]
THUMBNAIL_URLS = [f"https://cdn.example.com/thumbs/thumb-{i:04d}.jpg" for i in range(1, 21)]

IMAGE_DIMENSIONS = [
    (1080, 1080),
    (1080, 1350),
    (1920, 1080),
    (800, 600),
    (1200, 900),
]


# ================================================================
# 2.4  Link preview pools (20 records)
# ================================================================

LINK_PREVIEWS = [
    {"url": "https://techcrunch.com/article/new-startup-raises", "title": "New Startup Raises $50M", "description": "A promising startup just closed its Series B round.", "image": "https://cdn.example.com/previews/tc-01.jpg", "site_name": "TechCrunch"},
    {"url": "https://medium.com/design-tips-2025", "title": "10 Design Tips for 2025", "description": "Practical design advice for the modern creator.", "image": "https://cdn.example.com/previews/med-01.jpg", "site_name": "Medium"},
    {"url": "https://www.bbc.com/news/technology-update", "title": "Technology Update: AI Advances", "description": "The latest breakthroughs in artificial intelligence research.", "image": "https://cdn.example.com/previews/bbc-01.jpg", "site_name": "BBC News"},
    {"url": "https://www.theverge.com/gadget-review", "title": "Best Gadgets Reviewed This Month", "description": "Our editors pick the top gadgets worth buying.", "image": "https://cdn.example.com/previews/verge-01.jpg", "site_name": "The Verge"},
    {"url": "https://cooking.nytimes.com/recipes/seasonal", "title": "Seasonal Recipes You Must Try", "description": "Fresh seasonal dishes for every occasion.", "image": "https://cdn.example.com/previews/nyt-01.jpg", "site_name": "NYT Cooking"},
    {"url": "https://www.wired.com/ai-ethics-debate", "title": "The AI Ethics Debate Continues", "description": "Exploring the ethical boundaries of modern AI systems.", "image": "https://cdn.example.com/previews/wired-01.jpg", "site_name": "WIRED"},
    {"url": "https://www.forbes.com/small-business-tips", "title": "Top Small Business Tips for Growth", "description": "Expert advice on scaling your small business.", "image": "https://cdn.example.com/previews/forbes-01.jpg", "site_name": "Forbes"},
    {"url": "https://www.healthline.com/nutrition-guide", "title": "Complete Nutrition Guide 2025", "description": "Everything you need to know about balanced nutrition.", "image": "https://cdn.example.com/previews/hl-01.jpg", "site_name": "Healthline"},
    {"url": "https://www.espn.com/fitness-trends", "title": "Fitness Trends Taking Over Gyms", "description": "The workout routines everyone is trying this year.", "image": "https://cdn.example.com/previews/espn-01.jpg", "site_name": "ESPN"},
    {"url": "https://www.buzzfeed.com/best-finds", "title": "25 Best Finds Under $20", "description": "Budget-friendly picks our editors love.", "image": "https://cdn.example.com/previews/bf-01.jpg", "site_name": "BuzzFeed"},
    {"url": "https://www.reuters.com/market-outlook", "title": "Market Outlook: What to Expect", "description": "Financial analysts weigh in on market direction.", "image": "https://cdn.example.com/previews/reuters-01.jpg", "site_name": "Reuters"},
    {"url": "https://www.nytimes.com/travel-destinations", "title": "Hidden Travel Destinations Revealed", "description": "Underrated places that deserve your next vacation.", "image": "https://cdn.example.com/previews/nyt-02.jpg", "site_name": "New York Times"},
    {"url": "https://arstechnica.com/open-source-update", "title": "Open Source Projects to Watch", "description": "The most exciting open source work happening now.", "image": "https://cdn.example.com/previews/ars-01.jpg", "site_name": "Ars Technica"},
    {"url": "https://www.cnet.com/smart-home-guide", "title": "Smart Home Setup Guide", "description": "How to build a connected home from scratch.", "image": "https://cdn.example.com/previews/cnet-01.jpg", "site_name": "CNET"},
    {"url": "https://www.allrecipes.com/quick-meals", "title": "Quick Meals in Under 30 Minutes", "description": "Fast dinner ideas for busy weeknights.", "image": "https://cdn.example.com/previews/ar-01.jpg", "site_name": "AllRecipes"},
    {"url": "https://www.nature.com/climate-research", "title": "New Climate Research Findings", "description": "Scientists publish key findings on climate patterns.", "image": "https://cdn.example.com/previews/nature-01.jpg", "site_name": "Nature"},
    {"url": "https://www.producthunt.com/launches-today", "title": "Today's Top Product Launches", "description": "The hottest new products launched today.", "image": "https://cdn.example.com/previews/ph-01.jpg", "site_name": "Product Hunt"},
    {"url": "https://www.vice.com/street-food-culture", "title": "Street Food Culture Around the World", "description": "A global tour of the best street food scenes.", "image": "https://cdn.example.com/previews/vice-01.jpg", "site_name": "VICE"},
    {"url": "https://www.polygon.com/game-reviews", "title": "This Week's Best Game Reviews", "description": "Top-rated games reviewed by our editors.", "image": "https://cdn.example.com/previews/polygon-01.jpg", "site_name": "Polygon"},
    {"url": "https://www.insider.com/shopping-hacks", "title": "Shopping Hacks That Save Real Money", "description": "Insider tips for getting the best deals online.", "image": "https://cdn.example.com/previews/insider-01.jpg", "site_name": "Insider"},
]


# ================================================================
# 2.5  Distribution / weight pools
# ================================================================

LIFECYCLE_WEIGHTS = ["published"] * 92 + ["draft"] * 6 + ["deleted"] * 2

POST_TYPE_WEIGHTS_USER = (
    [PostType.TEXT] * 45
    + [PostType.IMAGE] * 25
    + [PostType.VIDEO] * 10
    + [PostType.LINK] * 12
    + [PostType.POLL] * 8
)

POST_TYPE_WEIGHTS_LEADER = (
    [PostType.TEXT] * 30
    + [PostType.IMAGE] * 20
    + [PostType.VIDEO] * 20
    + [PostType.LINK] * 20
    + [PostType.POLL] * 10
)

AUTHOR_TYPE_WEIGHTS = [AuthorType.USER] * 80 + [AuthorType.LEADER] * 20

# Reach multiplier per post type (VIDEO > IMAGE > POLL > LINK > TEXT)
REACH_MULTIPLIERS = {
    PostType.TEXT: 1.0,
    PostType.IMAGE: 2.5,
    PostType.VIDEO: 4.0,
    PostType.LINK: 1.5,
    PostType.POLL: 2.0,
}


# ================================================================
# Helpers — time
# ================================================================

def _utc_now():
    return datetime.now(timezone.utc)


def _random_past_time(max_days_ago=90):
    """Random time in the past, exponentially skewed toward recent."""
    days_ago = min(max_days_ago, random.expovariate(1 / 15))
    seconds_offset = random.randint(0, 86400)
    return _utc_now() - timedelta(days=days_ago, seconds=seconds_offset)


# ================================================================
# Helpers — content builders
# ================================================================

def _generate_text(post_type, topic):
    tone = random.choice(list(TEXT_TEMPLATES.keys()))
    template = random.choice(TEXT_TEMPLATES[tone])
    text = template.format(topic=topic)
    if random.random() < 0.4:
        text += " " + random.choice(CTA_POOL)
    return text


def _generate_media_image():
    w, h = random.choice(IMAGE_DIMENSIONS)
    return MediaAttachment(
        media_type="image",
        media_url=random.choice(IMAGE_URLS),
        width=w,
        height=h,
    )


def _generate_media_video():
    return MediaAttachment(
        media_type="video",
        media_url=random.choice(VIDEO_URLS),
        thumbnail_url=random.choice(THUMBNAIL_URLS),
        width=1920,
        height=1080,
        duration_seconds=random.randint(5, 180),
    )


def _generate_link_preview():
    lp = random.choice(LINK_PREVIEWS)
    return LinkPreview(
        url=lp["url"],
        title=lp["title"],
        description=lp["description"],
        image=lp["image"],
        site_name=lp["site_name"],
    )


# ================================================================
# Helpers — engagement stats
# ================================================================

def _generate_stats(post_type, lifecycle, published_at, updated_at):
    """Build PostStats correlated with post_type and lifecycle."""
    if lifecycle == "draft":
        return PostStats()

    # Power-law base views (many low, few high)
    base_views = int(random.paretovariate(1.5) * 50)
    view_count = min(int(base_views * REACH_MULTIPLIERS[post_type]), 50000)

    # Derive counts from views
    like_pct = random.uniform(0.003, 0.08)
    comment_pct = random.uniform(0.0, 0.02)
    share_pct = random.uniform(0.0, 0.01)
    save_pct = random.uniform(0.0, 0.03)

    if post_type == PostType.POLL:
        comment_pct *= 3
    if post_type in (PostType.IMAGE, PostType.VIDEO):
        save_pct *= 2

    like_count = int(view_count * like_pct)
    comment_count = int(view_count * comment_pct)
    share_count = int(view_count * share_pct)
    save_count = int(view_count * save_pct)

    # Deleted posts: freeze low engagement
    if lifecycle == "deleted":
        view_count = int(view_count * 0.3)
        like_count = int(like_count * 0.3)
        comment_count = int(comment_count * 0.3)
        share_count = int(share_count * 0.3)
        save_count = int(save_count * 0.3)

    # Computed engagement rate
    engagement_rate = round(
        100 * (like_count + comment_count + share_count + save_count)
        / max(view_count, 1),
        2,
    )

    # last_comment_at
    last_comment_at = None
    if comment_count > 0 and published_at:
        ceiling = updated_at or _utc_now()
        delta = (ceiling - published_at).total_seconds()
        if delta > 0:
            last_comment_at = published_at + timedelta(
                seconds=random.uniform(0, delta)
            )

    return PostStats(
        view_count=view_count,
        like_count=like_count,
        comment_count=comment_count,
        share_count=share_count,
        save_count=save_count,
        engagement_rate=engagement_rate,
        last_comment_at=last_comment_at,
    )


# ================================================================
# Main generation pipeline
# ================================================================

def generate_post(index, user_authors, leader_authors):
    """Generate a single Post document following Steps A–K."""

    # Step A — lifecycle bucket
    lifecycle = random.choice(LIFECYCLE_WEIGHTS)

    # Step B — author
    author_type = random.choice(AUTHOR_TYPE_WEIGHTS)
    if author_type == AuthorType.LEADER and leader_authors:
        author_data = random.choice(leader_authors)
    else:
        author_data = random.choice(user_authors)
        author_type = AuthorType.USER

    author = PostAuthor(
        user_id=author_data["user_id"],
        display_name=author_data["display_name"],
        avatar=author_data["avatar"],
        author_type=author_type,
    )

    # Step C — post_type (conditioned on author_type)
    if author_type == AuthorType.LEADER:
        post_type = random.choice(POST_TYPE_WEIGHTS_LEADER)
    else:
        post_type = random.choice(POST_TYPE_WEIGHTS_USER)

    # Step D — text_content (always present)
    topic = random.choice(TOPICS)
    text_content = _generate_text(post_type, topic)

    # Step E — type-specific payloads
    media = []
    link_preview = None

    if post_type == PostType.IMAGE:
        media = [_generate_media_image() for _ in range(random.randint(1, 4))]
    elif post_type == PostType.VIDEO:
        media = [_generate_media_video()]
    elif post_type == PostType.LINK:
        link_preview = _generate_link_preview()
    # TEXT / POLL: media=[], link_preview=None

    # Step K — timestamps
    created_at = _random_past_time(max_days_ago=90)

    # published_at
    published_at = None
    if lifecycle in ("published", "deleted"):
        published_at = created_at + timedelta(seconds=random.randint(0, 300))

    # updated_at >= created_at
    updated_at = created_at + timedelta(seconds=random.randint(0, 86400 * 5))

    # deleted_at
    deleted_at = None
    if lifecycle == "deleted":
        deleted_at = (published_at or created_at) + timedelta(
            days=random.randint(1, 14)
        )
        updated_at = deleted_at

    # Step 4 — engagement stats
    stats = _generate_stats(post_type, lifecycle, published_at, updated_at)

    post = Post(
        post_type=post_type,
        author=author,
        text_content=text_content,
        media=media,
        link_preview=link_preview,
        stats=stats,
        deleted_at=deleted_at,
        published_at=published_at,
        created_at=created_at,
        updated_at=updated_at,
    )

    return post, lifecycle


# ================================================================
# Validation pass
# ================================================================

def validate_posts(posts):
    errors = []
    for i, p in enumerate(posts):
        tag = f"post[{i}]"

        # link posts must have link_preview, others must not
        if p.post_type == PostType.LINK and p.link_preview is None:
            errors.append(f"{tag}: LINK post missing link_preview")
        if p.post_type != PostType.LINK and p.link_preview is not None:
            errors.append(f"{tag}: non-LINK post has link_preview")

        # media: IMAGE/VIDEO should have media; TEXT/LINK/POLL should not
        if p.post_type == PostType.IMAGE and len(p.media) == 0:
            errors.append(f"{tag}: IMAGE post has no media")
        if p.post_type == PostType.VIDEO and len(p.media) == 0:
            errors.append(f"{tag}: VIDEO post has no media")
        if p.post_type in (PostType.TEXT, PostType.POLL) and len(p.media) > 0:
            errors.append(f"{tag}: TEXT/POLL post should have empty media")

        # timestamps monotonic
        if p.updated_at < p.created_at:
            errors.append(f"{tag}: updated_at < created_at")

        # last_comment_at consistency
        if p.stats.last_comment_at:
            ref = p.published_at or p.created_at
            if p.stats.last_comment_at < ref:
                errors.append(f"{tag}: last_comment_at < published/created")

        # engagement_rate check
        total_eng = (
            p.stats.like_count
            + p.stats.comment_count
            + p.stats.share_count
            + p.stats.save_count
        )
        expected = round(100 * total_eng / max(p.stats.view_count, 1), 2)
        if abs(p.stats.engagement_rate - expected) > 0.01:
            errors.append(
                f"{tag}: engagement_rate {p.stats.engagement_rate} != expected {expected}"
            )

    return errors


# ================================================================
# Entry point
# ================================================================

async def main():
    client = AsyncIOMotorClient(MONGODB_URL)
    await init_beanie(database=client[DATABASE_NAME], document_models=[Post, User])

    # Fetch existing users for author pools
    users = await User.find({"deleted_at": None}).to_list()
    if not users:
        print("No users found. Run seed.py first.")
        sys.exit(1)

    # Build author pools — first 20 % as leaders, rest as users
    user_authors = []
    leader_authors = []
    leader_cutoff = max(1, len(users) // 5)

    for i, u in enumerate(users):
        entry = {
            "user_id": u.id,
            "display_name": u.profile.display_name,
            "avatar": u.profile.avatar,
        }
        if i < leader_cutoff:
            leader_authors.append(entry)
        else:
            user_authors.append(entry)

    # With a single user, they serve both pools
    if not user_authors:
        user_authors = leader_authors[:]

    # Generate posts
    posts = []
    for i in range(NUM_POSTS):
        post, lifecycle = generate_post(i, user_authors, leader_authors)
        posts.append(post)
        print(f"Post [{i + 1}/{NUM_POSTS}] {post.post_type.value:<6} [{lifecycle}]")

    # Validation pass
    errors = validate_posts(posts)
    if errors:
        print(f"\nValidation found {len(errors)} error(s):")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)

    # Bulk insert
    await Post.insert_many(posts)

    # Summary
    published = sum(1 for p in posts if p.published_at and not p.deleted_at)
    drafts = sum(1 for p in posts if not p.published_at and not p.deleted_at)
    deleted = sum(1 for p in posts if p.deleted_at)
    by_type = {}
    for p in posts:
        by_type[p.post_type.value] = by_type.get(p.post_type.value, 0) + 1

    print(f"\nDone. {NUM_POSTS} posts inserted.")
    print(f"  Published: {published}, Draft: {drafts}, Deleted: {deleted}")
    print(f"  By type: {by_type}")


if __name__ == "__main__":
    asyncio.run(main())
