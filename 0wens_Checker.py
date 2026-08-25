import csv
import os
import time
import requests
from pathlib import Path
from datetime import datetime, timezone

INPUT_FILE = "Combo List.txt"

OLD_FOLDER = "Old Accounts"
RAP_FOLDER = "RAP Accounts"
PRIVATE_FOLDER = "Private Inventories"
NAME_SNIPES_FOLDER = "Name Snipes"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (school research; public Roblox account checker)"
}


def load_usernames(path):
    usernames = []

    for line in Path(path).read_text(
        encoding="utf-8",
        errors="ignore"
    ).splitlines():

        line = line.strip()

        if not line:
            continue

        # Keep ONLY the username before the first colon.
        # Anything after ":" is completely ignored.
        username = line.split(":", 1)[0].strip()

        if username:
            usernames.append(username)

    return usernames


def resolve_users(usernames):
    resolved = {}
    url = "https://users.roblox.com/v1/usernames/users"

    for i in range(0, len(usernames), 100):
        batch = usernames[i:i + 100]

        payload = {
            "usernames": batch,
            "excludeBannedUsers": False
        }

        while True:
            r = requests.post(
                url,
                json=payload,
                headers=HEADERS,
                timeout=30
            )

            if r.status_code == 429:
                print("Rate limited while resolving usernames. Waiting 10 seconds...")
                time.sleep(10)
                continue

            r.raise_for_status()
            break

        for user in r.json().get("data", []):
            resolved[user["requestedUsername"].lower()] = {
                "id": user["id"],
                "name": user["name"]
            }

        print(
            f"Resolved {min(i + 100, len(usernames))}/{len(usernames)} usernames"
        )

        time.sleep(1)

    return resolved


def get_user_info(user_id):
    url = f"https://users.roblox.com/v1/users/{user_id}"

    while True:
        r = requests.get(
            url,
            headers=HEADERS,
            timeout=30
        )

        if r.status_code == 429:
            print(
                f"Rate limited while getting account info for {user_id}. "
                "Waiting 10 seconds..."
            )
            time.sleep(10)
            continue

        if r.status_code == 404:
            return None

        r.raise_for_status()
        return r.json()


def get_collectibles(user_id):
    url = (
        f"https://inventory.roblox.com/v1/users/"
        f"{user_id}/assets/collectibles"
    )

    params = {
        "sortOrder": "Asc",
        "limit": 100
    }

    items = []
    cursor = None

    while True:
        if cursor:
            params["cursor"] = cursor
        elif "cursor" in params:
            del params["cursor"]

        r = requests.get(
            url,
            params=params,
            headers=HEADERS,
            timeout=30
        )

        if r.status_code == 403:
            return None, "private"

        if r.status_code == 429:
            print(
                f"Rate limited while checking inventory for {user_id}. "
                "Waiting 10 seconds..."
            )
            time.sleep(10)
            continue

        if r.status_code == 404:
            return [], "not_found"

        r.raise_for_status()

        data = r.json()
        items.extend(data.get("data", []))

        cursor = data.get("nextPageCursor")

        if not cursor:
            break

        time.sleep(0.3)

    return items, "public"


def parse_created(created_value):
    if not created_value:
        return None

    try:
        return datetime.fromisoformat(
            created_value.replace("Z", "+00:00")
        )
    except Exception:
        return None


def account_age_years(created_dt):
    """
    Full account age in years as of today (UTC).
    Example: 17 means the account is 17 full years old.
    """
    today = datetime.now(timezone.utc).date()
    created = created_dt.date()

    years = today.year - created.year

    if (today.month, today.day) < (created.month, created.day):
        years -= 1

    return years


def write_two_column_csv(path, header1, header2, rows):
    with open(
        path,
        "w",
        newline="",
        encoding="utf-8-sig"
    ) as f:
        writer = csv.writer(f)
        writer.writerow([header1, header2])
        writer.writerows(rows)


def write_one_column_csv(path, header, rows):
    with open(
        path,
        "w",
        newline="",
        encoding="utf-8-sig"
    ) as f:
        writer = csv.writer(f)
        writer.writerow([header])

        for value in rows:
            writer.writerow([value])



def is_cool_name(username):
    """
    Heuristic for clean / rare-looking usernames.

    Favors:
    - dictionary/name-like words such as Rock or Josh
    - short clean alphabetic usernames
    - no numbers or underscores
    - reasonable length

    This is intentionally conservative so the output is a shortlist,
    not every ordinary username.
    """
    if not username:
        return False

    # Clean names only for this shortlist.
    if not username.isalpha():
        return False

    lower = username.lower()

    # Avoid very long names.
    if len(lower) < 4 or len(lower) > 12:
        return False

    # A curated set of clean/common words and first-name style words that
    # are especially strong "snipe" candidates if they occur in the input.
    strong_words = {
        "rock", "josh", "john", "james", "grace", "hunter", "raven",
        "laser", "gold", "ghost", "moon", "snow", "fire", "sonic",
        "angel", "diamond", "falcon", "scarface", "inferno", "eclipse",
        "shadow", "storm", "frost", "void", "zero", "rare", "magic",
        "princess", "victoria", "kylie", "kelvin", "lucas", "cameron",
        "connor", "dylan", "emily", "lauren", "nicole", "karina",
        "sarah", "robert", "pedro", "carlos", "mert", "emir", "jordan"
    }

    if lower in strong_words:
        return True

    # Short, clean, all-letter names are uncommon enough to shortlist.
    if 4 <= len(lower) <= 6:
        return True

    # For 7-12 letters, require a simple word/name-like shape:
    # not too many repeated characters and at least two vowels.
    vowels = sum(ch in "aeiouy" for ch in lower)
    max_repeat = max(lower.count(ch) for ch in set(lower))

    return vowels >= 2 and max_repeat <= 2


def main():
    usernames = load_usernames(INPUT_FILE)

    print(f"Loaded {len(usernames)} usernames.")
    print("Anything after ':' in the input file is ignored.")
    print("Starting Roblox checks...\n")

    resolved = resolve_users(usernames)

    old_accounts = []
    rap_accounts = []
    private_accounts = []
    name_snipes = []
    cool_names = []

    total = len(usernames)

    for index, requested in enumerate(usernames, start=1):
        info = resolved.get(requested.lower())

        if not info:
            print(
                f"Checked {index}/{total}: "
                f"{requested} | username not resolved"
            )
            continue

        user_id = info["id"]
        current_name = info["name"]

        # 3-4 character username check.
        if len(current_name) in (3, 4):
            name_snipes.append(current_name)

        if is_cool_name(current_name):
            cool_names.append(current_name)

        # Creation date / old-account check.
        created_dt = None

        try:
            user_data = get_user_info(user_id)

            if user_data:
                created_dt = parse_created(
                    user_data.get("created", "")
                )

        except Exception as e:
            print(
                f"Warning: creation-date error for "
                f"{current_name}: {type(e).__name__}"
            )

        if created_dt and created_dt.year <= 2009:
            old_accounts.append(
                (
                    current_name,
                    account_age_years(created_dt)
                )
            )

        # Public Limited RAP / private inventory check.
        rap = None
        inventory_status = "unknown"

        try:
            items, inventory_status = get_collectibles(user_id)

            if items is not None:
                rap = sum(
                    (item.get("recentAveragePrice") or 0)
                    for item in items
                )

                # Only include accounts that actually have RAP.
                if rap > 0:
                    rap_accounts.append(
                        (
                            current_name,
                            rap
                        )
                    )

            elif inventory_status == "private":
                private_accounts.append(current_name)

        except Exception as e:
            print(
                f"Warning: inventory error for "
                f"{current_name}: {type(e).__name__}"
            )

        rap_text = (
            f"{rap:,}"
            if isinstance(rap, int)
            else "private/unknown"
        )

        age_text = (
            str(account_age_years(created_dt))
            if created_dt and created_dt.year <= 2009
            else "-"
        )

        print(
            f"Checked {index}/{total}: "
            f"{current_name} | old-age {age_text} | RAP {rap_text}"
        )

        time.sleep(0.5)

    # Clean + sort the results.
    old_accounts = sorted(
        set(old_accounts),
        key=lambda row: (-row[1], row[0].lower())
    )

    rap_accounts = sorted(
        set(rap_accounts),
        key=lambda row: (-row[1], row[0].lower())
    )

    private_accounts = sorted(
        set(private_accounts),
        key=str.lower
    )

    name_snipes = sorted(
        set(name_snipes),
        key=lambda name: (len(name), name.lower())
    )

    cool_names = sorted(
        set(cool_names),
        key=lambda name: (len(name), name.lower())
    )

    # Make the four requested result folders.
    os.makedirs(OLD_FOLDER, exist_ok=True)
    os.makedirs(RAP_FOLDER, exist_ok=True)
    os.makedirs(PRIVATE_FOLDER, exist_ok=True)
    os.makedirs(NAME_SNIPES_FOLDER, exist_ok=True)

    # 1) Old Accounts: ONLY username + age.
    write_two_column_csv(
        os.path.join(
            OLD_FOLDER,
            "accounts_2009_and_older.csv"
        ),
        "username",
        "age",
        old_accounts
    )

    # 2) RAP Accounts: ONLY username + RAP.
    write_two_column_csv(
        os.path.join(
            RAP_FOLDER,
            "rap_accounts.csv"
        ),
        "username",
        "rap",
        rap_accounts
    )

    # 3) Private Inventories: ONLY username.
    write_one_column_csv(
        os.path.join(
            PRIVATE_FOLDER,
            "private_inventories.csv"
        ),
        "username",
        private_accounts
    )

    # 4) Name Snipes / 3-4 Characters: ONLY username.
    write_one_column_csv(
        os.path.join(
            NAME_SNIPES_FOLDER,
            "3-4_character_names.csv"
        ),
        "username",
        name_snipes
    )

    # 5) Name Snipes / Cool Names: clean, rare-looking usernames.
    write_one_column_csv(
        os.path.join(
            NAME_SNIPES_FOLDER,
            "name_snipes.csv"
        ),
        "username",
        cool_names
    )

    print("\nDONE")
    print(f"Old accounts (2009 or older): {len(old_accounts)}")
    print(f"Accounts with RAP > 0: {len(rap_accounts)}")
    print(f"Private inventories: {len(private_accounts)}")
    print(f"3-4 character names: {len(name_snipes)}")
    print(f"Cool-name candidates: {len(cool_names)}")
    print("\nCreated:")
    print(f"  {OLD_FOLDER}/accounts_2009_and_older.csv")
    print(f"  {RAP_FOLDER}/rap_accounts.csv")
    print(f"  {PRIVATE_FOLDER}/private_inventories.csv")
    print(
        f"  {NAME_SNIPES_FOLDER}/3-4_character_names.csv"
    )
    print(
        f"  {NAME_SNIPES_FOLDER}/name_snipes.csv"
    )


if __name__ == "__main__":
    main()
