#!/usr/bin/python
"""

"""
import sys
import psycopg2.extras
import cgi
import datetime
import pandas as pd
import pandas.io.sql as pdsql
import pyiem.cscap_utils as util


config = util.get_config(
    '/mesonet/www/apps/iemwebsite/scripts/cscap/mytokens.json')


def clean(val):
    ''' Clean the value we get '''
    if val is None:
        return ''
    if val.strip().lower() == 'did not collect':
        return 'DNC'
    if val.strip().lower() == 'n/a':
        return 'NA'
    return val.decode('ascii', 'ignore')


def check_auth(form):
    """ Make sure request is authorized """
    if form.getfirst('hash') != config['appauth']['sharedkey']:
        sys.stdout.write("Content-type: text/plain\n\n")
        sys.stdout.write("Unauthorized request!")
        sys.stderr.write(("Unauthorized CSCAP hash=%s"
                          ) % (form.getfirst('hash'),))
        sys.exit()


def get_nitratedata():
    ''' Fetch some nitrate data, for now '''
    pgconn = psycopg2.connect(database='sustainablecorn', host='iemdb',
                              user='nobody')
    cursor = pgconn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    res = "uniqueid,plotid,year,depth,soil15,soil16,soil23\n"
    cursor.execute("""SELECT site, plotid, depth, varname, year, value
    from soil_data WHERE value is not null
    and value ~* '[0-9\.]' and value != '.' and value !~* '<'
    and site in ('MASON', 'KELLOGG', 'GILMORE', 'ISUAG', 'WOOSTER.COV',
    'SEPAC', 'BRADFORD.C', 'BRADFORD.B1', 'BRADFORD.B2', 'FREEMAN')""")
    data = {}
    for row in cursor:
        key = "%s|%s|%s|%s" % (row['site'], row['plotid'], row['year'],
                               row['depth'])
        if key not in data:
            data[key] = {}
        data[key][row['varname']] = clean(row["value"])

    for key in data.keys():
        tokens = key.split("|")
        res += ("%s,%s,%s,%s,%s,%s,%s\n"
                ) % (tokens[0], tokens[1], tokens[2], tokens[3],
                     data[key].get('SOIL15', ''), data[key].get('SOIL16', ''),
                     data[key].get('SOIL23', ''))
    return res


def get_agdata():
    """
    Go to Google and demand my data back!
    """
    pgconn = psycopg2.connect(database='sustainablecorn', host='iemdb',
                              user='nobody')
    cursor = pgconn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cursor.execute("""SELECT site, a.plotid, year, varname, value,
    p.rep, p.tillage, p.rotation , p.nitrogen
    from agronomic_data a JOIN plotids p on (p.uniqueid = a.site and
    p.plotid = a.plotid) where
    varname in ('AGR1', 'AGR2', 'AGR7', 'AGR15', 'AGR16', 'AGR17', 'AGR19',
    'AGR39', 'AGR40')
    and value ~* '[0-9\.]' and value != '.' and value !~* '<'
    and (site in ('MASON', 'KELLOGG', 'GILMORE', 'ISUAG', 'WOOSTER.COV',
    'SEPAC', 'FREEMAN', 'BRADFORD.C') or
    (site in ('BRADFORD.B1', 'BRADFORD.B2') and p.nitrogen = 'NIT3')
    )""")
    data = {}
    for row in cursor:
        key = ("%s|%s|%s|%s|%s|%s|%s"
               ) % (row['site'], row['plotid'], row['year'],
                    row['rep'], row['tillage'], row['rotation'],
                    row['nitrogen'])
        if key not in data:
            data[key] = {}
        data[key][row['varname']] = clean(row["value"])

    # Get the Soil Nitrate data we are going to join with
    cursor.execute("""
    SELECT site, plotid, depth, varname, year, avg(value::float)
    from soil_data WHERE value is not null
    and value ~* '[0-9\.]' and value != '.' and value !~* '<'
    and site in ('MASON', 'KELLOGG', 'GILMORE', 'ISUAG', 'WOOSTER.COV',
    'SEPAC', 'BRADFORD.C', 'BRADFORD.B1', 'BRADFORD.B2', 'FREEMAN')
    and varname in ('SOIL13', 'SOIL23', 'SOIL14', 'SOIL27', 'SOIL28', 'SOIL1',
    'SOIL15',
    'SOIL11', 'SOIL32', 'SOIL31', 'SOIL2', 'SOIL26')
    GROUP by site, plotid, depth, varname, year
    """)
    sndata = {}
    for row in cursor:
        key = "%s|%s|%s|%s|%s" % (row['site'], row['plotid'], row['year'],
                                  row['varname'], row['depth'])
        sndata[key] = row['avg']

    res = ("uniqueid,plotid,year,rep,tillage,rotation,nitrogen,agr1,agr2,agr7,"
           "agr15,agr16,agr17,agr19,agr39,agr40,"
           "soil11_0-10,soil11_10-20,soil11_20-40,soil11_40-60,"
           "soil13_0-10,soil13_10-20,soil13_20-40,soil13_40-60,"
           "soil14_0-10,soil14_10-20,soil14_20-40,soil14_40-60,"
           "soil26_0-10,soil26_10-20,soil26_20-40,soil26_40-60,"
           "soil27_0-10,soil27_10-20,soil27_20-40,soil27_40-60,"
           "soil28_0-10,soil28_10-20,soil28_20-40,soil28_40-60,"
           "soil32_0-10,soil32_10-20,soil32_20-40,soil32_40-60,"
           "soil31_0-10,soil31_10-20,soil31_20-40,soil31_40-60,"
           "soil1_0-10,soil1_10-20,soil1_20-40,soil1_40-60,"
           "soil2_0-10,soil2_10-20,soil2_20-40,soil2_40-60,"
           "soil23_0-30,soil23_30-60,soil23_60-90,soil23_90-120,"
           "soil15_0-30,soil15_30-60,soil15_60-90,\n")
    for key in data.keys():
        tokens = key.split("|")
        lkp = "%s|%s|%s|%s" % (tokens[0], tokens[1], tokens[2], 'SOIL')
        res += ("%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,"
                "%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,"
                "%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s"
                "%s,%s,%s,\n"
                ) % (tokens[0], tokens[1],
                     tokens[2], tokens[3], tokens[4], tokens[5], tokens[6],
                     data[key].get('AGR1', ''), data[key].get('AGR2', ''),
                     data[key].get('AGR7', ''), data[key].get('AGR15', ''),
                     data[key].get('AGR16', ''), data[key].get('AGR17', ''),
                     data[key].get('AGR19', ''), data[key].get('AGR39', ''),
                     data[key].get('AGR40', ''),
                     sndata.get(lkp+"11|0 - 10", 'M'),
                     sndata.get(lkp+"11|10 - 20", 'M'),
                     sndata.get(lkp+"11|20 - 40", 'M'),
                     sndata.get(lkp+"11|40 - 60", 'M'),
                     sndata.get(lkp+"13|0 - 10", 'M'),
                     sndata.get(lkp+"13|10 - 20", 'M'),
                     sndata.get(lkp+"13|20 - 40", 'M'),
                     sndata.get(lkp+"13|40 - 60", 'M'),
                     sndata.get(lkp+"14|0 - 10", 'M'),
                     sndata.get(lkp+"14|10 - 20", 'M'),
                     sndata.get(lkp+"14|20 - 40", 'M'),
                     sndata.get(lkp+"14|40 - 60", 'M'),
                     sndata.get(lkp+"26|0 - 10", 'M'),
                     sndata.get(lkp+"26|10 - 20", 'M'),
                     sndata.get(lkp+"26|20 - 40", 'M'),
                     sndata.get(lkp+"26|40 - 60", 'M'),
                     sndata.get(lkp+"27|0 - 10", 'M'),
                     sndata.get(lkp+"27|10 - 20", 'M'),
                     sndata.get(lkp+"27|20 - 40", 'M'),
                     sndata.get(lkp+"27|40 - 60", 'M'),
                     sndata.get(lkp+"28|0 - 10", 'M'),
                     sndata.get(lkp+"28|10 - 20", 'M'),
                     sndata.get(lkp+"28|20 - 40", 'M'),
                     sndata.get(lkp+"28|40 - 60", 'M'),
                     sndata.get(lkp+"32|0 - 10", 'M'),
                     sndata.get(lkp+"32|10 - 20", 'M'),
                     sndata.get(lkp+"32|20 - 40", 'M'),
                     sndata.get(lkp+"32|40 - 60", 'M'),
                     sndata.get(lkp+"31|0 - 10", 'M'),
                     sndata.get(lkp+"31|10 - 20", 'M'),
                     sndata.get(lkp+"31|20 - 40", 'M'),
                     sndata.get(lkp+"31|40 - 60", 'M'),
                     sndata.get(lkp+"1|0 - 10", 'M'),
                     sndata.get(lkp+"1|10 - 20", 'M'),
                     sndata.get(lkp+"1|20 - 40", 'M'),
                     sndata.get(lkp+"1|40 - 60", 'M'),
                     sndata.get(lkp+"2|0 - 10", 'M'),
                     sndata.get(lkp+"2|10 - 20", 'M'),
                     sndata.get(lkp+"2|20 - 40", 'M'),
                     sndata.get(lkp+"2|40 - 60", 'M'),
                     sndata.get(lkp+"23|0 - 30", 'M'),
                     sndata.get(lkp+"23|30 - 60", 'M'),
                     sndata.get(lkp+"23|60 - 90", 'M'),
                     sndata.get(lkp+"23|90 - 120", 'M'),
                     sndata.get(lkp+"15|0 - 30", 'M'),
                     sndata.get(lkp+"15|30 - 60", 'M'),
                     sndata.get(lkp+"15|60 - 90", 'M'),
                     )

    return res


def get_dl(form):
    """ Process the form provided to us from the Internal website """
    pgconn = psycopg2.connect(database='sustainablecorn', host='iemdb',
                              user='nobody')

    years = form.getlist('years')
    if len(years) == 1:
        years.append('9')
    if "all" in years or len(years) == 0:
        yrlist = "('2011', '2012', '2013', '2014', '2015')"
    else:
        yrlist = str(tuple(years))

    treatlimiter = "1=1"
    treatments = form.getlist('treatments')
    if len(treatments) > 0 and 'all' not in treatments:
        if len(treatments) == 1:
            treatments.append('ZZ')
        s = str(tuple(treatments))
        treatlimiter = """(tillage in %s or rotation in %s or
        nitrogen in %s or landscape in %s)""" % (s, s, s, s)

    sitelimiter = "1=1"
    sites = form.getlist('sites')
    if len(sites) > 0 and 'all' not in sites:
        if len(sites) == 1:
            sites.append('ZZ')
        s = str(tuple(sites))
        treatlimiter = """t.site in %s""" % (s,)

    # columns!
    cols = ['year', 'site', 'plotid', 'depth', 'subsample', 'rep', 'rotation',
            'crop', 'tillage', 'drainage', 'nitrogen', 'landscape',
            'herbicide', 'sampledate']
    dvars = form.getlist("data")
    wants_soil = False
    for dv in dvars:
        if dv.startswith('SOIL') or dv == 'all':
            wants_soil = True
            break

    sys.stderr.write("1. %s\n" % (datetime.datetime.now(), ))
    if wants_soil:
        sql = """
        WITH ad as
        (SELECT site, plotid, ''::text as depth, varname, year,
        value, '1'::text as subsample, null::date as sampledate
         from agronomic_data WHERE year in %s),
        sd as
        (SELECT site, plotid, depth, varname, year, value, subsample,
        sampledate from soil_data WHERE year in %s),
        tot as
        (SELECT * from ad UNION select * from sd)

        SELECT site || '|' || p.plotid
        || '|' || coalesce(depth,'')
        || '|' || coalesce(subsample, '')
        || '|' || year
        || '|' || coalesce(rep, '')
        || '|' || coalesce(rotation, '')
        || '|' || coalesce(tillage, '')
        || '|' || coalesce(drainage, '')
        || '|' || coalesce(nitrogen, '')
        || '|' || coalesce(landscape, '')
        || '|' || coalesce(herbicide, '')
        || '|' || (case when sampledate is null then ''
                   else sampledate::text end) as lbl,
        varname, value
        from tot t JOIN plotids p on (t.site = p.uniqueid and
        t.plotid = p.plotid) WHERE 1=1 and %s and %s
        """ % (yrlist, yrlist, treatlimiter, sitelimiter)
    else:
        sql = """
        WITH ad as
        (SELECT site, plotid, ''::text as depth, varname, year,
        value, ''::text as subsample, ''::text as sampledate
         from agronomic_data WHERE year in %s),
        tot as
        (SELECT * from ad)

        SELECT site || '|' || p.plotid
        || '|' || coalesce(depth,'')
        || '|' || coalesce(subsample, '')
        || '|' || year
        || '|' || coalesce(rep, '')
        || '|' || coalesce(rotation, '')
        || '|' || coalesce(tillage, '')
        || '|' || coalesce(drainage, '')
        || '|' || coalesce(nitrogen, '')
        || '|' || coalesce(landscape, '')
        || '|' || coalesce(herbicide, '')
        || '|' || coalesce(sampledate, '') as lbl,
        varname, value from tot t JOIN plotids p on
        (t.site = p.uniqueid and t.plotid = p.plotid) WHERE 1=1 and %s and %s
        """ % (yrlist, treatlimiter, sitelimiter)

    df = pdsql.read_sql(sql, pgconn)
    sys.stderr.write("2. %s\n" % (datetime.datetime.now(), ))
    # sys.stderr.write(str(df.columns))

    dnc = form.getfirst('dnc', 'DNC')
    missing = form.getfirst('missing', '.')

    def cleaner(val):
        if val is None or val.strip() == '' or val.strip() == '.':
            return missing
        if val is not None:
            if val.strip().lower() == 'did not collect':
                return dnc
            if val.strip() == 'n/a':
                return "N/A"
        return val
    df['value'] = df['value'].apply(cleaner)
    df2 = df.pivot('lbl', 'varname', 'value')
    allcols = df2.columns.values.tolist()
    if 'all' in dvars:
        cols = cols + allcols
    else:
        cols = cols + dvars
    # sys.stderr.write(str(cols))
    (df2['site'], df2['plotid'], df2['depth'], df2['subsample'],
     df2['year'], df2['rep'], df2['rotation'], df2['tillage'],
     df2['drainage'], df2['nitrogen'], df2['landscape'],
     df2['herbicide'], df2['sampledate']
     ) = zip(*[item.split('|') for item in df2.index])
    df2['crop'] = None
    sys.stderr.write("3. %s\n" % (datetime.datetime.now(), ))

    df2cols = df2.columns.values.tolist()
    for col in cols:
        if col not in df2cols:
            cols.remove(col)

    # Assign in Rotations
    rotdf = pdsql.read_sql("""
        SELECT * from xref_rotation
        """, pgconn, index_col='code')

    def find_rotation(rotation, year):
        try:
            return rotdf.at[rotation, 'y%s' % (year, )]
        except:
            return ''
    df2['crop'] = df2[['rotation', 'year']].apply(lambda x:
                                                  find_rotation(x[0], x[1]),
                                                  axis=1)
    sys.stderr.write("4. %s\n" % (datetime.datetime.now(), ))

    fmt = form.getfirst('format', 'csv')
    if fmt == 'excel':
        sys.stdout.write("Content-type: application/vnd.ms-excel\n")
        sys.stdout.write((
            "Content-Disposition: attachment;Filename=cscap.xlsx\n\n"))
        writer = pd.ExcelWriter("/tmp/cscap.xlsx", engine='xlsxwriter')
        df2.to_excel(writer, columns=cols, index=False,
                     encoding='latin-1', sheet_name='Sheet1')
        workbook = writer.book
        worksheet = writer.sheets['Sheet1']
        format2 = workbook.add_format({'num_format': '@'})
        worksheet.set_column('B:E', None, format2)
        writer.close()
        return open('/tmp/cscap.xlsx', 'rb').read()
    elif fmt == 'tab':
        sys.stdout.write("Content-type: text/plain\n\n")
        return df2.to_csv(columns=cols, sep='\t', index=False)
    sys.stdout.write("Content-type: text/plain\n\n")
    sys.stderr.write("5. %s\n" % (datetime.datetime.now(), ))
    return df2.to_csv(columns=cols, index=False)


def main():
    """Main"""
    form = cgi.FieldStorage()
    check_auth(form)
    report = form.getfirst('report', 'ag1')
    if report == 'ag1':
        sys.stdout.write("Content-type: text/plain\n\n")
        sys.stdout.write(get_agdata())
    if report == 'dl':  # coming from internal website
        sys.stdout.write(get_dl(form))
    else:
        sys.stdout.write("Content-type: text/plain\n\n")
        sys.stdout.write(get_nitratedata())

if __name__ == '__main__':
    # Do Something
    main()
