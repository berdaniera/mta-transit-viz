from flask import Flask, render_template, request, jsonify
from bokeh.plotting import figure
from bokeh.embed import components
import requests as req
import numpy as np
import pandas as pa
import simplejson as json

app = Flask(__name__)

################
date_format_str = "%Y-%m-%d %H:%M:%S"
date_parser = lambda u: pa.datetime.strptime(u, date_format_str)
df = pa.read_csv("data/data1.csv",
                 parse_dates=True,
                 date_parser=date_parser,
                 index_col=0,header=None,names=['cnts']) # peek into the csv: col 0 is 'timestamp'

dates = df.resample('D').mean().index.format()
times = sorted(set([str(x.time()) for x in df.index]))

################
df2 = pa.read_csv("data/data2.csv",
                 index_col=0,header=None,names=['cnts']) # peek into the csv: col 0 is 'timestamp'

def _flatten_dict(root_key, nested_dict, flattened_dict):
    for key, value in nested_dict.iteritems():
        next_key = root_key + "_" + key if root_key != "" else key
        if isinstance(value, dict):
            _flatten_dict(next_key, value, flattened_dict)
        else:
            flattened_dict[next_key] = value
    return flattened_dict

#This is useful for the live MTA Data
def nyc_current():
    resp = req.get("http://api.prod.obanyc.com/api/siri/vehicle-monitoring.json?key=6368af34-d4ad-4d49-ad2c-98e827988e92").json()
    info = resp['Siri']['ServiceDelivery']['VehicleMonitoringDelivery'][0]['VehicleActivity']
    return pa.DataFrame([_flatten_dict('', i, {}) for i in info])

rounded_tm = lambda dt: pa.datetime(dt.year, dt.month, dt.day, dt.hour, 30*(dt.minute // 30))

################
df3 = pa.read_csv("data/manhattan.csv",
                 parse_dates=True,
                 date_parser=date_parser,
                 index_col=1) # peek into the csv: col 0 is 'timestamp'


def df_to_geojson(df, lat='MonitoredVehicleJourney_VehicleLocation_Latitude', lon='MonitoredVehicleJourney_VehicleLocation_Longitude'):
    geojson = {'type':'FeatureCollection', 'features':[]}
    for _, row in df.iterrows():
        feature = {'type':'Feature',
                   'properties':{},
                   'geometry':{'type':'Point',
                               'coordinates':[]}}
        feature['geometry']['coordinates'] = [row[lon],row[lat]]
        geojson['features'].append(feature)
    return geojson


@app.route('/hourcnts',methods=['GET','POST'])
def hourcnts():
    if request.method == 'GET':
        return render_template('index.html', dates=dates, times=times)
    else: #requets is post
        date0 = request.form['date0']
        time0 = request.form['time0']
        #date1 = request.form['dateEnd']
        time1 = request.form['time1']
        #print date0+time0
        mask = (df.index > date0+' '+time0) & (df.index <= date0+' '+time1)
        dat = df.loc[mask]
        totbus = dat['cnts'].sum() # total busses on the road in this interval
        p1 = figure(x_axis_type = "datetime", responsive=True, plot_height=300, plot_width=900)
        p1.title = "Time series"
        p1.xaxis.axis_label = 'Date'
        p1.yaxis.axis_label = 'Busses'

        p1.line(dat.index, dat['cnts'], color='blue')

        script, div = components(p1)
        # add bokeh stuff
        return render_template('next.html', script=script, div=div, totbus = totbus, dates=dates, times=times)

@app.route('/livecnts',methods=['GET','POST'])
def livecnts():
    if request.method == 'GET':
        return render_template('livecnts.html')
    else: #requets is post
        dr = nyc_current()
        tim = str(rounded_tm(pa.datetime.now()).time())
        totbus = len(dr)
        avgbus = df2[df2.index==tim].values[0]*1.
        histfrac = round(100*totbus/avgbus)

        p2 = figure(x_axis_type = "datetime", responsive=True, plot_height=300, plot_width=900)
        p2.title = "Time series"
        p2.xaxis.axis_label = 'Time'
        p2.yaxis.axis_label = 'Busses'
        p2.line(pa.to_datetime(df2.index), df2['cnts'], color='blue')
        #p2.circle(str(pa.to_datetime(tim)), totbus, size=20, color="navy", alpha=0.5)
        script2, div2 = components(p2)
        # add bokeh stuff
        return render_template('livecnts2.html', script=script2, div=div2, totbus = totbus, histfrac = histfrac)

@app.route('/staticmap')
def staticmap():
    return render_template('staticmap.html', dates=dates, times=times)


# Route that will process the AJAX request and return the
# result as a proper JSON response (Content-Type, etc.)
@app.route('/_getOutput', methods=['POST'])
def getOutput():
    # # load raster
    date0 = request.json['date0']
    time0 = request.json['time0']
    #date1 = request.form['dateEnd']
    time1 = request.json['time1']
    #print date0+time0
    mask = (df3.index > date0+' '+time0) & (df3.index <= date0+' '+time1)
    dat = df3.loc[mask]
    return jsonify(result=dat[['latitude','longitude']].values.tolist()) #result=out

@app.route('/livemap')
def livemap():
    return render_template('livemap.html')

@app.route('/_livedata', methods=['POST'])
def positions_at_time():
    dr = nyc_current()
    return jsonify(result=dr[['MonitoredVehicleJourney_VehicleLocation_Latitude','MonitoredVehicleJourney_VehicleLocation_Longitude']].values.tolist())

if __name__ == '__main__':
  app.run(host='0.0.0.0',port=5555,debug=True)
