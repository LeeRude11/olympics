from flask import Flask, render_template, request, jsonify
from itertools import groupby
from operator import itemgetter
from werkzeug.exceptions import default_exceptions
import database as db

app = Flask(__name__)


@app.route("/")
def index():

    medals = db.conn.execute(" ".join(db.base_query)).fetchall()
    sports = db.conn.names_list("sports")

    countries = {}
    # group all medals by country with country:medals as key:value pairs
    for key, values in groupby(medals, key=itemgetter("country")):
        countries[key] = list(v.serialize() for v in values)

    return render_template("index.html", rows=countries, sports=sports)


@app.route("/timeline")
def timeline():
    # q is an optional passed country name from main table
    q = request.args.get("q")

    timeline_query = db.base_query[:]
    timeline_query[1:1] = [", events.date AS date"]

    medals = db.conn.execute(" ".join(timeline_query)).fetchall()

    dates = db.conn.execute("SELECT DISTINCT date FROM events").fetch_singles()
    dates.sort()

    countries = {}

    for key, values in groupby(medals, key=itemgetter("country")):
        countries[key] = list(v.serialize_w_date() for v in values)

    return render_template("timeline.html", rows=countries,
                           dates=dates, query=q)


@app.route("/results", endpoint="results")
@app.route("/athletes", endpoint="athletes")
# @app.route("/results")
# @app.route("/athletes")
def results_athletes():
    countries = None
    # /athletes is similarly structured but requires a list of countries
    if request.endpoint == "athletes":
        countries = db.conn.names_list("countries")

    events = db.conn.execute("""SELECT events.name AS name,
                                sports.name AS sport FROM events
                                JOIN sports ON sports.id = events.sport_id"""
                             )
    sports = {}
    for e in events:
        sports.setdefault(e["sport"], []).append(e["name"])

    return render_template("results_athletes.html", page_name=request.endpoint,
                           sports=sports, countries=countries)


@app.route("/list_results")
def list_results():

    items_dict = request.args.to_dict()
    par_keys = ["sport", "an_event"]

    # both parameters are required
    parameters = [items_dict.get(key) for key in par_keys]
    if any(missing in parameters for missing in ["", None]):
        return jsonify("something went wrong")

    query_list = ["""SELECT GROUP_CONCAT(athletes.name, "|") AS name,
                  placings.place AS place, countries.name AS country""",
                  db.base_query[1],
                  """WHERE sports.name = ? AND events.name = ?
                  GROUP BY (CASE
                  WHEN events.team = 1 THEN place
                  ELSE athletes.id END), country
                  ORDER BY place"""]

    db_query = " ".join(query_list)
    athletes = db.conn.execute(db_query, parameters)
    final = []

    for athlete in athletes:
        final.append({
            "athletes": athlete["name"].split("|"),
            "place": athlete["place"],
            "country": athlete["country"]
            })

    return jsonify(final)


@app.route("/list_athletes")
def list_athletes():

    items_dict = request.args.to_dict()
    par_keys = ["country", "sport", "an_event"]

    # event results only require one parameter
    if not items_dict.get("country"):
        return jsonify("something went wrong")

    parameters = [items_dict.get(key) for key in par_keys
                  if items_dict.get(key)]

    # some events contain commas (10,000m mass start), so the separator is "|"
    query_list = ["""SELECT athletes.name AS name,
                  GROUP_CONCAT((COALESCE(placings.place, "") || "--" ||
                  events.name), "|") AS results,
                  sports.name AS sport""",
                  db.base_query[1],
                  "WHERE countries.name = ?"]

    if items_dict.get("sport"):
        query_list.append("AND sports.name = ?")
        if items_dict.get("an_event"):
            query_list.append("AND events.name = ?")

    if items_dict.get("medals") == "true":
        query_list.append("AND placings.place BETWEEN 1 AND 3")

    query_list.append("GROUP BY athletes.id")

    db_query = " ".join(query_list)
    athletes = db.conn.execute(db_query, parameters)
    final = []

    # create a list of athletes with them and their results sorted by score
    for athlete in athletes:
        results = []
        for result in athlete["results"].split("|"):
            place, event = result.split("--")
            results.append({"place": place, "event": event})

        # sort empty strings below numeric places
        results.sort(key=lambda res: float(res["place"] or "inf"))
        final.append({
            "name": athlete["name"],
            "results": results,
            "sport": athlete["sport"],
            "score": calc_score(results)
            })

    return jsonify(final)


def errorhandler(error):
    return render_template("error_render.html", error=error), error.code


# listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)

SCORING = {"1": 100, "2": 10, "3": 1}


def calc_score(results):
    score = 0
    for result in results:
        score += SCORING.get(result["place"], 0)
    # negate medals for sorting; best placing if no medals
    # if it"s an empty string, return arbitrary string
    # to be able to get class as cellValue
    return -(score) or results[0]["place"] or "no-placings"
