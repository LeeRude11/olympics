import sqlite3


# add a function (to return dictionary) to a default sqlite3.Row object
class RowToDict(sqlite3.Row):
    def serialize(self):
        return {
            "athletes": self["athletes"].split(","),
            "event": self["event"],
            "sport": self["sport"],
            "place": self["place"]
        }

    def serialize_w_date(self):
        dated = self.serialize()
        dated["date"] = self["date"]
        return dated


class CustomCursor(sqlite3.Cursor):

    def __init__(self, *args, **kwargs):
        super(self.__class__, self).__init__(*args, **kwargs)
        self.all_names = self.fetch_all_tables_names()

    # for when row objects in list have only one value
    # return a list of those values
    def fetch_singles(self):
        return [value for item in self.fetchall() for value in item]

    # all tables names as an array
    def fetch_all_tables_names(self):
        return self.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetch_singles()

    # if passed table_name is present, return all values from its name column
    def names_list(self, table_name):
        if table_name in self.all_names:
            name_query = self.execute(
                "SELECT name FROM {}".format(table_name)).fetch_singles()
            return name_query
        return []


conn = sqlite3.connect("olymp.db", check_same_thread=False).cursor(
    CustomCursor)
conn.row_factory = RowToDict


base_query = ["""SELECT GROUP_CONCAT(athletes.name) AS athletes,
                countries.name AS country, events.name AS event,
                sports.name AS sport, placings.place AS place""",
              """FROM athletes
                JOIN placings ON placings.athlete_id = athletes.id
                JOIN countries ON athletes.country_id = countries.id
                JOIN events ON placings.event_id = events.id
                JOIN sports ON events.sport_id = sports.id""",
              """WHERE placings.place BETWEEN 1 AND 3
                GROUP BY placings.event_id, place, country
                ORDER BY country, place"""]
