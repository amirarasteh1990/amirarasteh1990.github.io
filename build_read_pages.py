#!/usr/bin/env python3
"""
build_read_pages.py — Generate the per-language Opening pages /sedaha/read/<slug>/ for
editions beyond the hand-maintained EN/FA/DA three, straight from the BOOK repo's
edition sources. Single source of truth = the book repo.

Per language it renders one page from:
  * the edition's own Opening        — Other_Languages/<CODE>/00_Opening.md, block 0007
  * the edition's own Opening title  — block 0006 (page <h1> and browser-tab title)
  * the edition's own book title     — 00_Title_Info.md, block 0001, first line: swapped
                                       into og:title in place of the "Sedaha (Sounds)"
                                       placeholder, wrapped «…» (or the CJK brackets)
  * the LANGS table below            — share-card lines (og:title / og:description),
                                       the localized CTA paragraph, lang/dir/og:locale

It also (idempotently) wires discovery:
  * /sedaha/index.html               — adds an "Opening" link to each language's row
  * sitemap.xml                      — adds the new URLs

The share-card description per language is derived from that edition's OWN Opening
sentence (the "thread of words that were once sounds" image), so the card always
speaks with the translation's own voice. The EN/FA/DA pages are NOT touched here —
they are maintained by hand + sync_book_text.py.

Run whenever an Opening changes in the book repo, or when adding a language:
    python build_read_pages.py            # (re)generate all pages + wiring
    python build_read_pages.py --check    # report drift only; change nothing; exit 1 if stale
"""
from __future__ import annotations

import argparse
import datetime
import html
import json
import re
import sys
from pathlib import Path

from sync_footers import footer_html  # one canonical footer for the whole site
from sync_appnav import appnav_html   # one canonical nav shell for the whole site
from sync_head import head_html        # one canonical PWA head block for the whole site

SITE = Path(__file__).resolve().parent
BOOK_VOL = SITE.parent / "1_Sedaha" / "Volume1"  # sibling book repo. Edit if moved.
BOOK_LANGS = BOOK_VOL / "00_source_md" / "Other_Languages"
READ_DIR = SITE / "sedaha" / "read"
SOUNDS = SITE / "sedaha" / "index.html"
SITEMAP = SITE / "sitemap.xml"
STATUS_PAGE = SITE / "sedaha" / "languages" / "index.html"
RELEASE_TAG = "books"  # GitHub release the /sedaha/ download buttons point at
RELEASE_URL = "https://github.com/amirarasteh1990/amirarasteh1990.github.io/releases/download/books"

# Generated pages carry the standard footer. Change it in sync_footers.py, then
# rerun this script so the 111 Opening pages and /sedaha/languages/ follow.
FOOTER = footer_html()
# Generated pages live in the book section, so their shell highlights "Books".
NAV = appnav_html("books")
HEAD = head_html()  # PWA manifest + standalone hints, before </head>


def reader_tools_html() -> str:
    """The reading toolbar: type size, measure, light/dark. Wordless on purpose --
    it sits on 114 pages in 114 scripts, and an English label would be the only
    English on a Khmer page. assets/js/reader.js gives it behaviour and remembers
    the choice for every edition at once.

    Nothing here is visible English, but the labels a screen reader announces are,
    so the group is marked lang="en": a Japanese reader's screen reader then says
    them in an English voice instead of reading English letters through Japanese.

    The three hand-written Opening pages (EN/FA/DA) carry this same block; check.py
    compares them against this function so the four cannot drift apart."""
    return (
        '  <div class="reader-tools" role="group" lang="en" aria-label="Reading settings">\n'
        '    <button type="button" class="rt rt-smaller" aria-label="Smaller text" '
        'title="Smaller text"><span class="a-sm" aria-hidden="true">A</span></button>\n'
        '    <button type="button" class="rt rt-larger" aria-label="Larger text" '
        'title="Larger text"><span class="a-lg" aria-hidden="true">A</span></button>\n'
        '    <button type="button" class="rt rt-width" aria-label="Wider lines" '
        'title="Wider lines" aria-pressed="false">'
        '<svg aria-hidden="true" viewBox="0 0 24 24">'
        '<path d="M3 4v16M21 4v16"/><path d="M7 12h10"/>'
        '<path d="m9.5 9.5-2.5 2.5 2.5 2.5"/><path d="m14.5 9.5 2.5 2.5-2.5 2.5"/>'
        '</svg></button>\n'
        '    <button type="button" class="rt rt-theme" data-mode="auto" '
        'aria-label="Colours: following the system. Switch to light." '
        'title="Colours: following the system. Switch to light.">'
        '<svg aria-hidden="true" viewBox="0 0 24 24">'
        '<g class="i-auto"><circle cx="12" cy="12" r="7.5"/>'
        '<path d="M12 4.5a7.5 7.5 0 0 1 0 15z" fill="currentColor" stroke="none"/></g>'
        '<g class="i-light"><circle cx="12" cy="12" r="4.2"/>'
        '<path d="M12 2.5v2.2M12 19.3v2.2M2.5 12h2.2M19.3 12h2.2'
        'M5.3 5.3l1.6 1.6M17.1 17.1l1.6 1.6M18.7 5.3l-1.6 1.6M6.9 17.1l-1.6 1.6"/></g>'
        '<g class="i-dark"><path d="M20.5 14.8A8.6 8.6 0 0 1 9.2 3.5'
        'a8.6 8.6 0 1 0 11.3 11.3z"/></g>'
        '</svg></button>\n'
        '  </div>'
    )


READER_TOOLS = reader_tools_html()

# The three editions that exist in full. The strip above every opening offers them
# in their own names, so a reader who wants the whole book can see where it is.
COMPLETE = [("", "en", "English"), ("fa/", "fa", "فارسی"), ("da/", "da", "Dansk")]

# The buttons under the localized invitation. That sentence tells the reader the
# WHOLE book is free in these three, so the buttons hand over the whole book: they
# used to lead to another Opening page, which read as a promise withdrawn. The
# format is on the button so a download is never a surprise, and "EPUB" is the
# file's own name in every language.
def full_book_btns(complete: int) -> str:
    """The three the book was published in, then the way to all the rest.

    The localized sentence above these says the whole book is free in Persian,
    English and Danish. That was the whole truth at three complete editions and
    reads as a limit at twenty-three, so the row ends with the count and an arrow
    to the catalogue. A number and an arrow, not an English phrase: these pages are
    in 111 languages that are not English, and the strip at the top already uses
    exactly this idiom."""
    out = [f'      <a class="btn" href="{RELEASE_URL}/Sedaha_{file}.epub" '
           f'aria-label="{name}: the complete book, EPUB"><span lang="{lang}">{native}</span>'
           f'<span class="btn-fmt" lang="en">EPUB</span></a>'
           for file, lang, native, name in (("Farsi", "fa", "فارسی", "Persian"),
                                            ("English", "en", "English", "English"),
                                            ("Danish", "da", "Dansk", "Danish"))]
    out.append(f'      <a class="btn" href="/sedaha/#allLangs" lang="en" '
               f'aria-label="All {complete} complete editions">{complete} &rarr;</a>')
    return "\n".join(out)


SHARE_SVG = ('<svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke-width="2" '
             'stroke-linecap="round" stroke-linejoin="round"><path d="M12 2v13"/>'
             '<path d="m16 6-4-4-4 4"/>'
             '<path d="M20 10v9a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2v-9"/></svg>')


def top_actions_html(row: dict | None, url: str, desc: str, en: str) -> str:
    """The same offer as the foot of the page, at the head of it.

    A reader who arrives already knowing they want the book should not have to read
    the opening first to find the download, and one who wants to pass the page on
    should not have to reach the end to do it.

    What it offers is this edition's OWN files. The foot of an incomplete edition
    offers Persian, English and Danish instead, with a sentence in the reader's
    language explaining why -- and those three, stripped to bare EPUB chips at the
    top of a German page with no sentence around them, would read as a German
    download that is not one. So an opening-only page gets the share button alone,
    and its foot keeps the fuller offer."""
    out = []
    for f in (row["fmts"] if row and row["state"] == "ready" and row["fmts"] else []):
        out.append(f'    <a class="op-act" href="{RELEASE_URL}/{row["stem"]}.{f}" '
                   f'aria-label="{row["en"]}: the complete book, {f.upper()}">'
                   f'{f.upper()}</a>')
    out.append(f'    <button type="button" class="op-act op-act-icon btn-share" '
               f'aria-label="Share this opening" title="Share this opening" '
               f'data-share-url="{url}" data-share-title="Sedaha &mdash; Book One" '
               f'data-share-text="{_esc(desc)}">{SHARE_SVG}</button>')
    return ('  <div class="op-actions" lang="en" dir="ltr">\n'
            + "\n".join(out) + "\n  </div>")


def op_langs_html(slug: str, lang: str = "", native: str = "") -> str:
    """The strip above the opening: this same opening in the complete editions, the
    language being read, and the way to the other 114.

    It used to open with the words "Opening in:" and end with "all 114", which put
    English on a page whose whole point is that it is not in English. A globe says
    the same thing in no language, and the languages name themselves. The remaining
    English is the label a screen reader announces, so the strip is marked lang="en"
    and each name carries its own lang.

    slug is the edition being read ("" for English, "fa/", "ja/" ...); lang/native
    are needed only for an edition outside the complete three."""
    out = ['  <nav class="op-langs" lang="en" aria-label="This opening in other languages">',
           '    <svg class="op-globe" aria-hidden="true" viewBox="0 0 24 24">'
           '<circle cx="12" cy="12" r="9"/><path d="M3.2 9.2h17.6M3.2 14.8h17.6"/>'
           '<path d="M12 3c2.6 2.4 4 5.4 4 9s-1.4 6.6-4 9c-2.6-2.4-4-5.4-4-9s1.4-6.6 4-9z"/>'
           '</svg>']
    entries = list(COMPLETE)
    if not any(s == slug for s, _l, _n in entries):
        entries.append((slug, lang, native))
    for i, (s, lg, name) in enumerate(entries):
        tail = "" if i == len(entries) - 1 else " &middot;"
        if s == slug:
            out.append(f'    <span class="cur" lang="{lg}" aria-current="page">{name}</span>{tail}')
        else:
            out.append(f'    <a href="/sedaha/read/{s}" lang="{lg}">{name}</a>{tail}')
    out.append('    &middot; <a href="/sedaha/#allLangs" aria-label="Where all 114 languages stand">'
               '114 &rarr;</a>')
    out.append('  </nav>')
    return "\n".join(out)

# One entry per generated page. og_desc = the thread line in that edition's own words
# (grounded in its Opening sentence); cta = localized two-sentence invitation.
# slug = URL path under /sedaha/read/; code = folder in Other_Languages (also the lane tag).
# In og_title, "Sedaha (Sounds)" is a PLACEHOLDER: at render time it is replaced by the
# edition's own translated title (00_Title_Info.md block 0001), wrapped «…» / 《…》 / 『…』.
LANGS = [
    {"code": "DE", "slug": "de", "lang": "de", "rtl": False, "locale": "de_DE", "en": "German", "native": "Deutsch",
     "og_title": "Der Auftakt von Sedaha (Sounds), auf Deutsch",
     "og_desc": "Der Faden aus Wörtern, die einst Klänge waren…",
     "cta": "Das Buch beginnt hier. Die vollständige deutsche Ausgabe ist unterwegs; bis dahin ist das ganze Buch kostenlos zu lesen: auf Persisch, Englisch und Dänisch."},
    {"code": "FR", "slug": "fr", "lang": "fr", "rtl": False, "locale": "fr_FR", "en": "French", "native": "Français",
     "og_title": "L'ouverture de Sedaha (Sounds), en français",
     "og_desc": "Le fil des mots qui furent jadis des sons…",
     "cta": "Le livre commence ici. L'édition française complète est en route ; d'ici là, le livre entier se lit gratuitement : en persan, en anglais et en danois."},
    {"code": "ES", "slug": "es", "lang": "es", "rtl": False, "locale": "es_ES", "en": "Spanish", "native": "Español",
     "og_title": "La apertura de Sedaha (Sounds), en español",
     "og_desc": "El hilo de palabras que alguna vez fueron sonidos…",
     "cta": "El libro comienza aquí. La edición completa en español está en camino; mientras tanto, el libro entero puede leerse gratis: en persa, en inglés y en danés."},
    {"code": "IT", "slug": "it", "lang": "it", "rtl": False, "locale": "it_IT", "en": "Italian", "native": "Italiano",
     "og_title": "L'apertura di Sedaha (Sounds), in italiano",
     "og_desc": "Il filo di parole che un tempo erano suoni…",
     "cta": "Il libro comincia qui. L'edizione italiana completa è in arrivo; nel frattempo, l'intero libro si legge gratis: in persiano, in inglese e in danese."},
    {"code": "NL", "slug": "nl", "lang": "nl", "rtl": False, "locale": "nl_NL", "en": "Dutch", "native": "Nederlands",
     "og_title": "De opening van Sedaha (Sounds), in het Nederlands",
     "og_desc": "De draad van woorden die ooit klanken waren…",
     "cta": "Het boek begint hier. De volledige Nederlandse editie is onderweg; tot die tijd is het hele boek gratis te lezen: in het Perzisch, Engels en Deens."},
    {"code": "PT", "slug": "pt", "lang": "pt", "rtl": False, "locale": "pt_PT", "en": "Portuguese", "native": "Português",
     "og_title": "A abertura de Sedaha (Sounds), em português",
     "og_desc": "O fio de palavras que outrora foram sons…",
     "cta": "O livro começa aqui. A edição portuguesa completa está a caminho; até lá, o livro inteiro pode ser lido gratuitamente: em persa, em inglês e em dinamarquês."},
    {"code": "PT-BR", "slug": "pt-br", "lang": "pt-BR", "rtl": False, "locale": "pt_BR", "en": "Portuguese (Brazil)", "native": "Português (Brasil)",
     "og_title": "A abertura de Sedaha (Sounds), em português do Brasil",
     "og_desc": "O fio de palavras que um dia foram sons…",
     "cta": "O livro começa aqui. A edição completa em português do Brasil está a caminho; até lá, o livro inteiro pode ser lido de graça: em persa, em inglês e em dinamarquês."},
    {"code": "SV", "slug": "sv", "lang": "sv", "rtl": False, "locale": "sv_SE", "en": "Swedish", "native": "Svenska",
     "og_title": "Öppningen av Sedaha (Sounds), på svenska",
     "og_desc": "Tråden av ord som en gång var ljud…",
     "cta": "Boken börjar här. Den fullständiga svenska utgåvan är på väg; tills dess kan hela boken läsas gratis: på persiska, engelska och danska."},
    {"code": "NO", "slug": "no", "lang": "no", "rtl": False, "locale": "nb_NO", "en": "Norwegian", "native": "Norsk",
     "og_title": "Åpningen av Sedaha (Sounds), på norsk",
     "og_desc": "Tråden av ord som en gang var lyder…",
     "cta": "Boken begynner her. Den fullstendige norske utgaven er på vei; inntil da kan hele boken leses gratis: på persisk, engelsk og dansk."},
    {"code": "FI", "slug": "fi", "lang": "fi", "rtl": False, "locale": "fi_FI", "en": "Finnish", "native": "Suomi",
     "og_title": "Sedaha (Sounds): avaus suomeksi",
     "og_desc": "Kerran ääninä olleiden sanojen lanka…",
     "cta": "Kirja alkaa tästä. Täydellinen suomenkielinen laitos on tulossa; siihen asti koko kirjan voi lukea ilmaiseksi: persiaksi, englanniksi ja tanskaksi."},
    {"code": "IS", "slug": "is", "lang": "is", "rtl": False, "locale": "is_IS", "en": "Icelandic", "native": "Íslenska",
     "og_title": "Opnun Sedaha (Sounds), á íslensku",
     "og_desc": "Þráður orða sem voru einu sinni hljóð…",
     "cta": "Bókin hefst hér. Íslenska útgáfan í heild er á leiðinni; þangað til má lesa alla bókina ókeypis: á persnesku, ensku og dönsku."},
    {"code": "PL", "slug": "pl", "lang": "pl", "rtl": False, "locale": "pl_PL", "en": "Polish", "native": "Polski",
     "og_title": "Otwarcie Sedaha (Sounds), po polsku",
     "og_desc": "Nić ze słów, które niegdyś były dźwiękami…",
     "cta": "Książka zaczyna się tutaj. Pełne polskie wydanie jest w drodze; do tego czasu całą książkę można czytać za darmo: po persku, angielsku i duńsku."},
    {"code": "CS", "slug": "cs", "lang": "cs", "rtl": False, "locale": "cs_CZ", "en": "Czech", "native": "Čeština",
     "og_title": "Otevření knihy Sedaha (Sounds), česky",
     "og_desc": "Nit slov, která byla kdysi zvuky…",
     "cta": "Kniha začíná zde. Úplné české vydání je na cestě; do té doby lze celou knihu číst zdarma: persky, anglicky a dánsky."},
    {"code": "SK", "slug": "sk", "lang": "sk", "rtl": False, "locale": "sk_SK", "en": "Slovak", "native": "Slovenčina",
     "og_title": "Otvorenie knihy Sedaha (Sounds), po slovensky",
     "og_desc": "Niť slov, ktoré boli kedysi zvukmi…",
     "cta": "Kniha sa začína tu. Úplné slovenské vydanie je na ceste; dovtedy si celú knihu možno prečítať zadarmo: po perzsky, anglicky a dánsky."},
    {"code": "HU", "slug": "hu", "lang": "hu", "rtl": False, "locale": "hu_HU", "en": "Hungarian", "native": "Magyar",
     "og_title": "A Sedaha (Sounds) nyitánya, magyarul",
     "og_desc": "Cérna szavakból, amelyek egykor hangok voltak…",
     "cta": "A könyv itt kezdődik. A teljes magyar kiadás úton van; addig az egész könyv ingyen olvasható: perzsául, angolul és dánul."},
    {"code": "RO", "slug": "ro", "lang": "ro", "rtl": False, "locale": "ro_RO", "en": "Romanian", "native": "Română",
     "og_title": "Deschiderea cărții Sedaha (Sounds), în română",
     "og_desc": "Firul de cuvinte care au fost cândva sunete…",
     "cta": "Cartea începe aici. Ediția completă în română este pe drum; până atunci, întreaga carte se poate citi gratuit: în persană, în engleză și în daneză."},
    {"code": "BG", "slug": "bg", "lang": "bg", "rtl": False, "locale": "bg_BG", "en": "Bulgarian", "native": "Български",
     "og_title": "Встъплението на Sedaha (Sounds), на български",
     "og_desc": "Нишка от думи, които някога са били звуци…",
     "cta": "Книгата започва оттук. Пълното българско издание е на път; дотогава цялата книга може да се чете безплатно: на персийски, английски и датски."},
    {"code": "EL", "slug": "el", "lang": "el", "rtl": False, "locale": "el_GR", "en": "Greek", "native": "Ελληνικά",
     "og_title": "Το άνοιγμα του Sedaha (Sounds), στα ελληνικά",
     "og_desc": "Το νήμα των λέξεων που κάποτε ήταν ήχοι…",
     "cta": "Το βιβλίο αρχίζει εδώ. Η πλήρης ελληνική έκδοση είναι καθ' οδόν· ως τότε, ολόκληρο το βιβλίο διαβάζεται δωρεάν: στα περσικά, στα αγγλικά και στα δανικά."},
    {"code": "UK", "slug": "uk", "lang": "uk", "rtl": False, "locale": "uk_UA", "en": "Ukrainian", "native": "Українська",
     "og_title": "Вступ до Sedaha (Sounds), українською",
     "og_desc": "Нитка зі слів, що колись були звуками…",
     "cta": "Книга починається тут. Повне українське видання вже в дорозі; а поки що всю книгу можна читати безкоштовно: перською, англійською та данською."},
    {"code": "RU", "slug": "ru", "lang": "ru", "rtl": False, "locale": "ru_RU", "en": "Russian", "native": "Русский",
     "og_title": "Вступление к Sedaha (Sounds), по-русски",
     "og_desc": "Нить из слов, которые когда-то были звуками…",
     "cta": "Книга начинается здесь. Полное русское издание уже в пути; а пока всю книгу можно читать бесплатно: на персидском, английском и датском."},
    {"code": "HR", "slug": "hr", "lang": "hr", "rtl": False, "locale": "hr_HR", "en": "Croatian", "native": "Hrvatski",
     "og_title": "Otvaranje knjige Sedaha (Sounds), na hrvatskom",
     "og_desc": "Nit riječi koje su nekad bile zvukovi…",
     "cta": "Knjiga počinje ovdje. Potpuno hrvatsko izdanje je na putu; do tada se cijela knjiga može čitati besplatno: na perzijskom, engleskom i danskom."},
    {"code": "SR", "slug": "sr", "lang": "sr", "rtl": False, "locale": "sr_RS", "en": "Serbian", "native": "Српски",
     "og_title": "Отварање књиге Sedaha (Sounds), на српском",
     "og_desc": "Нит речи које су некада биле звуци…",
     "cta": "Књига почиње овде. Потпуно српско издање је на путу; дотад се цела књига може читати бесплатно: на персијском, енглеском и данском."},
    {"code": "SL", "slug": "sl", "lang": "sl", "rtl": False, "locale": "sl_SI", "en": "Slovenian", "native": "Slovenščina",
     "og_title": "Uvod v Sedaha (Sounds), v slovenščini",
     "og_desc": "Nit besed, ki so bile nekoč zvoki…",
     "cta": "Knjiga se začne tukaj. Celotna slovenska izdaja je na poti; do takrat je vso knjigo mogoče brati brezplačno: v perzijščini, angleščini in danščini."},
    {"code": "SQ", "slug": "sq", "lang": "sq", "rtl": False, "locale": "sq_AL", "en": "Albanian", "native": "Shqip",
     "og_title": "Hapja e Sedaha (Sounds), në shqip",
     "og_desc": "Filli i fjalëve që dikur ishin tinguj…",
     "cta": "Libri fillon këtu. Botimi i plotë në shqip është rrugës; deri atëherë, i gjithë libri lexohet falas: në persisht, në anglisht dhe në danisht."},
    {"code": "LT", "slug": "lt", "lang": "lt", "rtl": False, "locale": "lt_LT", "en": "Lithuanian", "native": "Lietuvių",
     "og_title": "Sedaha (Sounds) pradžia, lietuviškai",
     "og_desc": "Siūlas iš žodžių, kurie kadaise buvo garsai…",
     "cta": "Knyga prasideda čia. Pilnas lietuviškas leidimas jau pakeliui; iki tol visą knygą galima skaityti nemokamai: persiškai, angliškai ir daniškai."},
    {"code": "LV", "slug": "lv", "lang": "lv", "rtl": False, "locale": "lv_LV", "en": "Latvian", "native": "Latviešu",
     "og_title": "Sedaha (Sounds) ievads, latviski",
     "og_desc": "Vārdu pavediens, kas kādreiz bija skaņas…",
     "cta": "Grāmata sākas šeit. Pilns latviešu izdevums ir ceļā; līdz tam visu grāmatu var lasīt bez maksas: persiešu, angļu un dāņu valodā."},
    {"code": "ET", "slug": "et", "lang": "et", "rtl": False, "locale": "et_EE", "en": "Estonian", "native": "Eesti",
     "og_title": "Sedaha (Sounds) avamine, eesti keeles",
     "og_desc": "Lõng sõnadest, mis olid kunagi helid…",
     "cta": "Raamat algab siit. Täielik eestikeelne väljaanne on teel; seni saab kogu raamatut lugeda tasuta: pärsia, inglise ja taani keeles."},
    {"code": "TR", "slug": "tr", "lang": "tr", "rtl": False, "locale": "tr_TR", "en": "Turkish", "native": "Türkçe",
     "og_title": "Sedaha (Sounds) açılışı, Türkçe",
     "og_desc": "Bir zamanlar ses olan kelimelerin ipliği…",
     "cta": "Kitap burada başlıyor. Türkçe baskının tamamı yolda; o zamana kadar kitabın tümü ücretsiz okunabilir: Farsça, İngilizce ve Danca."},
    {"code": "AZ", "slug": "az", "lang": "az", "rtl": False, "locale": "az_AZ", "en": "Azerbaijani", "native": "Azərbaycanca",
     "og_title": "Sedaha (Sounds) açılışı, Azərbaycanca",
     "og_desc": "Bir vaxtlar səs olan sözlərin ipi…",
     "cta": "Kitab buradan başlayır. Tam Azərbaycanca nəşr yoldadır; o vaxta qədər bütün kitabı pulsuz oxumaq olar: farsca, ingiliscə və danca."},
    {"code": "KA", "slug": "ka", "lang": "ka", "rtl": False, "locale": "ka_GE", "en": "Georgian", "native": "ქართული",
     "og_title": "Sedaha (Sounds): გახსნა ქართულად",
     "og_desc": "ძაფი სიტყვებისა, რომლებიც ოდესღაც ხმები იყვნენ…",
     "cta": "წიგნი აქ იწყება. სრული ქართული გამოცემა გზაშია; მანამდე მთელი წიგნის წაკითხვა უფასოდ შეიძლება: სპარსულად, ინგლისურად და დანიურად."},
    {"code": "HY", "slug": "hy", "lang": "hy", "rtl": False, "locale": "hy_AM", "en": "Armenian", "native": "Հայերեն",
     "og_title": "Sedaha (Sounds). Բացումը՝ հայերեն",
     "og_desc": "Բառերի թելը, որ ժամանակին ձայներ են եղել…",
     "cta": "Գիրքը սկսվում է հենց այստեղից։ Ամբողջական հայերեն հրատարակությունը ճանապարհին է. մինչ այդ ամբողջ գիրքը կարելի է կարդալ անվճար՝ պարսկերեն, անգլերեն և դանիերեն։"},
    {"code": "AR", "slug": "ar", "lang": "ar", "rtl": True, "locale": "ar_AR", "en": "Arabic", "native": "العربية",
     "og_title": "افتتاحية Sedaha (Sounds)، بالعربية",
     "og_desc": "خيط من الكلمات التي كانت يوماً أصواتاً…",
     "cta": "يبدأ الكتاب من هنا. الطبعة العربية الكاملة في الطريق؛ وحتى ذلك الحين يمكن قراءة الكتاب كاملاً مجاناً: بالفارسية والإنجليزية والدنماركية."},
    {"code": "HE", "slug": "he", "lang": "he", "rtl": True, "locale": "he_IL", "en": "Hebrew", "native": "עברית",
     "og_title": "הפתיחה של Sedaha (Sounds), בעברית",
     "og_desc": "חוט של מילים שהיו פעם קולות…",
     "cta": "הספר מתחיל כאן. המהדורה העברית המלאה בדרך; עד אז אפשר לקרוא את הספר כולו בחינם: בפרסית, באנגלית ובדנית."},
    {"code": "UR", "slug": "ur", "lang": "ur", "rtl": True, "locale": "ur_PK", "en": "Urdu", "native": "اردو",
     "og_title": "Sedaha (Sounds) کا آغاز، اردو میں",
     "og_desc": "الفاظ کا وہ دھاگا جو کبھی آوازیں تھے…",
     "cta": "کتاب یہیں سے شروع ہوتی ہے۔ مکمل اردو ایڈیشن راستے میں ہے؛ تب تک پوری کتاب مفت پڑھی جا سکتی ہے: فارسی، انگریزی اور ڈینش میں۔"},
    {"code": "HI", "slug": "hi", "lang": "hi", "rtl": False, "locale": "hi_IN", "en": "Hindi", "native": "हिन्दी",
     "og_title": "Sedaha (Sounds) का प्रारंभ, हिन्दी में",
     "og_desc": "उन शब्दों का धागा जो कभी ध्वनियाँ थे…",
     "cta": "किताब यहीं से शुरू होती है। पूरा हिन्दी संस्करण रास्ते में है; तब तक पूरी किताब मुफ़्त पढ़ी जा सकती है: फ़ारसी, अंग्रेज़ी और डेनिश में।"},
    {"code": "BN", "slug": "bn", "lang": "bn", "rtl": False, "locale": "bn_IN", "en": "Bengali", "native": "বাংলা",
     "og_title": "Sedaha (Sounds)-এর শুরু, বাংলায়",
     "og_desc": "শব্দের সুতো, যা একদিন ধ্বনি ছিল…",
     "cta": "বইটি এখান থেকেই শুরু। সম্পূর্ণ বাংলা সংস্করণ আসছে; ততদিন পুরো বইটি বিনামূল্যে পড়া যায়: ফারসি, ইংরেজি ও ড্যানিশ ভাষায়।"},
    {"code": "PA", "slug": "pa", "lang": "pa", "rtl": False, "locale": "pa_IN", "en": "Punjabi", "native": "ਪੰਜਾਬੀ",
     "og_title": "Sedaha (Sounds) ਦੀ ਸ਼ੁਰੂਆਤ, ਪੰਜਾਬੀ ਵਿੱਚ",
     "og_desc": "ਉਨ੍ਹਾਂ ਸ਼ਬਦਾਂ ਦਾ ਧਾਗਾ ਜੋ ਕਦੇ ਆਵਾਜ਼ਾਂ ਸਨ…",
     "cta": "ਕਿਤਾਬ ਇੱਥੋਂ ਹੀ ਸ਼ੁਰੂ ਹੁੰਦੀ ਹੈ। ਪੂਰਾ ਪੰਜਾਬੀ ਐਡੀਸ਼ਨ ਰਾਹ ਵਿੱਚ ਹੈ; ਉਦੋਂ ਤੱਕ ਪੂਰੀ ਕਿਤਾਬ ਮੁਫ਼ਤ ਪੜ੍ਹੀ ਜਾ ਸਕਦੀ ਹੈ: ਫ਼ਾਰਸੀ, ਅੰਗਰੇਜ਼ੀ ਅਤੇ ਡੈਨਿਸ਼ ਵਿੱਚ।"},
    {"code": "TA", "slug": "ta", "lang": "ta", "rtl": False, "locale": "ta_IN", "en": "Tamil", "native": "தமிழ்",
     "og_title": "Sedaha (Sounds): தொடக்கம், தமிழில்",
     "og_desc": "ஒருகாலத்தில் ஒலிகளாக இருந்த சொற்களின் நூல்…",
     "cta": "புத்தகம் இங்கிருந்தே தொடங்குகிறது. முழுமையான தமிழ்ப் பதிப்பு வரும் வழியில் உள்ளது; அதுவரை முழு புத்தகத்தையும் இலவசமாக வாசிக்கலாம்: பாரசீகம், ஆங்கிலம், டேனிஷ் மொழிகளில்."},
    {"code": "TE", "slug": "te", "lang": "te", "rtl": False, "locale": "te_IN", "en": "Telugu", "native": "తెలుగు",
     "og_title": "Sedaha (Sounds): ప్రారంభం, తెలుగులో",
     "og_desc": "ఒకప్పుడు శబ్దాలుగా ఉన్న పదాల దారం…",
     "cta": "పుస్తకం ఇక్కడి నుంచే మొదలవుతుంది. పూర్తి తెలుగు ఎడిషన్ దారిలో ఉంది; అప్పటివరకు మొత్తం పుస్తకాన్ని ఉచితంగా చదవవచ్చు: పర్షియన్, ఇంగ్లీష్, డానిష్ భాషల్లో."},
    {"code": "ML", "slug": "ml", "lang": "ml", "rtl": False, "locale": "ml_IN", "en": "Malayalam", "native": "മലയാളം",
     "og_title": "Sedaha (Sounds): ആമുഖം, മലയാളത്തിൽ",
     "og_desc": "ഒരിക്കൽ ശബ്ദങ്ങളായിരുന്ന വാക്കുകളുടെ നൂൽ…",
     "cta": "പുസ്തകം ഇവിടെ നിന്നു തുടങ്ങുന്നു. സമ്പൂർണ്ണ മലയാളം പതിപ്പ് വഴിയിലാണ്; അതുവരെ മുഴുവൻ പുസ്തകവും സൗജന്യമായി വായിക്കാം: പേർഷ്യൻ, ഇംഗ്ലീഷ്, ഡാനിഷ് ഭാഷകളിൽ."},
    {"code": "KN", "slug": "kn", "lang": "kn", "rtl": False, "locale": "kn_IN", "en": "Kannada", "native": "ಕನ್ನಡ",
     "og_title": "Sedaha (Sounds): ಆರಂಭ, ಕನ್ನಡದಲ್ಲಿ",
     "og_desc": "ಒಂದು ಕಾಲದಲ್ಲಿ ಶಬ್ದಗಳಾಗಿದ್ದ ಪದಗಳ ಎಳೆ…",
     "cta": "ಪುಸ್ತಕ ಇಲ್ಲಿಂದಲೇ ಆರಂಭವಾಗುತ್ತದೆ. ಪೂರ್ಣ ಕನ್ನಡ ಆವೃತ್ತಿ ದಾರಿಯಲ್ಲಿದೆ; ಅಲ್ಲಿಯವರೆಗೆ ಇಡೀ ಪುಸ್ತಕವನ್ನು ಉಚಿತವಾಗಿ ಓದಬಹುದು: ಪರ್ಷಿಯನ್, ಇಂಗ್ಲಿಷ್ ಮತ್ತು ಡ್ಯಾನಿಷ್ ಭಾಷೆಗಳಲ್ಲಿ."},
    {"code": "MR", "slug": "mr", "lang": "mr", "rtl": False, "locale": "mr_IN", "en": "Marathi", "native": "मराठी",
     "og_title": "Sedaha (Sounds) चे उद्घाटन, मराठीत",
     "og_desc": "कधीकाळी ध्वनी असलेल्या शब्दांचा धागा…",
     "cta": "पुस्तक इथूनच सुरू होते. संपूर्ण मराठी आवृत्ती वाटेवर आहे; तोपर्यंत संपूर्ण पुस्तक मोफत वाचता येते: फारसी, इंग्रजी आणि डॅनिश भाषेत."},
    {"code": "ZH", "slug": "zh", "lang": "zh", "rtl": False, "locale": "zh_CN", "en": "Chinese", "native": "中文",
     "og_title": "《Sedaha (Sounds)》开篇，中文版",
     "og_desc": "曾经是声音的词语之线…",
     "cta": "这本书从这里开始。完整的中文版正在路上；在那之前，整本书可以免费阅读：波斯语、英语和丹麦语版本。"},
    {"code": "JA", "slug": "ja", "lang": "ja", "rtl": False, "locale": "ja_JP", "en": "Japanese", "native": "日本語",
     "og_title": "『Sedaha (Sounds)』開幕、日本語版",
     "og_desc": "かつて音だった言葉の糸…",
     "cta": "本はここから始まる。完全な日本語版は準備中。それまでは、ペルシア語・英語・デンマーク語で全文を無料で読むことができる。"},
    {"code": "KO", "slug": "ko", "lang": "ko", "rtl": False, "locale": "ko_KR", "en": "Korean", "native": "한국어",
     "og_title": "Sedaha (Sounds) 서문, 한국어판",
     "og_desc": "한때 소리였던 말들의 실타래…",
     "cta": "책은 여기서 시작된다. 한국어 완역판이 준비 중이다. 그때까지 책 전체를 페르시아어, 영어, 덴마크어로 무료로 읽을 수 있다."},
    {"code": "TH", "slug": "th", "lang": "th", "rtl": False, "locale": "th_TH", "en": "Thai", "native": "ไทย",
     "og_title": "บทเปิดของ Sedaha (Sounds) ภาษาไทย",
     "og_desc": "เส้นด้ายแห่งถ้อยคำที่ครั้งหนึ่งเคยเป็นเสียง…",
     "cta": "หนังสือเริ่มต้นจากตรงนี้ ฉบับภาษาไทยฉบับเต็มกำลังจะมา ระหว่างนี้อ่านทั้งเล่มได้ฟรีในภาษาเปอร์เซีย อังกฤษ และเดนมาร์ก"},
    {"code": "VI", "slug": "vi", "lang": "vi", "rtl": False, "locale": "vi_VN", "en": "Vietnamese", "native": "Tiếng Việt",
     "og_title": "Mở đầu của Sedaha (Sounds), bằng tiếng Việt",
     "og_desc": "Sợi chỉ của những từ ngữ từng một thời là âm thanh…",
     "cta": "Cuốn sách bắt đầu từ đây. Ấn bản tiếng Việt đầy đủ đang trên đường đến; trong lúc chờ, có thể đọc trọn cuốn sách miễn phí: bằng tiếng Ba Tư, tiếng Anh và tiếng Đan Mạch."},
    {"code": "ID", "slug": "id", "lang": "id", "rtl": False, "locale": "id_ID", "en": "Indonesian", "native": "Bahasa Indonesia",
     "og_title": "Pembukaan Sedaha (Sounds), dalam bahasa Indonesia",
     "og_desc": "Benang kata-kata yang dulunya pernah menjadi suara…",
     "cta": "Buku ini dimulai dari sini. Edisi bahasa Indonesia yang lengkap sedang dalam perjalanan; sementara itu, seluruh buku dapat dibaca gratis: dalam bahasa Persia, Inggris, dan Denmark."},
    {"code": "MS", "slug": "ms", "lang": "ms", "rtl": False, "locale": "ms_MY", "en": "Malay", "native": "Bahasa Melayu",
     "og_title": "Pembukaan Sedaha (Sounds), dalam bahasa Melayu",
     "og_desc": "Benang kata-kata yang suatu ketika dahulu pernah menjadi suara…",
     "cta": "Buku ini bermula di sini. Edisi bahasa Melayu yang lengkap sedang dalam perjalanan; sementara itu, seluruh buku boleh dibaca secara percuma: dalam bahasa Parsi, Inggeris, dan Denmark."},
    {"code": "SW", "slug": "sw", "lang": "sw", "rtl": False, "locale": "sw_KE", "en": "Swahili", "native": "Kiswahili",
     "og_title": "Ufunguzi wa Sedaha (Sounds), kwa Kiswahili",
     "og_desc": "Uzi wa maneno ambayo wakati mmoja yalikuwa sauti…",
     "cta": "Kitabu kinaanzia hapa. Toleo kamili la Kiswahili liko njiani; hadi wakati huo, kitabu chote kinaweza kusomwa bila malipo: kwa Kiajemi, Kiingereza na Kidenishi."},
    {"code": "PRS", "slug": "prs", "lang": "prs", "rtl": True, "locale": "prs_AF", "en": "Dari", "native": "دری",
     "og_title": "سرآغاز Sedaha (Sounds)، به دری",
     "og_desc": "سررشته‌ی کلماتی که زمانی صدا بوده‌اند…",
     "cta": "کتاب از همین‌جا آغاز می‌شود. نسخه‌ی کامل دری در راه است؛ تا آن زمان تمام کتاب را می‌توان رایگان خواند: به فارسی، انگلیسی و دنمارکی."},
    {"code": "PS", "slug": "ps", "lang": "ps", "rtl": True, "locale": "ps_AF", "en": "Pashto", "native": "پښتو",
     "og_title": "د Sedaha (Sounds) پیل، په پښتو",
     "og_desc": "د هغو کلمو تار چې یو وخت آوازونه وو…",
     "cta": "کتاب له همدې ځایه پیلېږي. بشپړه پښتو ګڼه په لاره کې ده؛ تر هغه وخته ټول کتاب وړیا لوستل کېدای شي: په فارسي، انګلیسي او ډنمارکي."},
    {"code": "CKB", "slug": "ckb", "lang": "ckb", "rtl": True, "locale": "ckb_IQ", "en": "Kurdish (Sorani)", "native": "کوردیی سۆرانی",
     "og_title": "کردنەوەی Sedaha (Sounds)، بە کوردیی سۆرانی",
     "og_desc": "دەزووی ئەو وشانەی کە جاران دەنگ بوون…",
     "cta": "کتێبەکە لێرەوە دەست پێدەکات. وەشانی تەواوی سۆرانی لە ڕێگایە؛ تا ئەو کاتە دەتوانیت هەموو کتێبەکە بەخۆڕایی بخوێنیتەوە: بە فارسی، ئینگلیزی و دانیمارکی."},
    {"code": "KU", "slug": "ku", "lang": "ku", "rtl": False, "locale": "ku_TR", "en": "Kurdish (Kurmanji)", "native": "Kurmancî",
     "og_title": "Vekirina Sedaha (Sounds), bi kurmancî",
     "og_desc": "Rêzika peyvên ku carekê deng bûne…",
     "cta": "Pirtûk ji vir dest pê dike. Çapa kurmancî ya temam di rê de ye; heta wê demê, tevahiya pirtûkê belaş tê xwendin: bi farisî, îngilîzî û danîmarkî."},
    {"code": "BAL", "slug": "bal", "lang": "bal", "rtl": True, "locale": "bal_IR", "en": "Balochi", "native": "بلۏچی",
     "og_title": "Sedaha (Sounds) ءِ بُنگیج، بلۏچی ءَ",
     "og_desc": "آ گالانی تار که یک وهدے توار اَتَنت…",
     "cta": "کتاب چہ اِدا بندات بیت. بلۏچی ءِ پوریں نسخہ راہ ءَ اِنت؛ تاں آ وهد ءَ سجّهیں کتاب مفت وانگ بیت: فارسی، انگریزی ءُ ڈنمارکی ءَ."},
    {"code": "GLK", "slug": "glk", "lang": "glk", "rtl": True, "locale": "glk_IR", "en": "Gilaki", "native": "گیلکی",
     "og_title": "سرآغازِ Sedaha (Sounds)، به گیلکی",
     "og_desc": "اون کلمه‌ئن ریشته کی یک زمانی صدا بید…",
     "cta": "کتاب همین جا جه سر گیره. گیلکی کامل نسخه راه سر ایسه؛ تا او موقع تانی همه کتابا مجانی بخانی: فارسی، انگلیسی و دانمارکی."},
    {"code": "LRC", "slug": "lrc", "lang": "lrc", "rtl": True, "locale": "lrc_IR", "en": "Northern Luri", "native": "لری",
     "og_title": "سرآغازِ Sedaha (Sounds)، به لری",
     "og_desc": "رِشته‌ی کلمه‌یایی که یه زمانی دَنگ بی‌یِنه…",
     "cta": "کتاو وِ همیچَه بند می‌بو. نسخه‌ی کاملِ لری مِن رَهه؛ تا او وقت تری همه‌ی کتاو نه مجانی بخونی: وِ فارسی، انگلیسی و دانمارکی."},
    {"code": "MZN", "slug": "mzn", "lang": "mzn", "rtl": True, "locale": "mzn_IR", "en": "Mazanderani", "native": "مازرونی",
     "og_title": "سرآغازِ Sedaha (Sounds)، به مازرونی",
     "og_desc": "اون کلمه‌هایِ رشته که یک زمونی صدا بی‌نه…",
     "cta": "کتاب همینجه جا شروع وونه. مازرونی کامل نسخه راه دله هسته؛ تا او موقع تونّی همه‌ی کتاب ره مجانی بخوندی: فارسی، انگلیسی و دانمارکی."},
    {"code": "SD", "slug": "sd", "lang": "sd", "rtl": True, "locale": "sd_PK", "en": "Sindhi", "native": "سنڌي",
     "og_title": "Sedaha (Sounds) جي شروعات، سنڌيءَ ۾",
     "og_desc": "لفظن جو اُھو ڌاڳو، جيڪي ڪنھن وقت آواز ھئا…",
     "cta": "ڪتاب ھتان ئي شروع ٿئي ٿو۔ مڪمل سنڌي ايڊيشن رستي ۾ آھي؛ تيستائين سڄو ڪتاب مفت پڙھي سگھجي ٿو: فارسي، انگريزي ۽ ڊينش ۾۔"},
    {"code": "UG", "slug": "ug", "lang": "ug", "rtl": True, "locale": "ug_CN", "en": "Uyghur", "native": "ئۇيغۇرچە",
     "og_title": "Sedaha (Sounds) نىڭ باشلىنىشى، ئۇيغۇرچە",
     "og_desc": "ئەسلىدە ئاۋاز بولغان سۆزلەر يىپى…",
     "cta": "كىتاب مۇشۇ يەردىن باشلىنىدۇ. تولۇق ئۇيغۇرچە نەشرى يولدا؛ ئۇ چاغقىچە پۈتۈن كىتابنى ھەقسىز ئوقۇغىلى بولىدۇ: پارسچە، ئىنگلىزچە ۋە دانىيەچە."},
    {"code": "KK", "slug": "kk", "lang": "kk", "rtl": False, "locale": "kk_KZ", "en": "Kazakh", "native": "Қазақ",
     "og_title": "Sedaha (Sounds) кіріспесі, қазақша",
     "og_desc": "Бір кезде дыбыс болған сөздер жібі…",
     "cta": "Кітап осы жерден басталады. Толық қазақша басылым жолда; оған дейін бүкіл кітапты тегін оқуға болады: парсыша, ағылшынша және датша."},
    {"code": "KY", "slug": "ky", "lang": "ky", "rtl": False, "locale": "ky_KG", "en": "Kyrgyz", "native": "Кыргызча",
     "og_title": "Sedaha (Sounds) башталышы, кыргызча",
     "og_desc": "Бир маал үн болгон сөздөр жиби…",
     "cta": "Китеп ушул жерден башталат. Толук кыргызча басылышы жолдо; ага чейин бүт китепти акысыз окууга болот: фарсыча, англисче жана датча."},
    {"code": "TG", "slug": "tg", "lang": "tg", "rtl": False, "locale": "tg_TJ", "en": "Tajik", "native": "Тоҷикӣ",
     "og_title": "Сарсухани Sedaha (Sounds), ба тоҷикӣ",
     "og_desc": "Риштаи калимоте, ки замоне садо буданд…",
     "cta": "Китоб аз ҳамин ҷо оғоз мешавад. Нашри пурраи тоҷикӣ дар роҳ аст; то он вақт тамоми китобро ройгон хондан мумкин аст: ба форсӣ, англисӣ ва даниягӣ."},
    {"code": "TK", "slug": "tk", "lang": "tk", "rtl": False, "locale": "tk_TM", "en": "Turkmen", "native": "Türkmençe",
     "og_title": "Sedaha (Sounds) açylyşy, türkmençe",
     "og_desc": "Bir wagtlar ses bolan sözleriň ýüplügi…",
     "cta": "Kitap şu ýerden başlanýar. Doly türkmen neşiri ýolda; şol wagta çenli tutuş kitaby mugt okap bolýar: parsça, iňlisçe we dança."},
    {"code": "TT", "slug": "tt", "lang": "tt", "rtl": False, "locale": "tt_RU", "en": "Tatar", "native": "Татарча",
     "og_title": "Sedaha (Sounds) сүз башы, татарча",
     "og_desc": "Бервакыт тавыш булган сүзләр җебе…",
     "cta": "Китап шушыннан башлана. Тулы татарча басма юлда; шул вакытка кадәр бөтен китапны бушлай укып була: фарсыча, инглизчә һәм датча."},
    {"code": "UZ", "slug": "uz", "lang": "uz", "rtl": False, "locale": "uz_UZ", "en": "Uzbek", "native": "Oʻzbekcha",
     "og_title": "Sedaha (Sounds) kirishi, oʻzbekcha",
     "og_desc": "Bir zamonlar ovoz boʻlgan soʻzlar ipi…",
     "cta": "Kitob shu yerdan boshlanadi. Toʻliq oʻzbekcha nashr yoʻlda; ungacha butun kitobni bepul oʻqish mumkin: fors, ingliz va dan tillarida."},
    {"code": "MN", "slug": "mn", "lang": "mn", "rtl": False, "locale": "mn_MN", "en": "Mongolian", "native": "Монгол",
     "og_title": "Sedaha (Sounds)-ийн оршил, монголоор",
     "og_desc": "Нэгэн цагт дуу байсан үгсийн утас…",
     "cta": "Ном эндээс эхэлнэ. Монгол хэл дээрх бүрэн хэвлэл замдаа явж байна; тэр болтол номыг бүхэлд нь үнэгүй унших боломжтой: перс, англи, дани хэлээр."},
    {"code": "GU", "slug": "gu", "lang": "gu", "rtl": False, "locale": "gu_IN", "en": "Gujarati", "native": "ગુજરાતી",
     "og_title": "Sedaha (Sounds)નો પ્રારંભ, ગુજરાતીમાં",
     "og_desc": "એ શબ્દોનો દોરો, જે એક સમયે અવાજો હતા…",
     "cta": "પુસ્તક અહીંથી જ શરૂ થાય છે. સંપૂર્ણ ગુજરાતી આવૃત્તિ રસ્તામાં છે; ત્યાં સુધી આખું પુસ્તક મફત વાંચી શકાય છે: ફારસી, અંગ્રેજી અને ડેનિશમાં."},
    {"code": "NE", "slug": "ne", "lang": "ne", "rtl": False, "locale": "ne_NP", "en": "Nepali", "native": "नेपाली",
     "og_title": "Sedaha (Sounds)को सुरुवात, नेपालीमा",
     "og_desc": "ती शब्दहरूको धागो, जुन एक समय ध्वनिहरू थिए…",
     "cta": "किताब यहीँबाट सुरु हुन्छ। पूरा नेपाली संस्करण बाटोमा छ; तबसम्म सिंगो किताब निःशुल्क पढ्न सकिन्छ: फारसी, अंग्रेजी र डेनिस भाषामा।"},
    {"code": "SI", "slug": "si", "lang": "si", "rtl": False, "locale": "si_LK", "en": "Sinhala", "native": "සිංහල",
     "og_title": "Sedaha (Sounds) හි ආරම්භය, සිංහලෙන්",
     "og_desc": "වරෙක හඬ වූ වචනවල නූල…",
     "cta": "පොත මෙතැනින් ආරම්භ වේ. සම්පූර්ණ සිංහල සංස්කරණය එමින් පවතී; එතෙක් මුළු පොතම නොමිලේ කියවිය හැක: පර්සියානු, ඉංග්‍රීසි සහ ඩෙන්මාර්ක භාෂාවලින්."},
    {"code": "AS", "slug": "as", "lang": "as", "rtl": False, "locale": "as_IN", "en": "Assamese", "native": "অসমীয়া",
     "og_title": "Sedaha (Sounds)-ৰ সূচনা, অসমীয়াত",
     "og_desc": "শব্দৰ সূতা, যি এসময় ধ্বনি আছিল…",
     "cta": "কিতাপখন ইয়াৰ পৰাই আৰম্ভ হয়। সম্পূৰ্ণ অসমীয়া সংস্কৰণ আহি আছে; তেতিয়ালৈকে গোটেই কিতাপখন বিনামূলীয়াকৈ পঢ়িব পাৰি: ফাৰ্চী, ইংৰাজী আৰু ডেনিছ ভাষাত।"},
    {"code": "OR", "slug": "or", "lang": "or", "rtl": False, "locale": "or_IN", "en": "Odia", "native": "ଓଡ଼ିଆ",
     "og_title": "Sedaha (Sounds)ର ଆରମ୍ଭ, ଓଡ଼ିଆରେ",
     "og_desc": "ସେହି ଶବ୍ଦଗୁଡ଼ିକର ସୂତ୍ର, ଯାହା ଏକ ସମୟରେ ଧ୍ୱନି ଥିଲେ…",
     "cta": "ପୁସ୍ତକ ଏଠାରୁ ହିଁ ଆରମ୍ଭ ହୁଏ। ସମ୍ପୂର୍ଣ୍ଣ ଓଡ଼ିଆ ସଂସ୍କରଣ ବାଟରେ ଅଛି; ସେ ପର୍ଯ୍ୟନ୍ତ ପୂରା ପୁସ୍ତକ ମାଗଣାରେ ପଢ଼ାଯାଇପାରିବ: ଫାର୍ସୀ, ଇଂରାଜୀ ଓ ଡେନିସ୍ ଭାଷାରେ।"},
    {"code": "MY", "slug": "my", "lang": "my", "rtl": False, "locale": "my_MM", "en": "Burmese", "native": "မြန်မာ",
     "og_title": "Sedaha (Sounds) ၏ နိဒါန်း၊ မြန်မာဘာသာဖြင့်",
     "og_desc": "တစ်ချိန်က အသံများဖြစ်ခဲ့သော စကားလုံးများ၏ ချည်ကြိုး…",
     "cta": "စာအုပ်သည် ဤနေရာမှ စတင်သည်။ မြန်မာဘာသာ အပြည့်အစုံ လမ်းခရီးတွင် ရှိသည်။ ထိုအချိန်အထိ စာအုပ်တစ်အုပ်လုံးကို အခမဲ့ ဖတ်နိုင်သည် — ပါရှန်း၊ အင်္ဂလိပ်နှင့် ဒိန်းမတ်ဘာသာဖြင့်။"},
    {"code": "KM", "slug": "km", "lang": "km", "rtl": False, "locale": "km_KH", "en": "Khmer", "native": "ខ្មែរ",
     "og_title": "អារម្ភកថានៃ Sedaha (Sounds) ជាភាសាខ្មែរ",
     "og_desc": "ខ្សែស្រឡាយពាក្យ ដែលកាលពីមុនធ្លាប់ជាសំឡេង…",
     "cta": "សៀវភៅចាប់ផ្តើមពីទីនេះ។ បោះពុម្ពខ្មែរពេញលេញកំពុងមកដល់ រហូតដល់ពេលនោះ អាចអានសៀវភៅទាំងមូលដោយឥតគិតថ្លៃ៖ ជាភាសាពែរ្ស អង់គ្លេស និងដាណឺម៉ាក។"},
    {"code": "LO", "slug": "lo", "lang": "lo", "rtl": False, "locale": "lo_LA", "en": "Lao", "native": "ລາວ",
     "og_title": "ບົດເປີດຂອງ Sedaha (Sounds) ພາສາລາວ",
     "og_desc": "ເສັ້ນດ້າຍຂອງຄໍາເວົ້າ ທີ່ເຄີຍເປັນສຽງມາກ່ອນ…",
     "cta": "ປຶ້ມເລີ່ມຕົ້ນຈາກບ່ອນນີ້ ສະບັບພາສາລາວເຕັມກໍາລັງມາ ລະຫວ່າງນີ້ອ່ານທັງເຫລັ້ມໄດ້ຟຣີ ເປັນພາສາເປີເຊຍ ອັງກິດ ແລະ ເດນມາກ"},
    {"code": "JV", "slug": "jv", "lang": "jv", "rtl": False, "locale": "jv_ID", "en": "Javanese", "native": "Basa Jawa",
     "og_title": "Pambuka Sedaha (Sounds), ing basa Jawa",
     "og_desc": "Lawe tembung-tembung sing biyen tau dadi swara…",
     "cta": "Buku iki diwiwiti saka kene. Edhisi basa Jawa sing komplit isih ana ing dalan; nganti wektu kuwi, kabeh buku bisa diwaca gratis: ing basa Persia, Inggris, lan Denmark."},
    {"code": "SU", "slug": "su", "lang": "su", "rtl": False, "locale": "su_ID", "en": "Sundanese", "native": "Basa Sunda",
     "og_title": "Bubuka Sedaha (Sounds), dina basa Sunda",
     "og_desc": "Benang kecap-kecap nu baheulana mangrupa sora…",
     "cta": "Buku ieu dimimitian ti dieu. Édisi basa Sunda nu lengkep keur di jalan; nepi ka waktu éta, sakabéh buku bisa dibaca haratis: dina basa Pérsia, Inggris, jeung Dénmark."},
    {"code": "CEB", "slug": "ceb", "lang": "ceb", "rtl": False, "locale": "ceb_PH", "en": "Cebuano", "native": "Cebuano",
     "og_title": "Ang pag-abli sa Sedaha (Sounds), sa Cebuano",
     "og_desc": "Ang hilo sa mga pulong nga kaniadto mga tingog…",
     "cta": "Ang libro magsugod dinhi. Ang kompletong edisyon sa Cebuano padulong na; hangtod niana, ang tibuok libro mabasa nga libre: sa Persian, English, ug Danish."},
    {"code": "TL", "slug": "tl", "lang": "tl", "rtl": False, "locale": "tl_PH", "en": "Tagalog", "native": "Tagalog",
     "og_title": "Ang pagbubukas ng Sedaha (Sounds), sa Tagalog",
     "og_desc": "Ang sinulid ng mga salitang minsan ay naging mga tunog…",
     "cta": "Nagsisimula ang aklat dito. Ang kumpletong edisyong Tagalog ay parating na; hanggang doon, mababasa nang libre ang buong aklat: sa Persian, Ingles, at Danish."},
    {"code": "EU", "slug": "eu", "lang": "eu", "rtl": False, "locale": "eu_ES", "en": "Basque", "native": "Euskara",
     "og_title": "Sedaha (Sounds): sarrera, euskaraz",
     "og_desc": "Behin soinuak izandako hitzen haria…",
     "cta": "Liburua hemen hasten da. Euskarazko edizio osoa bidean da; ordura arte, liburu osoa doan irakur daiteke: persieraz, ingelesez eta danieraz."},
    {"code": "BR", "slug": "br", "lang": "br", "rtl": False, "locale": "br_FR", "en": "Breton", "native": "Brezhoneg",
     "og_title": "Digoradur Sedaha (Sounds), e brezhoneg",
     "og_desc": "An neudenn gerioù a oa bet trouzioù ur wech…",
     "cta": "Al levr a grog amañ. Emañ an embannadur brezhonek klok o tont; betek-hen e c'haller lenn al levr a-bezh evit netra: e perseg, e saozneg hag e daneg."},
    {"code": "CA", "slug": "ca", "lang": "ca", "rtl": False, "locale": "ca_ES", "en": "Catalan", "native": "Català",
     "og_title": "L'obertura de Sedaha (Sounds), en català",
     "og_desc": "El fil de paraules que una vegada foren sons…",
     "cta": "El llibre comença aquí. L'edició catalana completa és en camí; mentrestant, el llibre sencer es pot llegir gratis: en persa, en anglès i en danès."},
    {"code": "CY", "slug": "cy", "lang": "cy", "rtl": False, "locale": "cy_GB", "en": "Welsh", "native": "Cymraeg",
     "og_title": "Agoriad Sedaha (Sounds), yn Gymraeg",
     "og_desc": "Edafedd o eiriau a fu unwaith yn synau…",
     "cta": "Mae'r llyfr yn dechrau yma. Mae'r argraffiad Cymraeg llawn ar ei ffordd; tan hynny, gellir darllen y llyfr cyfan am ddim: yn Perseg, Saesneg a Daneg."},
    {"code": "FY", "slug": "fy", "lang": "fy", "rtl": False, "locale": "fy_NL", "en": "Frisian", "native": "Frysk",
     "og_title": "De oanhef fan Sedaha (Sounds), yn it Frysk",
     "og_desc": "De tried fan wurden dy't ienris lûden west hawwe…",
     "cta": "It boek begjint hjir. De folsleine Fryske edysje is ûnderweis; oant dy tiid kin it hiele boek fergees lêzen wurde: yn it Perzysk, Ingelsk en Deensk."},
    {"code": "GA", "slug": "ga", "lang": "ga", "rtl": False, "locale": "ga_IE", "en": "Irish", "native": "Gaeilge",
     "og_title": "Oscailt Sedaha (Sounds), i nGaeilge",
     "og_desc": "Snáithe na bhfocal a bhí tráth ina bhfuaimeanna…",
     "cta": "Tosaíonn an leabhar anseo. Tá an t-eagrán iomlán Gaeilge ar an mbealach; go dtí sin, is féidir an leabhar ar fad a léamh saor in aisce: i bPeirsis, i mBéarla agus i nDanmhairgis."},
    {"code": "GD", "slug": "gd", "lang": "gd", "rtl": False, "locale": "gd_GB", "en": "Scottish Gaelic", "native": "Gàidhlig",
     "og_title": "Fosgladh Sedaha (Sounds), sa Ghàidhlig",
     "og_desc": "Snàth nam faclan a bha, aon uair, nan fuaimean…",
     "cta": "Tòisichidh an leabhar an-seo. Tha an deasachadh slàn Gàidhlig air an rathad; gus an uair sin, gabhaidh an leabhar gu lèir a leughadh an-asgaidh: ann am Peirsis, Beurla agus Danmhairgis."},
    {"code": "GL", "slug": "gl", "lang": "gl", "rtl": False, "locale": "gl_ES", "en": "Galician", "native": "Galego",
     "og_title": "A abertura de Sedaha (Sounds), en galego",
     "og_desc": "O fío de palabras que noutro tempo foron sons…",
     "cta": "O libro comeza aquí. A edición galega completa está en camiño; mentres tanto, o libro enteiro pódese ler de balde: en persa, en inglés e en dinamarqués."},
    {"code": "LB", "slug": "lb", "lang": "lb", "rtl": False, "locale": "lb_LU", "en": "Luxembourgish", "native": "Lëtzebuergesch",
     "og_title": "Den Optakt vu Sedaha (Sounds), op Lëtzebuergesch",
     "og_desc": "De Fuedem vu Wierder, déi emol Kläng waren…",
     "cta": "D'Buch fänkt hei un. Déi komplett Lëtzebuerger Editioun ass ënnerwee; bis dohin kann dat ganzt Buch gratis gelies ginn: op Persesch, Englesch an Dänesch."},
    {"code": "MT", "slug": "mt", "lang": "mt", "rtl": False, "locale": "mt_MT", "en": "Maltese", "native": "Malti",
     "og_title": "Il-ftuħ ta' Sedaha (Sounds), bil-Malti",
     "og_desc": "Il-ħajta ta' kliem li darba kien ħsejjes…",
     "cta": "Il-ktieb jibda hawn. L-edizzjoni Maltija sħiħa tinsab fit-triq; sa dak iż-żmien, il-ktieb kollu jista' jinqara b'xejn: bil-Persjan, bl-Ingliż u bid-Daniż."},
    {"code": "NDS", "slug": "nds", "lang": "nds", "rtl": False, "locale": "nds_DE", "en": "Low German", "native": "Plattdüütsch",
     "og_title": "De Uptakt vun Sedaha (Sounds), op Plattdüütsch",
     "og_desc": "De Faden vun Wöör, de mal Kläng weern…",
     "cta": "Dat Book fangt hier an. De hele plattdüütsche Utgaav is ünnerwegens; bet dorhen kann dat hele Book för ümsünst leest warrn: op Persisch, Engelsch un Däänsch."},
    {"code": "OC", "slug": "oc", "lang": "oc", "rtl": False, "locale": "oc_FR", "en": "Occitan", "native": "Occitan",
     "og_title": "La dubertura de Sedaha (Sounds), en occitan",
     "og_desc": "Lo fial de paraulas qu'èran, un temps, de sons…",
     "cta": "Lo libre comença aicí. L'edicion occitana completa es en camin; fins alara, tot lo libre se pòt legir a gratis: en persan, en anglés e en danés."},
    {"code": "RM", "slug": "rm", "lang": "rm", "rtl": False, "locale": "rm_CH", "en": "Romansh", "native": "Rumantsch",
     "og_title": "L'avertura da Sedaha (Sounds), per rumantsch",
     "og_desc": "Il fil da pleds che ina giada eran tuns…",
     "cta": "Il cudesch cumenza qua. L'ediziun rumantscha cumpletta è en via; fin lura po l'entir cudesch vegnir legì gratuitamain: per persian, englais e danais."},
    {"code": "SC", "slug": "sc", "lang": "sc", "rtl": False, "locale": "sc_IT", "en": "Sardinian", "native": "Sardu",
     "og_title": "S'abertura de Sedaha (Sounds), in sardu",
     "og_desc": "Su filu de fueddos chi, unu tempus, fiant boghes…",
     "cta": "Su libru cumintzat inoghe. S'editzione sarda cumpleta est in caminu; finas a tando totu su libru si podet lègere de badas: in persianu, in inglesu e in danesu."},
    {"code": "BE", "slug": "be", "lang": "be", "rtl": False, "locale": "be_BY", "en": "Belarusian", "native": "Беларуская",
     "og_title": "Уступ да Sedaha (Sounds), па-беларуску",
     "og_desc": "Нітка слоў, якія некалі былі гукамі…",
     "cta": "Кніга пачынаецца тут. Поўнае беларускае выданне ўжо ў дарозе; а пакуль усю кнігу можна чытаць бясплатна: па-персідску, па-англійску і па-дацку."},
    {"code": "BS", "slug": "bs", "lang": "bs", "rtl": False, "locale": "bs_BA", "en": "Bosnian", "native": "Bosanski",
     "og_title": "Otvaranje knjige Sedaha (Sounds), na bosanskom",
     "og_desc": "Nit riječi koje su nekoć bile zvukovi…",
     "cta": "Knjiga počinje ovdje. Potpuno bosansko izdanje je na putu; do tada se cijela knjiga može čitati besplatno: na perzijskom, engleskom i danskom."},
    {"code": "MK", "slug": "mk", "lang": "mk", "rtl": False, "locale": "mk_MK", "en": "Macedonian", "native": "Македонски",
     "og_title": "Отворањето на Sedaha (Sounds), на македонски",
     "og_desc": "Нишка од зборови кои некогаш биле звуци…",
     "cta": "Книгата почнува тука. Целосното македонско издание е на пат; дотогаш целата книга може да се чита бесплатно: на персиски, англиски и дански."},
    {"code": "ME", "slug": "me", "lang": "cnr", "rtl": False, "locale": "cnr_ME", "en": "Montenegrin", "native": "Crnogorski",
     "og_title": "Otvaranje knjige Sedaha (Sounds), na crnogorskom",
     "og_desc": "Nit riječi koje su nekada bile zvuci…",
     "cta": "Knjiga počinje ovdje. Potpuno crnogorsko izdanje je na putu; do tada se cijela knjiga može čitati besplatno: na persijskom, engleskom i danskom."},
    {"code": "YI", "slug": "yi", "lang": "yi", "rtl": True, "locale": "yi_US", "en": "Yiddish", "native": "ייִדיש",
     "og_title": "דער אָנהייב פֿון Sedaha (Sounds), אויף ייִדיש",
     "og_desc": "דער פֿאָדעם פֿון ווערטער, וואָס זײַנען אַ מאָל געווען קלאַנגען…",
     "cta": "דאָס בוך הייבט זיך אָן דאָ. די פֿולע ייִדישע אויסגאַבע איז אונטערוועגנס; ביז דעמאָלט קען מען דאָס גאַנצע בוך לייענען אומזיסט: אויף פּערסיש, ענגליש און דעניש."},
    {"code": "EO", "slug": "eo", "lang": "eo", "rtl": False, "locale": "eo_EO", "en": "Esperanto", "native": "Esperanto",
     "og_title": "La malfermo de Sedaha (Sounds), en Esperanto",
     "og_desc": "La fadeno el vortoj, kiuj iam estis sonoj…",
     "cta": "La libro komenciĝas ĉi tie. La kompleta Esperanta eldono estas survoje; ĝis tiam la tuta libro legeblas senpage: en la persa, la angla kaj la dana."},
    {"code": "FO", "slug": "fo", "lang": "fo", "rtl": False, "locale": "fo_FO", "en": "Faroese", "native": "Føroyskt",
     "og_title": "Byrjanin á Sedaha (Sounds), á føroyskum",
     "og_desc": "Tráðurin av orðum, ið eina ferð vóru ljóð…",
     "cta": "Bókin byrjar her. Fullfíggjaða føroyska útgávan er á veg; til tá kann øll bókin lesast ókeypis: á persiskum, enskum og donskum."},
    {"code": "KL", "slug": "kl", "lang": "kl", "rtl": False, "locale": "kl_GL", "en": "Greenlandic", "native": "Kalaallisut",
     "og_title": "Sedaha (Sounds) aallarniutaa, kalaallisut",
     "og_desc": "Ujaloq oqaatsinik, ilaanni nipiusunik…",
     "cta": "Atuagaq maannga aallartippoq. Kalaallisut naammassisaq aggersoq; taamanikkut atuagaq tamaat akeqanngitsumik atuarneqarsinnaavoq: persiskisut, tuluttut qallunaatullu."},
    {"code": "SE", "slug": "se", "lang": "se", "rtl": False, "locale": "se_NO", "en": "Northern Sami", "native": "Davvisámegiella",
     "og_title": "Sedaha (Sounds) álgu, davvisámegillii",
     "og_desc": "Láŋga sániin, mat leat leamaš jienasat…",
     "cta": "Girji álgá dás. Ollislaš davvisámegiel almmuheapmi lea boahtimin; dassážii sáhttá olles girjji lohkat nuvttá: persagillii, eaŋgalsgillii ja dánskkagillii."},
    {"code": "AF", "slug": "af", "lang": "af", "rtl": False, "locale": "af_ZA", "en": "Afrikaans", "native": "Afrikaans",
     "og_title": "Die opening van Sedaha (Sounds), in Afrikaans",
     "og_desc": "Die draad van woorde wat eens klanke was…",
     "cta": "Die boek begin hier. Die volledige Afrikaanse uitgawe is op pad; tot dan kan die hele boek gratis gelees word: in Persies, Engels en Deens."},
    {"code": "AM", "slug": "am", "lang": "am", "rtl": False, "locale": "am_ET", "en": "Amharic", "native": "አማርኛ",
     "og_title": "የSedaha (Sounds) መክፈቻ፣ በአማርኛ",
     "og_desc": "ድሮ ድምፆች ሆነው የነበሩ የቃላት ሱፍ…",
     "cta": "መጽሐፉ እዚህ ይጀምራል። ሙሉው የአማርኛ እትም በመንገድ ላይ ነው፤ እስከዚያው ድረስ መጽሐፉን ሙሉ በሙሉ በነፃ ማንበብ ይቻላል፦ በፋርስኛ፣ በእንግሊዝኛ እና በዴንማርክኛ።"},
    {"code": "HA", "slug": "ha", "lang": "ha", "rtl": False, "locale": "ha_NG", "en": "Hausa", "native": "Hausa",
     "og_title": "Buɗewar Sedaha (Sounds), a Hausa",
     "og_desc": "Zaren kalmomin da a wani lokaci suka kasance sautuka…",
     "cta": "Littafin yana farawa a nan. Cikakken bugun Hausa yana kan hanya; har zuwa lokacin, ana iya karanta dukan littafin kyauta: da Farisanci, Turanci da Danish."},
    {"code": "HT", "slug": "ht", "lang": "ht", "rtl": False, "locale": "ht_HT", "en": "Haitian Creole", "native": "Kreyòl ayisyen",
     "og_title": "Ouvèti Sedaha (Sounds), an kreyòl ayisyen",
     "og_desc": "Fil mo yo ki te son yon lè…",
     "cta": "Liv la kòmanse isit la. Edisyon konplè an kreyòl ayisyen an sou wout; jiska lè sa a, ou ka li tout liv la gratis: an pèsan, an angle ak an danwa."},
    {"code": "IG", "slug": "ig", "lang": "ig", "rtl": False, "locale": "ig_NG", "en": "Igbo", "native": "Igbo",
     "og_title": "Mmalite Sedaha (Sounds), n'asụsụ Igbo",
     "og_desc": "Eriri okwu ndị bụbu ụda mgbe ochie…",
     "cta": "Akwụkwọ a na-amalite ebe a. Mbipụta Igbo zuru ezu nọ n'ụzọ; ruo mgbe ahụ, a pụrụ ịgụ akwụkwọ a dum n'efu: n'asụsụ Peshia, Bekee na Danish."},
    {"code": "OM", "slug": "om", "lang": "om", "rtl": False, "locale": "om_ET", "en": "Oromo", "native": "Afaan Oromoo",
     "og_title": "Seensa Sedaha (Sounds), Afaan Oromootiin",
     "og_desc": "Kirrii jechootaa kan yeroo tokko sagalee ture…",
     "cta": "Kitaabichi asumaa jalqaba. Maxxansi Afaan Oromoo guutuun karaa irra jira; hamma sana, kitaabicha guutuu bilisaan dubbisuun ni danda'ama: Afaan Faarsii, Ingiliffaa fi Deenmaarkiin."},
    {"code": "SO", "slug": "so", "lang": "so", "rtl": False, "locale": "so_SO", "en": "Somali", "native": "Soomaali",
     "og_title": "Furaha Sedaha (Sounds), af-Soomaali",
     "og_desc": "Dun erayo ah, oo mar codad ahaa…",
     "cta": "Buuggu halkan ayuu ka bilaabmayaa. Daabacaadda Soomaaliga oo dhammaystiran ayaa soo socota; ilaa markaas, buugga oo dhan si bilaash ah ayaa loo akhrisan karaa: af-Faaris, af-Ingiriisi iyo af-Deenish."},
    {"code": "YO", "slug": "yo", "lang": "yo", "rtl": False, "locale": "yo_NG", "en": "Yoruba", "native": "Yorùbá",
     "og_title": "Ìṣífípé Sedaha (Sounds), ní èdè Yorùbá",
     "og_desc": "Okùn àwọn ọ̀rọ̀ tí wọ́n jẹ́ ohùn nígbà kan rí…",
     "cta": "Ìwé náà bẹ̀rẹ̀ níbí. Ẹ̀dà Yorùbá tó kún ń bọ̀ lọ́nà; títí di ìgbà náà, a lè ka gbogbo ìwé náà lọ́fẹ̀ẹ́: ní èdè Páṣíà, Gẹ̀ẹ́sì àti Danish."},
    {"code": "ZU", "slug": "zu", "lang": "zu", "rtl": False, "locale": "zu_ZA", "en": "Zulu", "native": "isiZulu",
     "og_title": "Ukuvula kwe-Sedaha (Sounds), ngesiZulu",
     "og_desc": "Umucu wamazwi ake aba ngamaphimbo…",
     "cta": "Incwadi iqala lapha. Uhlelo olugcwele lwesiZulu lusendleleni; kuze kube yileso sikhathi, yonke incwadi ingafundwa mahhala: ngesiPheresiya, isiNgisi nesiDanish."},
]


def _block(text: str, bid: str, code: str, fname: str) -> str:
    m = re.search(rf"^##\s+{bid}\s*$", text, re.M)
    if not m:
        raise ValueError(f"{code}/{fname}: block {bid} not found")
    rest = text[m.end():]
    nxt = re.search(r"^##\s+\S+\s*$", rest, re.M)
    seg = rest[:nxt.start()] if nxt else rest
    seg = re.sub(r"<!--.*?-->", "", seg, flags=re.S)
    seg = re.sub(r"^\*\*[A-Za-z-]+\*\*\s*$", "", seg, flags=re.M)
    out = re.sub(r"\s+", " ", seg).strip()
    if not out:
        raise ValueError(f"{code}/{fname}: block {bid} is empty")
    return out


def _title(code: str) -> str:
    """The edition's own book title: first line of block 0001 in 00_Title_Info.md."""
    f = BOOK_LANGS / code / "00_Title_Info.md"
    text = f.read_text(encoding="utf-8")
    m = re.search(r"^##\s+0001\s*$", text, re.M)
    if not m:
        raise ValueError(f"{code}/00_Title_Info.md: block 0001 not found")
    rest = text[m.end():]
    nxt = re.search(r"^##\s+\S+\s*$", rest, re.M)
    seg = rest[:nxt.start()] if nxt else rest
    seg = re.sub(r"<!--.*?-->", "", seg, flags=re.S)
    seg = re.sub(r"^\*\*[A-Za-z-]+\*\*\s*$", "", seg, flags=re.M)
    for line in seg.splitlines():
        line = line.strip()
        if line and not line.startswith("{"):
            return line
    raise ValueError(f"{code}/00_Title_Info.md: no title line in block 0001")


def _og_title(L: dict) -> str:
    """og_title with the 'Sedaha (Sounds)' placeholder swapped for the edition's own
    translated title, in «…» (the book's quotation device) or the CJK brackets the
    entry already provides."""
    t = _title(L["code"])
    og = L["og_title"]
    for opening, closing in (("《", "》"), ("『", "』")):
        wrapped = f"{opening}Sedaha (Sounds){closing}"
        if wrapped in og:
            return og.replace(wrapped, f"{opening}{t}{closing}")
    if "Sedaha (Sounds)" not in og:
        raise ValueError(f"{L['code']}: og_title lacks the 'Sedaha (Sounds)' placeholder")
    return og.replace("Sedaha (Sounds)", f"«{t}»")


def _opening(code: str) -> tuple[str, list[str]]:
    """Return (native Opening heading, opening paragraphs) from the edition source."""
    f = BOOK_LANGS / code / "00_Opening.md"
    text = f.read_text(encoding="utf-8")
    h1 = _block(text, "0006", code, f.name)
    m = re.search(r"^##\s+0007\s*$", text, re.M)
    rest = text[m.end():]
    nxt = re.search(r"^##\s+\S+\s*$", rest, re.M)
    seg = rest[:nxt.start()] if nxt else rest
    seg = re.sub(r"<!--.*?-->", "", seg, flags=re.S)
    seg = re.sub(r"^\*\*[A-Za-z-]+\*\*\s*$", "", seg, flags=re.M)
    paras = [re.sub(r"\s+", " ", p).strip() for p in re.split(r"\n\s*\n", seg) if p.strip()]
    if not paras:
        raise ValueError(f"{code}: no Opening text in block 0007")
    return h1, paras


def _esc(s: str) -> str:
    return html.escape(s, quote=True)


# Every localized invitation opens with the same true sentence -- "The book begins
# here." -- and then says the complete edition is still coming. Once it HAS come,
# that second half is false, so the first sentence is kept and the rest dropped.
# Rewriting the promise in each language would be a translation job in the book
# repo; taking the author's own words this far is not.
SENTENCE_ENDS = ".!?。۔।։።។܀؟！？"


def _first_sentence(text: str) -> str:
    """The opening sentence, or "" when this script does not mark sentence ends.

    Thai and Lao write without sentence punctuation, so there is nothing to cut on;
    those pages get the buttons and no sentence, which says the same thing with
    fewer risks than a guess would."""
    for i, ch in enumerate(text):
        if ch in SENTENCE_ENDS:
            head = text[:i + 1].strip()
            # Enough to be a sentence rather than an abbreviation. The bar is low on
            # purpose: a character carries a whole word in Chinese, and "本はここから始まる。"
            # is a complete sentence in ten characters. A length that suits German
            # silently threw away every CJK opening.
            return head if len(head) >= 5 else ""
    return ""


READ_INDEX_URL = "https://arasteh.art/sedaha/read/"


def alternates() -> str:
    """The hreflang cluster tying all Opening pages together as translations of one
    another: x-default and English point at the /sedaha/read/ hub, then one line per
    generated edition. Every page in the cluster must list every page, itself included."""
    # fa and da are hand-written pages, not in LANGS, but belong to the cluster.
    rows = [f'<link rel="alternate" hreflang="x-default" href="{READ_INDEX_URL}">',
            f'<link rel="alternate" hreflang="en" href="{READ_INDEX_URL}">',
            f'<link rel="alternate" hreflang="fa" href="{READ_INDEX_URL}fa/">',
            f'<link rel="alternate" hreflang="da" href="{READ_INDEX_URL}da/">']
    rows += [f'<link rel="alternate" hreflang="{L["lang"]}" '
             f'href="https://arasteh.art/sedaha/read/{L["slug"]}/">'
             for L in LANGS if L["slug"] not in HIDDEN_SLUGS]
    return "\n".join(rows)


PERSIAN_ORIGINAL = {"@type": "Book", "name": "صداها", "inLanguage": "fa",
                    "url": "https://arasteh.art/sedaha/read/fa/"}


def book_ld(L: dict, url: str) -> str:
    """schema.org for one edition. hreflang tells a crawler these pages are
    alternates of one another; this says what they actually are -- one book, in
    this language, free, translated from the Persian -- so a search engine can
    offer the right edition to someone searching in their own language."""
    data = {
        "@context": "https://schema.org",
        "@type": "Book",
        "name": _title(L["code"]),
        "alternateName": "Sedaha (Sounds)",
        "inLanguage": L["lang"],
        "author": {"@type": "Person", "name": "Amir Arasteh", "url": "https://arasteh.art/"},
        "publisher": {"@type": "Organization", "name": "Arasteh"},
        "url": url,
        "image": "https://arasteh.art/assets/img/paintings/sounds/01.jpg",
        "bookFormat": "https://schema.org/EBook",
        "isAccessibleForFree": True,
        "translationOfWork": PERSIAN_ORIGINAL,
        "datePublished": "2026",
    }
    body = json.dumps(data, ensure_ascii=False, indent=2)
    return f'<script type="application/ld+json">\n{body}\n</script>'


def render(L: dict, row: dict | None = None, complete: int = 3) -> str:
    """One Opening page. `row` is that language's entry in the edition record, when
    there is one: it is what tells this page whether the whole book now exists in
    the language being read. Without it the page falls back to the invitation to
    read the original three, which is what every page said before 23 editions were
    complete and 20 of them were still saying "on the way"."""
    h1, paras = _opening(L["code"])
    dir_attr = ' dir="rtl"' if L["rtl"] else ""
    # The book names itself, in its own script, instead of "Sounds" in Latin: the
    # two links out of the reading page are the only place the page still had to
    # say what book this is. Kept in a span of its own so the arrow beside it does
    # not get dragged across by a right-to-left title.
    title = _title(L["code"])
    own = (f'<span lang="{L["lang"]}"{dir_attr}>'
           f'{html.escape(title, quote=False)}</span>')

    # The invitation, in the language being read. Complete: its own files, labelled
    # with the book's own title, and only the half of the sentence that is still
    # true. Not complete yet: unchanged, the whole sentence and the original three.
    if row and row["state"] == "ready" and row["fmts"]:
        opener = _first_sentence(L["cta"])
        cta_p = (f'    <p lang="{L["lang"]}"{dir_attr}>{html.escape(opener, quote=False)}</p>\n'
                 if opener else "")
        # The size rides on the format chip -- "EPUB · 4.6 MB" -- exactly as the
        # finder already writes it, so the two decision points agree. A number is
        # language-neutral, which is what lets it onto 20 pages that are not in
        # English; the format-guidance SENTENCE lives only on the English page.
        buttons = "\n".join(
            f'      <a class="btn" href="{RELEASE_URL}/{row["stem"]}.{f}" '
            f'aria-label="{row["en"]}: the complete book, {f.upper()}'
            f'{", " + row["size"][f] if row["size"].get(f, "0 MB") != "0 MB" else ""}">'
            f'<span lang="{L["lang"]}"{dir_attr}>{html.escape(title, quote=False)}</span>'
            f'<span class="btn-fmt" lang="en">{f.upper()}'
            f'{" &middot; " + row["size"][f] if row["size"].get(f, "0 MB") != "0 MB" else ""}'
            f'</span></a>' for f in row["fmts"])
    else:
        cta_p = (f'    <p lang="{L["lang"]}"{dir_attr}>'
                 f'{html.escape(L["cta"], quote=False)}</p>\n')
        buttons = full_book_btns(complete)
    url = f"https://arasteh.art/sedaha/read/{L['slug']}/"
    # The description a search engine shows to someone searching in this language.
    # It was English on every page; the edition's own "thread of words" line already
    # exists in its own words, so use that and let the English name of the language
    # follow it for the crawler's sake.
    meta_desc = f"{L['og_desc']} — {_title(L['code'])}, {L['en']}. Amir Arasteh."
    body = "\n".join(f"    <p>{html.escape(p, quote=False)}</p>" for p in paras)
    return f"""<!DOCTYPE html>
<!-- GENERATED by build_read_pages.py from the book repo's {L['code']} edition. Do not edit by hand:
     edit the generator (or the edition source) and re-run  python build_read_pages.py -->
<html lang="{L['lang']}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(h1, quote=False)} &middot; Sedaha (Sounds), Book One &middot; Amir Arasteh</title>
<meta name="description" content="{_esc(meta_desc)}">
<meta name="theme-color" content="#F5EFE3">
<meta property="og:type" content="book">
<meta property="og:site_name" content="arasteh.art">
<meta property="og:title" content="{_esc(_og_title(L))}">
<meta property="og:description" content="{_esc(L['og_desc'])}">
<meta property="og:image" content="https://arasteh.art/assets/img/paintings/sounds/01.jpg">
<meta property="og:image:width" content="1500">
<meta property="og:image:height" content="1096">
<meta property="og:image:alt" content="The painting that opens Sedaha (Sounds), Book One, by Amir Arasteh.">
<meta property="og:url" content="{url}">
<meta property="og:locale" content="{L['locale']}">
<meta name="twitter:card" content="summary_large_image">
<link rel="canonical" href="{url}">
{book_ld(L, url)}
{alternates()}
<link rel="stylesheet" href="/assets/css/style.css">
<link rel="icon" href="/favicon.ico" sizes="any">
<link rel="icon" type="image/png" sizes="32x32" href="/assets/img/favicon-32.png">
<link rel="icon" type="image/png" sizes="16x16" href="/assets/img/favicon-16.png">
<link rel="apple-touch-icon" href="/assets/img/apple-touch-icon-180.png">
{HEAD}
</head>
<body class="book">
<a class="skip-link" href="#main" lang="en">Skip to content</a>
{NAV}
<main class="container" id="main">
  <a class="back" href="/sedaha/">&larr; {own}</a>

{op_langs_html(L['slug'] + '/', L['lang'], L['native'])}
  <div class="op-bar">
{top_actions_html(row, url, L['og_desc'], L['en'])}
{READER_TOOLS}
  </div>
  <article class="reader" lang="{L['lang']}"{dir_attr}>
    <h1>{html.escape(h1, quote=False)}</h1>
{body}
  </article>

  <div class="read-cta">
{cta_p}    <div class="btns">
{buttons}
      <button type="button" class="btn btn-icon btn-share" lang="en" aria-label="Share this opening" title="Share this opening" data-share-url="{url}" data-share-title="Sedaha &mdash; Book One" data-share-text="{_esc(L['og_desc'])}"><svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2v13"/><path d="m16 6-4-4-4 4"/><path d="M20 10v9a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2v-9"/></svg></button>
    </div>
    <a class="read-back" href="/sedaha/">{own} &rarr;</a>
  </div>
</main>

{FOOTER}
<script src="/assets/js/reader.js" defer></script>
<script src="/assets/js/share.js" defer></script>
<script src="/assets/js/backtotop.js" defer></script>
</body>
</html>
"""


# ---------------------------------------------------------------- status page
#
# Where each edition stands is an EDITORIAL judgement, not something the source
# markdown reveals: all 111 editions carry the same 2670 blocks with none empty,
# so file scanning would report every language as equally finished. The truth
# lives in build.py's curated TIER_A / HARD_EXCLUDE lists, joined with the files
# a reader can actually download (the GitHub release, not a local build).

# Reader-facing state -> (label, blurb). Order here is the order rows are sorted in.
STATES = [
    # Every one of the 114 has a readable Opening, so a label like "Ready to read"
    # did not distinguish the four that exist as whole books. Each label now says
    # what it says about the COMPLETE edition; the Opening is a given.
    # (state, short label, what it means). The short one is a command on a filter
    # chip and a badge repeated down 113 rows, so it stays a word or two; the
    # sentence explains it once, in the legend and the progress disclosure.
    ("ready",     "Complete",        "The whole book, free to download."),
    ("review",    "Final review",    "Translated in full; being checked before release."),
    ("translated", "Draft translated", "A complete draft exists; review still to come."),
    ("revising",  "Revising",        "Parts of this edition need reworking before it can be trusted."),
]

# The state sentence a reader gets from the search result, in the second person.
STATE_SENTENCE = {
    "ready": "The complete book is available now.",
    "review": "The complete edition is in final review.",
    "translated": "A complete draft is translated; review still to come.",
    "revising": "The complete edition is being revised.",
}

# EPUB first, everywhere. It was EPUB-then-PDF on the book page and PDF-then-EPUB
# in the status table, which is small friction repeated 114 times.
FMT_ORDER = ["epub", "pdf"]
FMT_WHAT = {"epub": "Fits any screen", "pdf": "Keeps the printed page"}

# Editions the book has but this website does not show. The author's call, made
# 2026-07-26: he writes from Iran and does not want the site to become a political
# object. The BOOK is untouched -- the edition exists, is translated, and ships in
# the repo and the releases; only arasteh.art stays quiet about it.
#
# Hiding is done here rather than by deleting the edition, so it is one line to
# undo: the language keeps its LANGS entry, its Opening source, and its place in
# the book. What this switch removes from the site is the generated page, the
# browse row, the status row, the hreflang cluster, the sitemap and the feed.
HIDDEN_SLUGS = {"he"}


def shown(rows: list[dict]) -> list[dict]:
    return [r for r in rows if r["slug"] not in HIDDEN_SLUGS]


# Hand-written editions: not in LANGS (which covers only the generated pages).
# share = that edition's own "thread of words" line, for the share sheet.
CORE = [
    {"code": "FA", "name": "Farsi", "en": "Persian", "native": "فارسی", "lang": "fa", "rtl": True,
     "url": "/sedaha/read/fa/", "share": "سررشته‌ی کلماتی که زمانی صدا بوده‌اند…"},
    {"code": "EN", "name": "English", "en": "English", "native": "English", "lang": "en",
     "url": "/sedaha/read/", "share": "The thread of words that were once sounds…"},
    {"code": "DA", "name": "Danish", "en": "Danish", "native": "Dansk", "lang": "da",
     "url": "/sedaha/read/da/", "share": "Tråden af ord, der engang var lyde…"},
]


def _book_lists() -> tuple[list[str], set[str]]:
    """TIER_A and HARD_EXCLUDE, read straight out of the book repo's build.py."""
    import ast
    src = (BOOK_VOL / "build.py").read_text(encoding="utf-8")
    out = {}
    for name in ("TIER_A", "HARD_EXCLUDE"):
        m = re.search(rf"^{name}\s*=\s*([\[{{].*?[\]}}])\s*$", src, re.M | re.S)
        if not m:
            raise ValueError(f"build.py: {name} not found - the status page needs it")
        out[name] = ast.literal_eval(m.group(1))
    return list(out["TIER_A"]), set(out["HARD_EXCLUDE"])


def _configured() -> dict[str, str]:
    """block_tag -> language name, scraped from export_translation.py's LANGUAGE_CONFIGS
    (regex, not import: importing it would drag in the whole docx/pdf toolchain)."""
    src = (BOOK_VOL / "export_translation.py").read_text(encoding="utf-8")
    m = re.search(r"^LANGUAGE_CONFIGS\s*=\s*\{$(.*?)^\}$", src, re.M | re.S)
    if not m:
        raise ValueError("export_translation.py: LANGUAGE_CONFIGS not found")
    tags = {}
    for entry in re.finditer(r'^    "([^"]+)": \{(.*?)^    \},?$', m.group(1), re.M | re.S):
        name, body = entry.group(1), entry.group(2)
        tag = re.search(r'"block_tag":\s*"([^"]+)"', body)
        if tag:
            tags[tag.group(1)] = name
    return tags


def _released() -> tuple[dict[str, set[str]], dict[str, str], dict[tuple[str, str], int]]:
    """language name -> {'pdf','epub'} downloadable from the GitHub release, the newest
    of its assets' timestamps (used by the Atom feed), and (language, format) -> bytes,
    so a download can say how big it is before anyone taps it on a metered connection.

    A reader can only read what is published, so the release is the truth here. If gh
    is unavailable we fall back to the local build dir and say so loudly, because that
    would list files nobody else can fetch."""
    import json
    import subprocess
    try:
        raw = subprocess.run(["gh", "release", "view", RELEASE_TAG, "--json", "assets"],
                             cwd=SITE, capture_output=True, text=True, timeout=60, check=True).stdout
        assets = [(a["name"], a.get("updatedAt") or a.get("createdAt"), a.get("size") or 0)
                  for a in json.loads(raw)["assets"]]
    except Exception as exc:  # noqa: BLE001 - any failure means "ask the filesystem"
        local = BOOK_VOL / "online"
        print(f"[warn]  gh release unavailable ({type(exc).__name__}); falling back to {local}")
        print("[warn]  the page may then list editions that are built locally but NOT uploaded")
        assets = [(p.name, datetime.datetime.utcfromtimestamp(p.stat().st_mtime)
                   .strftime("%Y-%m-%dT%H:%M:%SZ"), p.stat().st_size)
                  for p in local.glob("Sedaha_*.*")] if local.is_dir() else []
    out: dict[str, set[str]] = {}
    when: dict[str, str] = {}
    size: dict[tuple[str, str], int] = {}
    for name, stamp, nbytes in assets:
        m = re.fullmatch(r"Sedaha_(\w+)\.(pdf|epub)", name)
        if not m:
            continue
        out.setdefault(m.group(1), set()).add(m.group(2))
        size[(m.group(1), m.group(2))] = nbytes
        if stamp and stamp > when.get(m.group(1), ""):
            when[m.group(1)] = stamp
    return out, when, size


def _mb(nbytes: int) -> str:
    """A file size a reader can weigh against their data allowance. One decimal is
    enough; a book that reads "1.0 MB" and is really 1.04 has told no lie worth
    correcting, and "1048576 bytes" tells nobody anything."""
    if not nbytes:
        return ""
    mb = nbytes / 1048576
    return f"{mb:.1f} MB" if mb >= 0.1 else f"{max(1, round(nbytes / 1024))} KB"


def status_rows() -> list[dict]:
    """One row per edition, most-available first, then alphabetically by English name.

    THIS IS THE EDITION RECORD. Everything a visitor is told about availability comes
    from here: the complete-edition cards on /sedaha/, the sentences on /sedaha/ and
    the home page, the status table, the Atom feed, the counter. It used to feed only
    the table and the counter, while the cards and the copy were kept by hand -- which
    is exactly how the Italian edition came to be complete, downloadable, and mentioned
    nowhere a visitor would look. Add a consumer here rather than a second list."""
    tier_a, excluded = _book_lists()
    tags = _configured()
    released, released_at, sizes = _released()
    rows = []
    for L in CORE + [dict(L, name=None, url=f"/sedaha/read/{L['slug']}/") for L in LANGS]:
        name = L["name"] or tags.get(L["code"])
        fmts = released.get(name, set()) if name else set()
        if fmts:
            state = "ready"
        elif name in excluded:
            state = "revising"
        elif name in tier_a:
            state = "review"
        else:
            state = "translated"
        rows.append({"native": L["native"], "en": L["en"], "lang": L["lang"], "rtl": L.get("rtl", False),
                     "url": L["url"], "state": state, "stem": f"Sedaha_{name}" if name else None,
                     "slug": L["url"].rstrip("/").rsplit("/", 1)[-1] if L["url"] != "/sedaha/read/" else "en",
                     "share": L.get("share") or L.get("og_desc", ""),
                     "fmts": [f for f in FMT_ORDER if f in fmts],
                     "size": {f: _mb(sizes.get((name, f), 0)) for f in fmts},
                     "date": released_at.get(name) if name else None})
    order = {s[0]: i for i, s in enumerate(STATES)}
    rows.sort(key=lambda r: (order[r["state"]], r["en"]))
    return rows


# The original first, then the two it was published with, then the rest as they
# arrive. Alphabetical order would open the shelf with Danish.
FEATURED_FIRST = ["Persian", "English", "Danish"]


def complete_rows(rows: list[dict]) -> list[dict]:
    ready = [r for r in rows if r["state"] == "ready"]
    return sorted(ready, key=lambda r: (FEATURED_FIRST.index(r["en"])
                                        if r["en"] in FEATURED_FIRST else len(FEATURED_FIRST),
                                        r["en"]))


def and_list(names: list[str]) -> str:
    if len(names) < 2:
        return names[0] if names else ""
    return ", ".join(names[:-1]) + " and " + names[-1]


def availability_phrase(n: int) -> str:
    """The doorway's one availability line: how many languages the WHOLE BOOK is in.

    Replaces "More than 100 openings - N complete editions" (author, 2026-08-05). That
    line led with the Opening because for a long time the book itself existed in four
    languages; leading with the smaller, truer number is no longer the honest emphasis
    once the complete editions are the hundred.

    Derived, never hard-coded, for the same reason every other sentence here is: the
    round claim appears only when it is actually true. At 23 this says "23 languages";
    it starts saying "over 100" the day the 100th edition is on the release, and no one
    has to remember to change a string. `n` is the count of state=="ready" rows, i.e.
    editions a reader can really download -- not editions that merely exist locally.
    """
    if n >= 100:
        return "Available in over 100 languages"
    if n == 1:
        return "Available in 1 language"
    return f"Available in <strong>{n}</strong> languages"


def render_status(rows: list[dict], total: int | None = None) -> str:
    total = len(rows) if total is None else total
    counts = {s: sum(1 for r in rows if r["state"] == s) for s, _, _ in STATES}
    legend = "\n".join(
        f'      <div class="key"><span class="badge {s}">{lbl}</span> <span class="what">{blurb}</span>'
        f' <span class="n">{counts[s]}</span></div>' for s, lbl, blurb in STATES)
    body = []
    for r in rows:
        direction = ' dir="rtl"' if r["rtl"] else ""
        native = (f'<span class="native" lang="{r["lang"]}"'
                  f'{direction}>{html.escape(r["native"])}</span>')
        # don't print "Igbo Igbo": the English name is only worth showing when it differs
        if r["en"] != r["native"]:
            native += f' <span class="en">{html.escape(r["en"])}</span>'
        label = next(lbl for s, lbl, _ in STATES if s == r["state"])
        # the size is printed, not left in a title attribute: a phone has no hover,
        # and how big a file is decides whether it is downloaded on mobile data
        links = [f'<a href="{r["url"]}">Opening</a>']
        links += [f'<a href="{RELEASE_URL}/{r["stem"]}.{f}">{f.upper()}'
                  f'{" &middot; " + r["size"][f] if r["size"].get(f) else ""}</a>'
                  for f in r["fmts"]]
        # every language here can be passed on, complete or not: the reason to share
        # one is that somebody reads it, not that its EPUB happens to be finished
        links.append(
            f'<button type="button" class="lnk-share btn-share" '
            f'aria-label="Share the {r["en"]} opening" title="Share the {r["en"]} opening" '
            f'data-share-url="https://arasteh.art{r["url"]}" '
            f'data-share-title="Sedaha &mdash; Book One">'
            f'<svg aria-hidden="true" viewBox="0 0 24 24"><path d="M12 2v13"/>'
            f'<path d="m16 6-4-4-4 4"/>'
            f'<path d="M20 10v9a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2v-9"/></svg></button>')
        body.append(f'      <tr data-state="{r["state"]}"><th scope="row">{native}</th>'
                    f'<td><span class="badge {r["state"]}">{label}</span></td>'
                    f'<td class="links">{" ".join(links)}</td></tr>')
    ready = counts["ready"]
    A_tally = availability(rows, total)["tally"]
    # one chip per state, each carrying its own count: a reader who came here to ask
    # "what can I actually download" should get there without reading 114 rows
    # A state nothing is in is not a filter, it is a dead end. It was shown disabled;
    # simply leaving it out is quieter, and the legend above still names every state
    # with its count, so nothing is hidden from anyone who wants the whole picture.
    state_chips = "\n".join(
        f'    <button type="button" class="region-chip" data-state="{s}" aria-pressed="false">'
        f'{lbl} <span class="ccount">{counts[s]}</span></button>'
        for s, lbl, _ in STATES if counts[s])
    return f"""<!DOCTYPE html>
<!-- GENERATED by build_read_pages.py. Do not edit by hand: re-run  python build_read_pages.py -->
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Where each language stands &middot; Sedaha (Sounds) &middot; Amir Arasteh</title>
<meta name="description" content="The state of every language edition of Sedaha (Sounds), Book One: which are ready to read, which are in review, and which are still being worked on.">
<meta name="theme-color" content="#F5EFE3">
<meta property="og:type" content="website">
<meta property="og:site_name" content="arasteh.art">
<meta property="og:title" content="Where each language stands">
<meta property="og:description" content="The state of all {total} language editions of Sedaha (Sounds), Book One.">
<meta property="og:image" content="https://arasteh.art/assets/img/share-card.jpg">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="The Arasteh mark, a painted paisley, beside the words: paintings, and Sedaha (Sounds), a book free to read in more than a hundred languages.">
<meta property="og:url" content="https://arasteh.art/sedaha/languages/">
<link rel="canonical" href="https://arasteh.art/sedaha/languages/">
<meta name="twitter:card" content="summary_large_image">
<link rel="stylesheet" href="/assets/css/style.css">
<link rel="icon" href="/favicon.ico" sizes="any">
<link rel="icon" type="image/png" sizes="32x32" href="/assets/img/favicon-32.png">
<link rel="icon" type="image/png" sizes="16x16" href="/assets/img/favicon-16.png">
<link rel="apple-touch-icon" href="/assets/img/apple-touch-icon-180.png">
{HEAD}
</head>
<body class="book">
<a class="skip-link" href="#main" lang="en">Skip to content</a>
{NAV}
<main class="container" id="main">
  <a class="back" href="/sedaha/">&larr; Sounds</a>

  <h1>All languages</h1>
  <p class="read-kicker">Sounds &middot; Book One</p>
  <p class="lead">Every opening is readable today. {ready} of them continue as a
    complete book you can download.</p>

  <div class="language-finder">
    <label class="lang-search-label" for="langFilter">Find your language</label>
    <span class="lang-search-field">
      <input type="search" class="lang-search" id="langFilter" autocomplete="off"
        placeholder="Hindi, T&uuml;rk&ccedil;e, 日本語&hellip;">
      <svg class="lang-search-icon" aria-hidden="true" viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.8-3.8"/></svg>
      <button type="button" class="lang-clear" id="langClearFilter" aria-label="Clear the search" hidden>
        <svg aria-hidden="true" viewBox="0 0 24 24"><path d="M6 6l12 12M18 6L6 18"/></svg>
      </button>
    </span>
    <p class="visually-hidden" id="langFilterStatus" role="status" aria-live="polite"></p>
  </div>

  <div class="region-chips" role="group" aria-label="Show only one state">
    <button type="button" class="region-chip" data-state="all" aria-pressed="true">All</button>
{state_chips}
  </div>

  <div class="lang-table-wrap">
    <table class="lang-table">
      <caption class="visually-hidden">Every language edition of Sounds, Book One, with its current state and available files</caption>
      <thead>
        <tr><th scope="col">Language</th><th scope="col">State</th><th scope="col">Available now</th></tr>
      </thead>
      <tbody>
{chr(10).join(body)}
      </tbody>
    </table>
  </div>
  <p class="lang-noresult" hidden>No language matches that search yet.
    <a href="mailto:amirarasteh1990@gmail.com">Write to me</a> and I&rsquo;ll look.</p>

  <!-- The project's own numbers. Real, and secondary to "where is my language",
       so they wait behind a disclosure rather than meeting everyone first. -->
  <details class="progress-detail">
    <summary>Translation progress</summary>
    <div class="lang-key">
{legend}
    </div>
    <p class="muted-note">{A_tally}</p>
    <p class="muted-note">Editions are released as they pass review, not on a schedule.
      Every language here has a readable opening; a complete edition is the whole book,
      checked and published as a file.</p>
  </details>

  <p class="lang-foot">Downloads are hosted on GitHub. If that is blocked where you are,
    <a href="mailto:amirarasteh1990@gmail.com">write to me</a> and I will send the files.</p>
  <p class="lang-foot">Follow new editions on
    <a href="https://t.me/Sounds_AmirArasteh">Telegram</a> or by
    <a href="/feed.xml">feed</a>. The registered first edition (2026) has its own
    <a href="/editions/first-edition/">archival page</a>.</p>
</main>

{FOOTER}
<!-- the other names each language answers to; must run before the filter below -->
<script src="/assets/js/lang-alias.js"></script>
<script>
/* Filter the table, and answer deep links such as /sedaha/languages/#ja by
   filling the search in, so the filtered table always explains itself. */
(function(){{
  var input = document.getElementById('langFilter');
  if(!input) return;
  var rows = [].slice.call(document.querySelectorAll('.lang-table tbody tr'));
  var noResult = document.querySelector('.lang-noresult');
  var status = document.getElementById('langFilterStatus');
  var clearBtn = document.getElementById('langClearFilter');
  var chips = [].slice.call(document.querySelectorAll('.region-chip[data-state]'));
  var flagged = null, only = 'all';

  /* Fold accents away so a keyboard that cannot type them still finds the name:
     turkce finds Turkce, espanol finds Espanol. Letters that do not decompose
     into base plus mark are mapped by hand. Kept identical to /sedaha/. */
  var LETTERS = {{'ø':'o','æ':'ae','ß':'ss','đ':'d','ð':'d',
                 'þ':'th','ł':'l','ı':'i','œ':'oe','’':"'"}};
  function fold(s){{
    s = String(s).toLowerCase().replace(/[øæßđðþłıœ’]/g,
                                        function(c){{ return LETTERS[c]; }});
    return s.normalize ? s.normalize('NFD').replace(/[\\u0300-\\u036f]/g, '') : s;
  }}

  /* What a row is searchable BY: its two printed names, the other names it answers
     to, and its code. Field by field, NOT the row's whole textContent -- that also
     holds the state label and the file links, so "pdf" or "review" matched dozens
     of languages. */
  var ALIAS = window.LANG_ALIASES || {{}};
  rows.forEach(function(tr){{
    var a = tr.querySelector('a[href^="/sedaha/read/"]');
    if(!a) return;
    var slug = a.getAttribute('href').slice('/sedaha/read/'.length).replace('/', '') || 'en';
    var nat = tr.querySelector('.native'), en = tr.querySelector('.en');
    tr.setAttribute('data-hay', fold([nat ? nat.textContent : '', en ? en.textContent : '',
                                      ALIAS[slug] || '', slug].join(' ')));
  }});

  function apply(){{
    var q = fold(input.value.trim()), n = 0;
    rows.forEach(function(tr){{
      var hit = (tr.getAttribute('data-hay') || '').indexOf(q) > -1 &&
                (only === 'all' || tr.getAttribute('data-state') === only);
      tr.style.display = hit ? '' : 'none';
      if(hit) n += 1;
    }});
    if(noResult) noResult.hidden = !(q && !n);
    if(clearBtn) clearBtn.hidden = !q;
    // an empty result after a FILTER is not a failed search, and must not say it was
    if(status) status.textContent = (q || only !== 'all') ?
      (n ? n + (n === 1 ? ' language.' : ' languages.') :
        (q ? 'No language matches that search.' : 'No editions are in that state.')) :
      'Showing every language.';
  }}
  function unflag(){{ if(flagged){{ flagged.classList.remove('deep-target'); flagged = null; }} }}
  input.addEventListener('input', function(){{ unflag(); apply(); }});
  if(clearBtn) clearBtn.addEventListener('click', function(){{
    input.value = ''; unflag(); apply(); input.focus();
  }});
  chips.forEach(function(chip){{
    chip.addEventListener('click', function(){{
      only = chip.getAttribute('data-state');
      chips.forEach(function(c){{
        c.setAttribute('aria-pressed', String(c.getAttribute('data-state') === only));
      }});
      unflag();
      apply();
    }});
  }});

  var bySlug = {{}};
  rows.forEach(function(tr){{
    var a = tr.querySelector('a[href^="/sedaha/read/"]');
    if(!a) return;
    var slug = a.getAttribute('href').slice('/sedaha/read/'.length).replace('/', '') || 'en';
    if(!bySlug[slug]) bySlug[slug] = tr;
  }});
  function openFromHash(){{
    var tr = bySlug[decodeURIComponent(location.hash.slice(1)).toLowerCase()];
    if(!tr) return;
    var cell = tr.querySelector('th');
    only = 'all';   // a state filter must not hide the row someone linked to
    chips.forEach(function(c){{
      c.setAttribute('aria-pressed', String(c.getAttribute('data-state') === 'all'));
    }});
    input.value = cell ? cell.textContent.trim() : '';
    unflag();
    apply();
    tr.classList.add('deep-target');
    flagged = tr;
    tr.scrollIntoView({{block: 'center'}});
  }}
  openFromHash();
  window.addEventListener('hashchange', openFromHash);
}})();
</script>
<script src="/assets/js/backtotop.js" defer></script>
</body>
</html>
"""


FEED = SITE / "feed.xml"
UNDATED = "2026-01-01T00:00:00Z"   # an edition whose release timestamp is unknown


def render_feed(rows: list[dict]) -> str:
    """An Atom feed of the complete editions, so following the work does not have
    to mean Telegram (which part of the readership cannot reach)."""
    ready = [r for r in rows if r["state"] == "ready"]
    ready.sort(key=lambda r: (r["date"] or UNDATED, r["en"]), reverse=True)
    updated = max((r["date"] or UNDATED for r in ready), default=UNDATED)
    entries = []
    for r in ready:
        url = f"https://arasteh.art{r['url']}"
        title = f"{r['native']} · {r['en']}" if r["native"] != r["en"] else r["en"]
        files = " and ".join(f.upper() for f in r["fmts"]) or "the full text"
        entries.append(
            "  <entry>\n"
            f"    <title>{html.escape(title)}</title>\n"
            f'    <link href="{url}"/>\n'
            f"    <id>{url}</id>\n"
            f"    <updated>{r['date'] or UNDATED}</updated>\n"
            f"    <summary>The complete {html.escape(r['en'])} edition of Sedaha (Sounds), "
            f"Book One: free to read, and to download as {files}.</summary>\n"
            "  </entry>")
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<feed xmlns="http://www.w3.org/2005/Atom">\n'
        "  <title>Sedaha (Sounds) — new editions</title>\n"
        "  <subtitle>Complete editions of Book One by Amir Arasteh, as each is released.</subtitle>\n"
        '  <link href="https://arasteh.art/feed.xml" rel="self"/>\n'
        '  <link href="https://arasteh.art/sedaha/"/>\n'
        "  <id>https://arasteh.art/feed.xml</id>\n"
        f"  <updated>{updated}</updated>\n"
        "  <author><name>Amir Arasteh</name><uri>https://arasteh.art/</uri></author>\n"
        "  <rights>The book is free to read and share, complete and unchanged.</rights>\n"
        + "\n".join(entries) + "\n</feed>\n")


def patch_feed(check: bool, rows: list[dict]) -> bool:
    feed = render_feed(rows)
    if FEED.is_file() and FEED.read_text(encoding="utf-8") == feed:
        print("[ok]    feed.xml: current")
        return True
    if check:
        print("[drift] feed.xml: missing or stale")
        return False
    FEED.write_text(feed, encoding="utf-8", newline="\n")
    print(f"[write] feed.xml  ({sum(1 for r in rows if r['state'] == 'ready')} editions)")
    return True








EDITIONS_JS = SITE / "assets" / "js" / "editions.js"

# Four editorially fixed quick starts, then a fifth the visitor's browser may
# replace (assets/js/finder.js). Slugs only: every label, URL, direction and the
# availability itself come from the edition record, so a language cannot appear
# here unless its complete edition is actually on the release.
QUICK_SLUGS = ["fa", "en", "ar", "es", "de", "fr", "hi", "ja"]
# A configured quick start appears whether or not its complete edition is out yet:
# the author's call, 2026-07-28, for Hindi. Clicking it is still honest — the panel
# behind it says the edition is in preparation and offers the whole book in the
# three it was published in. The language the BROWSER swaps in is still required to
# be complete (finder.js): a choice made for someone should be the safe one.
QUICK_ALLOW_INCOMPLETE = True
QUICK_FALLBACK = "zh"
# The heading reads into the row: "Pick up the thread in  فارسی  English  …", which
# is the book's own image for what a reader does — the author unwinds the thread of
# words from his side, the reader gathers it from the other. NOT "most read": this
# site keeps no analytics, and these five are chosen editorially, so that would be a
# claim it cannot support. One line to change.
QUICK_HEADING = "Pick up the thread in"


def quick_starts_html(rows: list[dict]) -> str:
    """A few immediate choices, for a visitor who does not want to type.

    Generated rather than written by hand, and generated from the same record as
    everything else, because a hand-kept shortlist is exactly how Italian came to
    be complete and named nowhere. Rendered server-side so it works without
    scripting; the fifth is swapped in the browser when it can be."""
    by_slug = {r["slug"]: r for r in rows}
    picked, missing, waiting = [], [], []
    for slug in QUICK_SLUGS + [QUICK_FALLBACK]:
        r = by_slug.get(slug)
        if r is None:                       # not a language this site carries at all
            missing.append(slug)
            continue
        # "complete" means a file is actually on the release, not merely a state
        if not r["fmts"] and not QUICK_ALLOW_INCOMPLETE:
            missing.append(slug)
            continue
        if not r["fmts"]:
            waiting.append(r["en"])
        picked.append(r)
    if missing:
        print(f"[warn]  quick starts: {', '.join(missing)} not carried by the site - left out")
    if waiting:
        print(f"[note]  quick starts: {', '.join(waiting)} shown before its edition is out")
    links = []
    for r in picked:
        rtl = ' dir="rtl"' if r["rtl"] else ""
        # The native name is the visible label and carries its own lang, so a screen
        # reader pronounces it properly. The English name follows it, hidden, rather
        # than living in an aria-label: a label can hold only one language, so it
        # would have had to drop one of the two names or mispronounce the other.
        also = ("" if r["en"] == r["native"]
                else f'<span class="visually-hidden"> — {html.escape(r["en"])}</span>')
        links.append(f'        <a class="lang-box" href="{r["url"]}" lang="{r["lang"]}"{rtl} '
                     f'data-slug="{r["slug"]}">{html.escape(r["native"])}{also}</a>')
    return (f'      <h2 class="quick-heading" id="quick-heading">{QUICK_HEADING}</h2>\n'
            f'      <nav class="quick-row" aria-labelledby="quick-heading" '
            f'data-fallback="{QUICK_FALLBACK}">\n' + "\n".join(links) + "\n      </nav>")


def editions_js(rows: list[dict]) -> str:
    """Every edition the site carries, as data.

    /sedaha/ used to hold all 113 languages as markup -- three cards, twenty list
    rows and a browser of the rest -- and the finder searched that markup. The page
    is a doorway now, so the languages arrive as a small array instead: the finder
    reads it, the catalogue at /sedaha/languages/ keeps the visible table, and the
    door stays a door. Same record behind both, so they cannot disagree."""
    out = []
    for r in rows:
        files = [[f, r["size"].get(f, ""), f"{RELEASE_URL}/{r['stem']}.{f}"] for f in r["fmts"]]
        entry = {"slug": r["slug"], "native": r["native"], "en": r["en"],
                 "lang": r["lang"], "url": r["url"], "state": r["state"]}
        if r["rtl"]:
            entry["rtl"] = 1
        if files:
            entry["files"] = files
        out.append(json.dumps(entry, ensure_ascii=False, separators=(",", ":")))
    return ("/* Generated by build_read_pages.py from the GitHub release. Do not edit.\n"
            "   The languages this site carries, for the finder on /sedaha/. The visible\n"
            "   catalogue lives at /sedaha/languages/; both come from status_rows(). */\n"
            "window.EDITIONS = [\n" + ",\n".join("  " + e for e in out) + "\n];\n")


def patch_quick_starts(check: bool, rows: list[dict]) -> bool:
    body = SOUNDS.read_text(encoding="utf-8")
    pattern = r'(<!-- QUICK:START[^>]*-->\n)(?:.|\n)*?(\s*<!-- QUICK:END -->)'
    if not re.search(pattern, body):
        print("[warn]  /sedaha/: QUICK markers not found - quick starts not generated")
        return False
    block = quick_starts_html(rows)
    new = re.sub(pattern, lambda m: m.group(1) + block + m.group(2), body, count=1)
    n = len(re.findall(r'data-slug="', block))
    if new == body:
        print(f"[ok]    /sedaha/ quick starts: {n}")
        return True
    if check:
        print(f"[drift] /sedaha/ quick starts: should be {n}")
        return False
    SOUNDS.write_text(new, encoding="utf-8", newline="\n")
    print(f"[write] /sedaha/ quick starts: {n}")
    return True


def patch_editions_js(check: bool, rows: list[dict]) -> bool:
    body = editions_js(rows)
    if EDITIONS_JS.is_file() and EDITIONS_JS.read_text(encoding="utf-8") == body:
        print(f"[ok]    assets/js/editions.js: {len(rows)} languages")
        return True
    if check:
        print(f"[drift] assets/js/editions.js: should list {len(rows)} languages")
        return False
    EDITIONS_JS.write_text(body, encoding="utf-8", newline="\n")
    print(f"[write] assets/js/editions.js  ({len(rows)} languages)")
    return True


def availability(rows: list[dict], total: int | None = None) -> dict[str, str]:
    """One availability story, in the few lengths the site needs it.

    "Free to read in more than a hundred languages" was the old claim. It is not
    false -- the Opening really is readable in 114 -- but a reader hears it as the
    whole book in all of them, and the whole book exists in four. Every sentence
    below distinguishes the two, and all of them are derived, so the day a fifth
    edition is released no sentence has to be remembered.

    The complete editions are counted, not listed. Naming them was right at four
    and wrong at fourteen, and twenty more are on the way; the cards below the
    sentence are the list, and they generate themselves.

    `total` is the number of languages THE BOOK has, which is not always the number
    this site lists: see HIDDEN_SLUGS. It defaults to the rows given."""
    total = len(rows) if total is None else total
    done = complete_rows(rows)
    n = len(done)
    editions = f"{n} complete edition{'' if n == 1 else 's'} to download, more on the way"
    return {
        "total": str(total),
        "ready": str(n),
        "names": and_list([r["en"] for r in done]),
        # the full sentence, for the book page and search-engine descriptions
        "long": f"The opening in {total} languages. {editions[0].upper()}{editions[1:]}.",
        # the short one, for cards and share previews
        "short": f"The opening in {total} languages &middot; {editions}",
        # the quiet one, for the doorway. Now says what the reader can actually get
        # -- the whole book -- instead of leading with the Opening count, which read
        # as a hedge. Derived from n, so it states the true number until there really
        # are 100+ and only then makes the round claim. See availability_phrase().
        "quiet": availability_phrase(n),
        # the breakdown, which is project detail and belongs below the useful part
        "tally": " &middot; ".join(
            f"{sum(1 for r in rows if r['state'] == s)} {word}"
            for s, word in (("ready", "complete"), ("review", "in final review"),
                            ("translated", "translated drafts"), ("revising", "being revised"))) + ".",
    }


def patch_availability(check: bool, rows: list[dict], total: int | None = None) -> bool:
    """Stamp that one story everywhere it is told. Each target is matched by its own
    anchor, and a target that stops matching is reported rather than skipped: a silent
    miss here is precisely the failure this function exists to prevent."""
    A = availability(rows, total)
    plain = A["long"]
    targets = [
        (SOUNDS, r'(<meta name="description" content=")[^"]*(">)',
         f'Sedaha (Sounds), Book 1 by Amir Arasteh. {plain} Free.'),
        (SOUNDS, r'(<meta property="og:description" content=")[^"]*(">)',
         f'By Amir Arasteh. {plain} Free.'),
        # The book page itself no longer carries a sentence: it says the quiet line
        # (patch_meter) and nothing else. The full sentence survives where it does
        # work a visitor never sees, in the two descriptions a search engine and a
        # shared link read.
        (SITE / "index.html", r'(<meta name="description" content=")[^"]*(">)',
         f'Paintings, and Sedaha (Sounds). {plain} Free.'),
        (SITE / "index.html", r'(<meta property="og:description" content=")[^"]*(">)',
         f'Paintings, and Sedaha (Sounds). {plain} Free.'),
        # what a search engine is told the book exists in: it said four while the
        # page said twenty-three. Derived, so the two cannot part company again.
        (SOUNDS, r'("inLanguage": )\[[^\]]*\](,)',
         json.dumps([r["lang"] for r in complete_rows(rows)], ensure_ascii=False)),
        # The home page's Books card says only the title now (the author's call,
        # 2026-07-27: the availability sentence made it a paragraph where a label
        # belonged). The claim still travels with that page, in its description
        # meta above, which is what a search engine and a shared link read.
        # the tally moved to /sedaha/languages/, which is generated whole
    ]
    edits, misses = 0, []
    bodies: dict[Path, str] = {}
    for path, pattern, text in targets:
        body = bodies.get(path) or path.read_text(encoding="utf-8")
        new, n = re.subn(pattern, lambda m, t=text: m.group(1) + t + m.group(2), body, count=1)
        if n == 0:
            misses.append(f"{path.name}: {pattern[:40]}")
            continue
        if new != body:
            edits += 1
        bodies[path] = new
    if misses:
        print(f"[warn]  availability copy: {len(misses)} anchor(s) not found - {misses[0]}")
        return False
    if not edits:
        print(f"[ok]    availability copy: {A['ready']} complete of {A['total']}")
        return True
    if check:
        print(f"[drift] availability copy: should say {A['ready']} complete ({A['names']})")
        return False
    for path, body in bodies.items():
        path.write_text(body, encoding="utf-8", newline="\n")
    print(f"[write] availability copy: {A['ready']} complete ({A['names']})")
    return True




def patch_meter(check: bool, rows: list[dict], total: int | None = None) -> bool:
    """Keep /sedaha/'s hero count honest: the ready count comes from the release,
    the same source the status page uses, so the number cannot quietly go stale.

    It used to be a 3.5%-full progress bar reading "4 of 114 editions complete",
    directly under the Read button. True, but it argued against the book at the
    moment of deciding: what a visitor saw first was 96% unfinished. The same two
    numbers, said as what exists rather than what is missing."""
    ready = sum(1 for r in rows if r["state"] == "ready")
    total = len(rows) if total is None else total
    body = SOUNDS.read_text(encoding="utf-8")
    note = f'<p class="progress-note">{availability_phrase(ready)}</p>'
    # a lambda, so nothing in the replacement text is read as a backreference
    new = re.sub(r'<p class="progress-note">.*?</p>', lambda _m: note,
                 body, count=1, flags=re.S)
    if new == body:
        print(f"[ok]    /sedaha/ meter: {ready} of {total}")
        return True
    if check:
        print(f"[drift] /sedaha/ meter: should read {ready} of {total}")
        return False
    SOUNDS.write_text(new, encoding="utf-8", newline="\n")
    print(f"[write] /sedaha/ meter: {ready} of {total}")
    return True


REDIRECT_PAGE = """<!DOCTYPE html>
<!-- GENERATED by build_read_pages.py. The catalogue that stood here is retired: the
     list on /sedaha/ now carries the same languages, grouped into the whole book and
     the opening, and every edition's files are on its own reading page. This stub
     stays because the URL was published and is in search results; a bookmark should
     land somewhere, not on a 404. Delete the folder if you would rather it 404. -->
<html lang="en">
<head>
<meta charset="utf-8">
<title>All languages &middot; Sedaha (Sounds)</title>
<link rel="canonical" href="https://arasteh.art/sedaha/">
<meta name="robots" content="noindex">
<meta http-equiv="refresh" content="0; url=/sedaha/#allLangs">
</head>
<body>
<p>Every language is now listed on the <a href="/sedaha/#allLangs">book page</a>.</p>
</body>
</html>
"""


def patch_status_page(check: bool, rows: list[dict], total: int | None = None) -> bool:
    """The catalogue is retired; what is left at its URL is a way onward.

    /sedaha/ already groups every language into the whole book and the opening, and
    each edition's own files sit on its reading page, so a second full listing was a
    page to keep in step for nothing. What it alone carried -- the state breakdown,
    the region chips, the #slug deep links -- is gone with it.

    The URL is not gone. It was published, it is in search results, and a reader with
    a bookmark should arrive somewhere rather than at a 404."""
    if STATUS_PAGE.is_file() and STATUS_PAGE.read_text(encoding="utf-8") == REDIRECT_PAGE:
        print("[ok]    /sedaha/languages/: retired, redirect in place")
        return True
    if check:
        print("[drift] /sedaha/languages/: redirect missing or stale")
        return False
    STATUS_PAGE.parent.mkdir(parents=True, exist_ok=True)
    STATUS_PAGE.write_text(REDIRECT_PAGE, encoding="utf-8", newline="\n")
    print("[write] sedaha/languages/index.html  (retired: redirects to /sedaha/#allLangs)")
    return True




GALLERY = SITE / "paintings" / "sounds" / "index.html"
IMAGE_NS = 'xmlns:image="http://www.google.com/schemas/sitemap-image/1.1"'


def _paintings() -> list[tuple[str, str]]:
    """(full-size URL, caption) for every painting in the gallery, read from the
    gallery page itself so the sitemap cannot list a picture the site does not show."""
    body = GALLERY.read_text(encoding="utf-8")
    out = []
    for href, caption in re.findall(
            r'<a class="shot" href="([^"]+)" data-caption="([^"]+)"', body):
        out.append(("https://arasteh.art" + href, html.unescape(caption)))
    return out


def patch_sitemap_images(check: bool) -> bool:
    """Attach the paintings to the gallery's sitemap entry. Image search is how a
    painting gets found by someone who was not looking for a book."""
    body = SITEMAP.read_text(encoding="utf-8")
    shots = _paintings()
    if not shots:
        print("[warn]  sitemap: no paintings found in the gallery page")
        return True
    tags = "".join(
        "    <image:image>\n"
        f"      <image:loc>{html.escape(url, quote=False)}</image:loc>\n"
        f"      <image:title>{html.escape(cap, quote=False)}</image:title>\n"
        "    </image:image>\n" for url, cap in shots)
    want = re.search(
        r'  <url>\n    <loc>https://arasteh\.art/paintings/sounds/</loc>\n'
        r'(.*?)\n?(?:    <image:image>.*?</image:image>\n)*  </url>\n', body, re.S)
    if not want:
        print("[warn]  sitemap: /paintings/sounds/ entry not found")
        return True
    entry = (f'  <url>\n    <loc>https://arasteh.art/paintings/sounds/</loc>\n'
             f'{want.group(1)}\n{tags}  </url>\n')
    new = body[:want.start()] + entry + body[want.end():]
    if IMAGE_NS not in new:
        new = new.replace('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
                          f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"\n'
                          f'        {IMAGE_NS}>', 1)
    if new == body:
        print(f"[ok]    sitemap: {len(shots)} paintings listed")
        return True
    if check:
        print("[drift] sitemap: painting entries missing or stale")
        return False
    SITEMAP.write_text(new, encoding="utf-8", newline="\n")
    print(f"[write] sitemap: {len(shots)} paintings listed on the gallery entry")
    return True


HAND_PAGES = ["sedaha/read/index.html", "sedaha/read/fa/index.html",
              "sedaha/read/da/index.html"]


def patch_hand_sizes(check: bool, rows: list[dict]) -> bool:
    """Stamp file sizes into the three hand-written Opening pages' buttons.

    The generated pages get "EPUB · 4.6 MB" from the release at every build; a
    hand-typed size on EN/FA/DA would freeze the number the day it was typed and
    drift the first time an edition is re-uploaded. So the size is stamped by the
    same build that reads the release, keyed on each button's own href -- the one
    part of the anchor that names which file it is."""
    by_stem = {r["stem"]: r for r in rows if r["fmts"]}
    ok = True
    for rel in HAND_PAGES:
        path = SITE / rel
        body = path.read_text(encoding="utf-8")
        new = body
        for stem, row in by_stem.items():
            for f in row["fmts"]:
                size = row["size"].get(f, "0 MB")
                if size == "0 MB":
                    continue
                inner = (f'{f.upper()}<span class="btn-fmt" lang="en">'
                         f'&middot; {size}</span>')
                new = re.sub(
                    rf'(<a class="btn" href="{re.escape(RELEASE_URL)}/{stem}\.{f}"'
                    rf'[^>]*>).*?(</a>)',
                    lambda m, i=inner: m.group(1) + i + m.group(2), new)
        if new == body:
            continue
        if check:
            print(f"[drift] {rel}: download sizes out of date")
            ok = False
            continue
        path.write_text(new, encoding="utf-8", newline="\n")
        print(f"[write] {rel}  (download sizes stamped from the release)")
    if ok and not check:
        print("[ok]    hand-written pages: download sizes current")
    return ok


def patch_sitemap(check: bool) -> bool:
    body = SITEMAP.read_text(encoding="utf-8")
    today = datetime.date.today().isoformat()
    # the catalogue is retired: what is at that URL now is a redirect carrying
    # noindex, so listing it for crawlers would be asking them to index a signpost
    if "/sedaha/languages/</loc>" in body:
        if check:
            print("[drift] sitemap: the retired /sedaha/languages/ is still listed")
            return False
        body = re.sub(r'  <url>\n    <loc>https://arasteh\.art/sedaha/languages/</loc>\n'
                      r'(?:(?!</url>).)*?</url>\n', "", body, flags=re.S)
        SITEMAP.write_text(body, encoding="utf-8", newline="\n")
        print("[write] sitemap: removed the retired /sedaha/languages/")
    # a hidden edition must not be advertised to crawlers either
    for slug in HIDDEN_SLUGS:
        gone = re.sub(rf'  <url>\n    <loc>https://arasteh\.art/sedaha/read/{slug}/</loc>\n'
                      rf'(?:(?!</url>).)*?</url>\n', "", body, flags=re.S)
        if gone != body:
            if check:
                print(f"[drift] sitemap: /sedaha/read/{slug}/ is hidden but still listed")
                return False
            body = gone
            SITEMAP.write_text(body, encoding="utf-8", newline="\n")
            print(f"[write] sitemap: removed the hidden /sedaha/read/{slug}/")
    missing = [L for L in LANGS if f"/sedaha/read/{L['slug']}/</loc>" not in body
               and L["slug"] not in HIDDEN_SLUGS]
    if not missing:
        print("[ok]    sitemap: all read pages present")
        return True
    if check:
        print(f"[drift] sitemap: {len(missing)} read pages missing")
        return False
    entries = "".join(
        f"  <url>\n    <loc>https://arasteh.art/sedaha/read/{L['slug']}/</loc>\n"
        f"    <lastmod>{today}</lastmod>\n    <priority>0.7</priority>\n  </url>\n"
        for L in missing)
    body = body.replace("</urlset>", entries + "</urlset>")
    SITEMAP.write_text(body, encoding="utf-8", newline="\n")
    print(f"[write] sitemap: added {len(missing)} read pages")
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate /sedaha/read/<lang>/ Opening pages from the book repo.")
    ap.add_argument("--check", action="store_true", help="report drift only; change nothing; exit 1 if stale")
    args = ap.parse_args()
    if not BOOK_LANGS.is_dir():
        sys.exit(f"Book repo not found: {BOOK_LANGS}")

    # the record first: the Opening pages need to know which editions are complete
    rows = status_rows()
    by_slug = {r["slug"]: r for r in rows}
    # how many complete editions exist, for the row of buttons on each Opening
    n_complete = len(complete_rows(shown(rows)))

    ok = True
    for L in LANGS:
        dest = READ_DIR / L["slug"] / "index.html"
        if L["slug"] in HIDDEN_SLUGS:
            # the edition stays in the book; the site does not carry the page
            if dest.is_file():
                if args.check:
                    print(f"[drift] {L['slug']}: hidden, but its page is still on the site")
                    ok = False
                else:
                    dest.unlink()
                    try:
                        dest.parent.rmdir()
                    except OSError:
                        pass
                    print(f"[write] removed sedaha/read/{L['slug']}/  (hidden: {L['en']})")
            continue
        page = render(L, by_slug.get(L["slug"]), n_complete)
        if dest.is_file() and dest.read_text(encoding="utf-8") == page:
            continue
        if args.check:
            print(f"[drift] {L['slug']}: page missing or stale")
            ok = False
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(page, encoding="utf-8", newline="\n")
        print(f"[write] sedaha/read/{L['slug']}/index.html  ({L['en']})")
    if ok and args.check:
        print(f"[ok]    all {len(LANGS)} generated pages in sync")

    # `rows` is the book's record; `site` is what this website carries. They differ
    # only by HIDDEN_SLUGS, and `total` stays the book's number: the sentences speak
    # about the book's reach, the lists show what the site lists.
    site, total = shown(rows), len(rows)
    ok &= patch_status_page(args.check, site, total)
    # /sedaha/ is a doorway now: no cards, no rows, no browser. The languages reach
    # it as data instead, and the visible catalogue is /sedaha/languages/.
    ok &= patch_editions_js(args.check, site)
    ok &= patch_quick_starts(args.check, site)
    ok &= patch_availability(args.check, site, total)
    ok &= patch_meter(args.check, site, total)
    ok &= patch_feed(args.check, site)
    ok &= patch_hand_sizes(args.check, site)
    ok &= patch_sitemap(args.check)
    ok &= patch_sitemap_images(args.check)
    if not args.check:
        hidden = ", ".join(r["en"] for r in rows if r["slug"] in HIDDEN_SLUGS)
        print(f"done: {len(LANGS)} languages" + (f"  (hidden from the site: {hidden})" if hidden else ""))
    return 1 if (args.check and not ok) else 0


if __name__ == "__main__":
    sys.exit(main())
