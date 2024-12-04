import re
import time
from list_wikis import Wikilister

# import matplotlib.pyplot as plt
import pandas as pd
import pywikibot
from sklearn.linear_model import LinearRegression
from api.utils import to_malagasy_month


class RevisionLister(object):
    def __init__(self, page_name, site_type="wiktionary"):
        self.page_name = page_name
        self.revisions = []
        self.page = pywikibot.Page(pywikibot.Site("mg", site_type), page_name)
        self.revisions = self.page.revisions()
        self.last_count = None
        self.last_most_recent = None
        self.last_returned = None

    def get_revisions(self, count=250, most_recent=False):
        if (
            self.last_count == count
            and self.last_most_recent == most_recent
            and self.last_returned is not None
        ):
            return self.last_returned
        else:
            returned = []

        if most_recent:
            revisions = [r for r in self.revisions][:count]
        else:
            revisions = [r for r in self.revisions][-count:]

        for revision in revisions:
            print(revision)
            returned.append(
                (
                    revision.timestamp,
                    revision.revid,
                    self.page.getOldVersion(revision.revid),
                )
            )

        self.last_count = count
        self.last_most_recent = most_recent
        self.last_returned = returned
        return returned


page_name = "Mpikambana:Bot-Jagwar/Lisitry ny Wikibolana/tabilao"
revisions = RevisionLister(page_name)
stats_page = revisions.page


def to_malagasy_date(timestamp):
    date = f"{timestamp.day} {to_malagasy_month(timestamp.month)} {timestamp.year}"
    return f"{date}"


def compile_pagecount_csv_file(language, site, history_depth=50):
    with open(f"user_data/milestones/wikistats-{site}-{language}.csv", "w") as out_file:
        # print(f'compiling csv file for {language}')
        revisions_data = revisions.get_revisions(history_depth, most_recent=True)
        for timestamp, revision_id, text in revisions_data:
            lines = text.split("\n")
            # Output:
            try:
                line = [
                    line
                    for line in lines
                    if f"//{language}.{site}.org/w/api.php?"
                    f"action=query&meta=siteinfo&format=xml&siprop=statistics" in line
                ][0]
                article = re.findall("\{\{formatnum:([0-9]+)\}\}", line)[0]
            except IndexError:
                # print('error')
                pass
            else:
                out_file.write(f"{timestamp.timestamp()},{article}\n")


def build_regression_model_on_stats_data(
    language,
    site,
    milestones=(
        1e4,
        2e4,
        3e4,
        4e4,
        5e4,
        6e4,
        7e4,
        8e4,
        9e4,
        1e5,
        2e5,
        3e5,
        4e5,
        5e5,
        6e5,
        7e5,
        8e5,
        9e5,
        1e6,
        2e6,
        3e6,
        4e6,
        5e6,
        6e6,
        7e6,
        8e6,
        9e6,
        10e6,
        15e6,
        20e6,
    ),
):
    return_data = {}
    data = pd.read_csv(f"user_data/milestones/wikistats-{site}-{language}.csv")
    X = data.iloc[:, 0].values.reshape(-1, 1)
    y = data.iloc[:, 1].values.reshape(-1, 1)

    linear_regressor = LinearRegression()
    linear_regressor.fit(X, y)
    linear_regressor_inv = LinearRegression()
    linear_regressor_inv.fit(y, X)
    # y_pred = linear_regressor.predict(X)

    for milestone in milestones:
        date_as_ts = linear_regressor_inv.predict([[milestone]])
        try:
            pd_timestamp = pd.to_datetime(date_as_ts[0][0], unit="s")
            return_data[milestone] = {
                "date": to_malagasy_date(pd_timestamp),
                "timestamp": date_as_ts[0][0],
            }
            # print(f"milestone: {milestone} on date", date)
        except pd.errors.OutOfBoundsDatetime as exc:
            # print(f'ERROR: date too far in the future/past. Skipped: {exc}')
            pass
        except Exception as exc:
            # print(f'{exc.__class__.__name__}: {exc}')
            pass
    # plt.scatter(X, y)
    # plt.plot(X, y_pred, color='red')
    # plt.show()

    return return_data


def predict_milestones(site_type="wiktionary"):
    mappings = {
        "wiktionary": "Wikibolana",
        "wikipedia": "Wikipedia",
    }
    wl = Wikilister()
    wiki_file = "user_data/future-milestones.wiki"
    with open(wiki_file, "w") as f:
        f.write(
            "Ity vinavina ity dia nohavaozina farany ny "
            "{{subst:CURRENTDAY}} {{CURRENTMONTHNAME}} {{CURRENTYEAR}}.\n"
        )
        for language in wl.getLangs(site_type):
            section_added = False
            # print(language)
            current_date = time.time()
            compile_pagecount_csv_file(language, site_type, history_depth=50)
            try:
                milestone_dates = build_regression_model_on_stats_data(
                    language, site_type
                )
            except ValueError:
                continue

            for milestone, milestone_data in milestone_dates.items():
                if milestone_data["timestamp"] < current_date:
                    continue
                if not section_added:
                    f.write(f"\n; {language}.{site_type}\n")
                    section_added = True
                milestone_as_str = "{{formatnum:" + str(int(milestone)) + "}}"
                f.write(
                    f"* Hahatratra pejim-botoatiny '''{milestone_as_str}''' amin'ny daty {milestone_data['date']}\n"
                )

    with open("user_data/future-milestones.wiki", "r") as f:
        wikitext = f.read()
        page = pywikibot.Page(
            pywikibot.Site("mg", "wiktionary"),
            f"Mpikambana:Bot-Jagwar/Lisitry ny {mappings[site_type]}/dingana ho avy",
        )
        page.put(
            wikitext, "Rôbô : fanavaozana ny dingana sy ny daty hahatratrarana azy"
        )


if __name__ == "__main__":
    # main('wikipedia')
    predict_milestones("wiktionary")
