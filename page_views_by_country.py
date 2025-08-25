import os
from datetime import datetime, timedelta
import json
import sys

import requests
import pandas as pd
import pywikibot

from list_wikis import Wikilister
from api.utils import to_malagasy_month, dataframe_to_wikitable


class PageViewsByCountry(object):

    def __init__(self, country="MG", site_type="wiktionary"):
        self.country = country
        self.site_type = site_type
        self.wikilister = Wikilister()
        self.page = None
        self.revisions = []

    def build_pageview_csv(self, language, ct_date):
        headers = {
            "User-Agent": "Bot-Jagwar/1.7.2 (https://github.com/botjagwar/botjagwar; radomd92@gmail.com)"
        }
        directory = "/opt/botjagwar/user_data/pageviews"
        filename = (
            f"{directory}/{language}{self.site_type}_{ct_date.year}_%02d.csv"
            % ct_date.month
        )

        if os.path.exists(filename):
            print(f"File '{filename}' already exists. Skipped.")
            return

        route = (
            f"https://wikimedia.org/api/rest_v1/metrics/pageviews/top-by-country/{language}.{self.site_type}.org/all-access/{ct_date.year}/%02d"
            % int(ct_date.month)
        )
        resp = requests.get(route, headers=headers)
        if resp.status_code != 200:
            print(f"Error fetching {route}:", resp, resp.text)
            return
        try:
            stats = resp.json()
        except json.decoder.JSONDecodeError as error:
            print(f"Error decoding JSON from {route}", error)
            return

        # create directory if not exist
        stats = stats["items"][0]["countries"]
        stats_dataframe = pd.DataFrame(stats)
        if not os.path.exists(directory):
            os.makedirs(directory)
            print(f"Directory '{directory}' created.")
        stats_dataframe["wiki"] = f"{language}{self.site_type}"

        # save data
        stats_dataframe.to_csv(filename)

    def compile_page_views(self, begin_year=2022, begin_month=1, months=3):
        begin_date = datetime(begin_year, begin_month, 1)
        end_date = begin_date + timedelta(days=30 * months)

        for language in list(self.wikilister.getLangs(self.site_type)):
            ct_date = begin_date
            while ct_date < end_date:
                self.build_pageview_csv(language, ct_date)

                ct_date += timedelta(days=30)

    def merge_csv_data(self, begin_year=2022, begin_month=1, months=3):
        begin_date = datetime(begin_year, begin_month, 1)
        end_date = begin_date + timedelta(days=30 * months)
        dataframes = []
        directory = "/opt/botjagwar/user_data/pageviews"
        for language in list(self.wikilister.getLangs("wiktionary")):
            ct_date = begin_date
            while ct_date < end_date:
                filename = (
                    f"{directory}/{language}{self.site_type}_{ct_date.year}_%02d.csv"
                    % ct_date.month
                )
                try:
                    dataframes.append(pd.read_csv(filename))
                except FileNotFoundError as error:
                    print(f"Error reading data for {language} on {ct_date}", error)
                ct_date += timedelta(days=30)

        df = pd.concat(dataframes, ignore_index=True)
        result = (
            df[df["country"] == self.country]  # Filter where country = 'MG'
            .groupby(["country", "wiki"])  # Group by country and wiki
            .agg({"views_ceil": "sum"})  # Sum the views_ceil
            .sort_values(by="views_ceil", ascending=False)
            .reset_index()
        )  # Reset the index

        # Rename the columns if necessary
        result.columns = ["country", "wiki", "sum_views_ceil"]
        result.rename(
            columns={
                "country": "Firenena",
                "wiki": "Wiki",
                "rank": "Laharana",
                "sum_views_ceil": "Jery",
            },
            inplace=True,
        )

        print(result)
        return result


def page_views_by_country(year, month, country, site="wiktionary"):
    views = PageViewsByCountry(country, site)
    begin_year, begin_month = year, month
    months_to_aggregate = 1
    views.compile_page_views(
        begin_year=begin_year, begin_month=begin_month, months=months_to_aggregate
    )
    df = views.merge_csv_data(
        begin_year=begin_year, begin_month=begin_month, months=months_to_aggregate
    )
    return dataframe_to_wikitable(df)


def main(country="MG"):
    page = pywikibot.Page(
        pywikibot.Site("mg", "wiktionary"),
        "Mpikambana:Bot-Jagwar/Isan'ny jerim-pejy ao Madagasikara",
    )
    content = page.get() if page.exists() else ""
    analysis_date = datetime.now()
    month = 12 if analysis_date.month == 1 else analysis_date.month - 1
    year = analysis_date.year - 1 if analysis_date.month == 1 else analysis_date.year
    explanation_text = "Ireo no isan'ny jery tao Madagasikara mahakasika ny tetikasa Wikipedia sy Wikibolana ary Wikiboky.\n"
    views_as_table = (
        f"\n\n=={to_malagasy_month(month)} {year}==\n"
        + explanation_text
        + "\n\n; Wikipedia\n"
        + page_views_by_country(year, month, country, "wikipedia")
        + "\n\n; Wikibolana\n"
        + page_views_by_country(year, month, country, "wiktionary")
        + "\n\n; Wikiboky\n"
        + page_views_by_country(year, month, country, "wikibooks")
        + "\n(~~~~~)"
    )
    print(views_as_table)
    content += views_as_table
    page.put(content, "Isan'ny jery amin'n Wiki malagasy")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        main(sys.argv[1].upper())
    else:
        main()
