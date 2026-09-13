# User Guide

How to use the EU Regulatory Compliance RAG Chatbot. For installation and
administration of the server, see the [README](README.md).

> **Not legal advice.** The corpus is frozen at **August 2019**; recent
> legislation may be missing. Always verify against
> [eur-lex.europa.eu](https://eur-lex.europa.eu) before acting.

## Contents

- [Signing in](#signing-in)
- [Asking questions](#asking-questions)
  - [Choosing datasets](#choosing-datasets)
  - [Mentioning a document or act with `@`](#mentioning-a-document-or-act-with-)
  - [Reading an answer](#reading-an-answer)
  - [Answer language](#answer-language)
- [My Documents](#my-documents)
- [Topics](#topics)
- [Datasets](#datasets)
- [Account settings](#account-settings)
- [Admin: managing users](#admin-managing-users)
- [Tips for good questions](#tips-for-good-questions)
- [Troubleshooting](#troubleshooting)

## Signing in

1. Open the app (default: <http://localhost>).
2. **Register** with a username (≥ 3 characters) and password (≥ 8 characters),
   or sign in if you already have an account.
3. The **first account created becomes an administrator**; later accounts are
   regular users. On a fresh server an `admin` account also exists — change its
   password right away (see [Account settings](#account-settings)).

Your username in the top-right is a link to **Settings**.

## Asking questions

Type a question in the box at the bottom of **Chat** and press Enter. For
example:

- “Is the GDPR still in force?”
- “What obligations does the AI Act impose on providers?”
- “Summarise the anti-money-laundering rules for credit institutions.”

### Choosing datasets

Above the input, the **Datasets** row lists everything you can search:

- **Regulatory texts** (e.g. *EURLEX Regulatory Texts*) — shared, read-only law
  collections.
- **My Documents** — your private uploads.

Click a chip to include or exclude a dataset. By default all regulatory
datasets are selected. Selecting a document dataset lets you also narrow to
individual files with `@` mentions (below).

### Mentioning a document or act with `@`

Type `@` followed by a few characters to search across your documents **and**
the regulatory datasets, then pick a result:

- `@contract` → your file `contract_2024.pdf`
- `@2016/679` or `@32016R0679` → the GDPR

Selections appear as removable chips above the input and **scope the answer to
exactly those items**. Use ↑/↓ and Enter to pick from the list, Esc to close.
Remove a chip with its **×**. Remove all chips to search normally again.

### Reading an answer

Each answer includes:

- **Sources** — the acts/documents used, with CELEX number, title, status, and a
  link to EUR-Lex; click to expand an excerpt.
- **Warnings** — e.g. when a cited act is no longer in force, or when the model
  referenced something that wasn’t in the retrieved text (the *grounding*
  guardrail). Treat ungrounded citations with extra caution.
- **Feedback** — thumbs up/down on an answer (used for evaluation).

Answers are saved to your **Recent History** (sidebar); click an item to reopen
the exchange, or **Open** to see and delete the full history.

### Answer language

Settings → **Language** lets you choose the language the assistant writes in:
**English**, **Français**, or **Tiếng Việt**. CELEX numbers, act titles, and
links are always kept as-is.

## My Documents

Your private library (nobody else can see it).

1. Go to **Datasets → My Documents** (or the *My Documents* card).
2. Optionally type **tags** (e.g. `contracts, 2024`) to group files.
3. **Choose files** or drop them — PDF, DOCX, TXT, MD, CSV (max 20 MB each).
   They are extracted, chunked, and indexed automatically.
4. Use **Search my documents** to find passages across your files.
5. Delete a file with the trash icon. To chat with a specific file, use
   `@filename` in Chat.

## Topics

**Topics** let you track how regulation on a subject evolves.

1. Click **New Topic**, give it a name (and optional description/filters).
2. Open the topic to see a **timeline** of matching acts, plotted by document
   date, with a short summary per act.
3. **Refresh** re-runs the search while keeping summaries it already generated.

## Datasets

The **Datasets** page lists everything you can search, grouped into
**Regulatory texts** and **My documents**.

- Open a **regulatory dataset** to browse its items: search, sort any column,
  change the page size, and page through the list. Click a row to read the full
  text of that act, grouped by section, with a **Copy** button.
- **Export** (regulatory) downloads a `.rcdataset.zip` bundle you can share.
- **Administrators** can **Import regulatory dataset** (a bundle file) and
  **Remove dataset** (which requires typing the dataset name to confirm).

## Account settings

Click your username in the top-right to open **Settings**.

- **Account** — change your **username** (must be unique) and **password**
  (enter your current password first).
- **Language** — choose the answer language (English / Français / Tiếng Việt).
- **Retrieval** — include repealed/superseded acts in results.
- **Display / Notifications** — UI preferences.
- **Users** (admins only) — see below.

## Admin: managing users

Administrators see a **Users** panel in Settings:

- **Add user** — create an account (optionally with admin rights).
- **Rename**, **Reset password**, and **grant/revoke admin** per user.
- **Delete user** — permanently removes the user and everything they own
  (documents, files, vectors, topics, history). Requires typing the username to
  confirm. You cannot delete yourself or demote/delete the last admin.

## Tips for good questions

- Be specific: name the act, sector, or obligation (“records of processing under
  **Article 30 GDPR**”).
- Ask one thing at a time.
- Use `@` when you want an answer restricted to a particular file or act.
- Prefer clicking a **source** to read the original wording before relying on a
  summary.
- If an act is repealed, enable **Include repealed acts** in Settings (or ask
  explicitly) to make it retrievable.

## Troubleshooting

| Symptom | What to do |
| --- | --- |
| “No supporting sources retrieved” | Rephrase or broaden the question; make sure the relevant dataset is selected. |
| Answer cites something not in the sources | The grounding warning fired — open the sources and verify before trusting the citation. |
| A recent law is missing | The corpus is frozen at Aug 2019; check EUR-Lex directly. |
| `@` shows no results | Check the spelling; regulatory search needs 2+ characters. |
| Upload rejected | Supported formats are PDF/DOCX/TXT/MD/CSV, up to 20 MB. |
| Login redirects oddly on reload | Ensure the web server routes SPA paths to the frontend (the bundled Caddy config does this). |

For server/installation issues, see the [README](README.md) and
[CONTRIBUTING](CONTRIBUTING.md).
