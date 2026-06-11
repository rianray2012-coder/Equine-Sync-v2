"""Phase 8D — email/recap brand polish + digest raw-id humanization.

Pure-composition tests (no DB, no network). Verify:
  * the Equine-Sync wordmark + tagline + "Sync" lilac appear in HTML & text
  * the old "EquineSync" string is gone from rendered output
  * the hosted horse mark appears only when an app base URL is provided
  * subjects are hyphenated "Equine-Sync"
  * a leaked engine token ("Follow-up: vetfu-<uuid>") never reaches the owner
"""
from datetime import datetime, timezone, timedelta

from owner_digest import (
    render_digest_html,
    render_digest_text,
    render_weekly_recap_html,
    render_weekly_recap_text,
    _upcoming_phrase,
)

LILAC = "#6E5A99"


def _digest_payload():
    return {
        "for_date": "2026-06-11",
        "horse_count": 1,
        "updates_count": 1,
        "sections": [{"horse_id": "h1", "horse_name": "Halo",
                      "lines": ["Halo received Bute today."]}],
    }


def _weekly_payload():
    return {
        "kind": "weekly",
        "sections": [{"horse_id": "h1", "horse_name": "Halo",
                      "lines": ["Halo completed all scheduled medications this week."]}],
        "upcoming_count": 2,
        "updates_count": 2,
    }


# ---------------------------------------------------------------- brand presence

def test_digest_html_has_brand_wordmark_tagline_and_no_old_name():
    html = render_digest_html(_digest_payload())
    assert "Equine-" in html and ">Sync<" in html
    assert "Every Horse. Every Task. In Sync." in html
    assert LILAC in html  # "Sync" rendered in Smoky Lilac
    assert "EquineSync" not in html  # old un-hyphenated name gone
    # section + headline preserved
    assert "Daily Care" in html
    assert "Today at the barn" in html


def test_weekly_html_has_brand_and_preserves_sections():
    html = render_weekly_recap_html(_weekly_payload())
    assert "Equine-" in html and ">Sync<" in html
    assert "Every Horse. Every Task. In Sync." in html
    assert "EquineSync" not in html
    assert "Weekly Recap" in html
    assert "This week at the barn" in html
    assert "Looking ahead" in html
    assert "2 upcoming care appointments" in html


def test_text_versions_carry_brand_and_drop_old_name():
    dtext = render_digest_text(_digest_payload())
    wtext = render_weekly_recap_text(_weekly_payload())
    for t in (dtext, wtext):
        assert t.startswith("Equine-Sync")
        assert "Every Horse. Every Task. In Sync." in t
        assert "EquineSync\n" not in t and "EquineSync —" not in t
    assert "Today at the barn" in dtext
    assert "This week at the barn" in wtext


# ---------------------------------------------------------------- hosted mark gating

def test_hosted_mark_only_when_base_url_present():
    without = render_digest_html(_digest_payload(), app_base_url="")
    assert "<img" not in without  # text wordmark only

    with_url = render_digest_html(_digest_payload(), app_base_url="https://app.example.com/")
    assert 'src="https://app.example.com/icon-192.png"' in with_url
    assert 'alt="Equine-Sync"' in with_url


# ---------------------------------------------------------------- subjects (indirect)

def test_subjects_are_hyphenated():
    # subjects are built inside the send_* functions; assert the literal that
    # those functions interpolate is hyphenated by checking the source values.
    import owner_digest
    import inspect
    src = inspect.getsource(owner_digest)
    assert 'Equine-Sync · Today\'s update' in src
    assert 'Equine-Sync · This week at the barn' in src
    assert "EquineSync ·" not in src


# ---------------------------------------------------------------- raw-id humanization

def _vet_task(title):
    when = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    return {"category": "vet", "scheduled_at": when, "title": title}


def test_upcoming_phrase_humanizes_engine_token():
    leaked = "Follow-up: vetfu-b1068a4b-4a41-46f8-8e89-62bb779a9df4"
    line = _upcoming_phrase([_vet_task(leaked)], "Halo")
    assert line is not None
    assert "vetfu" not in line.lower()
    assert "b1068a4b" not in line
    assert "follow-up" in line.lower()        # reads as a human follow-up
    assert "is scheduled for" in line          # singular grammar for the label


def test_upcoming_phrase_keeps_genuine_human_title():
    line = _upcoming_phrase([_vet_task("Spring Vaccines")], "Halo")
    assert "Spring Vaccines are scheduled for" in line


def test_upcoming_phrase_empty_title_falls_back_cleanly():
    line = _upcoming_phrase([_vet_task("")], "Halo")
    assert line is not None
    assert "is scheduled for" in line
    # no stray "None" / empty artifacts
    assert "none" not in line.lower()
