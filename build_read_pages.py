#!/usr/bin/env python3
"""
build_read_pages.py — Generate the per-language Opening pages /sedaha/read/<slug>/ for
editions beyond the hand-maintained EN/FA/DA three, straight from the BOOK repo's
edition sources. Single source of truth = the book repo.

Per language it renders one page from:
  * the edition's own Opening        — Other_Languages/<CODE>/00_Opening.md, block 0007
  * the edition's own Opening title  — block 0006 (page <h1> and browser-tab title)
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
import re
import sys
from pathlib import Path

SITE = Path(__file__).resolve().parent
BOOK_LANGS = SITE.parent / "1_Sedaha" / "Volume1" / "00_source_md" / "Other_Languages"  # sibling book repo. Edit if moved.
READ_DIR = SITE / "sedaha" / "read"
SOUNDS = SITE / "sedaha" / "index.html"
SITEMAP = SITE / "sitemap.xml"

# One entry per generated page. og_desc = the thread line in that edition's own words
# (grounded in its Opening sentence); cta = localized two-sentence invitation.
# slug = URL path under /sedaha/read/; code = folder in Other_Languages (also the lane tag).
LANGS = [
    {"code": "DE", "slug": "de", "lang": "de", "rtl": False, "locale": "de_DE", "en": "German", "native": "Deutsch",
     "og_title": "Der Auftakt von Sedaha (Sounds), auf Deutsch",
     "og_desc": "Der Faden aus Wörtern, die einst Klänge waren.",
     "cta": "Das Buch beginnt hier. Die vollständige deutsche Ausgabe ist unterwegs; bis dahin ist das ganze Buch kostenlos zu lesen: auf Persisch, Englisch und Dänisch."},
    {"code": "FR", "slug": "fr", "lang": "fr", "rtl": False, "locale": "fr_FR", "en": "French", "native": "Français",
     "og_title": "L'ouverture de Sedaha (Sounds), en français",
     "og_desc": "Le fil des mots qui furent jadis des sons.",
     "cta": "Le livre commence ici. L'édition française complète est en route ; d'ici là, le livre entier se lit gratuitement : en persan, en anglais et en danois."},
    {"code": "ES", "slug": "es", "lang": "es", "rtl": False, "locale": "es_ES", "en": "Spanish", "native": "Español",
     "og_title": "La apertura de Sedaha (Sounds), en español",
     "og_desc": "El hilo de palabras que alguna vez fueron sonidos.",
     "cta": "El libro comienza aquí. La edición completa en español está en camino; mientras tanto, el libro entero puede leerse gratis: en persa, en inglés y en danés."},
    {"code": "IT", "slug": "it", "lang": "it", "rtl": False, "locale": "it_IT", "en": "Italian", "native": "Italiano",
     "og_title": "L'apertura di Sedaha (Sounds), in italiano",
     "og_desc": "Il filo di parole che un tempo erano suoni.",
     "cta": "Il libro comincia qui. L'edizione italiana completa è in arrivo; nel frattempo, l'intero libro si legge gratis: in persiano, in inglese e in danese."},
    {"code": "NL", "slug": "nl", "lang": "nl", "rtl": False, "locale": "nl_NL", "en": "Dutch", "native": "Nederlands",
     "og_title": "De opening van Sedaha (Sounds), in het Nederlands",
     "og_desc": "De draad van woorden die ooit klanken waren.",
     "cta": "Het boek begint hier. De volledige Nederlandse editie is onderweg; tot die tijd is het hele boek gratis te lezen: in het Perzisch, Engels en Deens."},
    {"code": "PT", "slug": "pt", "lang": "pt", "rtl": False, "locale": "pt_PT", "en": "Portuguese", "native": "Português",
     "og_title": "A abertura de Sedaha (Sounds), em português",
     "og_desc": "O fio de palavras que outrora foram sons.",
     "cta": "O livro começa aqui. A edição portuguesa completa está a caminho; até lá, o livro inteiro pode ser lido gratuitamente: em persa, em inglês e em dinamarquês."},
    {"code": "PT-BR", "slug": "pt-br", "lang": "pt-BR", "rtl": False, "locale": "pt_BR", "en": "Portuguese (Brazil)", "native": "Português (Brasil)",
     "og_title": "A abertura de Sedaha (Sounds), em português do Brasil",
     "og_desc": "O fio de palavras que um dia foram sons.",
     "cta": "O livro começa aqui. A edição completa em português do Brasil está a caminho; até lá, o livro inteiro pode ser lido de graça: em persa, em inglês e em dinamarquês."},
    {"code": "SV", "slug": "sv", "lang": "sv", "rtl": False, "locale": "sv_SE", "en": "Swedish", "native": "Svenska",
     "og_title": "Öppningen av Sedaha (Sounds), på svenska",
     "og_desc": "Tråden av ord som en gång var ljud.",
     "cta": "Boken börjar här. Den fullständiga svenska utgåvan är på väg; tills dess kan hela boken läsas gratis: på persiska, engelska och danska."},
    {"code": "NO", "slug": "no", "lang": "no", "rtl": False, "locale": "nb_NO", "en": "Norwegian", "native": "Norsk",
     "og_title": "Åpningen av Sedaha (Sounds), på norsk",
     "og_desc": "Tråden av ord som en gang var lyder.",
     "cta": "Boken begynner her. Den fullstendige norske utgaven er på vei; inntil da kan hele boken leses gratis: på persisk, engelsk og dansk."},
    {"code": "FI", "slug": "fi", "lang": "fi", "rtl": False, "locale": "fi_FI", "en": "Finnish", "native": "Suomi",
     "og_title": "Sedaha (Sounds): avaus suomeksi",
     "og_desc": "Kerran ääninä olleiden sanojen lanka.",
     "cta": "Kirja alkaa tästä. Täydellinen suomenkielinen laitos on tulossa; siihen asti koko kirjan voi lukea ilmaiseksi: persiaksi, englanniksi ja tanskaksi."},
    {"code": "IS", "slug": "is", "lang": "is", "rtl": False, "locale": "is_IS", "en": "Icelandic", "native": "Íslenska",
     "og_title": "Opnun Sedaha (Sounds), á íslensku",
     "og_desc": "Þráður orða sem voru einu sinni hljóð.",
     "cta": "Bókin hefst hér. Íslenska útgáfan í heild er á leiðinni; þangað til má lesa alla bókina ókeypis: á persnesku, ensku og dönsku."},
    {"code": "PL", "slug": "pl", "lang": "pl", "rtl": False, "locale": "pl_PL", "en": "Polish", "native": "Polski",
     "og_title": "Otwarcie Sedaha (Sounds), po polsku",
     "og_desc": "Nić ze słów, które niegdyś były dźwiękami.",
     "cta": "Książka zaczyna się tutaj. Pełne polskie wydanie jest w drodze; do tego czasu całą książkę można czytać za darmo: po persku, angielsku i duńsku."},
    {"code": "CS", "slug": "cs", "lang": "cs", "rtl": False, "locale": "cs_CZ", "en": "Czech", "native": "Čeština",
     "og_title": "Otevření knihy Sedaha (Sounds), česky",
     "og_desc": "Nit slov, která byla kdysi zvuky.",
     "cta": "Kniha začíná zde. Úplné české vydání je na cestě; do té doby lze celou knihu číst zdarma: persky, anglicky a dánsky."},
    {"code": "SK", "slug": "sk", "lang": "sk", "rtl": False, "locale": "sk_SK", "en": "Slovak", "native": "Slovenčina",
     "og_title": "Otvorenie knihy Sedaha (Sounds), po slovensky",
     "og_desc": "Niť slov, ktoré boli kedysi zvukmi.",
     "cta": "Kniha sa začína tu. Úplné slovenské vydanie je na ceste; dovtedy si celú knihu možno prečítať zadarmo: po perzsky, anglicky a dánsky."},
    {"code": "HU", "slug": "hu", "lang": "hu", "rtl": False, "locale": "hu_HU", "en": "Hungarian", "native": "Magyar",
     "og_title": "A Sedaha (Sounds) nyitánya, magyarul",
     "og_desc": "Cérna szavakból, amelyek egykor hangok voltak.",
     "cta": "A könyv itt kezdődik. A teljes magyar kiadás úton van; addig az egész könyv ingyen olvasható: perzsául, angolul és dánul."},
    {"code": "RO", "slug": "ro", "lang": "ro", "rtl": False, "locale": "ro_RO", "en": "Romanian", "native": "Română",
     "og_title": "Deschiderea cărții Sedaha (Sounds), în română",
     "og_desc": "Firul de cuvinte care au fost cândva sunete.",
     "cta": "Cartea începe aici. Ediția completă în română este pe drum; până atunci, întreaga carte se poate citi gratuit: în persană, în engleză și în daneză."},
    {"code": "BG", "slug": "bg", "lang": "bg", "rtl": False, "locale": "bg_BG", "en": "Bulgarian", "native": "Български",
     "og_title": "Встъплението на Sedaha (Sounds), на български",
     "og_desc": "Нишка от думи, които някога са били звуци.",
     "cta": "Книгата започва оттук. Пълното българско издание е на път; дотогава цялата книга може да се чете безплатно: на персийски, английски и датски."},
    {"code": "EL", "slug": "el", "lang": "el", "rtl": False, "locale": "el_GR", "en": "Greek", "native": "Ελληνικά",
     "og_title": "Το άνοιγμα του Sedaha (Sounds), στα ελληνικά",
     "og_desc": "Το νήμα των λέξεων που κάποτε ήταν ήχοι.",
     "cta": "Το βιβλίο αρχίζει εδώ. Η πλήρης ελληνική έκδοση είναι καθ' οδόν· ως τότε, ολόκληρο το βιβλίο διαβάζεται δωρεάν: στα περσικά, στα αγγλικά και στα δανικά."},
    {"code": "UK", "slug": "uk", "lang": "uk", "rtl": False, "locale": "uk_UA", "en": "Ukrainian", "native": "Українська",
     "og_title": "Вступ до Sedaha (Sounds), українською",
     "og_desc": "Нитка зі слів, що колись були звуками.",
     "cta": "Книга починається тут. Повне українське видання вже в дорозі; а поки що всю книгу можна читати безкоштовно: перською, англійською та данською."},
    {"code": "RU", "slug": "ru", "lang": "ru", "rtl": False, "locale": "ru_RU", "en": "Russian", "native": "Русский",
     "og_title": "Вступление к Sedaha (Sounds), по-русски",
     "og_desc": "Нить из слов, которые когда-то были звуками.",
     "cta": "Книга начинается здесь. Полное русское издание уже в пути; а пока всю книгу можно читать бесплатно: на персидском, английском и датском."},
    {"code": "HR", "slug": "hr", "lang": "hr", "rtl": False, "locale": "hr_HR", "en": "Croatian", "native": "Hrvatski",
     "og_title": "Otvaranje knjige Sedaha (Sounds), na hrvatskom",
     "og_desc": "Nit riječi koje su nekad bile zvukovi.",
     "cta": "Knjiga počinje ovdje. Potpuno hrvatsko izdanje je na putu; do tada se cijela knjiga može čitati besplatno: na perzijskom, engleskom i danskom."},
    {"code": "SR", "slug": "sr", "lang": "sr", "rtl": False, "locale": "sr_RS", "en": "Serbian", "native": "Српски",
     "og_title": "Отварање књиге Sedaha (Sounds), на српском",
     "og_desc": "Нит речи које су некада биле звуци.",
     "cta": "Књига почиње овде. Потпуно српско издање је на путу; дотад се цела књига може читати бесплатно: на персијском, енглеском и данском."},
    {"code": "SL", "slug": "sl", "lang": "sl", "rtl": False, "locale": "sl_SI", "en": "Slovenian", "native": "Slovenščina",
     "og_title": "Uvod v Sedaha (Sounds), v slovenščini",
     "og_desc": "Nit besed, ki so bile nekoč zvoki.",
     "cta": "Knjiga se začne tukaj. Celotna slovenska izdaja je na poti; do takrat je vso knjigo mogoče brati brezplačno: v perzijščini, angleščini in danščini."},
    {"code": "SQ", "slug": "sq", "lang": "sq", "rtl": False, "locale": "sq_AL", "en": "Albanian", "native": "Shqip",
     "og_title": "Hapja e Sedaha (Sounds), në shqip",
     "og_desc": "Filli i fjalëve që dikur ishin tinguj.",
     "cta": "Libri fillon këtu. Botimi i plotë në shqip është rrugës; deri atëherë, i gjithë libri lexohet falas: në persisht, në anglisht dhe në danisht."},
    {"code": "LT", "slug": "lt", "lang": "lt", "rtl": False, "locale": "lt_LT", "en": "Lithuanian", "native": "Lietuvių",
     "og_title": "Sedaha (Sounds) pradžia, lietuviškai",
     "og_desc": "Siūlas iš žodžių, kurie kadaise buvo garsai.",
     "cta": "Knyga prasideda čia. Pilnas lietuviškas leidimas jau pakeliui; iki tol visą knygą galima skaityti nemokamai: persiškai, angliškai ir daniškai."},
    {"code": "LV", "slug": "lv", "lang": "lv", "rtl": False, "locale": "lv_LV", "en": "Latvian", "native": "Latviešu",
     "og_title": "Sedaha (Sounds) ievads, latviski",
     "og_desc": "Vārdu pavediens, kas kādreiz bija skaņas.",
     "cta": "Grāmata sākas šeit. Pilns latviešu izdevums ir ceļā; līdz tam visu grāmatu var lasīt bez maksas: persiešu, angļu un dāņu valodā."},
    {"code": "ET", "slug": "et", "lang": "et", "rtl": False, "locale": "et_EE", "en": "Estonian", "native": "Eesti",
     "og_title": "Sedaha (Sounds) avamine, eesti keeles",
     "og_desc": "Lõng sõnadest, mis olid kunagi helid.",
     "cta": "Raamat algab siit. Täielik eestikeelne väljaanne on teel; seni saab kogu raamatut lugeda tasuta: pärsia, inglise ja taani keeles."},
    {"code": "TR", "slug": "tr", "lang": "tr", "rtl": False, "locale": "tr_TR", "en": "Turkish", "native": "Türkçe",
     "og_title": "Sedaha (Sounds) açılışı, Türkçe",
     "og_desc": "Bir zamanlar ses olan kelimelerin ipliği.",
     "cta": "Kitap burada başlıyor. Türkçe baskının tamamı yolda; o zamana kadar kitabın tümü ücretsiz okunabilir: Farsça, İngilizce ve Danca."},
    {"code": "AZ", "slug": "az", "lang": "az", "rtl": False, "locale": "az_AZ", "en": "Azerbaijani", "native": "Azərbaycanca",
     "og_title": "Sedaha (Sounds) açılışı, Azərbaycanca",
     "og_desc": "Bir vaxtlar səs olan sözlərin ipi.",
     "cta": "Kitab buradan başlayır. Tam Azərbaycanca nəşr yoldadır; o vaxta qədər bütün kitabı pulsuz oxumaq olar: farsca, ingiliscə və danca."},
    {"code": "KA", "slug": "ka", "lang": "ka", "rtl": False, "locale": "ka_GE", "en": "Georgian", "native": "ქართული",
     "og_title": "Sedaha (Sounds): გახსნა ქართულად",
     "og_desc": "ძაფი სიტყვებისა, რომლებიც ოდესღაც ხმები იყვნენ.",
     "cta": "წიგნი აქ იწყება. სრული ქართული გამოცემა გზაშია; მანამდე მთელი წიგნის წაკითხვა უფასოდ შეიძლება: სპარსულად, ინგლისურად და დანიურად."},
    {"code": "HY", "slug": "hy", "lang": "hy", "rtl": False, "locale": "hy_AM", "en": "Armenian", "native": "Հայերեն",
     "og_title": "Sedaha (Sounds). Բացումը՝ հայերեն",
     "og_desc": "Բառերի թելը, որ ժամանակին ձայներ են եղել։",
     "cta": "Գիրքը սկսվում է հենց այստեղից։ Ամբողջական հայերեն հրատարակությունը ճանապարհին է. մինչ այդ ամբողջ գիրքը կարելի է կարդալ անվճար՝ պարսկերեն, անգլերեն և դանիերեն։"},
    {"code": "AR", "slug": "ar", "lang": "ar", "rtl": True, "locale": "ar_AR", "en": "Arabic", "native": "العربية",
     "og_title": "افتتاحية Sedaha (Sounds)، بالعربية",
     "og_desc": "خيط من الكلمات التي كانت يوماً أصواتاً.",
     "cta": "يبدأ الكتاب من هنا. الطبعة العربية الكاملة في الطريق؛ وحتى ذلك الحين يمكن قراءة الكتاب كاملاً مجاناً: بالفارسية والإنجليزية والدنماركية."},
    {"code": "HE", "slug": "he", "lang": "he", "rtl": True, "locale": "he_IL", "en": "Hebrew", "native": "עברית",
     "og_title": "הפתיחה של Sedaha (Sounds), בעברית",
     "og_desc": "חוט של מילים שהיו פעם קולות.",
     "cta": "הספר מתחיל כאן. המהדורה העברית המלאה בדרך; עד אז אפשר לקרוא את הספר כולו בחינם: בפרסית, באנגלית ובדנית."},
    {"code": "UR", "slug": "ur", "lang": "ur", "rtl": True, "locale": "ur_PK", "en": "Urdu", "native": "اردو",
     "og_title": "Sedaha (Sounds) کا آغاز، اردو میں",
     "og_desc": "الفاظ کا وہ دھاگا جو کبھی آوازیں تھے۔",
     "cta": "کتاب یہیں سے شروع ہوتی ہے۔ مکمل اردو ایڈیشن راستے میں ہے؛ تب تک پوری کتاب مفت پڑھی جا سکتی ہے: فارسی، انگریزی اور ڈینش میں۔"},
    {"code": "HI", "slug": "hi", "lang": "hi", "rtl": False, "locale": "hi_IN", "en": "Hindi", "native": "हिन्दी",
     "og_title": "Sedaha (Sounds) का प्रारंभ, हिन्दी में",
     "og_desc": "उन शब्दों का धागा जो कभी ध्वनियाँ थे।",
     "cta": "किताब यहीं से शुरू होती है। पूरा हिन्दी संस्करण रास्ते में है; तब तक पूरी किताब मुफ़्त पढ़ी जा सकती है: फ़ारसी, अंग्रेज़ी और डेनिश में।"},
    {"code": "BN", "slug": "bn", "lang": "bn", "rtl": False, "locale": "bn_IN", "en": "Bengali", "native": "বাংলা",
     "og_title": "Sedaha (Sounds)-এর শুরু, বাংলায়",
     "og_desc": "শব্দের সুতো, যা একদিন ধ্বনি ছিল।",
     "cta": "বইটি এখান থেকেই শুরু। সম্পূর্ণ বাংলা সংস্করণ আসছে; ততদিন পুরো বইটি বিনামূল্যে পড়া যায়: ফারসি, ইংরেজি ও ড্যানিশ ভাষায়।"},
    {"code": "PA", "slug": "pa", "lang": "pa", "rtl": False, "locale": "pa_IN", "en": "Punjabi", "native": "ਪੰਜਾਬੀ",
     "og_title": "Sedaha (Sounds) ਦੀ ਸ਼ੁਰੂਆਤ, ਪੰਜਾਬੀ ਵਿੱਚ",
     "og_desc": "ਉਨ੍ਹਾਂ ਸ਼ਬਦਾਂ ਦਾ ਧਾਗਾ ਜੋ ਕਦੇ ਆਵਾਜ਼ਾਂ ਸਨ।",
     "cta": "ਕਿਤਾਬ ਇੱਥੋਂ ਹੀ ਸ਼ੁਰੂ ਹੁੰਦੀ ਹੈ। ਪੂਰਾ ਪੰਜਾਬੀ ਐਡੀਸ਼ਨ ਰਾਹ ਵਿੱਚ ਹੈ; ਉਦੋਂ ਤੱਕ ਪੂਰੀ ਕਿਤਾਬ ਮੁਫ਼ਤ ਪੜ੍ਹੀ ਜਾ ਸਕਦੀ ਹੈ: ਫ਼ਾਰਸੀ, ਅੰਗਰੇਜ਼ੀ ਅਤੇ ਡੈਨਿਸ਼ ਵਿੱਚ।"},
    {"code": "TA", "slug": "ta", "lang": "ta", "rtl": False, "locale": "ta_IN", "en": "Tamil", "native": "தமிழ்",
     "og_title": "Sedaha (Sounds): தொடக்கம், தமிழில்",
     "og_desc": "ஒருகாலத்தில் ஒலிகளாக இருந்த சொற்களின் நூல்.",
     "cta": "புத்தகம் இங்கிருந்தே தொடங்குகிறது. முழுமையான தமிழ்ப் பதிப்பு வரும் வழியில் உள்ளது; அதுவரை முழு புத்தகத்தையும் இலவசமாக வாசிக்கலாம்: பாரசீகம், ஆங்கிலம், டேனிஷ் மொழிகளில்."},
    {"code": "TE", "slug": "te", "lang": "te", "rtl": False, "locale": "te_IN", "en": "Telugu", "native": "తెలుగు",
     "og_title": "Sedaha (Sounds): ప్రారంభం, తెలుగులో",
     "og_desc": "ఒకప్పుడు శబ్దాలుగా ఉన్న పదాల దారం.",
     "cta": "పుస్తకం ఇక్కడి నుంచే మొదలవుతుంది. పూర్తి తెలుగు ఎడిషన్ దారిలో ఉంది; అప్పటివరకు మొత్తం పుస్తకాన్ని ఉచితంగా చదవవచ్చు: పర్షియన్, ఇంగ్లీష్, డానిష్ భాషల్లో."},
    {"code": "ML", "slug": "ml", "lang": "ml", "rtl": False, "locale": "ml_IN", "en": "Malayalam", "native": "മലയാളം",
     "og_title": "Sedaha (Sounds): ആമുഖം, മലയാളത്തിൽ",
     "og_desc": "ഒരിക്കൽ ശബ്ദങ്ങളായിരുന്ന വാക്കുകളുടെ നൂൽ.",
     "cta": "പുസ്തകം ഇവിടെ നിന്നു തുടങ്ങുന്നു. സമ്പൂർണ്ണ മലയാളം പതിപ്പ് വഴിയിലാണ്; അതുവരെ മുഴുവൻ പുസ്തകവും സൗജന്യമായി വായിക്കാം: പേർഷ്യൻ, ഇംഗ്ലീഷ്, ഡാനിഷ് ഭാഷകളിൽ."},
    {"code": "KN", "slug": "kn", "lang": "kn", "rtl": False, "locale": "kn_IN", "en": "Kannada", "native": "ಕನ್ನಡ",
     "og_title": "Sedaha (Sounds): ಆರಂಭ, ಕನ್ನಡದಲ್ಲಿ",
     "og_desc": "ಒಂದು ಕಾಲದಲ್ಲಿ ಶಬ್ದಗಳಾಗಿದ್ದ ಪದಗಳ ಎಳೆ.",
     "cta": "ಪುಸ್ತಕ ಇಲ್ಲಿಂದಲೇ ಆರಂಭವಾಗುತ್ತದೆ. ಪೂರ್ಣ ಕನ್ನಡ ಆವೃತ್ತಿ ದಾರಿಯಲ್ಲಿದೆ; ಅಲ್ಲಿಯವರೆಗೆ ಇಡೀ ಪುಸ್ತಕವನ್ನು ಉಚಿತವಾಗಿ ಓದಬಹುದು: ಪರ್ಷಿಯನ್, ಇಂಗ್ಲಿಷ್ ಮತ್ತು ಡ್ಯಾನಿಷ್ ಭಾಷೆಗಳಲ್ಲಿ."},
    {"code": "MR", "slug": "mr", "lang": "mr", "rtl": False, "locale": "mr_IN", "en": "Marathi", "native": "मराठी",
     "og_title": "Sedaha (Sounds) चे उद्घाटन, मराठीत",
     "og_desc": "कधीकाळी ध्वनी असलेल्या शब्दांचा धागा.",
     "cta": "पुस्तक इथूनच सुरू होते. संपूर्ण मराठी आवृत्ती वाटेवर आहे; तोपर्यंत संपूर्ण पुस्तक मोफत वाचता येते: फारसी, इंग्रजी आणि डॅनिश भाषेत."},
    {"code": "ZH", "slug": "zh", "lang": "zh", "rtl": False, "locale": "zh_CN", "en": "Chinese", "native": "中文",
     "og_title": "《Sedaha (Sounds)》开篇，中文版",
     "og_desc": "曾经是声音的词语之线。",
     "cta": "这本书从这里开始。完整的中文版正在路上；在那之前，整本书可以免费阅读：波斯语、英语和丹麦语版本。"},
    {"code": "JA", "slug": "ja", "lang": "ja", "rtl": False, "locale": "ja_JP", "en": "Japanese", "native": "日本語",
     "og_title": "『Sedaha (Sounds)』開幕、日本語版",
     "og_desc": "かつて音だった言葉の糸。",
     "cta": "本はここから始まる。完全な日本語版は準備中。それまでは、ペルシア語・英語・デンマーク語で全文を無料で読むことができる。"},
    {"code": "KO", "slug": "ko", "lang": "ko", "rtl": False, "locale": "ko_KR", "en": "Korean", "native": "한국어",
     "og_title": "Sedaha (Sounds) 서문, 한국어판",
     "og_desc": "한때 소리였던 말들의 실타래.",
     "cta": "책은 여기서 시작된다. 한국어 완역판이 준비 중이다. 그때까지 책 전체를 페르시아어, 영어, 덴마크어로 무료로 읽을 수 있다."},
    {"code": "TH", "slug": "th", "lang": "th", "rtl": False, "locale": "th_TH", "en": "Thai", "native": "ไทย",
     "og_title": "บทเปิดของ Sedaha (Sounds) ภาษาไทย",
     "og_desc": "เส้นด้ายแห่งถ้อยคำที่ครั้งหนึ่งเคยเป็นเสียง",
     "cta": "หนังสือเริ่มต้นจากตรงนี้ ฉบับภาษาไทยฉบับเต็มกำลังจะมา ระหว่างนี้อ่านทั้งเล่มได้ฟรีในภาษาเปอร์เซีย อังกฤษ และเดนมาร์ก"},
    {"code": "VI", "slug": "vi", "lang": "vi", "rtl": False, "locale": "vi_VN", "en": "Vietnamese", "native": "Tiếng Việt",
     "og_title": "Mở đầu của Sedaha (Sounds), bằng tiếng Việt",
     "og_desc": "Sợi chỉ của những từ ngữ từng một thời là âm thanh.",
     "cta": "Cuốn sách bắt đầu từ đây. Ấn bản tiếng Việt đầy đủ đang trên đường đến; trong lúc chờ, có thể đọc trọn cuốn sách miễn phí: bằng tiếng Ba Tư, tiếng Anh và tiếng Đan Mạch."},
    {"code": "ID", "slug": "id", "lang": "id", "rtl": False, "locale": "id_ID", "en": "Indonesian", "native": "Bahasa Indonesia",
     "og_title": "Pembukaan Sedaha (Sounds), dalam bahasa Indonesia",
     "og_desc": "Benang kata-kata yang dulunya pernah menjadi suara.",
     "cta": "Buku ini dimulai dari sini. Edisi bahasa Indonesia yang lengkap sedang dalam perjalanan; sementara itu, seluruh buku dapat dibaca gratis: dalam bahasa Persia, Inggris, dan Denmark."},
    {"code": "MS", "slug": "ms", "lang": "ms", "rtl": False, "locale": "ms_MY", "en": "Malay", "native": "Bahasa Melayu",
     "og_title": "Pembukaan Sedaha (Sounds), dalam bahasa Melayu",
     "og_desc": "Benang kata-kata yang suatu ketika dahulu pernah menjadi suara.",
     "cta": "Buku ini bermula di sini. Edisi bahasa Melayu yang lengkap sedang dalam perjalanan; sementara itu, seluruh buku boleh dibaca secara percuma: dalam bahasa Parsi, Inggeris, dan Denmark."},
    {"code": "SW", "slug": "sw", "lang": "sw", "rtl": False, "locale": "sw_KE", "en": "Swahili", "native": "Kiswahili",
     "og_title": "Ufunguzi wa Sedaha (Sounds), kwa Kiswahili",
     "og_desc": "Uzi wa maneno ambayo wakati mmoja yalikuwa sauti.",
     "cta": "Kitabu kinaanzia hapa. Toleo kamili la Kiswahili liko njiani; hadi wakati huo, kitabu chote kinaweza kusomwa bila malipo: kwa Kiajemi, Kiingereza na Kidenishi."},
    {"code": "PRS", "slug": "prs", "lang": "prs", "rtl": True, "locale": "prs_AF", "en": "Dari", "native": "دری",
     "og_title": "سرآغاز Sedaha (Sounds)، به دری",
     "og_desc": "سررشته‌ی کلماتی که زمانی صدا بوده‌اند.",
     "cta": "کتاب از همین‌جا آغاز می‌شود. نسخه‌ی کامل دری در راه است؛ تا آن زمان تمام کتاب را می‌توان رایگان خواند: به فارسی، انگلیسی و دنمارکی."},
    {"code": "PS", "slug": "ps", "lang": "ps", "rtl": True, "locale": "ps_AF", "en": "Pashto", "native": "پښتو",
     "og_title": "د Sedaha (Sounds) پیل، په پښتو",
     "og_desc": "د هغو کلمو تار چې یو وخت آوازونه وو.",
     "cta": "کتاب له همدې ځایه پیلېږي. بشپړه پښتو ګڼه په لاره کې ده؛ تر هغه وخته ټول کتاب وړیا لوستل کېدای شي: په فارسي، انګلیسي او ډنمارکي."},
    {"code": "CKB", "slug": "ckb", "lang": "ckb", "rtl": True, "locale": "ckb_IQ", "en": "Kurdish (Sorani)", "native": "کوردیی سۆرانی",
     "og_title": "کردنەوەی Sedaha (Sounds)، بە کوردیی سۆرانی",
     "og_desc": "دەزووی ئەو وشانەی کە جاران دەنگ بوون.",
     "cta": "کتێبەکە لێرەوە دەست پێدەکات. وەشانی تەواوی سۆرانی لە ڕێگایە؛ تا ئەو کاتە دەتوانیت هەموو کتێبەکە بەخۆڕایی بخوێنیتەوە: بە فارسی، ئینگلیزی و دانیمارکی."},
    {"code": "KU", "slug": "ku", "lang": "ku", "rtl": False, "locale": "ku_TR", "en": "Kurdish (Kurmanji)", "native": "Kurmancî",
     "og_title": "Vekirina Sedaha (Sounds), bi kurmancî",
     "og_desc": "Rêzika peyvên ku carekê deng bûne.",
     "cta": "Pirtûk ji vir dest pê dike. Çapa kurmancî ya temam di rê de ye; heta wê demê, tevahiya pirtûkê belaş tê xwendin: bi farisî, îngilîzî û danîmarkî."},
    {"code": "BAL", "slug": "bal", "lang": "bal", "rtl": True, "locale": "bal_IR", "en": "Balochi", "native": "بلۏچی",
     "og_title": "Sedaha (Sounds) ءِ بُنگیج، بلۏچی ءَ",
     "og_desc": "آ گالانی تار که یک وهدے توار اَتَنت.",
     "cta": "کتاب چہ اِدا بندات بیت. بلۏچی ءِ پوریں نسخہ راہ ءَ اِنت؛ تاں آ وهد ءَ سجّهیں کتاب مفت وانگ بیت: فارسی، انگریزی ءُ ڈنمارکی ءَ."},
    {"code": "GLK", "slug": "glk", "lang": "glk", "rtl": True, "locale": "glk_IR", "en": "Gilaki", "native": "گیلکی",
     "og_title": "سرآغازِ Sedaha (Sounds)، به گیلکی",
     "og_desc": "اون کلمه‌ئن ریشته کی یک زمانی صدا بید.",
     "cta": "کتاب همین جا جه سر گیره. گیلکی کامل نسخه راه سر ایسه؛ تا او موقع تانی همه کتابا مجانی بخانی: فارسی، انگلیسی و دانمارکی."},
    {"code": "LRC", "slug": "lrc", "lang": "lrc", "rtl": True, "locale": "lrc_IR", "en": "Northern Luri", "native": "لری",
     "og_title": "سرآغازِ Sedaha (Sounds)، به لری",
     "og_desc": "رِشته‌ی کلمه‌یایی که یه زمانی دَنگ بی‌یِنه.",
     "cta": "کتاو وِ همیچَه بند می‌بو. نسخه‌ی کاملِ لری مِن رَهه؛ تا او وقت تری همه‌ی کتاو نه مجانی بخونی: وِ فارسی، انگلیسی و دانمارکی."},
    {"code": "MZN", "slug": "mzn", "lang": "mzn", "rtl": True, "locale": "mzn_IR", "en": "Mazanderani", "native": "مازرونی",
     "og_title": "سرآغازِ Sedaha (Sounds)، به مازرونی",
     "og_desc": "اون کلمه‌هایِ رشته که یک زمونی صدا بی‌نه.",
     "cta": "کتاب همینجه جا شروع وونه. مازرونی کامل نسخه راه دله هسته؛ تا او موقع تونّی همه‌ی کتاب ره مجانی بخوندی: فارسی، انگلیسی و دانمارکی."},
    {"code": "SD", "slug": "sd", "lang": "sd", "rtl": True, "locale": "sd_PK", "en": "Sindhi", "native": "سنڌي",
     "og_title": "Sedaha (Sounds) جي شروعات، سنڌيءَ ۾",
     "og_desc": "لفظن جو اُھو ڌاڳو، جيڪي ڪنھن وقت آواز ھئا۔",
     "cta": "ڪتاب ھتان ئي شروع ٿئي ٿو۔ مڪمل سنڌي ايڊيشن رستي ۾ آھي؛ تيستائين سڄو ڪتاب مفت پڙھي سگھجي ٿو: فارسي، انگريزي ۽ ڊينش ۾۔"},
    {"code": "UG", "slug": "ug", "lang": "ug", "rtl": True, "locale": "ug_CN", "en": "Uyghur", "native": "ئۇيغۇرچە",
     "og_title": "Sedaha (Sounds) نىڭ باشلىنىشى، ئۇيغۇرچە",
     "og_desc": "ئەسلىدە ئاۋاز بولغان سۆزلەر يىپى.",
     "cta": "كىتاب مۇشۇ يەردىن باشلىنىدۇ. تولۇق ئۇيغۇرچە نەشرى يولدا؛ ئۇ چاغقىچە پۈتۈن كىتابنى ھەقسىز ئوقۇغىلى بولىدۇ: پارسچە، ئىنگلىزچە ۋە دانىيەچە."},
    {"code": "KK", "slug": "kk", "lang": "kk", "rtl": False, "locale": "kk_KZ", "en": "Kazakh", "native": "Қазақ",
     "og_title": "Sedaha (Sounds) кіріспесі, қазақша",
     "og_desc": "Бір кезде дыбыс болған сөздер жібі.",
     "cta": "Кітап осы жерден басталады. Толық қазақша басылым жолда; оған дейін бүкіл кітапты тегін оқуға болады: парсыша, ағылшынша және датша."},
    {"code": "KY", "slug": "ky", "lang": "ky", "rtl": False, "locale": "ky_KG", "en": "Kyrgyz", "native": "Кыргызча",
     "og_title": "Sedaha (Sounds) башталышы, кыргызча",
     "og_desc": "Бир маал үн болгон сөздөр жиби.",
     "cta": "Китеп ушул жерден башталат. Толук кыргызча басылышы жолдо; ага чейин бүт китепти акысыз окууга болот: фарсыча, англисче жана датча."},
    {"code": "TG", "slug": "tg", "lang": "tg", "rtl": False, "locale": "tg_TJ", "en": "Tajik", "native": "Тоҷикӣ",
     "og_title": "Сарсухани Sedaha (Sounds), ба тоҷикӣ",
     "og_desc": "Риштаи калимоте, ки замоне садо буданд.",
     "cta": "Китоб аз ҳамин ҷо оғоз мешавад. Нашри пурраи тоҷикӣ дар роҳ аст; то он вақт тамоми китобро ройгон хондан мумкин аст: ба форсӣ, англисӣ ва даниягӣ."},
    {"code": "TK", "slug": "tk", "lang": "tk", "rtl": False, "locale": "tk_TM", "en": "Turkmen", "native": "Türkmençe",
     "og_title": "Sedaha (Sounds) açylyşy, türkmençe",
     "og_desc": "Bir wagtlar ses bolan sözleriň ýüplügi.",
     "cta": "Kitap şu ýerden başlanýar. Doly türkmen neşiri ýolda; şol wagta çenli tutuş kitaby mugt okap bolýar: parsça, iňlisçe we dança."},
    {"code": "TT", "slug": "tt", "lang": "tt", "rtl": False, "locale": "tt_RU", "en": "Tatar", "native": "Татарча",
     "og_title": "Sedaha (Sounds) сүз башы, татарча",
     "og_desc": "Бервакыт тавыш булган сүзләр җебе.",
     "cta": "Китап шушыннан башлана. Тулы татарча басма юлда; шул вакытка кадәр бөтен китапны бушлай укып була: фарсыча, инглизчә һәм датча."},
    {"code": "UZ", "slug": "uz", "lang": "uz", "rtl": False, "locale": "uz_UZ", "en": "Uzbek", "native": "Oʻzbekcha",
     "og_title": "Sedaha (Sounds) kirishi, oʻzbekcha",
     "og_desc": "Bir zamonlar ovoz boʻlgan soʻzlar ipi.",
     "cta": "Kitob shu yerdan boshlanadi. Toʻliq oʻzbekcha nashr yoʻlda; ungacha butun kitobni bepul oʻqish mumkin: fors, ingliz va dan tillarida."},
    {"code": "MN", "slug": "mn", "lang": "mn", "rtl": False, "locale": "mn_MN", "en": "Mongolian", "native": "Монгол",
     "og_title": "Sedaha (Sounds)-ийн оршил, монголоор",
     "og_desc": "Нэгэн цагт дуу байсан үгсийн утас.",
     "cta": "Ном эндээс эхэлнэ. Монгол хэл дээрх бүрэн хэвлэл замдаа явж байна; тэр болтол номыг бүхэлд нь үнэгүй унших боломжтой: перс, англи, дани хэлээр."},
    {"code": "GU", "slug": "gu", "lang": "gu", "rtl": False, "locale": "gu_IN", "en": "Gujarati", "native": "ગુજરાતી",
     "og_title": "Sedaha (Sounds)નો પ્રારંભ, ગુજરાતીમાં",
     "og_desc": "એ શબ્દોનો દોરો, જે એક સમયે અવાજો હતા.",
     "cta": "પુસ્તક અહીંથી જ શરૂ થાય છે. સંપૂર્ણ ગુજરાતી આવૃત્તિ રસ્તામાં છે; ત્યાં સુધી આખું પુસ્તક મફત વાંચી શકાય છે: ફારસી, અંગ્રેજી અને ડેનિશમાં."},
    {"code": "NE", "slug": "ne", "lang": "ne", "rtl": False, "locale": "ne_NP", "en": "Nepali", "native": "नेपाली",
     "og_title": "Sedaha (Sounds)को सुरुवात, नेपालीमा",
     "og_desc": "ती शब्दहरूको धागो, जुन एक समय ध्वनिहरू थिए।",
     "cta": "किताब यहीँबाट सुरु हुन्छ। पूरा नेपाली संस्करण बाटोमा छ; तबसम्म सिंगो किताब निःशुल्क पढ्न सकिन्छ: फारसी, अंग्रेजी र डेनिस भाषामा।"},
    {"code": "SI", "slug": "si", "lang": "si", "rtl": False, "locale": "si_LK", "en": "Sinhala", "native": "සිංහල",
     "og_title": "Sedaha (Sounds) හි ආරම්භය, සිංහලෙන්",
     "og_desc": "වරෙක හඬ වූ වචනවල නූල.",
     "cta": "පොත මෙතැනින් ආරම්භ වේ. සම්පූර්ණ සිංහල සංස්කරණය එමින් පවතී; එතෙක් මුළු පොතම නොමිලේ කියවිය හැක: පර්සියානු, ඉංග්‍රීසි සහ ඩෙන්මාර්ක භාෂාවලින්."},
    {"code": "AS", "slug": "as", "lang": "as", "rtl": False, "locale": "as_IN", "en": "Assamese", "native": "অসমীয়া",
     "og_title": "Sedaha (Sounds)-ৰ সূচনা, অসমীয়াত",
     "og_desc": "শব্দৰ সূতা, যি এসময় ধ্বনি আছিল।",
     "cta": "কিতাপখন ইয়াৰ পৰাই আৰম্ভ হয়। সম্পূৰ্ণ অসমীয়া সংস্কৰণ আহি আছে; তেতিয়ালৈকে গোটেই কিতাপখন বিনামূলীয়াকৈ পঢ়িব পাৰি: ফাৰ্চী, ইংৰাজী আৰু ডেনিছ ভাষাত।"},
    {"code": "OR", "slug": "or", "lang": "or", "rtl": False, "locale": "or_IN", "en": "Odia", "native": "ଓଡ଼ିଆ",
     "og_title": "Sedaha (Sounds)ର ଆରମ୍ଭ, ଓଡ଼ିଆରେ",
     "og_desc": "ସେହି ଶବ୍ଦଗୁଡ଼ିକର ସୂତ୍ର, ଯାହା ଏକ ସମୟରେ ଧ୍ୱନି ଥିଲେ।",
     "cta": "ପୁସ୍ତକ ଏଠାରୁ ହିଁ ଆରମ୍ଭ ହୁଏ। ସମ୍ପୂର୍ଣ୍ଣ ଓଡ଼ିଆ ସଂସ୍କରଣ ବାଟରେ ଅଛି; ସେ ପର୍ଯ୍ୟନ୍ତ ପୂରା ପୁସ୍ତକ ମାଗଣାରେ ପଢ଼ାଯାଇପାରିବ: ଫାର୍ସୀ, ଇଂରାଜୀ ଓ ଡେନିସ୍ ଭାଷାରେ।"},
    {"code": "MY", "slug": "my", "lang": "my", "rtl": False, "locale": "my_MM", "en": "Burmese", "native": "မြန်မာ",
     "og_title": "Sedaha (Sounds) ၏ နိဒါန်း၊ မြန်မာဘာသာဖြင့်",
     "og_desc": "တစ်ချိန်က အသံများဖြစ်ခဲ့သော စကားလုံးများ၏ ချည်ကြိုး။",
     "cta": "စာအုပ်သည် ဤနေရာမှ စတင်သည်။ မြန်မာဘာသာ အပြည့်အစုံ လမ်းခရီးတွင် ရှိသည်။ ထိုအချိန်အထိ စာအုပ်တစ်အုပ်လုံးကို အခမဲ့ ဖတ်နိုင်သည် — ပါရှန်း၊ အင်္ဂလိပ်နှင့် ဒိန်းမတ်ဘာသာဖြင့်။"},
    {"code": "KM", "slug": "km", "lang": "km", "rtl": False, "locale": "km_KH", "en": "Khmer", "native": "ខ្មែរ",
     "og_title": "អារម្ភកថានៃ Sedaha (Sounds) ជាភាសាខ្មែរ",
     "og_desc": "ខ្សែស្រឡាយពាក្យ ដែលកាលពីមុនធ្លាប់ជាសំឡេង។",
     "cta": "សៀវភៅចាប់ផ្តើមពីទីនេះ។ បោះពុម្ពខ្មែរពេញលេញកំពុងមកដល់ រហូតដល់ពេលនោះ អាចអានសៀវភៅទាំងមូលដោយឥតគិតថ្លៃ៖ ជាភាសាពែរ្ស អង់គ្លេស និងដាណឺម៉ាក។"},
    {"code": "LO", "slug": "lo", "lang": "lo", "rtl": False, "locale": "lo_LA", "en": "Lao", "native": "ລາວ",
     "og_title": "ບົດເປີດຂອງ Sedaha (Sounds) ພາສາລາວ",
     "og_desc": "ເສັ້ນດ້າຍຂອງຄໍາເວົ້າ ທີ່ເຄີຍເປັນສຽງມາກ່ອນ",
     "cta": "ປຶ້ມເລີ່ມຕົ້ນຈາກບ່ອນນີ້ ສະບັບພາສາລາວເຕັມກໍາລັງມາ ລະຫວ່າງນີ້ອ່ານທັງເຫລັ້ມໄດ້ຟຣີ ເປັນພາສາເປີເຊຍ ອັງກິດ ແລະ ເດນມາກ"},
    {"code": "JV", "slug": "jv", "lang": "jv", "rtl": False, "locale": "jv_ID", "en": "Javanese", "native": "Basa Jawa",
     "og_title": "Pambuka Sedaha (Sounds), ing basa Jawa",
     "og_desc": "Lawe tembung-tembung sing biyen tau dadi swara.",
     "cta": "Buku iki diwiwiti saka kene. Edhisi basa Jawa sing komplit isih ana ing dalan; nganti wektu kuwi, kabeh buku bisa diwaca gratis: ing basa Persia, Inggris, lan Denmark."},
    {"code": "SU", "slug": "su", "lang": "su", "rtl": False, "locale": "su_ID", "en": "Sundanese", "native": "Basa Sunda",
     "og_title": "Bubuka Sedaha (Sounds), dina basa Sunda",
     "og_desc": "Benang kecap-kecap nu baheulana mangrupa sora.",
     "cta": "Buku ieu dimimitian ti dieu. Édisi basa Sunda nu lengkep keur di jalan; nepi ka waktu éta, sakabéh buku bisa dibaca haratis: dina basa Pérsia, Inggris, jeung Dénmark."},
    {"code": "CEB", "slug": "ceb", "lang": "ceb", "rtl": False, "locale": "ceb_PH", "en": "Cebuano", "native": "Cebuano",
     "og_title": "Ang pag-abli sa Sedaha (Sounds), sa Cebuano",
     "og_desc": "Ang hilo sa mga pulong nga kaniadto mga tingog.",
     "cta": "Ang libro magsugod dinhi. Ang kompletong edisyon sa Cebuano padulong na; hangtod niana, ang tibuok libro mabasa nga libre: sa Persian, English, ug Danish."},
    {"code": "TL", "slug": "tl", "lang": "tl", "rtl": False, "locale": "tl_PH", "en": "Tagalog", "native": "Tagalog",
     "og_title": "Ang pagbubukas ng Sedaha (Sounds), sa Tagalog",
     "og_desc": "Ang sinulid ng mga salitang minsan ay naging mga tunog.",
     "cta": "Nagsisimula ang aklat dito. Ang kumpletong edisyong Tagalog ay parating na; hanggang doon, mababasa nang libre ang buong aklat: sa Persian, Ingles, at Danish."},
    {"code": "EU", "slug": "eu", "lang": "eu", "rtl": False, "locale": "eu_ES", "en": "Basque", "native": "Euskara",
     "og_title": "Sedaha (Sounds): sarrera, euskaraz",
     "og_desc": "Behin soinuak izandako hitzen haria.",
     "cta": "Liburua hemen hasten da. Euskarazko edizio osoa bidean da; ordura arte, liburu osoa doan irakur daiteke: persieraz, ingelesez eta danieraz."},
    {"code": "BR", "slug": "br", "lang": "br", "rtl": False, "locale": "br_FR", "en": "Breton", "native": "Brezhoneg",
     "og_title": "Digoradur Sedaha (Sounds), e brezhoneg",
     "og_desc": "An neudenn gerioù a oa bet trouzioù ur wech.",
     "cta": "Al levr a grog amañ. Emañ an embannadur brezhonek klok o tont; betek-hen e c'haller lenn al levr a-bezh evit netra: e perseg, e saozneg hag e daneg."},
    {"code": "CA", "slug": "ca", "lang": "ca", "rtl": False, "locale": "ca_ES", "en": "Catalan", "native": "Català",
     "og_title": "L'obertura de Sedaha (Sounds), en català",
     "og_desc": "El fil de paraules que una vegada foren sons.",
     "cta": "El llibre comença aquí. L'edició catalana completa és en camí; mentrestant, el llibre sencer es pot llegir gratis: en persa, en anglès i en danès."},
    {"code": "CY", "slug": "cy", "lang": "cy", "rtl": False, "locale": "cy_GB", "en": "Welsh", "native": "Cymraeg",
     "og_title": "Agoriad Sedaha (Sounds), yn Gymraeg",
     "og_desc": "Edafedd o eiriau a fu unwaith yn synau.",
     "cta": "Mae'r llyfr yn dechrau yma. Mae'r argraffiad Cymraeg llawn ar ei ffordd; tan hynny, gellir darllen y llyfr cyfan am ddim: yn Perseg, Saesneg a Daneg."},
    {"code": "FY", "slug": "fy", "lang": "fy", "rtl": False, "locale": "fy_NL", "en": "Frisian", "native": "Frysk",
     "og_title": "De oanhef fan Sedaha (Sounds), yn it Frysk",
     "og_desc": "De tried fan wurden dy't ienris lûden west hawwe.",
     "cta": "It boek begjint hjir. De folsleine Fryske edysje is ûnderweis; oant dy tiid kin it hiele boek fergees lêzen wurde: yn it Perzysk, Ingelsk en Deensk."},
    {"code": "GA", "slug": "ga", "lang": "ga", "rtl": False, "locale": "ga_IE", "en": "Irish", "native": "Gaeilge",
     "og_title": "Oscailt Sedaha (Sounds), i nGaeilge",
     "og_desc": "Snáithe na bhfocal a bhí tráth ina bhfuaimeanna.",
     "cta": "Tosaíonn an leabhar anseo. Tá an t-eagrán iomlán Gaeilge ar an mbealach; go dtí sin, is féidir an leabhar ar fad a léamh saor in aisce: i bPeirsis, i mBéarla agus i nDanmhairgis."},
    {"code": "GD", "slug": "gd", "lang": "gd", "rtl": False, "locale": "gd_GB", "en": "Scottish Gaelic", "native": "Gàidhlig",
     "og_title": "Fosgladh Sedaha (Sounds), sa Ghàidhlig",
     "og_desc": "Snàth nam faclan a bha, aon uair, nan fuaimean.",
     "cta": "Tòisichidh an leabhar an-seo. Tha an deasachadh slàn Gàidhlig air an rathad; gus an uair sin, gabhaidh an leabhar gu lèir a leughadh an-asgaidh: ann am Peirsis, Beurla agus Danmhairgis."},
    {"code": "GL", "slug": "gl", "lang": "gl", "rtl": False, "locale": "gl_ES", "en": "Galician", "native": "Galego",
     "og_title": "A abertura de Sedaha (Sounds), en galego",
     "og_desc": "O fío de palabras que noutro tempo foron sons.",
     "cta": "O libro comeza aquí. A edición galega completa está en camiño; mentres tanto, o libro enteiro pódese ler de balde: en persa, en inglés e en dinamarqués."},
    {"code": "LB", "slug": "lb", "lang": "lb", "rtl": False, "locale": "lb_LU", "en": "Luxembourgish", "native": "Lëtzebuergesch",
     "og_title": "Den Optakt vu Sedaha (Sounds), op Lëtzebuergesch",
     "og_desc": "De Fuedem vu Wierder, déi emol Kläng waren.",
     "cta": "D'Buch fänkt hei un. Déi komplett Lëtzebuerger Editioun ass ënnerwee; bis dohin kann dat ganzt Buch gratis gelies ginn: op Persesch, Englesch an Dänesch."},
    {"code": "MT", "slug": "mt", "lang": "mt", "rtl": False, "locale": "mt_MT", "en": "Maltese", "native": "Malti",
     "og_title": "Il-ftuħ ta' Sedaha (Sounds), bil-Malti",
     "og_desc": "Il-ħajta ta' kliem li darba kien ħsejjes.",
     "cta": "Il-ktieb jibda hawn. L-edizzjoni Maltija sħiħa tinsab fit-triq; sa dak iż-żmien, il-ktieb kollu jista' jinqara b'xejn: bil-Persjan, bl-Ingliż u bid-Daniż."},
    {"code": "NDS", "slug": "nds", "lang": "nds", "rtl": False, "locale": "nds_DE", "en": "Low German", "native": "Plattdüütsch",
     "og_title": "De Uptakt vun Sedaha (Sounds), op Plattdüütsch",
     "og_desc": "De Faden vun Wöör, de mal Kläng weern.",
     "cta": "Dat Book fangt hier an. De hele plattdüütsche Utgaav is ünnerwegens; bet dorhen kann dat hele Book för ümsünst leest warrn: op Persisch, Engelsch un Däänsch."},
    {"code": "OC", "slug": "oc", "lang": "oc", "rtl": False, "locale": "oc_FR", "en": "Occitan", "native": "Occitan",
     "og_title": "La dubertura de Sedaha (Sounds), en occitan",
     "og_desc": "Lo fial de paraulas qu'èran, un temps, de sons.",
     "cta": "Lo libre comença aicí. L'edicion occitana completa es en camin; fins alara, tot lo libre se pòt legir a gratis: en persan, en anglés e en danés."},
    {"code": "RM", "slug": "rm", "lang": "rm", "rtl": False, "locale": "rm_CH", "en": "Romansh", "native": "Rumantsch",
     "og_title": "L'avertura da Sedaha (Sounds), per rumantsch",
     "og_desc": "Il fil da pleds che ina giada eran tuns.",
     "cta": "Il cudesch cumenza qua. L'ediziun rumantscha cumpletta è en via; fin lura po l'entir cudesch vegnir legì gratuitamain: per persian, englais e danais."},
    {"code": "SC", "slug": "sc", "lang": "sc", "rtl": False, "locale": "sc_IT", "en": "Sardinian", "native": "Sardu",
     "og_title": "S'abertura de Sedaha (Sounds), in sardu",
     "og_desc": "Su filu de fueddos chi, unu tempus, fiant boghes.",
     "cta": "Su libru cumintzat inoghe. S'editzione sarda cumpleta est in caminu; finas a tando totu su libru si podet lègere de badas: in persianu, in inglesu e in danesu."},
    {"code": "BE", "slug": "be", "lang": "be", "rtl": False, "locale": "be_BY", "en": "Belarusian", "native": "Беларуская",
     "og_title": "Уступ да Sedaha (Sounds), па-беларуску",
     "og_desc": "Нітка слоў, якія некалі былі гукамі.",
     "cta": "Кніга пачынаецца тут. Поўнае беларускае выданне ўжо ў дарозе; а пакуль усю кнігу можна чытаць бясплатна: па-персідску, па-англійску і па-дацку."},
    {"code": "BS", "slug": "bs", "lang": "bs", "rtl": False, "locale": "bs_BA", "en": "Bosnian", "native": "Bosanski",
     "og_title": "Otvaranje knjige Sedaha (Sounds), na bosanskom",
     "og_desc": "Nit riječi koje su nekoć bile zvukovi.",
     "cta": "Knjiga počinje ovdje. Potpuno bosansko izdanje je na putu; do tada se cijela knjiga može čitati besplatno: na perzijskom, engleskom i danskom."},
    {"code": "MK", "slug": "mk", "lang": "mk", "rtl": False, "locale": "mk_MK", "en": "Macedonian", "native": "Македонски",
     "og_title": "Отворањето на Sedaha (Sounds), на македонски",
     "og_desc": "Нишка од зборови кои некогаш биле звуци.",
     "cta": "Книгата почнува тука. Целосното македонско издание е на пат; дотогаш целата книга може да се чита бесплатно: на персиски, англиски и дански."},
    {"code": "ME", "slug": "me", "lang": "cnr", "rtl": False, "locale": "cnr_ME", "en": "Montenegrin", "native": "Crnogorski",
     "og_title": "Otvaranje knjige Sedaha (Sounds), na crnogorskom",
     "og_desc": "Nit riječi koje su nekada bile zvuci.",
     "cta": "Knjiga počinje ovdje. Potpuno crnogorsko izdanje je na putu; do tada se cijela knjiga može čitati besplatno: na persijskom, engleskom i danskom."},
    {"code": "YI", "slug": "yi", "lang": "yi", "rtl": True, "locale": "yi_US", "en": "Yiddish", "native": "ייִדיש",
     "og_title": "דער אָנהייב פֿון Sedaha (Sounds), אויף ייִדיש",
     "og_desc": "דער פֿאָדעם פֿון ווערטער, וואָס זײַנען אַ מאָל געווען קלאַנגען.",
     "cta": "דאָס בוך הייבט זיך אָן דאָ. די פֿולע ייִדישע אויסגאַבע איז אונטערוועגנס; ביז דעמאָלט קען מען דאָס גאַנצע בוך לייענען אומזיסט: אויף פּערסיש, ענגליש און דעניש."},
    {"code": "EO", "slug": "eo", "lang": "eo", "rtl": False, "locale": "eo_EO", "en": "Esperanto", "native": "Esperanto",
     "og_title": "La malfermo de Sedaha (Sounds), en Esperanto",
     "og_desc": "La fadeno el vortoj, kiuj iam estis sonoj.",
     "cta": "La libro komenciĝas ĉi tie. La kompleta Esperanta eldono estas survoje; ĝis tiam la tuta libro legeblas senpage: en la persa, la angla kaj la dana."},
    {"code": "FO", "slug": "fo", "lang": "fo", "rtl": False, "locale": "fo_FO", "en": "Faroese", "native": "Føroyskt",
     "og_title": "Byrjanin á Sedaha (Sounds), á føroyskum",
     "og_desc": "Tráðurin av orðum, ið eina ferð vóru ljóð.",
     "cta": "Bókin byrjar her. Fullfíggjaða føroyska útgávan er á veg; til tá kann øll bókin lesast ókeypis: á persiskum, enskum og donskum."},
    {"code": "KL", "slug": "kl", "lang": "kl", "rtl": False, "locale": "kl_GL", "en": "Greenlandic", "native": "Kalaallisut",
     "og_title": "Sedaha (Sounds) aallarniutaa, kalaallisut",
     "og_desc": "Ujaloq oqaatsinik, ilaanni nipiusunik.",
     "cta": "Atuagaq maannga aallartippoq. Kalaallisut naammassisaq aggersoq; taamanikkut atuagaq tamaat akeqanngitsumik atuarneqarsinnaavoq: persiskisut, tuluttut qallunaatullu."},
    {"code": "SE", "slug": "se", "lang": "se", "rtl": False, "locale": "se_NO", "en": "Northern Sami", "native": "Davvisámegiella",
     "og_title": "Sedaha (Sounds) álgu, davvisámegillii",
     "og_desc": "Láŋga sániin, mat leat leamaš jienasat.",
     "cta": "Girji álgá dás. Ollislaš davvisámegiel almmuheapmi lea boahtimin; dassážii sáhttá olles girjji lohkat nuvttá: persagillii, eaŋgalsgillii ja dánskkagillii."},
    {"code": "AF", "slug": "af", "lang": "af", "rtl": False, "locale": "af_ZA", "en": "Afrikaans", "native": "Afrikaans",
     "og_title": "Die opening van Sedaha (Sounds), in Afrikaans",
     "og_desc": "Die draad van woorde wat eens klanke was.",
     "cta": "Die boek begin hier. Die volledige Afrikaanse uitgawe is op pad; tot dan kan die hele boek gratis gelees word: in Persies, Engels en Deens."},
    {"code": "AM", "slug": "am", "lang": "am", "rtl": False, "locale": "am_ET", "en": "Amharic", "native": "አማርኛ",
     "og_title": "የSedaha (Sounds) መክፈቻ፣ በአማርኛ",
     "og_desc": "ድሮ ድምፆች ሆነው የነበሩ የቃላት ሱፍ።",
     "cta": "መጽሐፉ እዚህ ይጀምራል። ሙሉው የአማርኛ እትም በመንገድ ላይ ነው፤ እስከዚያው ድረስ መጽሐፉን ሙሉ በሙሉ በነፃ ማንበብ ይቻላል፦ በፋርስኛ፣ በእንግሊዝኛ እና በዴንማርክኛ።"},
    {"code": "HA", "slug": "ha", "lang": "ha", "rtl": False, "locale": "ha_NG", "en": "Hausa", "native": "Hausa",
     "og_title": "Buɗewar Sedaha (Sounds), a Hausa",
     "og_desc": "Zaren kalmomin da a wani lokaci suka kasance sautuka.",
     "cta": "Littafin yana farawa a nan. Cikakken bugun Hausa yana kan hanya; har zuwa lokacin, ana iya karanta dukan littafin kyauta: da Farisanci, Turanci da Danish."},
    {"code": "HT", "slug": "ht", "lang": "ht", "rtl": False, "locale": "ht_HT", "en": "Haitian Creole", "native": "Kreyòl ayisyen",
     "og_title": "Ouvèti Sedaha (Sounds), an kreyòl ayisyen",
     "og_desc": "Fil mo yo ki te son yon lè.",
     "cta": "Liv la kòmanse isit la. Edisyon konplè an kreyòl ayisyen an sou wout; jiska lè sa a, ou ka li tout liv la gratis: an pèsan, an angle ak an danwa."},
    {"code": "IG", "slug": "ig", "lang": "ig", "rtl": False, "locale": "ig_NG", "en": "Igbo", "native": "Igbo",
     "og_title": "Mmalite Sedaha (Sounds), n'asụsụ Igbo",
     "og_desc": "Eriri okwu ndị bụbu ụda mgbe ochie.",
     "cta": "Akwụkwọ a na-amalite ebe a. Mbipụta Igbo zuru ezu nọ n'ụzọ; ruo mgbe ahụ, a pụrụ ịgụ akwụkwọ a dum n'efu: n'asụsụ Peshia, Bekee na Danish."},
    {"code": "OM", "slug": "om", "lang": "om", "rtl": False, "locale": "om_ET", "en": "Oromo", "native": "Afaan Oromoo",
     "og_title": "Seensa Sedaha (Sounds), Afaan Oromootiin",
     "og_desc": "Kirrii jechootaa kan yeroo tokko sagalee ture.",
     "cta": "Kitaabichi asumaa jalqaba. Maxxansi Afaan Oromoo guutuun karaa irra jira; hamma sana, kitaabicha guutuu bilisaan dubbisuun ni danda'ama: Afaan Faarsii, Ingiliffaa fi Deenmaarkiin."},
    {"code": "SO", "slug": "so", "lang": "so", "rtl": False, "locale": "so_SO", "en": "Somali", "native": "Soomaali",
     "og_title": "Furaha Sedaha (Sounds), af-Soomaali",
     "og_desc": "Dun erayo ah, oo mar codad ahaa.",
     "cta": "Buuggu halkan ayuu ka bilaabmayaa. Daabacaadda Soomaaliga oo dhammaystiran ayaa soo socota; ilaa markaas, buugga oo dhan si bilaash ah ayaa loo akhrisan karaa: af-Faaris, af-Ingiriisi iyo af-Deenish."},
    {"code": "YO", "slug": "yo", "lang": "yo", "rtl": False, "locale": "yo_NG", "en": "Yoruba", "native": "Yorùbá",
     "og_title": "Ìṣífípé Sedaha (Sounds), ní èdè Yorùbá",
     "og_desc": "Okùn àwọn ọ̀rọ̀ tí wọ́n jẹ́ ohùn nígbà kan rí.",
     "cta": "Ìwé náà bẹ̀rẹ̀ níbí. Ẹ̀dà Yorùbá tó kún ń bọ̀ lọ́nà; títí di ìgbà náà, a lè ka gbogbo ìwé náà lọ́fẹ̀ẹ́: ní èdè Páṣíà, Gẹ̀ẹ́sì àti Danish."},
    {"code": "ZU", "slug": "zu", "lang": "zu", "rtl": False, "locale": "zu_ZA", "en": "Zulu", "native": "isiZulu",
     "og_title": "Ukuvula kwe-Sedaha (Sounds), ngesiZulu",
     "og_desc": "Umucu wamazwi ake aba ngamaphimbo.",
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


def render(L: dict) -> str:
    h1, paras = _opening(L["code"])
    dir_attr = ' dir="rtl"' if L["rtl"] else ""
    url = f"https://arasteh.art/sedaha/read/{L['slug']}/"
    meta_desc = (f"Read the opening of Sedaha (Sounds), Book One by Amir Arasteh, "
                 f"in {L['en']}, then continue with the full book, free.")
    body = "\n".join(f"    <p>{html.escape(p, quote=False)}</p>" for p in paras)
    return f"""<!DOCTYPE html>
<!-- GENERATED by build_read_pages.py from the book repo's {L['code']} edition. Do not edit by hand:
     edit the generator (or the edition source) and re-run  python build_read_pages.py -->
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(h1, quote=False)} &middot; Sedaha (Sounds), Book One &middot; Amir Arasteh</title>
<meta name="description" content="{_esc(meta_desc)}">
<meta name="theme-color" content="#F5EFE3">
<meta property="og:type" content="book">
<meta property="og:title" content="{_esc(L['og_title'])}">
<meta property="og:description" content="{_esc(L['og_desc'])}">
<meta property="og:image" content="https://arasteh.art/assets/img/paintings/sounds/01.jpg">
<meta property="og:image:alt" content="The painting that opens Sedaha (Sounds), Book One, by Amir Arasteh.">
<meta property="og:url" content="{url}">
<meta property="og:locale" content="{L['locale']}">
<meta name="twitter:card" content="summary_large_image">
<link rel="stylesheet" href="/assets/css/style.css">
<link rel="icon" href="/favicon.ico" sizes="any">
<link rel="icon" type="image/png" sizes="32x32" href="/assets/img/favicon-32.png">
<link rel="icon" type="image/png" sizes="16x16" href="/assets/img/favicon-16.png">
<link rel="apple-touch-icon" href="/assets/img/apple-touch-icon-180.png">
</head>
<body class="book">
<a class="skip-link" href="#main">Skip to content</a>
<div class="container" id="main">
  <a class="back" href="/sedaha/">&larr; Sounds</a>

  <p class="read-kicker">Sounds &middot; Book One</p>
  <p class="op-langs">Opening in: <a href="/sedaha/read/">English</a> &middot;
    <a href="/sedaha/read/fa/" lang="fa">فارسی</a> &middot;
    <a href="/sedaha/read/da/" lang="da">Dansk</a> &middot;
    <span class="cur" lang="{L['lang']}">{L['native']}</span> &middot;
    <a href="/sedaha/">+ more</a></p>
  <article class="reader" lang="{L['lang']}"{dir_attr}>
    <h1>{html.escape(h1, quote=False)}</h1>
{body}
  </article>

  <div class="read-cta">
    <p lang="{L['lang']}"{dir_attr}>{html.escape(L['cta'], quote=False)}</p>
    <div class="btns">
      <button type="button" class="btn btn-share" data-share-url="{url}" data-share-title="Sedaha &mdash; Book One" data-share-text="{_esc(L['og_desc'])}">Share this opening</button>
    </div>
    <a class="read-back" href="/sedaha/">All languages &amp; downloads &rarr;</a>
  </div>
</div>

<footer class="site-footer">
  <div class="container">
    <a class="foot-logo" href="/" aria-label="Arasteh, home">
      <picture>
        <source srcset="/assets/img/logo-lockup-web.webp" type="image/webp">
        <img src="/assets/img/logo-lockup.png" width="380" height="676" alt="">
      </picture>
    </a>
    &copy; 2026 Amir Arasteh &middot;
    <a href="/sedaha/">Books</a> &middot;
    <a href="/paintings/">Paintings</a> &middot;
    <a href="/comments/">Comments</a> &middot;
    <a href="/support/">Support</a> &middot;
    <a href="/license.html">License</a> &middot;
    <a href="https://t.me/Sounds_AmirArasteh">Telegram</a>
  </div>
</footer>
<script src="/assets/js/share.js" defer></script>
</body>
</html>
"""


def patch_index(check: bool) -> bool:
    """Add an 'Opening' link to each generated language's row on /sedaha/ (idempotent)."""
    body = SOUNDS.read_text(encoding="utf-8")
    orig = body
    for L in LANGS:
        href = f"/sedaha/read/{L['slug']}/"
        if href in body:
            continue
        mini = f'<span class="mini"><a href="{href}">Opening</a></span> '
        # row is identified by its English name span; link goes before the status span
        pat = (rf'(<span class="en">{re.escape(L["en"])}</span></span>) '
               rf'(<span class="(?:soon|mini)">)')
        new_body, n = re.subn(pat, rf"\1 {mini}\2", body, count=1)
        if n == 0:
            print(f"[warn]  /sedaha/ row not found for {L['en']} - no Opening link added")
            continue
        body = new_body
    if body == orig:
        print("[ok]    /sedaha/ rows: all Opening links present")
        return True
    if check:
        print("[drift] /sedaha/ rows: Opening links missing")
        return False
    SOUNDS.write_text(body, encoding="utf-8", newline="\n")
    print("[write] /sedaha/ rows: Opening links added")
    return True


def patch_sitemap(check: bool) -> bool:
    body = SITEMAP.read_text(encoding="utf-8")
    today = datetime.date.today().isoformat()
    missing = [L for L in LANGS if f"/sedaha/read/{L['slug']}/</loc>" not in body]
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

    ok = True
    for L in LANGS:
        dest = READ_DIR / L["slug"] / "index.html"
        page = render(L)
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

    ok &= patch_index(args.check)
    ok &= patch_sitemap(args.check)
    if not args.check:
        print(f"done: {len(LANGS)} languages")
    return 1 if (args.check and not ok) else 0


if __name__ == "__main__":
    sys.exit(main())
