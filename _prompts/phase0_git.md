# Phase 0 — Git und GitHub einrichten

> Läuft **vor** Phase 1. Kopiere alles ab der Trennlinie in Claude Code.

---

Richte die Versionsverwaltung für dieses Projekt ein. Lies vorher `CLAUDE.md`, insbesondere
Abschnitt 2 (Architekturregeln) und Abschnitt 3 (Verzeichnisstruktur).

**Diese Phase erzeugt keinen Anwendungscode.** Sie legt nur Git, `.gitignore`,
`.gitattributes` und das GitHub-Repository an. Halte am Ende an und berichte.

## Aufgabe 1 — `.gitattributes` anlegen

Dieses Projekt läuft unter Windows, und die Reproduzierbarkeit hängt an SHA-256-Hashes von
CSV- und Parquet-Dateien. Wenn Git die Zeilenenden automatisch umschreibt, ändern sich die
Hashes zwischen Rechnern und der Reproduzierbarkeitstest schlägt fehl — ohne dass jemand
den Grund sieht.

```gitattributes
* text=auto eol=lf

# Referenzdaten: feste Zeilenenden, damit die Hashes stabil bleiben
data/reference/*.csv text eol=lf

# Binärformate niemals anfassen
*.parquet binary
*.png binary
*.pdf binary
*.docx binary
*.xlsx binary
```

Setze zusätzlich `git config core.autocrlf false` im Repository.

## Aufgabe 2 — `.gitignore` anlegen

```gitignore
# Python
__pycache__/
*.py[cod]
*.egg-info/
.venv/
venv/
.env

# Werkzeug-Caches
.pytest_cache/
.mypy_cache/
.ruff_cache/
.ipynb_checkpoints/

# Laufartefakte: aus master_seed und Konfiguration exakt reproduzierbar,
# deshalb nicht versionieren. Bei mehreren tausend Läufen entstünden
# sonst zweistellige Gigabyte.
data/runs/

# Betriebssystem
.DS_Store
Thumbs.db
desktop.ini
```

**Nicht ignoriert werden** — das ist wichtig:

| Pfad | Warum er ins Repository gehört |
|---|---|
| `data/reference/` | Die Referenztabellen sind Eingabedaten, keine Ergebnisse. Ohne sie ist kein Lauf reproduzierbar. `CLAUDE.md` Abschnitt 3 schreibt das ausdrücklich vor |
| `results/` | Tabellen, Abbildungen und `metrics.json` gehen direkt in die Arbeit und in den Reproduzierbarkeitsnachweis |
| `spec/` | Die fachliche Spezifikation ist das Design-Artefakt der Arbeit |
| `docs/` | Iterationslog und Verteilungsquellen sind Anhangmaterial |
| `_prompts/` | Dokumentiert, wie das Projekt entstanden ist |

## Aufgabe 3 — Repository initialisieren

```bash
git init
git branch -M main
git add -A
git commit -m "Projektgedaechtnis und fachliche Spezifikation"
```

Der erste Commit enthält bewusst nur `CLAUDE.md`, `spec/`, `_prompts/`, `.gitignore` und
`.gitattributes` — also die Spezifikation, bevor eine Zeile Code existiert. Das ist für die
Nachvollziehbarkeit der Arbeit nützlich: Der Commit-Verlauf zeigt, dass die Spezifikation
vor der Implementierung stand.

## Aufgabe 4 — GitHub-Repository anlegen

Zielaccount: **`Showmaker1337`** (persönlicher Account). Sichtbarkeit: **privat**.

Prüfe zuerst den Anmeldestatus:

```bash
gh auth status
```

- Ist ein **anderer** Account eingeloggt: **halte an und melde dich bei mir**, führe kein
  `gh auth login` von dir aus durch und wechsle keinen Account.
- Ist `gh` gar nicht installiert oder nicht angemeldet: melde das ebenfalls, statt einen
  Workaround zu bauen.

Wenn `Showmaker1337` eingeloggt ist:

```bash
gh repo create Showmaker1337/Bachelorarbeit_Programm \
  --private \
  --source=. \
  --remote=origin \
  --push \
  --description "Prototyp und Evaluationsumgebung zur Bachelorarbeit: Regelbasierte Datenvalidierung in Versicherungsvergleichssystemen"
```

Existiert der Name schon, hänge ein Suffix an und berichte es — überschreibe nichts.

## Aufgabe 5 — README

Lege ein `README.md` an mit:

- Titel und Forschungsfrage der Arbeit (aus `CLAUDE.md`, Abschnitt 1)
- dem Hinweis, dass ausschließlich **synthetische** Daten verarbeitet werden und keinerlei
  echte Personen- oder Bestandsdaten
- der Phasenübersicht mit den Kommandos, soweit sie schon existieren
- einem Abschnitt „Reproduzierbarkeit" mit Python-Version und dem Verweis auf
  `requirements.txt` (wird in Phase 1 gefüllt)
- einem Platzhalter-Abschnitt „Freeze des Regelkatalogs", in den nach Phase 3 der
  Commit-Hash des Tags `freeze-regelkatalog` eingetragen wird

Keine Lizenzdatei anlegen. Bei einer Abschlussarbeit hängt die Lizenzfrage von der
Hochschulordnung ab — das entscheidet der Autor, nicht das Werkzeug.

## Aufgabe 6 — Commit-Konvention festlegen

Trage in `CLAUDE.md`, Abschnitt 5 (Konventionen), zwei Zeilen nach:

- Commit-Nachrichten auf Deutsch, im Imperativ, eine Zeile, ohne Emoji.
- Je Phase mindestens ein Commit. Der Phasenabschluss wird als eigener Commit markiert.

Committe diese Ergänzung und pushe.

## Aufgabe 7 — Was du für später wissen musst

Nach Phase 3 wird der Regelkatalog eingefroren. Der Tag muss **auch auf GitHub landen**,
sonst ist er im Anhang der Arbeit nicht belegbar:

```bash
git tag -a freeze-regelkatalog -m "Freeze des Regelkatalogs vor Implementierung des Fehlerinjektors"
git push origin main --follow-tags
```

`git push` allein überträgt keine Tags. Merke dir das für Phase 3 — der Commit-Hash dieses
Tags ist der Beleg dafür, dass die Validierungsregeln nicht nachträglich auf die injizierten
Fehler zugeschnitten wurden. Ohne ihn ist die Behauptung nicht überprüfbar.

## Abnahmekriterien

1. `git log` zeigt mindestens zwei Commits.
2. `git remote -v` zeigt `origin` auf `Showmaker1337/Bachelorarbeit_Programm`.
3. `gh repo view --json visibility` meldet `PRIVATE`.
4. `data/runs/` ist ignoriert, `data/reference/` und `results/` sind es nicht.
5. `.gitattributes` existiert, `core.autocrlf` steht auf `false`.
6. Das README nennt Titel, Forschungsfrage und den Hinweis auf synthetische Daten.

## Nicht in dieser Phase

Kein Anwendungscode, keine `requirements.txt`, keine Verzeichnisse unter `src/` — das
kommt in Phase 1. Kein `gh auth login`, kein Accountwechsel, keine Lizenzdatei.

Halte am Ende an und berichte: URL des Repositories, Sichtbarkeit, Zahl der Commits und ob
beim Anmeldestatus etwas unklar war.
