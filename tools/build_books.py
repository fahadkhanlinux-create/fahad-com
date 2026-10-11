#!/usr/bin/env python3
"""Download public-domain books from Project Gutenberg and build PDFs + books.json."""
import html
import json
import os
import re
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TXT_DIR = os.path.join(BASE, "tools", "txt")
PDF_DIR = os.path.join(BASE, "pdfs")
DATA = os.path.join(BASE, "data", "books.json")

BOOKS = [
    dict(id="pride-and-prejudice", gid=1342, title="Pride and Prejudice", author="Jane Austen", year="1813", category="Fiction",
         desc="Elizabeth Bennet's wit clashes with the proud Mr. Darcy in Austen's beloved comedy of manners, love and social class."),
    dict(id="jane-eyre", gid=1260, title="Jane Eyre", author="Charlotte Brontë", year="1847", category="Fiction",
         desc="An orphaned governess fights for love, dignity and independence in Brontë's towering gothic romance."),
    dict(id="moby-dick", gid=2701, title="Moby-Dick", author="Herman Melville", year="1851", category="Fiction",
         desc="Captain Ahab's obsessive hunt for the white whale becomes an epic meditation on fate, nature and madness."),
    dict(id="sherlock-holmes", gid=1661, title="The Adventures of Sherlock Holmes", author="Arthur Conan Doyle", year="1892", category="Fiction",
         desc="Twelve brilliant cases featuring the world's most famous detective and his loyal friend Dr. Watson."),
    dict(id="frankenstein", gid=84, title="Frankenstein", author="Mary Shelley", year="1818", category="Fiction",
         desc="The original science-fiction nightmare: a scientist's creation turns on its maker in Shelley's dark classic."),
    dict(id="jekyll-and-hyde", gid=43, title="Dr Jekyll and Mr Hyde", author="Robert Louis Stevenson", year="1886", category="Fiction",
         desc="A London lawyer uncovers the horrifying double life of his friend in this chilling tale of good and evil within one man."),
    dict(id="romeo-and-juliet", gid=1112, title="Romeo and Juliet", author="William Shakespeare", year="1597", category="Fiction",
         desc="Shakespeare's immortal tragedy of two young lovers caught between feuding families in Verona."),

    dict(id="alice-in-wonderland", gid=11, title="Alice's Adventures in Wonderland", author="Lewis Carroll", year="1865", category="Children",
         desc="Alice falls down the rabbit hole into a wonderland of mad hatters, cheshire cats and nonsense logic."),
    dict(id="grimms-fairy-tales", gid=2591, title="Grimm's Fairy Tales", author="Jacob & Wilhelm Grimm", year="1812", category="Children",
         desc="The complete collection of timeless folk tales: Cinderella, Hansel and Gretel, Rapunzel, Snow White and many more."),
    dict(id="peter-pan", gid=16, title="Peter Pan", author="J. M. Barrie", year="1911", category="Children",
         desc="The boy who never grew up flies the Darling children away to Neverland, mermaids, pirates and Captain Hook."),

    dict(id="origin-of-species", gid=1228, title="On the Origin of Species", author="Charles Darwin", year="1859", category="Science",
         desc="Darwin's revolutionary work presenting evolution by natural selection — the book that changed biology forever."),
    dict(id="einstein-relativity", gid=11335, title="The Einstein Theory of Relativity", author="H. A. Lorentz", year="1920", category="Science",
         desc="A clear, concise popular statement of Einstein's special and general relativity from a Nobel laureate physicist."),

    dict(id="autobiography-of-franklin", gid=148, title="The Autobiography of Benjamin Franklin", author="Benjamin Franklin", year="1791", category="History",
         desc="The life story of America's greatest polymath — printer, scientist, diplomat and Founding Father — in his own words."),
    dict(id="the-prince", gid=1232, title="The Prince", author="Niccolò Machiavelli", year="1532", category="Strategy",
         desc="The founding text of modern political science: a blunt manual of power, statecraft and realpolitik."),
    dict(id="the-art-of-money-getting", gid=8581, title="The Art of Money Getting", author="P. T. Barnum", year="1880", category="Business",
         desc="Golden rules for making money from the original showman — practical Victorian wisdom on work, economy and integrity."),

    dict(id="holy-quran", gid=3434, title="The Holy Quran (English Translation)", author="J. M. Rodwell", year="1861", category="Islam & Religion",
         desc="A classic public-domain English translation of the Quran, arranged in chronological order of revelation."),
    dict(id="holy-bible", gid=30, title="The Holy Bible (King James Version)", author="King James translators", year="1611", category="Islam & Religion",
         desc="The complete King James Version of the Old and New Testaments — a monument of English literature and faith."),

    dict(id="meditations", gid=2680, title="Meditations", author="Marcus Aurelius", year="180", category="Philosophy",
         desc="The private journal of a Roman emperor: timeless Stoic lessons on discipline, mortality and inner peace."),
    dict(id="the-republic", gid=1497, title="The Republic", author="Plato", year="380 BC", category="Philosophy",
         desc="Plato's masterwork of justice, ideal government and the famous allegory of the cave."),
    dict(id="thus-spoke-zarathustra", gid=1998, title="Thus Spoke Zarathustra", author="Friedrich Nietzsche", year="1883", category="Philosophy",
         desc="Nietzsche's poetic philosophical novel on the Übermensch, eternal recurrence and the death of God."),

    dict(id="as-a-man-thinketh", gid=4507, title="As a Man Thinketh", author="James Allen", year="1903", category="Self-Help",
         desc="A powerful classic on how thoughts shape character, circumstances and destiny — short, sharp and life-changing."),
    dict(id="science-of-getting-rich", gid=59844, title="The Science of Getting Rich", author="W. D. Wattles", year="1910", category="Self-Help",
         desc="The 1910 prosperity classic that inspired The Secret: practical principles for building wealth through thought and action."),
    dict(id="art-of-war", gid=132, title="The Art of War", author="Sun Tzu", year="5th c. BC", category="Strategy",
         desc="The ancient Chinese classic of strategy, leadership and conflict — required reading for business and life."),
    dict(id="self-help", gid=935, title="Self-Help", author="Samuel Smiles", year="1859", category="Self-Help",
         desc="The Victorian original: Smiles's bestselling celebration of industry, perseverance and self-reliance."),
    dict(id="character", gid=2541, title="Character", author="Samuel Smiles", year="1871", category="Self-Help",
         desc="Smiles on how moral fiber, discipline and duty shape a meaningful life — a Victorian self-improvement classic."),
    dict(id="thrift", gid=14418, title="Thrift", author="Samuel Smiles", year="1875", category="Self-Help",
         desc="A practical Victorian guide to saving, frugality and financial independence through steady habits."),
    dict(id="how-to-live-on-24-hours-a-day", gid=2274, title="How to Live on 24 Hours a Day", author="Arnold Bennett", year="1910", category="Self-Help",
         desc="Arnold Bennett's timeless time-management classic: stop drifting through your days and live with purpose."),
    dict(id="a-message-to-garcia", gid=17195, title="A Message to Garcia", author="Elbert Hubbard", year="1899", category="Self-Help",
         desc="The famous essay on initiative, loyalty and doing the job without being told twice — a workplace parable."),

    dict(id="interpretation-of-dreams", gid=66048, title="The Interpretation of Dreams", author="Sigmund Freud", year="1900", category="Psychology",
         desc="Freud's landmark work: dreams as wish-fulfillment and the 'royal road' to the unconscious mind."),
    dict(id="psychopathology-of-everyday-life", gid=67332, title="Psychopathology of Everyday Life", author="Sigmund Freud", year="1901", category="Psychology",
         desc="Why slips of the tongue and forgotten names mean more than you think — Freud's accessible classic."),
    dict(id="group-psychology", gid=35877, title="Group Psychology and The Analysis of The Ego", author="Sigmund Freud", year="1921", category="Psychology",
         desc="How the individual mind changes inside a crowd: Freud on groups, leaders and mass behaviour."),
    dict(id="civilization-and-its-discontents", gid=78221, title="Civilization and Its Discontents", author="Sigmund Freud", year="1930", category="Psychology",
         desc="Freud's sweeping essay on why civilization demands sacrifice — and why we remain fundamentally unhappy."),
    dict(id="the-crowd", gid=445, title="The Crowd: A Study of the Popular Mind", author="Gustave Le Bon", year="1895", category="Psychology",
         desc="The founding text of crowd psychology: why individuals act differently inside a mob."),

    dict(id="wealth-of-nations", gid=3300, title="An Inquiry into the Nature and Causes of the Wealth of Nations", author="Adam Smith", year="1776", category="Business",
         desc="Adam Smith's foundational treatise on markets, division of labour and capitalism — the blueprint of modern economics."),

    dict(id="leaves-of-grass", gid=1322, title="Leaves of Grass", author="Walt Whitman", year="1855", category="Poetry",
         desc="Whitman's revolutionary free-verse masterpiece celebrating the self, democracy and the American spirit."),
    dict(id="song-of-hiawatha", gid=19, title="The Song of Hiawatha", author="Henry Wadsworth Longfellow", year="1855", category="Poetry",
         desc="Longfellow's epic narrative poem of the Great Lakes — the legend of the noble Hiawatha, in flowing trochaic verse."),

    dict(id="crime-and-punishment", gid=2554, title="Crime and Punishment", author="Fyodor Dostoyevsky", year="1866", category="Fiction",
         desc="Raskolnikov's theory of the superior man collapses under guilt — Dostoyevsky's masterpiece of crime and redemption."),
    dict(id="sense-and-sensibility", gid=21839, title="Sense and Sensibility", author="Jane Austen", year="1811", category="Fiction",
         desc="Two Dashwood sisters learn that heart and head both have their seasons as they search for love without rank."),
    dict(id="middlemarch", gid=145, title="Middlemarch", author="George Eliot", year="1871", category="Fiction",
         desc="George Eliot's sweeping study of provincial life, ambition and marriage — the great English novel of ideas."),
    dict(id="oliver-twist", gid=730, title="Oliver Twist", author="Charles Dickens", year="1838", category="Fiction",
         desc="An orphan boy survives the workhouse and Fagin's gang — Dickens at his dark, humane best."),
    dict(id="great-expectations", gid=1400, title="Great Expectations", author="Charles Dickens", year="1861", category="Fiction",
         desc="Pip's rise from the forge to London's fog — Dickens's finest coming-of-age story."),
    dict(id="a-tale-of-two-cities", gid=98, title="A Tale of Two Cities", author="Charles Dickens", year="1859", category="Fiction",
         desc="It was the best of times... Dickens's drama of sacrifice set in the French Revolution."),
    dict(id="count-of-monte-cristo", gid=1184, title="The Count of Monte Cristo", author="Alexandre Dumas", year="1844", category="Fiction",
         desc="Betrayed and imprisoned, Edmond Dantès returns as a fabulously wealthy count hungry for revenge."),
    dict(id="dracula", gid=345, title="Dracula", author="Bram Stoker", year="1897", category="Fiction",
         desc="The novel that invented the vampire — Stoker's Gothic masterpiece of letters, diaries and dread."),
    dict(id="hound-of-the-baskervilles", gid=2852, title="The Hound of the Baskervilles", author="Arthur Conan Doyle", year="1902", category="Fiction",
         desc="Sherlock Holmes's most atmospheric case: the spectral hound stalking the Baskerville heirs."),
    dict(id="around-the-world-in-eighty-days", gid=103, title="Around the World in Eighty Days", author="Jules Verne", year="1872", category="Fiction",
         desc="Phileas Fogg's wager-driven race around the globe with Passepartout in hot pursuit."),
    dict(id="war-and-peace", gid=2600, title="War and Peace", author="Leo Tolstoy", year="1869", category="Fiction",
         desc="Tolstoy's colossal epic of Napoleon's invasion of Russia — war, family and the meaning of history."),
    dict(id="anna-karenina", gid=1399, title="Anna Karenina", author="Leo Tolstoy", year="1877", category="Fiction",
         desc="Anna's forbidden passion and Levin's search for meaning — Tolstoy on happiness and how to be good."),
    dict(id="wuthering-heights", gid=768, title="Wuthering Heights", author="Emily Brontë", year="1847", category="Fiction",
         desc="Heathcliff and Catherine's destructive, spectral love on the Yorkshire moors."),
    dict(id="picture-of-dorian-gray", gid=174, title="The Picture of Dorian Gray", author="Oscar Wilde", year="1890", category="Fiction",
         desc="Youth without aging, sin within the canvas — Wilde's parable of beauty and corruption."),
    dict(id="scarlet-letter", gid=25344, title="The Scarlet Letter", author="Nathaniel Hawthorne", year="1850", category="Fiction",
         desc="Hester Prynne's solitary stand for dignity in Puritan Boston — America's great moral novel."),
    dict(id="tom-sawyer", gid=74, title="The Adventures of Tom Sawyer", author="Mark Twain", year="1876", category="Fiction",
         desc="Whitewashing fences, treasure hunts and boyhood mischief on the Mississippi."),
    dict(id="huckleberry-finn", gid=76, title="Adventures of Huckleberry Finn", author="Mark Twain", year="1884", category="Fiction",
         desc="Huck and Jim raft the river down — Twain's masterpiece and a founding American epic."),
    dict(id="call-of-the-wild", gid=215, title="The Call of the Wild", author="Jack London", year="1903", category="Fiction",
         desc="Buck the sled dog answers the call back to the wolf in London's primeval adventure."),
    dict(id="time-machine", gid=35, title="The Time Machine", author="H. G. Wells", year="1895", category="Fiction",
         desc="A Victorian scientist rides a machine into 802,701 AD and finds the future split in two."),
    dict(id="war-of-the-worlds", gid=36, title="The War of the Worlds", author="H. G. Wells", year="1898", category="Fiction",
         desc="Martian tripods devastate Victorian England — Wells's terrifying classic of invaders."),
    dict(id="gullivers-travels", gid=829, title="Gulliver's Travels", author="Jonathan Swift", year="1726", category="Fiction",
         desc="Gulliver sails to Lilliput, Brobdingnag, Laputa and the Houyhnhnms — Swift's savage satire of mankind."),
    dict(id="don-quixote", gid=996, title="Don Quixote", author="Miguel de Cervantes", year="1605", category="Fiction",
         desc="The mad knight who charges windmills alongside the practical Sancho — the first great novel."),
    dict(id="emma", gid=158, title="Emma", author="Jane Austen", year="1815", category="Fiction",
         desc="Austen's clever, entitled Emma Woodhouse dabbles in matchmaking — with comic, humbling results."),
    dict(id="three-musketeers", gid=1257, title="The Three Musketeers", author="Alexandre Dumas", year="1844", category="Fiction",
         desc="D'Artagnan and the gascons of the king: swords, court intrigue and four-who-are-one adventure."),
    dict(id="notre-dame-de-paris", gid=2610, title="Notre-Dame de Paris", author="Victor Hugo", year="1831", category="Fiction",
         desc="Quasimodo, Frollo and the bells of Notre-Dame — Hugo's towering Romantic tragedy (English title: The Hunchback of Notre-Dame)."),
    dict(id="heart-of-darkness", gid=219, title="Heart of Darkness", author="Joseph Conrad", year="1899", category="Fiction",
         desc="Marlowe hunts Mr. Kurtz up the Congo — Conrad's haunting parable about light and darkness."),
    dict(id="treasure-island", gid=120, title="Treasure Island", author="Robert Louis Stevenson", year="1883", category="Fiction",
         desc="Long John Silver, a treasure map and a boy named Jim — where pirate adventure was born."),
    dict(id="connecticut-yankee", gid=86, title="A Connecticut Yankee in King Arthur's Court", author="Mark Twain", year="1889", category="Fiction",
         desc="A modern Yankee builds machines and undermines Camelot — Twain's most philosophical satire."),
    dict(id="20000-leagues-under-the-sea", gid=164, title="Twenty Thousand Leagues under the Sea", author="Jules Verne", year="1870", category="Fiction",
         desc="Captain Nemo's submerged odyssey aboard the Nautilus, predating modern submarines."),
    dict(id="murder-of-roger-ackroyd", gid=69087, title="The Murder of Roger Ackroyd", author="Agatha Christie", year="1926", category="Fiction",
         desc="Christie's most famous mystery, with the most famous twist in detective fiction."),
    dict(id="a-study-in-scarlet", gid=244, title="A Study in Scarlet", author="Arthur Conan Doyle", year="1887", category="Fiction",
         desc="Holmes and Watson's first case: a murder that crosses London and the American desert."),
    dict(id="mystery-of-edwin-drood", gid=564, title="The Mystery of Edwin Drood", author="Charles Dickens", year="1870", category="Fiction",
         desc="Dickens's unfinished mystery — the disappearance of Edwin Drood, left forever unsolved."),
    dict(id="man-who-was-thursday", gid=1695, title="The Man Who Was Thursday", author="G. K. Chesterton", year="1908", category="Fiction",
         desc="A secret agent infiltrates a council of anarchists — Chesterton's surreal comedy of a thriller."),
    dict(id="a-room-with-a-view", gid=2641, title="A Room with a View", author="E. M. Forster", year="1908", category="Fiction",
         desc="Lucy Honeychurch faces the choice between safe Cecil and passionate George on holiday in Florence."),
    dict(id="mysteries-of-udolpho", gid=3268, title="The Mysteries of Udolpho", author="Ann Radcliffe", year="1794", category="Fiction",
         desc="Emily trapped in the vast, fog-haunted Udolpho castle — the definitive Gothic novel."),
    dict(id="farewell-to-arms", gid=75201, title="A Farewell to Arms", author="Ernest Hemingway", year="1929", category="Fiction",
         desc="An ambulance driver and a nurse flee the Italian front — Hemingway's stark love story."),
    dict(id="king-in-yellow", gid=8492, title="The King in Yellow", author="Robert W. Chambers", year="1895", category="Fiction",
         desc="A forbidden playbook whose readers descend into madness — the horror classic that inspired True Detective."),
    dict(id="carmen", gid=2465, title="Carmen", author="Prosper Mérimée", year="1845", category="Fiction",
         desc="The novella behind Bizet's opera: a soldier ruins himself for the free-spirited Carmen."),
    dict(id="david-copperfield", gid=766, title="David Copperfield", author="Charles Dickens", year="1850", category="Fiction",
         desc="David's journey from bleak childhood to writer — Dickens's most autobiographical novel."),
    dict(id="invisible-man", gid=5230, title="The Invisible Man", author="H. G. Wells", year="1897", category="Fiction",
         desc="A scientist rendered invisible turns on the village — Wells's chilling morality tale."),
    dict(id="turn-of-the-screw", gid=209, title="The Turn of the Screw", author="Henry James", year="1898", category="Fiction",
         desc="A governess suspects ghosts at Bly Manor — James's most unsettling ambiguity."),
    dict(id="arsene-lupin", gid=6133, title="The Extraordinary Adventures of Arsène Lupin", author="Maurice Leblanc", year="1907", category="Fiction",
         desc="The gentleman-burglar outwits Paris police — France's answer to Sherlock Holmes."),
    dict(id="hamlet", gid=1787, title="Hamlet", author="William Shakespeare", year="1602", category="Fiction",
         desc="Whether 'tis nobler... Shakespeare's prince of contemplation confronts a murderous court."),
    dict(id="innocents-abroad", gid=3176, title="The Innocents Abroad", author="Mark Twain", year="1869", category="Fiction",
         desc="Twain satirises American travellers in Europe and the Near East — the book that made him famous."),

    dict(id="secret-garden", gid=113, title="The Secret Garden", author="Frances Hodgson Burnett", year="1911", category="Children",
         desc="Mary discovers a walled garden and, within it, friendship, health and a hidden mystery."),
    dict(id="black-beauty", gid=271, title="Black Beauty", author="Anna Sewell", year="1877", category="Children",
         desc="The life of a horse, told by the horse — the humane classic read by every generation."),
    dict(id="wind-in-the-willows", gid=289, title="The Wind in the Willows", author="Kenneth Grahame", year="1908", category="Children",
         desc="Mole, Ratty, Toad and Badger on the riverbank — the coziest of all children's classics."),
    dict(id="wizard-of-oz", gid=55, title="The Wonderful Wizard of Oz", author="L. Frank Baum", year="1900", category="Children",
         desc="Dorothy follows the yellow brick road to the Emerald City — America's great fairy tale."),
    dict(id="little-women", gid=37106, title="Little Women", author="Louisa May Alcott", year="1868", category="Children",
         desc="The four March sisters grow up through joy and sorrow — Alcott's beloved family classic."),
    dict(id="book-of-dragons", gid=23661, title="The Book of Dragons", author="E. Nesbit", year="1912", category="Children",
         desc="Edith Nesbit's whimsical tales of domesticated dragons at large in Edwardian England."),
    dict(id="anne-of-green-gables", gid=45, title="Anne of Green Gables", author="L. M. Montgomery", year="1908", category="Children",
         desc="Red-haired orphan Anne arrives at Green Gables and makes a home out of an island and a village."),
    dict(id="aesops-fables", gid=11339, title="Aesop's Fables", author="Aesop", year="6th c. BC", category="Children",
         desc="The tortoise and the hare, the boy who cried wolf — timeless fables of wit and wisdom."),

    dict(id="rubaiyat", gid=246, title="The Rubáiyát of Omar Khayyam", author="Omar Khayyam", year="1100", category="Poetry",
         desc="Fitzgerald's immortal translation: wine, stars, and life's brief hour in Persian quatrains."),
    dict(id="paradise-lost", gid=26, title="Paradise Lost", author="John Milton", year="1667", category="Poetry",
         desc="Milton's epic of the Fall, the war in Heaven and Man's disobedience — in blank verse of titanic scale."),
    dict(id="odyssey", gid=1727, title="The Odyssey", author="Homer", year="8th c. BC", category="Poetry",
         desc="Odysseus fights monsters and storms for one more night on Ithaca — the original long journey home."),
    dict(id="iliad", gid=6130, title="The Iliad", author="Homer", year="8th c. BC", category="Poetry",
         desc="Achilles' rage at Troy, the world's oldest war epic, in flowing English verse."),
    dict(id="lady-of-the-lake", gid=3011, title="The Lady of the Lake", author="Walter Scott", year="1810", category="Poetry",
         desc="Scott's romantic narrative of clans, kings and exile in the Scottish Highlands."),

    dict(id="beyond-good-and-evil", gid=4363, title="Beyond Good and Evil", author="Friedrich Nietzsche", year="1886", category="Philosophy",
         desc="Nietzsche's assault on traditional morality — the manifesto for free spirits and the coming philosophy."),
    dict(id="problems-of-philosophy", gid=5827, title="The Problems of Philosophy", author="Bertrand Russell", year="1912", category="Philosophy",
         desc="Russell's clear, concise introduction to epistemology, logic and the big questions of philosophy."),
    dict(id="pascais-pensees", gid=18269, title="Pascal's Pensées", author="Blaise Pascal", year="1670", category="Philosophy",
         desc="Fragments of a wager between reason and faith — Pascal's lightning-bolt sketches of the human condition."),
    dict(id="seneca-on-benefits", gid=3794, title="L. Annaeus Seneca on Benefits", author="Seneca the Younger", year="55", category="Philosophy",
         desc="Stoic counsel on gratitude, obligation, and what we owe one another in private life and civic duty."),
    dict(id="confessions", gid=3296, title="The Confessions of St. Augustine", author="Augustine of Hippo", year="400", category="Philosophy",
         desc="The original memoir: Augustine's restless road to faith, two desires at war, and the longing for rest."),
    dict(id="treatise-of-human-nature", gid=4705, title="A Treatise of Human Nature", author="David Hume", year="1739", category="Philosophy",
         desc="Hume's youthful masterpiece: knowledge, causation, passion and the is-ought line."),

    dict(id="a-modest-proposal", gid=1080, title="A Modest Proposal", author="Jonathan Swift", year="1729", category="History",
         desc="Swift's biting satire: the Irish poor should feed their children to the rich. The blueprint for systemic critique."),

    dict(id="general-introduction-psychoanalysis", gid=38219, title="A General Introduction to Psychoanalysis", author="Sigmund Freud", year="1920", category="Psychology",
         desc="Freud's lecture-series primer on the unconscious, dreams, slips of the tongue and everyday neuroses."),

    dict(id="tesla-inventions", gid=39272, title="Inventions, Researches and Writings of Nikola Tesla", author="Thomas Commerford Martin", year="1894", category="Technology",
         desc="The definitive contemporary record of Tesla's inventions — AC motors, wireless transmission, robotics and more."),
]

HEAD_RE = re.compile(
    r"^(CHAPTER|Chapter|BOOK|Book|PART|Part|SECTION|Section|LETTER|Letter|CANTO|Canto|PREFACE|Preface|INTRODUCTION|Introduction|APPENDIX|Appendix|CONCLUSION|Conclusion)\b"
    r"|^[IVXLCDM]+[.)]?$|^[0-9]{1,3}[.)]$"
)


def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def fetch_text(book):
    os.makedirs(TXT_DIR, exist_ok=True)
    path = os.path.join(TXT_DIR, book["id"] + ".txt")
    if os.path.exists(path) and os.path.getsize(path) > 1000:
        return path
    url = f"https://www.gutenberg.org/cache/epub/{book['gid']}/pg{book['gid']}.txt"
    print(f"  downloading {book['title']} ...", flush=True)
    import time
    data = None
    for attempt in range(8):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (fahad-books)"})
            with urllib.request.urlopen(req, timeout=10) as r:
                data = r.read().decode("utf-8", errors="replace")
            if not re.search(
                r"END OF (THE|THIS) PROJECT GUTENBERG|END-OF-PROJECT-GUTENBERG|End of (the|this) Project Gutenberg",
                data, re.I,
            ):
                print(f"    incomplete text ({len(data)} bytes), retrying ...", flush=True)
                data = None
                time.sleep(3 * (attempt + 1))
                continue
            break
        except Exception as e:
            print(f"    retry {attempt + 1} ({e})", flush=True)
            time.sleep(3 * (attempt + 1))
    if data is None:
        raise RuntimeError(f"failed to download {url}")
    # strip Gutenberg header/footer
    m = re.search(r"\*\*\* ?START OF (THE|THIS) PROJECT GUTENBERG EBOOK[^\n]*\n", data, re.I)
    if m:
        data = data[m.end():]
    m = re.search(r"\*\*\* ?END OF (THE|THIS) PROJECT GUTENBERG EBOOK", data, re.I)
    if m:
        data = data[: m.start()]
    data = data.replace("\r\n", "\n").strip() + "\n"
    with open(path, "w", encoding="utf-8") as f:
        f.write(data)
    return path


def _page_setup():
    """Fonts and paragraph styles shared by the cover and the body."""
    from reportlab import rl_config

    rl_config.useA85 = 0

    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import Flowable, Paragraph

    fdir = "/usr/share/fonts/truetype/dejavu/"
    pdfmetrics.registerFont(TTFont("DJSerif", fdir + "DejaVuSerif.ttf"))
    pdfmetrics.registerFont(TTFont("DJSerif-Bold", fdir + "DejaVuSerif-Bold.ttf"))
    pdfmetrics.registerFont(TTFont("DJSerif-Italic", fdir + "DejaVuSerif-Italic.ttf"))
    pdfmetrics.registerFont(TTFont("DJSerif-BoldItalic", fdir + "DejaVuSerif-BoldItalic.ttf"))
    pdfmetrics.registerFontFamily(
        "DJSerif", normal="DJSerif", bold="DJSerif-Bold",
        italic="DJSerif-Italic", boldItalic="DJSerif-BoldItalic",
    )

    ss = getSampleStyleSheet()
    styles = {
        "body": ParagraphStyle(
            "Body", parent=ss["BodyText"], fontName="DJSerif", fontSize=10.5, leading=15.5,
            alignment=TA_JUSTIFY, spaceAfter=7, firstLineIndent=14,
        ),
        "heading": ParagraphStyle(
            "Heading", parent=ss["Heading2"], fontName="DJSerif-Bold", fontSize=14,
            leading=19, spaceBefore=18, spaceAfter=10, alignment=TA_CENTER, textColor="#1a1a1a",
        ),
        "title_pg": ParagraphStyle(
            "TitlePage", parent=ss["Title"], fontName="DJSerif-Bold", fontSize=30,
            leading=38, alignment=TA_CENTER, spaceAfter=14, textColor="#111",
        ),
        "sub": ParagraphStyle(
            "Sub", parent=ss["Normal"], fontName="DJSerif", fontSize=15, leading=22,
            alignment=TA_CENTER, spaceAfter=8, textColor="#444",
        ),
        "small": ParagraphStyle(
            "Small", parent=ss["Normal"], fontName="DJSerif", fontSize=10, leading=15,
            alignment=TA_CENTER, textColor="#777",
        ),
        "brand": ParagraphStyle(
            "Brand", parent=ss["Normal"], fontName="DJSerif-Bold", fontSize=11,
            leading=16, alignment=TA_CENTER, textColor="#b8860b",
        ),
    }
    styles["body_first"] = ParagraphStyle("BodyFirst", parent=styles["body"], firstLineIndent=0)

    class Divider(Flowable):
        """Rule with a diamond, drawn with vector ops.

        A dingbat character (this used to be U+2767) is not in DejaVuSerif, so
        reportlab silently emitted a missing-glyph box that landed on every
        generated cover. Drawing it keeps the cover identical on any font set.
        """

        HEIGHT = 16

        def __init__(self, width):
            Flowable.__init__(self)
            self.width = width

        def wrap(self, availWidth, availHeight):
            return (self.width, self.HEIGHT)

        def draw(self):
            c = self.canv
            mid, y = self.width / 2.0, self.HEIGHT / 2.0
            c.setLineWidth(0.5)
            c.setStrokeColor(colors.HexColor("#c8c8c8"))
            c.line(0, y, mid - 12, y)
            c.line(mid + 12, y, self.width, y)
            c.setFillColor(colors.HexColor("#c9a227"))
            p = c.beginPath()
            p.moveTo(mid, y + 5)
            p.lineTo(mid + 4.5, y)
            p.lineTo(mid, y - 5)
            p.lineTo(mid - 4.5, y)
            p.close()
            c.drawPath(p, fill=1, stroke=0)

    return dict(styles=styles, Divider=Divider, mm=mm, A4=A4)


def draw_cover(canvas, book, setup):
    """Paint the cover centred on the current page.

    Painting it directly (rather than flowing spacers) means a one-line and a
    five-line title both end up optically centred, so the page-1 thumbnail every book
    card shows is balanced instead of sitting high with dead space under it.

    Two details matter here: drawOn hangs a flowable downwards from the y it is
    given, and a Paragraph's height includes the spaceBefore/spaceAfter of its style,
    which is blank. Both are compensated, otherwise the block drifts to the foot of
    the page and every card grows a white band across the top.
    """
    from reportlab.platypus import Paragraph

    styles, Divider = setup["styles"], setup["Divider"]
    mm, A4 = setup["mm"], setup["A4"]
    small, title_pg, sub, brand = styles["small"], styles["title_pg"], styles["sub"], styles["brand"]
    text_width = A4[0] - 44 * mm

    blocks = [
        (Paragraph(html.escape(book["category"].upper()), small), 5 * mm),
        (Paragraph(html.escape(book["title"]), title_pg), 9 * mm),
        (Paragraph(html.escape(book["author"]), sub), 2 * mm),
    ]
    if book.get("year"):
        blocks.append((Paragraph(html.escape(str(book["year"])), small), 0))
    blocks.append((Divider(text_width * 0.55), 6 * mm))
    blocks.append((Paragraph("FAHAD.COM &#8212; Free Book Library", brand), 2 * mm))
    blocks.append((Paragraph("Public Domain Edition", small), 0))

    laid_out = []
    for flowable, gap in blocks:
        width, height = flowable.wrap(text_width, A4[1])
        style = getattr(flowable, "style", None)
        blank = 0.0
        if style is not None:
            blank = (style.spaceBefore or 0) + (style.spaceAfter or 0)
        laid_out.append((flowable, width, height, max(1.0, height - blank), gap))

    ink_total = sum(b[3] for b in laid_out) + sum(b[4] for b in laid_out)

    canvas.saveState()
    y = (A4[1] + ink_total) / 2.0
    for flowable, width, height, ink, gap in laid_out:
        y -= ink
        flowable.drawOn(canvas, (A4[0] - width) / 2.0, y)
        y -= gap
    canvas.restoreState()


def make_cover_pdf(book, path):
    """Write just the cover as a one-page PDF, for tools/fix_covers.py."""
    from reportlab.pdfgen import canvas as canvasmod

    setup = _page_setup()
    c = canvasmod.Canvas(path, pagesize=setup["A4"])
    c.setTitle(book["title"])
    c.setAuthor(book["author"])
    c.setSubject(book["category"])
    c.setCreator("Fahad.com")
    draw_cover(c, book, setup)
    c.showPage()
    c.save()
    return path


def build_pdf(book):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        BaseDocTemplate, Frame, NextPageTemplate, PageBreak, PageTemplate, Paragraph,
    )

    setup = _page_setup()
    styles = setup["styles"]

    pdf_path = os.path.join(PDF_DIR, book["id"] + ".pdf")
    os.makedirs(PDF_DIR, exist_ok=True)

    def decorate(canvas, doc):
        canvas.saveState()
        canvas.setFont("DJSerif", 8)
        canvas.setFillColor("#888888")
        if doc.page > 1:
            canvas.drawCentredString(A4[0] / 2, 12 * mm, str(doc.page - 1))
            canvas.drawString(20 * mm, 12 * mm, book["title"][:44])
            canvas.drawRightString(A4[0] - 20 * mm, 12 * mm, "Fahad.com")
            canvas.setStrokeColor("#dddddd")
            canvas.setLineWidth(0.5)
            canvas.line(20 * mm, 16 * mm, A4[0] - 20 * mm, 16 * mm)
        canvas.restoreState()

    def title_page(canvas, doc):
        draw_cover(canvas, book, setup)

    frame = Frame(22 * mm, 20 * mm, A4[0] - 44 * mm, A4[1] - 40 * mm, id="main")
    doc = BaseDocTemplate(
        pdf_path, pagesize=A4, title=book["title"], author=book["author"],
        subject=book["category"], creator="Fahad.com",
    )
    doc.addPageTemplates([
        PageTemplate(id="cover", frames=[frame], onPage=title_page),
        PageTemplate(id="all", frames=[frame], onPage=decorate),
    ])

    story = [NextPageTemplate("all"), PageBreak()]

    with open(fetch_text(book), encoding="utf-8", errors="replace") as f:
        raw = f.read()

    blocks = [b.strip() for b in re.split(r"\n\s*\n", raw)]
    used_heading = False
    prev_para = False
    for b in blocks:
        if not b:
            prev_para = False
            continue
        text = re.sub(r"\s*\n\s*", " ", b).strip()
        if not text:
            continue
        is_heading = (
            len(text) < 90
            and ("\n" not in b)
            and (
                HEAD_RE.match(text)
                or (text.isupper() and len(text) > 3 and not text.endswith((".", "?", "!", '"', "'")))
            )
        )
        style = styles["heading"] if is_heading else (
            styles["body_first"] if not prev_para else styles["body"]
        )
        prev_para = not is_heading
        if is_heading:
            used_heading = True
        story.append(Paragraph(html.escape(text), style))

    if not used_heading:
        pass
    doc.build(story)

    size = os.path.getsize(pdf_path)
    print(f"  built {book['id']}.pdf ({size/1024:.0f} KB)", flush=True)
    return dict(size=size)


def main():
    only = sys.argv[1:]
    books = [b for b in BOOKS if not only or b["id"] in only]
    print(f"Fetching {len(books)} books ...", flush=True)
    with ThreadPoolExecutor(max_workers=6) as ex:
        list(ex.map(fetch_text, books))

    results = {}
    for i, b in enumerate(books, 1):
        print(f"[{i}/{len(books)}] {b['title']}", flush=True)
        results[b["id"]] = build_pdf(b)

    # merge into books.json
    from pypdf import PdfReader

    entries = []
    for b in BOOKS:
        pdf = os.path.join(PDF_DIR, b["id"] + ".pdf")
        if not os.path.exists(pdf):
            continue
        try:
            pages = len(PdfReader(pdf).pages)
        except Exception:
            pages = None
        entries.append({
            "id": b["id"],
            "title": b["title"],
            "author": b["author"],
            "year": b["year"],
            "category": b["category"],
            "desc": b["desc"],
            "file": f"pdfs/{b['id']}.pdf",
            "size": os.path.getsize(pdf),
            "pages": pages,
        })
    os.makedirs(os.path.dirname(DATA), exist_ok=True)
    with open(DATA, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)
    total = sum(e["size"] for e in entries)
    print(f"\nDone: {len(entries)} books, total PDF {total/1024/1024:.1f} MB -> {DATA}", flush=True)


if __name__ == "__main__":
    main()
