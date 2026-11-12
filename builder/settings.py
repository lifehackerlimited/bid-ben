"""The few things you might want to change about the site, in one place."""

SITE = "https://bidben.betttech.co.uk"

# Where the sign-up box sends its form. This is the Formspree form the Betttech website's contact page uses, so
# sign-ups arrive in the same inbox with the subject "Bid Ben sign-up". To give Bid Ben a form of its own, make
# one at formspree.io and put its ID (the part after /f/) here.
FORMSPREE_ID = "mdeabnwz"
FORM_ACTION = f"https://formspree.io/f/{FORMSPREE_ID}"

CONTACT_EMAIL = "info@betttech.co.uk"
PRICE = "£20 a month, including VAT"
TRIAL_WEEKS = "four"
COMPANY = "Betttech Global Ventures Ltd, company no. 11753604"
OFFICE = "7 Clim Down, Kingsdown, Deal, Kent CT14 8EX"

RECENT_DAYS = 90        # how long a closed tender stays in a county's "recently closed" list
