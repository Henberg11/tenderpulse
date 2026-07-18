# TenderPulse Dashboard

A mobile-friendly page that reads your tenders directly from Supabase. Hosted
free on GitHub Pages, auto-deployed every time you push a change to this
folder.

## One-time setup

### 1. Fill in `config.js`

Open `config.js` in this folder and replace the two placeholder values with
your real Supabase project URL and "anon public" key -- both found at:
Supabase dashboard -> Settings -> API.

This key is safe to commit and publish (see the comment in that file for
why) -- but only once you've done step 2 below.

### 2. Set up a read-only security rule in Supabase

This is the step that makes it safe for this key to be public. Go to your
Supabase project -> SQL Editor -> New query, and run:

```sql
ALTER TABLE tenders ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow public read-only access"
ON tenders
FOR SELECT
USING (true);
```

This means: anyone with the link can *view* your tenders, but the anon key
can never be used to add, change, or delete anything -- no policy grants
those actions, and Supabase denies by default.

### 3. Turn on GitHub Pages

1. On GitHub, go to your repo -> Settings -> Pages
2. Under "Build and deployment" -> Source, select **"GitHub Actions"**
3. Push a commit that touches anything in this `dashboard/` folder (or
   manually run the "Deploy Dashboard" workflow from the Actions tab)
4. After a minute, your dashboard will be live at:
   `https://YOUR_GITHUB_USERNAME.github.io/tenderpulse/`

Bookmark that URL on your phone -- that's your "check tenders anywhere"
screen.

## What it shows

- Every tender, sorted by closest deadline first
- "Core Match" badge for tenders that precisely match your product line
  (vs. broader uniform-related ones you can still see but aren't your focus)
- "Recently Changed" badge when a corrigendum was detected
- AI-generated summary, eligibility requirements, and risk factors, when
  available (populated by the document intelligence pipeline -- requires
  `GEMINI_API_KEY` to be set in the main app's `.env`)
- Search box and filter chips
- Auto-refreshes every 5 minutes if left open
