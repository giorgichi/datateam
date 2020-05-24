"""Plot!"""
# pylint: disable=abstract-class-instantiated
import sys
import datetime
import os

import pandas as pd
from pandas.io.sql import read_sql
import numpy as np
from paste.request import parse_formvars
from pyiem.util import get_dbconn

sys.path.append("/opt/datateam/htdocs/td")
from common import CODES, getColor, send_error

LINESTYLE = [
    "-",
    "-",
    "-",
    "-",
    "-",
    "-",
    "-",
    "-",
    "-.",
    "-.",
    "-.",
    "-.",
    "-.",
    "-",
    "-.",
    "-.",
    "-.",
    "-.",
    "-.",
    "-.",
    "-.",
    "-.",
    "-.",
    "-.",
]


def make_plot(form, start_response):
    """Make the plot"""
    pgconn = get_dbconn("td")
    (uniqueid, plotid) = form.get("site", "ISUAG::302E").split("::")

    sts = datetime.datetime.strptime(
        form.get("date", "2014-01-01"), "%Y-%m-%d"
    )
    days = int(form.get("days", 1))
    group = int(form.get("group", 0))
    ets = sts + datetime.timedelta(days=days)
    tzname = (
        "America/Chicago"
        if uniqueid in ["ISUAG", "SERF", "GILMORE"]
        else "America/New_York"
    )
    viewopt = form.get("view", "plot")
    ptype = form.get("ptype", "1")
    missing = form.get("missing", "M")
    custom_missing = form.get("custom_missing", "M")
    missing = missing if missing != "__custom__" else custom_missing
    if ptype == "1":
        df = read_sql(
            """SELECT valid at time zone 'UTC' as v, plotid,
        wat20 as load
        from nitrateload_data WHERE uniqueid = %s
        and valid between %s and %s ORDER by valid ASC
        """,
            pgconn,
            params=(uniqueid, sts.date(), ets.date()),
        )
    elif ptype == "2":
        df = read_sql(
            """SELECT
        date_trunc('month', valid at time zone 'UTC') as v, plotid,
        sum(wat20) as load
        from nitrateload_data WHERE uniqueid = %s
        and valid between %s and %s GROUP by v, plotid ORDER by v ASC
        """,
            pgconn,
            params=(uniqueid, sts.date(), ets.date()),
        )
    if len(df.index) < 3:
        send_error(
            start_response, viewopt, "No / Not Enough Data Found, sorry!"
        )
    linecol = "plotid"
    if group == 1:
        # Generate the plotid lookup table
        plotdf = read_sql(
            "SELECT * from plotids where siteid = %s",
            pgconn,
            params=(uniqueid,),
            index_col="plotid",
        )

        def lookup(row):
            try:
                return plotdf.loc[row["plotid"], "y%s" % (row["v"].year,)]
            except KeyError:
                return row["plotid"]

        df["treatment"] = df.apply(lookup, axis=1)
        del df["plotid"]
        df = df.groupby(["treatment", "v"]).mean()
        df.reset_index(inplace=True)
        linecol = "treatment"
    if ptype not in ["2"]:
        df["v"] = df["v"].apply(
            lambda x: x.tz_localize("UTC").tz_convert(tzname)
        )

    if viewopt not in ["plot", "js"]:
        df = df.fillna(missing)
        df["v"] = df["v"].dt.strftime("%Y-%m-%d %H:%M")
        df.rename(
            columns=dict(v="timestamp", load="Load (kg ha-1)"), inplace=True
        )
        if viewopt == "html":
            start_response("200 OK", [("Content-type", "text/html")])
            return df.to_html(index=False).encode("utf-8")
        if viewopt == "csv":
            start_response(
                "200 OK",
                [
                    ("Content-type", "application/octet-stream"),
                    (
                        "Content-Disposition",
                        "attachment; filename=%s_%s_%s_%s.csv"
                        % (
                            uniqueid,
                            plotid,
                            sts.strftime("%Y%m%d"),
                            ets.strftime("%Y%m%d"),
                        ),
                    ),
                ],
            )
            return df.to_csv(index=False).encode("utf-8")
        if viewopt == "excel":
            start_response(
                "200 OK",
                [
                    ("Content-type", "application/octet-stream"),
                    (
                        "Content-Disposition",
                        "attachment; filename=%s_%s_%s_%s.xlsx"
                        % (
                            uniqueid,
                            plotid,
                            sts.strftime("%Y%m%d"),
                            ets.strftime("%Y%m%d"),
                        ),
                    ),
                ],
            )
            with pd.ExcelWriter("/tmp/ss.xlsx") as writer:
                df.to_excel(writer, "Data", index=False)
            res = open("/tmp/ss.xlsx", "rb").read()
            os.unlink("/tmp/ss.xlsx")
            return res

    # Begin highcharts output
    start_response("200 OK", [("Content-type", "application/javascript")])
    title = ("Nitrate Load for Site: %s (%s to %s)") % (
        uniqueid,
        sts.strftime("%-d %b %Y"),
        ets.strftime("%-d %b %Y"),
    )
    s = []
    plot_ids = df[linecol].unique()
    plot_ids.sort()
    if group == "1":
        plot_ids = plot_ids[::-1]
    df["ticks"] = df["v"].astype(np.int64) // 10 ** 6
    seriestype = "line" if ptype == "1" else "column"
    for i, plotid in enumerate(plot_ids):
        df2 = df[df[linecol] == plotid]
        s.append(
            (
                """{type: '"""
                + seriestype
                + """',
            """
                + getColor(plotid, i)
                + """,
            name: '"""
                + CODES.get(plotid, plotid)
                + """',
            data: """
                + str(
                    [
                        [a, b]
                        for a, b in zip(
                            df2["ticks"].values, df2["load"].values
                        )
                    ]
                )
                + """
        }"""
            )
            .replace("None", "null")
            .replace("nan", "null")
        )
    series = ",".join(s)
    res = (
        """
$("#hc").highcharts({
    title: {text: '"""
        + title
        + """'},
    chart: {zoomType: 'x'},
    yAxis: {title: {text: 'Load (kg ha-1)'}
    },
    plotOptions: {line: {turboThreshold: 0}},
    xAxis: {
        type: 'datetime'
    },
    tooltip: {
        dateTimeLabelFormats: {
            hour: "%b %e %Y, %H:%M",
            minute: "%b %e %Y, %H:%M"
        },
        shared: true,
        valueDecimals: 4,
        valueSuffix: ' kg ha-1'
    },
    series: ["""
        + series
        + """]
});
    """
    )
    return res.encode("utf-8")


def application(environ, start_response):
    """Do Something"""
    form = parse_formvars(environ)
    return [make_plot(form, start_response)]
