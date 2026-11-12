# Bid Ben

The website at [bidben.betttech.co.uk](https://bidben.betttech.co.uk): public-sector cleaning, grounds, tree work
and pest control contracts that small firms can realistically win, explained in plain English.

It looks after itself. Every morning GitHub fetches the new notices from the two official sources, rebuilds every
page, and on Mondays builds the week's issue. You don't upload anything by hand any more.

## What's on the site

| Page | What it's for |
|---|---|
| `/` | What Bid Ben is, the sign-up box, and what's open now |
| `/tenders/` | Every open tender |
| `/tenders/cleaning/` | One trade across the UK (five trades) |
| `/tenders/cleaning/kent/` | One trade in one county. These are the pages firms find when they search |
| `/areas/kent/` | One county, all trades |
| `/issues/` | Every Monday issue, newest first |
| `/signup/`, `/privacy/` | The sign-up page and the privacy notice |

A county page with nothing on it yet is still there, so every link works and people can sign up to be told. It's
hidden from Google until it has a tender to show, so the site isn't judged on empty pages.

## Sign-ups

The sign-up box is on every page. It sends the form to Formspree, which emails it to you with the subject
"Bid Ben sign-up". The outreach autopilot (the private `outreach-autopilot` repository) reads that inbox each
weekday morning, adds the person to the subscriber list, welcomes them, and sends them each issue. Its README has
the details.

The form's address is `FORMSPREE_ID` in `builder/settings.py`. For now it's the same form as the Betttech
website's contact page.

## How it works

Everything is in `builder/` (Python, standard library only):

| File | What it does |
|---|---|
| `settings.py` | The few things you might change: the site address, the form, the price |
| `trades.py` | The trades, and how a notice is matched to one |
| `places.py` | Turning the area codes in notices into counties |
| `feeds.py` | Fetching from Contracts Finder and Find a Tender |
| `notices.py` | Reading a notice, and judging who it suits |
| `store.py` | Keeping what's been fetched in `data/notices.json` |
| `show.py` | The wording for one tender |
| `site.py` | Every page |
| `issue.py` | The Monday issue |

The pages themselves (`index.html`, `tenders/`, `areas/`, `issues/`) are written by the builder. Don't edit them
by hand: change the builder and run it, or your edit is overwritten the next morning.

**"Small-firm fit" and "Our view" are automatic.** They're worked out from the value, the buyer, the procedure and
a few warning words in the notice (TUPE, a deadline after the start date, paper bids). The rules are in
`assess()` in `notices.py` and `view()` in `show.py`. Every fact on a page is copied from the official notice.

## Running it yourself

```bash
python3 -m builder all       # what the daily job runs: fetch, build the issue if it's due, rebuild the pages
python3 -m builder build     # only rebuild the pages (no internet needed)
python3 -m builder status    # how many tenders are in the store
python3 -m unittest discover -s tests
```

To look at the result, run `python3 -m http.server` in this folder and open http://localhost:8000.

To run the daily job now: Actions tab > Site > Run workflow. To pause it: Actions tab > Site > "..." > Disable
workflow.

## Adding a trade

Add an entry to `TRADES` in `builder/trades.py` (a name, the CPV codes buyers file that work under, and the words
that give it away in a title), then run `python3 -m builder fetch --days 21` and `python3 -m builder build`. Its
pages for every county appear by themselves.

## If the daily job fails

GitHub emails you, and the Actions tab shows a red cross. The site simply shows yesterday's tenders until the next
run, and the next run catches up on the days it missed. Find a Tender limits how fast anyone can fetch, so a run
normally takes five to ten minutes.

## Where the information comes from

Tender details come from Contracts Finder and Find a Tender. They contain public sector information licensed under
the [Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/).
Area names and codes are from the Office for National Statistics, under the same licence. Postcodes are looked up
with postcodes.io.
