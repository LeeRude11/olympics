from urllib import request, error
from bs4 import BeautifulSoup as soup, element
from copy import copy
from os import path, remove
import argparse
import re
import sqlite3

db = None
OLYM_DATES = {"month": "February", "year": "2018"}
OLYM_URL = "/wiki/2018_Winter_Olympics"
# a flag for events SQL table can be changed in multiple functions
team_flag = False


def main():
    # ensure proper usage
    parser = argparse.ArgumentParser()
    parser.add_argument("output", help="output file")
    parser.add_argument("-rw", "--rewrite",
                        help="rewrite a file with same name",
                        action="store_true")
    args = parser.parse_args()
    if path.isfile(args.output):
        # don't delete file without flag
        if args.rewrite:
            remove(args.output)
        else:
            print("File with this name already exists")
            print("Use -rw flag to rewrite")
            return 1

    initiate_table(args.output)

    olym_soup = get_wiki_soup(OLYM_URL)

    countries = get_countries(olym_soup)
    # sports are divided by categories and therefore overall are not sorted
    sports = get_sports(olym_soup)
    sports.sort(key=lambda sport: sport["name"])

    write_to_db(countries, "countries")
    write_to_db(sports, "sports")

    print("Total countries =", len(countries), "Total sports =", len(sports))

    iterate_sports(sports)


def initiate_table(name):
    global db
    db = sqlite3.connect(name)
    # create_table ="CREATE TABLE countries(id integer primary key, name text)"
    db.execute("CREATE TABLE countries(id integer primary key, name text)")
    db.execute("CREATE TABLE sports(id integer primary key, name text)")
    db.execute("""CREATE TABLE athletes(id integer primary key, name text,
        country_id integer, unique(name), foreign key(country_id)
        references country(id))""")
    db.execute("""CREATE TABLE events(id integer primary key, name text,
        team integer, sport_id integer, date text, foreign key(sport_id)
        references sports(id))""")
    db.execute("""CREATE TABLE placings(event_id integer, athlete_id integer,
        place integer, foreign key(event_id) references events(id),
        foreign key(athlete_id) references athletes(id))""")


def iterate_sports(sports):
    for sport in sports:
        sport_soup = get_wiki_soup(sport["link"])
        events_table = sport_soup.find(class_="vertical-navbox")
        events_urls = []
        # first <td> is an icon and last is wiki nav buttons
        for data_cell in events_table.find_all("td")[1:-1]:
            # ignore padding cells
            if data_cell.a is not None:
                link = data_cell.a.get("href")
                # skip qualification links
                if "qualification" not in link.lower():
                    events_urls.append(link)

        # hard coded hockey page treatment
        if sport["name"] == "Ice hockey":
            event_summaries = get_hockey_summaries(events_urls)
            for summary in event_summaries:
                print(sport["name"], summary["title"], summary["date"],
                      summary["team"])
                write_events_to_db(summary, sport=sport["name"])
        else:
            for event in events_urls:
                event_summary = get_summary(event)
                print(sport["name"], event_summary["title"],
                      event_summary["date"], event_summary["team"])
                write_events_to_db(event_summary, sport=sport["name"])
                # for result in event_summary["results"]:
                #    print(result)


def get_summary(event_url):
    event_soup = get_wiki_soup(event_url)

    # read_table() is determined based on the event page structure
    # this "default" function is for events with a result table,
    # which contains all participating athletes
    read_table = get_table

    # reset to default state
    global team_flag
    team_flag = False
    # pick up all the DOM elements which indicate the structure
    medal_imgs = event_soup.find_all("img", alt="1st, gold medalist(s)")
    # there are mostly two tables with medals imgs -
    # an event card at top of the page and final table at bottom
    results = medal_imgs[-1].find_parent("table")
    # tables dict gets new keys if more tables need reading
    tables = {"results": results}
    # qualification table have green rows for passed athletes
    qual_row = event_soup.find("tr", bgcolor=True)
    # functionally seeding table is close to qualification
    seeding = event_soup.find(id="Seeding")
    # all curling events and team-event in figure skating
    teams_header = event_soup.find(id=["Teams", "Entries"])

    if teams_header is not None:
        team_flag = True
        teams_table = teams_header.parent.find_next_sibling("table")
        tables["entries"] = teams_table

        read_table = get_table_w_teams

    # qualification tables are parsed to pick all participating athletes
    # since results only contain some of them
    elif qual_row is not None:
        qual_table = qual_row.find_parent("table")
        # results table may have colored rows for DSQ
        if qual_table != results:
            tables["qualification"] = qual_table
            read_table = get_table_w_qual

            # if medals are only in event card table
            if len(medal_imgs) == 1:
                tables["results"] = get_event_card_table(results, qual_table)
                tables["skip_tree"] = True
                # apline skiing mixed team event
                entries = event_soup.find(id="Qualified_teams")
                if entries is not None:
                    tables["entries"] = entries.parent.find_next("ul")
                    read_table = get_alpine_mixed_table

            # in some events with elimination athletes go through seeding first
            elif seeding is not None:
                tables["qualification"] = seeding.parent.find_next_sibling(
                    "table")
        else:
            # if only one table needs to be read, pass it instead of a dict
            tables = results
    else:
        tables = results

    event_summary = {
        "results": read_table(tables),
        "title": get_event_title(event_soup),
        "date": get_event_date(event_soup),
        "team": team_flag
    }

    return event_summary


def write_to_db(db_values, table):
    db_query = "INSERT INTO {}('name') VALUES (?)".format(table)
    if table == "countries":
        for value in db_values:
            db.execute(db_query, [value])
    elif table == "sports":
        for value in db_values:
            db.execute(db_query, [value["name"]])
    else:
        return None
    db.commit()


def write_events_to_db(event, sport):
    db.execute("""INSERT INTO events('name', 'date', 'team', 'sport_id')
        SELECT ?, ?, ?, sports.id FROM sports WHERE sports.name = ?""",
               [event["title"], event["date"], event["team"], sport])

    for result in event["results"]:
        # don't duplicate athletes
        db.execute("""INSERT OR IGNORE INTO athletes('name', 'country_id')
        SELECT ?, countries.id FROM countries WHERE countries.name = ?""",
                   [result["name"], result["country"]])
        # events across sports can have same names
        db.execute("""INSERT INTO placings('event_id', 'athlete_id', 'place')
        SELECT events.id, athletes.id, ? FROM events JOIN athletes
        JOIN sports ON sports.id = events.sport_id
        WHERE athletes.name = ? AND events.name = ? AND sports.name = ?""",
                   [result["rank"], result["name"], event["title"], sport])
    db.commit()


def get_hockey_summaries(links):
    pre_results = {"Women": {}, "Men": {}}
    summary = []

    for link in links:
        if "qualification" not in link:

            link_soup = get_wiki_soup(link)

            if "Women" in link:
                key = "Women"
            else:
                key = "Men"

            if "team_rosters" in link:
                pre_results[key]["rosters"] = get_hockey_rosters(link_soup)
            else:
                pre_results[key]["standings"] = get_hockey_results(link_soup)
                pre_results[key]["title"] = get_event_title(link_soup)
                pre_results[key]["date"] = get_event_date(link_soup)

    for k, v in pre_results.items():
        summary.append({
            "results": join_countries_athletes(v["standings"], v["rosters"]),
            "title": v["title"],
            "date": v["date"],
            "team": True
        })

    return summary


def get_hockey_results(results_soup):
    results_header = results_soup.find("span", id="Final_ranking").parent
    pre_rows = results_header.find_next_sibling("table")("tr")
    headers = get_col_indices(pre_rows, True)

    # skip grey rows
    results_rows = [row for row in pre_rows
                    if "".join(row.stripped_strings)]

    results = iter_rows(headers, results_rows)
    return results


def get_hockey_rosters(rosters_soup):
    teams = rosters_soup("table", class_="wikitable")
    rosters = {}
    # all roster tables have same headers
    headers = get_col_indices(teams[0]("tr"), True)
    for team in teams:
        # don't include header
        team_rows = team("tr")[1:]
        country = team.find_previous_sibling("h3").span.string
        rosters[country] = [athlete["name"] for athlete in
                            iter_rows(headers, team_rows)]
    return rosters


def get_table(table, qual=False):

    results_rows = del_empty_rows(table("tr"), 3)

    # get required headers indices
    headers = get_col_indices(results_rows)

    # IndexError happens when table header is 2 rows high
    for i in range(3):
        try:
            iter_rows(headers, results_rows[:1])
        except(IndexError):
            results_rows.pop(0)
            continue
        break

    # if passed table doesn't contain medals, i.e. qualification table
    if qual:
        headers["rank"]["path"] = lambda td: None

    return iter_rows(headers, results_rows)


# parse separate tables of qualification and results
def get_table_w_qual(tables):
    qual_table = tables["qualification"]
    results_table = tables["results"]

    qualification = get_table(qual_table, qual=True)
    results = get_table(results_table)

    # if results of tree table are passed,
    # don't check for 2nd heat or small final
    if not tables.get("skip_tree", False):
        # check if qualification table is actually first heat
        # meaning there are more participants in the next table
        after_qual_table = qual_table.find_next_sibling("table")
        if after_qual_table != results_table:
            second_qualification = get_table(after_qual_table, qual=True)
            # none of athletes present in second heat are in first heat
            # index 0 is chosen arbitrarily
            if not second_qualification[0] in qualification:
                qualification.extend(second_qualification)

        # check if the table above results is actually small final
        # meaning they have rank but are not present in big final
        pre_results_table = results_table.find_previous_sibling("table")
        if pre_results_table != qual_table:
            small_final = get_table(pre_results_table)
            for athlete in small_final:
                # if an athlete is present in results, the table is semifinal
                if find_by_key(results, athlete, "name"):
                    break
            # if all athletes are unique, it's part of results
            else:
                # to concatenate two tables, remove first row - headers
                pre_results_table.tr.decompose()
                results_table.append(pre_results_table)
                results = get_table(results_table)
                # sort two tables, as sometimes results from big final
                # may be ranked below small final results (DNF, PEN etc)
                results.sort(key=lambda result: int(result["rank"]))

    # side-note: all quals in team events are semifinals, meaning there is no
    # mid-stage where team has an athlete not present in initial qual or finals

    # insert athletes who participated in team quals but not finals
    # flag was set in get_table -> iter_rows, if it's a team event
    if team_flag is True:
        for athlete in qualification:
            # if-clause is entered when athlete was not found in results
            if not find_by_key(results, athlete, "name"):
                # search for any athlete with the same country as current one
                teammate = find_by_key(results, athlete, "country")
                # in a team competition if a teammate is not found, the team
                # did not qualify
                if not teammate:
                    results.append(athlete)
                else:
                    athlete["rank"] = teammate["rank"]
                    results.insert(results.index(teammate), athlete)
    else:
        for athlete in qualification:
            # if an athlete isn't in results,
            # they didn't qualify and added with rank of None
            if not find_by_key(results, athlete, "name"):
                results.append(athlete)
    return results


# takes a list of dicts, a dict and a key, by which seeks value
# from single in list
def find_by_key(list_of_dicts, single_dict, key):
    return next((a_dict for a_dict in list_of_dicts
                if a_dict[key] == single_dict[key]), False)


# Figure skating team event and curling,
# where results are composed with countries, and athletes are listed separately
def get_table_w_teams(tables):
    entries_table = tables["entries"]
    results_rows = tables["results"]("tr")

    athletes = {}
    # curling
    if len(entries_table("th")) == len(entries_table("td")):
        for nation, team in zip(entries_table("th"), entries_table("td")):
            country = nation.a.string
            # team names are inside <p>, unlike pair names
            names = team.select("p a, > a")
            athletes[country] = [name.string for name in names]
    # skating
    else:
        for row in entries_table("tr"):
            # first <a> in row is country, the rest are athletes
            country = row.a.string
            # direct children cause some links are not athletes but references
            names = row.select("td > a")[1:]
            athletes[country] = [name.string for name in names]

    # get countries ranks
    headers = get_col_indices(results_rows, True)
    standings = iter_rows(headers, results_rows)

    return join_countries_athletes(standings, athletes)


# search header row for wanted column headers
# and return a dictionary of indices to use while iterating over table
def get_col_indices(results_rows, del_empty=False):
    headers = base_dict(
        {"column": None, "path": get_elem_str},
        {"column": None, "path": get_rank},
        {"column": None, "path": get_elem_str}
    )
    # same meaning columns have various names across tables
    variations = base_dict(
        ["Name", "Athlete", "Athletes", "name"],
        ["Rank", "Place", "Pl.", "Pos", "rank"],
        ["Country", "Nation", "Team", "country"]
    )

    while True:
        header_row = results_rows.pop(0)
        for i, th in enumerate(header_row("th")):
            cur_header = get_elem_str(th)
            if cur_header is None:
                continue
            for k, v in variations.items():
                if cur_header in v:
                    headers[k]["column"] = i
                    # remove found header to not seek it anymore
                    del variations[k]
                    break
            # when iteration over variations wasn't broken out from
            # break from header_row iteration if headers are filled
            else:
                if len(variations) == 0:
                    break
        # entering this "no-break" else means some headers were not found
        else:
            # when del_empty=True is passed, delete empty keys from headers
            if del_empty:
                for k in variations:
                    del headers[k]
                return headers

            # tables may contain upper row without sought headers(ski jumping)
            elif headers["rank"]["column"] is None:
                # run loop, first row is popped again
                continue
            # when <td> contains a country and its athletes
            elif headers["name"]["column"] is None:
                headers["name"]["column"] = headers["country"]["column"]
        break

    # is_team replaces "path" function or returns None
    headers["name"]["path"] = is_team(
        headers, results_rows[0]) or headers["name"]["path"]

    return headers


# returns stripped string from passed element
def get_elem_str(td):
    try:
        return next((td.a.stripped_strings), None)
    except(AttributeError):
        return next((td.stripped_strings), None)


def base_dict(name, rank, country):
    return {
        "name": name,
        "rank": rank,
        "country": country
    }


# from an event card return a basic table with headers and 4 results
def get_event_card_table(table, qual_table):
    fourth_place = get_4th(qual_table.find_next_sibling("table"))

    # create two row copies - one for headers, the other - for 4th place
    table.tr.insert_before(copy(table.tr))
    table("tr")[-1].insert_after(copy(table.tr))

    # iterate over both rows cells, to fill with headers names or data
    for cell_head, cell_4th in zip(table.tr, table("tr")[-1]):
        cell_4th.clear()
        cell_head.name = "th"
        if cell_head.img is not None:
            if cell_head.a is not None:
                header = "country"
            else:
                header = "rank"
        # padding cell
        elif get_elem_str(cell_head) is None:
            continue
        else:
            header = "name"

        cell_head.clear()
        cell_4th.append(fourth_place[header])
        cell_head.string = header
    return table


# alpine mixed team event is unique as it incorporates both tree table
# and teams in unordered list
def get_alpine_mixed_table(tables):
    entries_list = tables["entries"]
    results_rows = tables["results"]("tr")

    headers = get_col_indices(results_rows)

    # delete name from headers for use with join_countries_athletes()
    del headers["name"]

    standings = iter_rows(headers, results_rows)
    top_countries = [country["country"] for country in standings]
    athletes = {}
    # countries in list contain lists of athletes
    for list_item in entries_list("li", recursive=False):
        country = list_item.a.string
        if country not in top_countries:
            standings.append({
                "rank": None,
                "country": country
            })
        athletes[country] = []
        for athlete in list_item("li"):
            athletes[country].append(athlete.a.string)

    return join_countries_athletes(standings, athletes)


# get 4th placed athlete from a tree table
def get_4th(tree_table):
    count = {}

    # winners in each pair are in <b>
    for athlete in tree_table("b"):
        name = athlete.a
        count[name] = count.get(name, 0) + 1

    # alpine skiing has <a>-less <b> elements
    try:
        del count[None]
    except(KeyError):
        pass

    # delete top-3 <b> "mentions" - first 3 places
    for k in range(3):
        current = max(count, key=lambda v: count[v])
        del count[current]
    fourth_place = max(count, key=lambda v: count[v])
    # snowboard giant slalom athletes have countries link next to it
    # both theirs and countries names are shortened, but not in title attr
    # and previous link respectively
    if len(tree_table.a.find_parent("td")("a")) == 2:
        fourth_place.string = fourth_place["title"]
        country_link = fourth_place.find_parent("td")("a")[1]
        # find link from qual table with full country name
        # full = country_link.find_previous("a", href=country_link["href"])
        full = tree_table.find_previous("a", href=country_link["href"])
        # copy link as to not mutate qual table, which will be used
        fourth_place = base_dict(fourth_place, "4", copy(full))
    else:
        # in alpine skiing fourth_place is a country
        fourth_place = base_dict("", "4", fourth_place)
    # dict with <a> elements is returned
    return fourth_place


def iter_rows(headers, rows_array):
    tmp = []
    for result_row in rows_array:
        # some data is in <th> rather than <td>
        row_data = result_row(["td", "th"])
        to_add = {}
        try:
            for k, v in headers.items():
                td = row_data[v["column"]]
                to_add[k] = v["path"](td)
        except(IndexError):
            # when two athletes finished equal and rank is on previous row
            for k, v in headers.items():
                if k == "rank":
                    to_add["rank"] = tmp[-1]["rank"]
                else:
                    # shift column access to account for "missing" column
                    td = row_data[v["column"] - 1]
                    to_add[k] = v["path"](td)
        tmp.append(to_add)
    # in team-events athletes are packed in a list-like bs4.ResultSet or a list
    try:
        if type(tmp[0]["name"]) in (list, element.ResultSet):
            global team_flag
            team_flag = True
            return [ath for to_add in tmp for ath in divide_athletes(to_add)]
    # rows may lack names, i.e. some team sports
    except(KeyError):
        pass
    return tmp


# delete every row, which has less than required number of columns
def del_empty_rows(rows, no_of_cols):
    cleared_rows = [row for row in rows if
                    len(row) >= no_of_cols]
    return cleared_rows


def get_event_title(event_soup):
    full_title = event_soup.h1.string
    title = full_title.split(" – ")[-1]
    return title


# one list contains dicts of countries and their ranks
# the athletes dict - countries as keys and athletes list as values
def join_countries_athletes(standings, athletes):
    global team_flag
    team_flag = True
    results = []
    for standing in standings:
        for athlete in athletes[standing["country"]]:
            results.append(base_dict(
                athlete, standing["rank"], standing["country"]))
    return results


# get rank from img of medal or string
def get_rank(td):
    # the image's alt contains a string with rank
    if td.img is not None:
        return int(td.img["alt"][0])
    try:
        return int(get_elem_str(td))
    # don't return strings like "DSQ" and "DNF"
    except(TypeError, ValueError):
        return


# pass headers to find name in passed rows
# and determine whether it contains a team or a single athlete
def is_team(headers, row):
    # check whether there are multiple athletes
    name_cell = row(["td", "th"])[headers["name"]["column"]]
    # multiple athletes are usually in a <small> element
    if name_cell.small is not None:
        return lambda td: td.small("a")
    # and sometimes they are just <a> elements in <td>
    elif len(name_cell("a")) > 1:
        # the element might include country <a> indicated by flag img
        if name_cell.img is not None:
            return lambda td: td("a")[1:]
        else:
            return lambda td: td("a")
    return None


# from a list of names contained in dict, create a list of dicts
# with single names and same key-values of the rest of the dicts
def divide_athletes(to_add):
    divided = []
    for athlete in to_add["name"]:
        divided.append(base_dict(
            get_elem_str(athlete),
            to_add["rank"],
            to_add["country"]
        ))
    return divided


def get_event_date(event_soup):
    date_header = event_soup.find("th", string=["Date", "Dates"])
    date = date_header.next_sibling
    # brake in date means there are multiple stages, but only last is used
    if date.br is not None:
        event_date = list(date.stripped_strings)[-1]
    else:
        event_date = get_elem_str(date)
    last_digits = re.compile(r"\d{1,2}\s" + OLYM_DATES["month"])
    # some events span multiple dates, so pick only final
    return (last_digits.findall(event_date)[-1] + " " + OLYM_DATES["year"])


def get_wiki_soup(url):
    # wiki sub-URLs are of form "/wiki/<page>"
    full_url = "https://en.wikipedia.org" + url
    try:
        presoup_html = request.urlopen(full_url).read()
    except(error.URLError):
        print("Could not connect to", full_url)
        raise SystemExit
    request.urlopen(full_url).close()
    return soup(presoup_html, "html.parser")


def get_sports(olym_soup):
    sports_header = olym_soup.find(id="Sports").parent
    sports_list = sports_header.find_next_sibling("div").select("ul li")
    sports = []
    for item in sports_list:
        sports.append({
            "name": item.a.string,
            "link": item.span.a.get("href")
        })
    return sports


def get_countries(olym_soup):
    # find the table by header string
    for link in olym_soup("a", string="National Olympic Committees"):
        cur_table = link.find_parent("table")
        if cur_table is not None:
            countries_table = cur_table

    # row after header contains list items with countries in first links
    return [li.a.string for li in countries_table("tr")[1]("li")]


if __name__ == "__main__":
    main()
